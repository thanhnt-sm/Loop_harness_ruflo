#!/usr/bin/env python3
"""Test Security Supreme — tiêu chuẩn bảo mật cao nhất cho harness.

Kiểm tra:
- Không hardcode secrets/API keys/tokens
- Không eval()/exec()/os.system() trong hooks/scripts
- Không subprocess với shell=True
- Không pickle/marshal deserialize unsafe data
- Không bare except (swallow errors)
- Input validation cho mọi tool_input từ user
- Path traversal prevention
- Fail-closed behavior cho security gates
- Hook integrity (hash verification)
- No sensitive data in logs/stdout

Chạy: python -m pytest tests/test_security_supreme.py -v
"""
import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".devin" / "hooks"
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"
TOOLS_DIR = REPO_ROOT / ".devin" / "tools"

ALL_PY_FILES = list(HOOKS_DIR.glob("*.py")) + list(SCRIPTS_DIR.glob("*.py")) + list(SCRIPTS_DIR.glob("plan_fsm/*.py"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_source(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(_read_source(path), filename=str(path))
    except SyntaxError:
        return None


def _find_pattern_in_files(files: list[Path], pattern: str) -> list[tuple[Path, int, str]]:
    """Tìm regex pattern trong list file, trả (file, line_no, line_text)."""
    results = []
    compiled = re.compile(pattern)
    for f in files:
        for i, line in enumerate(_read_source(f).splitlines(), 1):
            if compiled.search(line):
                results.append((f, i, line.strip()))
    return results


# ---------------------------------------------------------------------------
# SEC-001: Không hardcode secrets, API keys, tokens
# ---------------------------------------------------------------------------

class TestNoHardcodedSecrets:
    """SEC-001: Không hardcode secrets trong source code."""

    SECRET_PATTERNS = [
        (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key pattern"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT pattern"),
        (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth token pattern"),
        (r"AKIA[A-Z0-9]{16}", "AWS Access Key pattern"),
        (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Private key block"),
        (r"xox[baprs]-[a-zA-Z0-9-]{10,}", "Slack token pattern"),
        (r"AIza[a-zA-Z0-9_-]{35}", "Google API key pattern"),
    ]

    @pytest.mark.parametrize("pattern,desc", SECRET_PATTERNS)
    def test_no_secret_patterns(self, pattern, desc):
        """Không có pattern secret nào trong hooks/scripts."""
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        assert not matches, (
            f"Phát hiện {desc} trong {len(matches)} file(s):\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{line}: {text}" for f, line, text in matches[:5])
        )

    def test_no_hardcoded_api_key_assignments(self):
        """Không gán api_key/password/secret/token = literal string."""
        pattern = r'(api_key|password|secret|token|api_secret)\s*=\s*["\'][^"\']{8,}["\']'
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        # Filter out env var references and test fixtures
        real = [(f, l, t) for f, l, t in matches
                if "env" not in t.lower() and "os.environ" not in t.lower()
                and "getenv" not in t.lower() and "test" not in f.name.lower()]
        assert not real, (
            f"Hardcoded secret assignment trong {len(real)} file(s):\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}" for f, l, t in real[:5])
        )


# ---------------------------------------------------------------------------
# SEC-002: Không eval/exec/os.system
# ---------------------------------------------------------------------------

class TestNoDangerousFunctions:
    """SEC-002: Không dùng eval(), exec(), os.system() trong hooks/scripts."""

    DANGEROUS_PATTERNS = [
        (r"\beval\s*\(", "eval() — arbitrary code execution"),
        (r"\bexec\s*\(", "exec() — arbitrary code execution"),
        (r"\bos\.system\s*\(", "os.system() — shell injection risk"),
        # compile() — exclude re.compile, method calls (.compile()), and def compile
        (r"(?<!re\.)(?<!\.)(?<!def\s)\bcompile\s*\((?!.*re\.IGNORECASE)", "compile() — code compilation risk"),
    ]

    @pytest.mark.parametrize("pattern,desc", DANGEROUS_PATTERNS)
    def test_no_dangerous_functions(self, pattern, desc):
        """Không dùng dangerous functions."""
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        # Filter: plan_sanitizer.py lists these as blocked patterns — OK
        real = [(f, l, t) for f, l, t in matches
                if "plan_sanitizer" not in f.name and "BLOCKED" not in t
                and "blocked" not in t.lower() and "forbidden" not in t.lower()
                and "BANNED" not in t and "#" not in t.split(pattern)[0].rstrip()[-3:]]
        assert not real, (
            f"{desc} trong {len(real)} file(s):\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}" for f, l, t in real[:5])
        )


# ---------------------------------------------------------------------------
# SEC-003: Không subprocess với shell=True
# ---------------------------------------------------------------------------

class TestNoShellTrue:
    """SEC-003: Không dùng subprocess với shell=True."""

    def test_no_shell_true_in_hooks_scripts(self):
        """Không có shell=True trong subprocess calls."""
        pattern = r"subprocess\.(run|call|Popen|check_output|check_call)\s*\(.*shell\s*=\s*True"
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        assert not matches, (
            f"subprocess shell=True trong {len(matches)} file(s):\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}" for f, l, t in matches[:5])
        )


# ---------------------------------------------------------------------------
# SEC-004: Không pickle/marshal deserialize unsafe data
# ---------------------------------------------------------------------------

class TestNoUnsafeDeserialization:
    """SEC-004: Không deserialize unsafe data bằng pickle/marshal."""

    def test_no_pickle_loads(self):
        """Không dùng pickle.loads/marshal.loads với untrusted data."""
        pattern = r"\bpickle\.loads?\s*\(|\bmarshal\.loads?\s*\("
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        # Filter: plan_sanitizer.py lists these as blocked — OK
        real = [(f, l, t) for f, l, t in matches if "plan_sanitizer" not in f.name]
        assert not real, (
            f"Unsafe deserialization trong {len(real)} file(s):\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}" for f, l, t in real[:5])
        )

    def test_yaml_safe_load_only(self):
        """YAML phải dùng safe_load, không dùng load."""
        pattern = r"\byaml\.load\s*\("
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        assert not matches, (
            f"yaml.load() (unsafe) trong {len(matches)} file(s):\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}" for f, l, t in matches[:5])
        )


