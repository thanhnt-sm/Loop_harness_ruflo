#!/usr/bin/env python3
"""Test Issue Reporter — quét toàn bộ harness, xuất list lỗi/issues buộc fix.

Test này chạy tất cả checks từ security, architecture, code quality,
thu thập tất cả issues và xuất báo cáo structured ra stdout + file.

Output:
- stdout: tóm tắt issues theo severity
- File: docs/reports/HARNESS_ISSUES_<date>.md — báo cáo chi tiết

Chạy: python -m pytest tests/test_issue_reporter.py -v --tb=short -s
Hoặc: python tests/test_issue_reporter.py
"""
import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".devin" / "hooks"
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"
TOOLS_DIR = REPO_ROOT / ".devin" / "tools"
REPORT_DIR = REPO_ROOT / "docs" / "reports"

ALL_PY_FILES = list(HOOKS_DIR.glob("*.py")) + list(SCRIPTS_DIR.glob("*.py"))
ALL_PY_FILES = [f for f in ALL_PY_FILES if f.name != "__init__.py" and "test_" not in f.name]

# Issue severity levels
CRITICAL = "CRITICAL"
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
INFO = "INFO"

# Global issue collector
ISSUES: list[dict] = []


def _add_issue(severity: str, category: str, file: Path, line: int, description: str, fix: str = ""):
    """Thêm issue vào collector."""
    file_str = ""
    if file:
        try:
            file_str = str(file.resolve().relative_to(REPO_ROOT))
        except (ValueError, OSError):
            file_str = str(file)
    ISSUES.append({
        "severity": severity,
        "category": category,
        "file": file_str,
        "line": line,
        "description": description,
        "fix": fix,
    })