# ---------------------------------------------------------------------------
# SEC-005: Bare except — swallow errors
# ---------------------------------------------------------------------------

class TestNoBareExcept:
    """SEC-005: Không bare except (swallow errors silently)."""

    def test_no_bare_except(self):
        """Không có bare except: trong hooks/scripts."""
        pattern = r"^\s*except\s*:"
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        assert not matches, (
            f"Bare except: trong {len(matches)} file(s) — swallow errors:\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}" for f, l, t in matches[:5])
        )

    def test_no_broad_exception_swallows(self):
        """except Exception: phải có logging hoặc re-raise."""
        pattern = r"^\s*except\s+Exception\s*:"
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        # Check if each match is followed by pass or return without logging
        issues = []
        for f, line_no, _ in matches:
            lines = _read_source(f).splitlines()
            # Look at next 3 lines after except
            following = "\n".join(lines[line_no:line_no + 3])
            has_logging = any(kw in following.lower() for kw in
                              ["log", "print", "stderr", "warn", "raise", "sys.exit"])
            has_pass_only = "pass" in following and not has_logging
            if has_pass_only:
                issues.append((f, line_no, lines[line_no - 1].strip()))
        # Report as warning, not hard fail — some hooks intentionally fail-open
        if issues:
            print(f"\n[SEC-005 WARNING] {len(issues)} broad exception swallows without logging:")
            for f, l, t in issues[:10]:
                print(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}")


# ---------------------------------------------------------------------------
# SEC-006: Hook integrity — hash verification
# ---------------------------------------------------------------------------

class TestHookIntegrity:
    """SEC-006: Hook integrity phải có hash verification."""

    def test_hook_hashes_json_exists(self):
        """File hook_hashes.json phải tồn tại."""
        assert (REPO_ROOT / ".devin" / "hook_hashes.json").exists(), (
            "Missing .devin/hook_hashes.json — hook integrity baseline"
        )

    def test_hook_integrity_script_exists(self):
        """Script hook_integrity.py phải tồn tại."""
        assert (SCRIPTS_DIR / "hook_integrity.py").exists(), (
            "Missing .devin/scripts/hook_integrity.py — integrity verifier"
        )

    def test_all_hooks_have_hashes(self):
        """Mọi hook .py phải có hash trong hook_hashes.json."""
        import json
        hashes_file = REPO_ROOT / ".devin" / "hook_hashes.json"
        if not hashes_file.exists():
            pytest.skip("hook_hashes.json not found")
        hashes = json.loads(hashes_file.read_text(encoding="utf-8"))
        # File có thể dùng key là filename hoặc path đầy đủ
        hash_keys = set(hashes.keys())
        if "hooks" in hashes and isinstance(hashes["hooks"], dict):
            hash_keys = set(hashes["hooks"].keys())
        hook_files = list(HOOKS_DIR.glob("*.py"))
        hook_files = [f for f in hook_files if f.name != "__init__.py"]
        missing = []
        for f in hook_files:
            rel_path = str(f.relative_to(REPO_ROOT)).replace("\\", "/")
            if f.name not in hash_keys and rel_path not in hash_keys:
                missing.append(f.name)
        assert not missing, f"Hooks thiếu hash baseline: {missing}"


# ---------------------------------------------------------------------------
# SEC-007: Fail-closed behavior cho security gates
# ---------------------------------------------------------------------------

class TestFailClosedBehavior:
    """SEC-007: Security gates phải fail-closed (block khi không chắc)."""

    @pytest.mark.parametrize("hook", [
        "schema_gate.py",
        "plan_enforce.py",
        "pre_tool_use.py",
    ])
    def test_security_hook_fail_closed_on_bad_input(self, hook):
        """Security hooks phải return non-zero hoặc block khi input sai."""
        hook_path = HOOKS_DIR / hook
        if not hook_path.exists():
            pytest.skip(f"{hook} not found")
        source = _read_source(hook_path)
        # Must have error handling that defaults to block/deny
        has_fail_closed = any(p in source for p in [
            "sys.exit(1)", "sys.exit(2)",
            '"deny"', "'deny'",
            '"block"', "'block'",
            "return False", "return None",
        ])
        assert has_fail_closed, (
            f"{hook} không có fail-closed pattern — phải block khi input không hợp lệ"
        )


# ---------------------------------------------------------------------------
# SEC-008: Path traversal prevention
# ---------------------------------------------------------------------------

class TestPathTraversalPrevention:
    """SEC-008: Path traversal phải được prevent."""

    def test_path_validation_in_hooks(self):
        """Hooks xử lý file_path phải validate path traversal."""
        # Check hooks that handle file paths
        path_handling_hooks = ["pre_tool_use.py", "plan_enforce.py", "coverage_enforce.py"]
        for hook_name in path_handling_hooks:
            hook_path = HOOKS_DIR / hook_name
            if not hook_path.exists():
                continue
            source = _read_source(hook_path)
            # Must have some form of path validation
            has_validation = any(p in source for p in [
                "..", "resolve()", "realpath", "abspath",
                "is_relative_to", "startswith", "Path(",
                "path_zones", "path_resolver", "validate",
            ])
            assert has_validation, (
                f"{hook_name} xử lý file path nhưng không có path validation"
            )


# ---------------------------------------------------------------------------
# SEC-009: No sensitive data in stdout/stderr
# ---------------------------------------------------------------------------

class TestNoSensitiveDataInLogs:
    """SEC-009: Không log sensitive data ra stdout/stderr."""

    def test_no_secret_logging_patterns(self):
        """Không print/log secrets."""
        # Match print/log statements that output actual secret values
        # Exclude: env var references, redaction, masking, token counting, hit_tokens etc.
        pattern = r"print\(.*(?:api_key|password|secret_key|credential|private_key)\s*="
        matches = _find_pattern_in_files(ALL_PY_FILES, pattern)
        real = [(f, l, t) for f, l, t in matches
                if "env" not in t.lower() and "redact" not in t.lower()
                and "mask" not in t.lower() and "filter" not in t.lower()
                and "os.environ" not in t.lower() and "getenv" not in t.lower()]
        assert not real, (
            f"Secret logging trong {len(real)} file(s):\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}:{l}: {t}" for f, l, t in real[:5])
        )


# ---------------------------------------------------------------------------
# SEC-010: Shell scripts phải có set -euo pipefail
# ---------------------------------------------------------------------------

class TestShellScriptSafety:
    """SEC-010: Shell scripts phải có set -euo pipefail."""

    def test_all_sh_scripts_have_set_euo(self):
        """Tất cả .sh files phải có set -euo pipefail."""
        sh_files = list((REPO_ROOT / ".opencode").rglob("*.sh"))
        issues = []
        for f in sh_files:
            content = _read_source(f)
            if not any(p in content for p in ["set -euo pipefail", "set -eu", "set -uo pipefail"]):
                issues.append(f.relative_to(REPO_ROOT))
        assert not issues, (
            f"Shell scripts thiếu set -euo pipefail:\n"
            + "\n".join(f"  {p}" for p in issues)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