def _read_source(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(_read_source(path), filename=str(path))
    except SyntaxError:
        return None


def _find_pattern(files: list[Path], pattern: str) -> list[tuple[Path, int, str]]:
    results = []
    compiled = re.compile(pattern)
    for f in files:
        for i, line in enumerate(_read_source(f).splitlines(), 1):
            if compiled.search(line):
                results.append((f, i, line.strip()))
    return results


# ---------------------------------------------------------------------------
# Scan functions — mỗi scan thu thập issues
# ---------------------------------------------------------------------------

def scan_hardcoded_secrets():
    """SEC-001: Quét hardcoded secrets."""
    patterns = [
        (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key", CRITICAL),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT", CRITICAL),
        (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth token", CRITICAL),
        (r"AKIA[A-Z0-9]{16}", "AWS Access Key", CRITICAL),
        (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Private key block", CRITICAL),
        (r"xox[baprs]-[a-zA-Z0-9-]{10,}", "Slack token", CRITICAL),
        (r"AIza[a-zA-Z0-9_-]{35}", "Google API key", CRITICAL),
    ]
    for pattern, desc, sev in patterns:
        matches = _find_pattern(ALL_PY_FILES, pattern)
        for f, line, text in matches:
            _add_issue(sev, "SEC-001: Hardcoded Secret", f, line,
                       f"{desc} detected", "Remove secret, use env var")


def scan_dangerous_functions():
    """SEC-002: Quét eval/exec/os.system."""
    patterns = [
        (r"\beval\s*\(", "eval()", CRITICAL),
        (r"\bexec\s*\(", "exec()", CRITICAL),
        (r"\bos\.system\s*\(", "os.system()", HIGH),
    ]
    for pattern, desc, sev in patterns:
        matches = _find_pattern(ALL_PY_FILES, pattern)
        for f, line, text in matches:
            if "plan_sanitizer" in f.name or "BLOCKED" in text or "blocked" in text.lower():
                continue
            _add_issue(sev, "SEC-002: Dangerous Function", f, line,
                       f"{desc} — arbitrary code execution risk",
                       "Remove or replace with safe alternative")


def scan_shell_true():
    """SEC-003: Quét subprocess shell=True."""
    matches = _find_pattern(ALL_PY_FILES, r"shell\s*=\s*True")
    for f, line, text in matches:
        _add_issue(HIGH, "SEC-003: Shell Injection", f, line,
                   "subprocess with shell=True — injection risk",
                   "Use shell=False with list args")


def scan_unsafe_deserialization():
    """SEC-004: Quét pickle/marshal/yaml.load."""
    for pattern, desc in [(r"\bpickle\.loads?\s*\(", "pickle.loads"),
                           (r"\bmarshal\.loads?\s*\(", "marshal.loads"),
                           (r"\byaml\.load\s*\(", "yaml.load (unsafe)")]:
        matches = _find_pattern(ALL_PY_FILES, pattern)
        for f, line, text in matches:
            if "plan_sanitizer" in f.name:
                continue
            _add_issue(HIGH, "SEC-004: Unsafe Deserialization", f, line,
                       f"{desc} — arbitrary code execution via untrusted data",
                       "Use json.loads or yaml.safe_load")


def scan_bare_except():
    """SEC-005: Quét bare except."""
    matches = _find_pattern(ALL_PY_FILES, r"^\s*except\s*:")
    for f, line, text in matches:
        _add_issue(MEDIUM, "SEC-005: Bare Except", f, line,
                   "Bare except: swallows all errors including KeyboardInterrupt",
                   "Use except Exception: or specific exception types")


def scan_broad_exception_swallow():
    """SEC-005b: Quét except Exception: pass without logging."""
    matches = _find_pattern(ALL_PY_FILES, r"^\s*except\s+Exception\s*:")
    for f, line_no, _ in matches:
        lines = _read_source(f).splitlines()
        following = "\n".join(lines[line_no:line_no + 3])
        has_logging = any(kw in following.lower() for kw in
                          ["log", "print", "stderr", "warn", "raise", "sys.exit"])
        has_pass_only = "pass" in following and not has_logging
        if has_pass_only:
            _add_issue(LOW, "SEC-005b: Silent Error Swallow", f, line_no,
                       "except Exception: pass — errors swallowed silently",
                       "Add logging or re-raise")


def scan_file_length():
    """QUAL-001: File > 500 lines."""
    for f in ALL_PY_FILES:
        source = _read_source(f)
        line_count = len(source.splitlines())
        if line_count > 500:
            _add_issue(MEDIUM, "QUAL-001: File Too Long", f, line_count,
                       f"File has {line_count} lines (> 500 limit)",
                       "Split into smaller modules")


def scan_function_length():
    """QUAL-002: Function > 50 lines."""
    for f in ALL_PY_FILES:
        tree = _parse_ast(f)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if length > 50:
                    _add_issue(LOW, "QUAL-002: Function Too Long", f, node.lineno,
                               f"{node.name}: {length} lines (> 50 limit)",
                               "Refactor into smaller functions")


def scan_todo_fixme():
    """QUAL-003: TODO/FIXME/HACK/XXX."""
    matches = _find_pattern(ALL_PY_FILES, r"#\s*(TODO|FIXME|HACK|XXX|BUG)")
    for f, line, text in matches:
        _add_issue(LOW, "QUAL-003: TODO/FIXME", f, line,
                   f"Unresolved: {text[:80]}",
                   "Resolve or convert to issue tracker")


def scan_missing_type_hints():
    """QUAL-004: Public functions missing return type hints."""
    for f in ALL_PY_FILES[:15]:  # Sample
        tree = _parse_ast(f)
        if tree is None:
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") and node.returns is None:
                    _add_issue(LOW, "QUAL-004: Missing Type Hint", f, node.lineno,
                               f"Function '{node.name}' missing return type hint",
                               "Add return type annotation")


def scan_missing_docstrings():
    """QUAL-007: Public functions missing docstrings."""
    for f in ALL_PY_FILES[:15]:
        tree = _parse_ast(f)
        if tree is None:
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    if not (node.body and isinstance(node.body[0], ast.Expr)
                            and isinstance(node.body[0].value, ast.Constant)
                            and isinstance(node.body[0].value.value, str)):
                        _add_issue(LOW, "QUAL-007: Missing Docstring", f, node.lineno,
                                   f"Function '{node.name}' missing docstring",
                                   "Add docstring describing purpose")


def scan_io_without_error_handling():
    """QUAL-005: I/O operations without try/except."""
    for f in ALL_PY_FILES:
        source = _read_source(f)
        if not any(p in source for p in [".read_text(", ".write_text(", "open("]):
            continue
        if "try:" not in source and "try :" not in source:
            _add_issue(MEDIUM, "QUAL-005: Missing I/O Error Handling", f, 0,
                       "File has I/O operations but no try/except",
                       "Wrap I/O in try/except with proper error handling")


def scan_hook_integrity():
    """ARCH-006: Hook integrity baseline."""
    hashes_file = REPO_ROOT / ".devin" / "hook_hashes.json"
    if not hashes_file.exists():
        _add_issue(HIGH, "ARCH-006: Missing Hook Hashes", hashes_file, 0,
                   "hook_hashes.json not found — no integrity baseline",
                   "Run hook_integrity.py --generate")
        return
    hashes = json.loads(hashes_file.read_text(encoding="utf-8"))
    # File có thể dùng key là filename hoặc path đầy đủ
    hash_keys = set(hashes.keys())
    if "hooks" in hashes and isinstance(hashes["hooks"], dict):
        hash_keys = set(hashes["hooks"].keys())
    hook_files = [f for f in HOOKS_DIR.glob("*.py") if f.name != "__init__.py"]
    for f in hook_files:
        # Check cả filename và path đầy đủ
        rel_path = str(f.relative_to(REPO_ROOT)).replace("\\", "/")
        if f.name not in hash_keys and rel_path not in hash_keys:
            _add_issue(MEDIUM, "ARCH-006: Missing Hash", f, 0,
                       f"Hook {f.name} not in hash baseline",
                       "Regenerate baseline with hook_integrity.py --generate")


def scan_shell_scripts_safety():
    """SEC-010: Shell scripts without set -euo pipefail."""
    sh_files = list((REPO_ROOT / ".opencode").rglob("*.sh"))
    for f in sh_files:
        content = _read_source(f)
        if not any(p in content for p in ["set -euo pipefail", "set -eu", "set -uo pipefail"]):
            _add_issue(MEDIUM, "SEC-010: Unsafe Shell Script", f, 0,
                       "Missing set -euo pipefail — script continues on error",
                       "Add 'set -euo pipefail' at top of script")


def scan_unused_imports():
    """QUAL-006: Unused imports."""
    for f in ALL_PY_FILES[:15]:
        tree = _parse_ast(f)
        if tree is None:
            continue
        source = _read_source(f)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    lines = source.splitlines()
                    usage = sum(1 for line in lines if name in line) - 1
                    if usage <= 0:
                        _add_issue(LOW, "QUAL-006: Unused Import", f, node.lineno,
                                   f"'{name}' imported but not used",
                                   "Remove unused import")
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    lines = source.splitlines()
                    usage = sum(1 for line in lines if name in line) - 1
                    if usage <= 0:
                        _add_issue(LOW, "QUAL-006: Unused Import", f, node.lineno,
                                   f"'{name}' imported but not used",
                                   "Remove unused import")


def scan_destructive_blocking():
    """ARCH-006: Destructive operation blocking coverage."""
    pre_src = _read_source(HOOKS_DIR / "pre_tool_use.py")
    if not pre_src:
        _add_issue(HIGH, "ARCH-006: Missing pre_tool_use", HOOKS_DIR / "pre_tool_use.py", 0,
                   "pre_tool_use.py not found — no destructive operation blocking",
                   "Create pre_tool_use.py hook")
        return
    destructive = [
        "rm -rf", "rm -r ", "rmdir", "git push --force", "git push -f",
        "git reset --hard", "DROP TABLE", "DELETE FROM", "format ", "mkfs", "shred",
    ]
    missing = [p for p in destructive if p.lower() not in pre_src.lower()]
    for p in missing:
        _add_issue(MEDIUM, "ARCH-006: Unblocked Destructive", HOOKS_DIR / "pre_tool_use.py", 0,
                   f"Destructive pattern '{p}' not blocked by pre_tool_use.py",
                   f"Add block rule for '{p}'")


def scan_missing_hooks():
    """ARCH-007: Required hooks check."""
    required_hooks = [
        "pre_tool_use.py", "post_tool_use.py", "session_start.py",
        "session_end.py", "stop.py", "user_prompt_submit.py",
        "schema_gate.py", "plan_enforce.py", "coverage_enforce.py",
        "self_heal.py", "cross_family_verify.py",
    ]
    for hook in required_hooks:
        if not (HOOKS_DIR / hook).exists():
            _add_issue(HIGH, "ARCH-007: Missing Required Hook", HOOKS_DIR / hook, 0,
                       f"Required hook {hook} not found",
                       f"Create {hook} in .devin/hooks/")


def scan_missing_scripts():
    """ARCH-008: Required scripts check."""
    required_scripts = [
        "hook_integrity.py", "plan_orchestrator.py",
        "approval_gate.py", "plan_quality_check.py", "coverage_matrix.py",
        "subagent_isolation.py", "cost_tracker.py", "migrate_state.py",
        "path_resolver.py", "quota_check.py",
    ]
    for script in required_scripts:
        if not (SCRIPTS_DIR / script).exists():
            _add_issue(HIGH, "ARCH-008: Missing Required Script", SCRIPTS_DIR / script, 0,
                       f"Required script {script} not found",
                       f"Create {script} in .devin/scripts/")


def scan_governance_files():
    """ARCH-009: Governance files check."""
    required_files = [
        "AGENTS.md", "CLAUDE.md", ".devin/AGENTS.md",
        ".devin/rules/WORKSPACE_GOVERNANCE.md",
        ".devin/hook_order.json", ".devin/hook_hashes.json",
        "pytest.ini", ".gitignore",
    ]
    for f in required_files:
        path = REPO_ROOT / f
        if not path.exists():
            _add_issue(MEDIUM, "ARCH-009: Missing Governance File", path, 0,
                       f"Required file {f} not found",
                       f"Create {f}")


def scan_test_coverage():
    """ARCH-010: Test coverage check — count test files per module."""
    test_dir = REPO_ROOT / "tests"
    test_files = list(test_dir.glob("test_*.py"))
    # Check if critical modules have tests
    critical_modules = [
        "ahd_session", "pre_tool_use", "plan_enforce", "schema_gate",
        "coverage_enforce", "self_heal", "subagent_isolation",
        "plan_orchestrator", "approval_gate", "migrate_state",
    ]
    for module in critical_modules:
        has_test = any(module in t.name for t in test_files)
        if not has_test:
            _add_issue(MEDIUM, "ARCH-010: Missing Test Coverage", Path(f".devin/hooks/{module}.py"), 0,
                       f"No test file for {module}",
                       f"Create tests/test_{module}.py")


# ---------------------------------------------------------------------------
# Main test — chạy tất cả scans và xuất báo cáo
# ---------------------------------------------------------------------------

ALL_SCANS = [
    scan_hardcoded_secrets,
    scan_dangerous_functions,
    scan_shell_true,
    scan_unsafe_deserialization,
    scan_bare_except,
    scan_broad_exception_swallow,
    scan_file_length,
    scan_function_length,
    scan_todo_fixme,
    scan_missing_type_hints,
    scan_missing_docstrings,
    scan_io_without_error_handling,
    scan_hook_integrity,
    scan_shell_scripts_safety,
    scan_unused_imports,
    scan_destructive_blocking,
    scan_missing_hooks,
    scan_missing_scripts,
    scan_governance_files,
    scan_test_coverage,
]


class TestIssueReporter:
    """Chạy tất cả scans, thu thập issues, xuất báo cáo."""

    @pytest.fixture(autouse=True)
    def _clear_issues(self):
        ISSUES.clear()
        yield
        # Don't clear after — let report generation use it

    def test_run_all_scans(self):
        """Chạy tất cả scans và thu thập issues."""
        for scan in ALL_SCANS:
            try:
                scan()
            except Exception as e:
                _add_issue(HIGH, "SCAN_ERROR", Path("tests/test_issue_reporter.py"), 0,
                           f"Scan {scan.__name__} failed: {e}", "Fix scan function")

        # Categorize by severity
        by_severity = defaultdict(list)
        for issue in ISSUES:
            by_severity[issue["severity"]].append(issue)

        # Print summary
        print(f"\n{'='*70}")
        print(f"HARNESS ISSUE REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        print(f"Total issues: {len(ISSUES)}")
        print(f"  CRITICAL: {len(by_severity[CRITICAL])}")
        print(f"  HIGH:     {len(by_severity[HIGH])}")
        print(f"  MEDIUM:   {len(by_severity[MEDIUM])}")
        print(f"  LOW:      {len(by_severity[LOW])}")
        print(f"  INFO:     {len(by_severity[INFO])}")
        print(f"{'='*70}\n")

        # Print CRITICAL issues
        if by_severity[CRITICAL]:
            print(f"--- CRITICAL ({len(by_severity[CRITICAL])}) — BUỘC FIX NGAY ---")
            for i, issue in enumerate(by_severity[CRITICAL], 1):
                print(f"  {i}. [{issue['category']}] {issue['file']}:{issue['line']}")
                print(f"     {issue['description']}")
                if issue['fix']:
                    print(f"     Fix: {issue['fix']}")
            print()

        # Print HIGH issues
        if by_severity[HIGH]:
            print(f"--- HIGH ({len(by_severity[HIGH])}) — BUỘC FIX ---")
            for i, issue in enumerate(by_severity[HIGH], 1):
                print(f"  {i}. [{issue['category']}] {issue['file']}:{issue['line']}")
                print(f"     {issue['description']}")
                if issue['fix']:
                    print(f"     Fix: {issue['fix']}")
            print()

        # Print MEDIUM issues (first 20)
        if by_severity[MEDIUM]:
            print(f"--- MEDIUM ({len(by_severity[MEDIUM])}) — NÊN FIX ---")
            for i, issue in enumerate(by_severity[MEDIUM][:20], 1):
                print(f"  {i}. [{issue['category']}] {issue['file']}:{issue['line']}")
                print(f"     {issue['description']}")
            if len(by_severity[MEDIUM]) > 20:
                print(f"  ... và {len(by_severity[MEDIUM]) - 20} issues nữa")
            print()

        # Print LOW count
        if by_severity[LOW]:
            print(f"--- LOW ({len(by_severity[LOW])}) — CÓ THỂ FIX SAU ---")
            # Group by category
            by_cat = defaultdict(list)
            for issue in by_severity[LOW]:
                by_cat[issue["category"]].append(issue)
            for cat, issues in sorted(by_cat.items()):
                print(f"  {cat}: {len(issues)} issues")
            print()

        # Generate report file
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / f"HARNESS_ISSUES_{datetime.now().strftime('%Y-%m-%d')}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Harness Issue Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"## Tóm tắt\n\n")
            f.write(f"| Severity | Count | Trạng thái |\n")
            f.write(f"|----------|-------|------------|\n")
            f.write(f"| CRITICAL | {len(by_severity[CRITICAL])} | {'✅ PASS' if not by_severity[CRITICAL] else '❌ FAIL'} |\n")
            f.write(f"| HIGH | {len(by_severity[HIGH])} | {'✅ PASS' if not by_severity[HIGH] else '❌ FAIL'} |\n")
            f.write(f"| MEDIUM | {len(by_severity[MEDIUM])} | {'✅ PASS' if not by_severity[MEDIUM] else '⚠️ REVIEW'} |\n")
            f.write(f"| LOW | {len(by_severity[LOW])} | ℹ️ INFO |\n")
            f.write(f"| **TOTAL** | **{len(ISSUES)}** | |\n\n")

            for severity in [CRITICAL, HIGH, MEDIUM, LOW]:
                issues = by_severity[severity]
                if not issues:
                    continue
                f.write(f"## {severity} ({len(issues)} issues)\n\n")
                f.write(f"| # | Category | File | Line | Description | Fix |\n")
                f.write(f"|---|----------|------|------|-------------|-----|\n")
                for i, issue in enumerate(issues, 1):
                    f.write(f"| {i} | {issue['category']} | `{issue['file']}` | {issue['line']} | {issue['description']} | {issue['fix']} |\n")
                f.write("\n")

            f.write(f"## Danh sách issues buộc fix (CRITICAL + HIGH)\n\n")
            must_fix = by_severity[CRITICAL] + by_severity[HIGH]
            if not must_fix:
                f.write("✅ Không có issue CRITICAL hoặc HIGH — harness đạt tiêu chuẩn bảo mật cao.\n\n")
            else:
                f.write(f"| # | Severity | Category | File | Description | Fix |\n")
                f.write(f"|---|----------|----------|------|-------------|-----|\n")
                for i, issue in enumerate(must_fix, 1):
                    f.write(f"| {i} | {issue['severity']} | {issue['category']} | `{issue['file']}` | {issue['description']} | {issue['fix']} |\n")
                f.write("\n")

        print(f"Báo cáo chi tiết: {report_path.relative_to(REPO_ROOT)}")
        print(f"{'='*70}\n")

        # Assert: CRITICAL issues must be 0
        assert len(by_severity[CRITICAL]) == 0, (
            f"{len(by_severity[CRITICAL])} CRITICAL issues — BUỘC FIX NGAY:\n"
            + "\n".join(f"  {i['file']}:{i['line']}: {i['description']}" for i in by_severity[CRITICAL])
        )


if __name__ == "__main__":
    # Run standalone
    ISSUES.clear()
    for scan in ALL_SCANS:
        try:
            scan()
        except Exception as e:
            _add_issue(HIGH, "SCAN_ERROR", Path("tests/test_issue_reporter.py"), 0,
                       f"Scan {scan.__name__} failed: {e}", "Fix scan function")

    by_severity = defaultdict(list)
    for issue in ISSUES:
        by_severity[issue["severity"]].append(issue)

    print(f"\n{'='*70}")
    print(f"HARNESS ISSUE REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}")
    print(f"Total issues: {len(ISSUES)}")
    for sev in [CRITICAL, HIGH, MEDIUM, LOW, INFO]:
        print(f"  {sev}: {len(by_severity[sev])}")

    # Print all CRITICAL and HIGH
    for sev in [CRITICAL, HIGH]:
        if by_severity[sev]:
            print(f"\n--- {sev} ({len(by_severity[sev])}) ---")
            for i, issue in enumerate(by_severity[sev], 1):
                print(f"  {i}. [{issue['category']}] {issue['file']}:{issue['line']}")
                print(f"     {issue['description']}")
                if issue['fix']:
                    print(f"     Fix: {issue['fix']}")

    # Print MEDIUM summary
    if by_severity[MEDIUM]:
        print(f"\n--- MEDIUM ({len(by_severity[MEDIUM])}) ---")
        for i, issue in enumerate(by_severity[MEDIUM][:20], 1):
            print(f"  {i}. [{issue['category']}] {issue['file']}:{issue['line']}: {issue['description']}")

    # Print LOW summary
    if by_severity[LOW]:
        print(f"\n--- LOW ({len(by_severity[LOW])}) ---")
        by_cat = defaultdict(list)
        for issue in by_severity[LOW]:
            by_cat[issue["category"]].append(issue)
        for cat, issues in sorted(by_cat.items()):
            print(f"  {cat}: {len(issues)} issues")

    print(f"\n{'='*70}")
    sys.exit(0 if not by_severity[CRITICAL] else 1)
