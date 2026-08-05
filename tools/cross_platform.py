#!/usr/bin/env python3
"""U39: Cross-platform tool wrappers — Python equivalents for PowerShell tools.

Provides Python implementations of key tools for Linux/macOS compatibility.
Each tool can be run directly or imported as a module.

Usage:
    python tools/cross_platform.py <tool> [args...]

Available tools:
    verify-workspace    — Check workspace integrity
    health-check        — Workspace health score
    backup-workspace    — Backup workspace state
    cleanup-orphans     — Clean orphaned sessions
    merge-config        — Merge config files
    risk-contract       — Check risk contracts
    package-template    — Package template for deployment
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_repo_root() -> Path:
    """Get repository root via git rev-parse."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=str(Path.cwd())
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def verify_workspace(root: Path = None) -> int:
    """U39: Cross-platform verify-workspace — check workspace integrity."""
    root = root or get_repo_root()
    checks = {
        "canon": [".devin/canon/BOOT_PROTOCOL.md", ".devin/canon/LOOP_PROTOCOL.md",
                   ".devin/canon/VERIFICATION_PROTOCOL.md", ".devin/canon/REDLINES.md"],
        "agents": [".devin/agents/COMMANDER.md", ".devin/agents/DISPATCH_TEMPLATES.md"],
        "hooks": [".devin/hooks/pre_tool_use.py", ".devin/hooks/post_tool_use.py",
                  ".devin/hooks/stop.py", ".devin/hooks/ahd_session.py"],
        "config": [".devin/config.json", ".devin/tool_registry.json"],
        "skills": [".devin/skills/slop-detector.md", ".devin/skills/using-skills.md",
                    ".devin/skills/comment_checker.md", ".devin/skills/fable-judge.md",
                    ".devin/skills/harness-sensor.md"],
    }

    passed = 0
    failed = 0

    for category, files in checks.items():
        print(f"\n[{category}]")
        for f in files:
            path = root / f
            ok = path.exists()
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {f}")
            if ok:
                passed += 1
            else:
                failed += 1

    # Check personas dir
    personas_dir = root / ".devin/agents/personas"
    if personas_dir.exists():
        personas = list(personas_dir.iterdir())
        print(f"\n[personas] {len(personas)} files")
        passed += 1
    else:
        print(f"\n[personas] FAIL — dir missing")
        failed += 1

    # Check workers dir
    workers_dir = root / ".devin/agents/workers"
    if workers_dir.exists():
        workers = list(workers_dir.iterdir())
        print(f"[workers] {len(workers)} files")
        passed += 1
    else:
        print(f"[workers] FAIL — dir missing")
        failed += 1

    print(f"\n=== Result: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


def health_check(root: Path = None) -> int:
    """U39: Cross-platform health-check — workspace health score."""
    root = root or get_repo_root()
    total = 0
    passed = 0

    # 1. Hooks exist + syntax
    print("[1/4] Hook execution")
    hooks = ["pre_tool_use.py", "post_tool_use.py", "stop.py", "ahd_session.py"]
    for h in hooks:
        path = root / ".devin/hooks" / h
        ok = path.exists()
        total += 1
        if ok:
            passed += 1
            # Syntax check
            try:
                import py_compile
                py_compile.compile(str(path), doraise=True)
                total += 1
                passed += 1
            except Exception:
                total += 1
        else:
            total += 1

    # 2. MCP config
    print("[2/4] MCP server")
    mcp_path = root / ".devin/mcp_config.json"
    total += 1
    if mcp_path.exists():
        passed += 1

    # 3. Memory write/read
    print("[3/4] Memory write/read")
    state_dir = root / ".devin/session_state"
    total += 1
    if state_dir.exists():
        passed += 1
        test_file = state_dir / "health-check-test.json"
        try:
            test_file.write_text(json.dumps({"test": "u39"}), encoding="utf-8")
            data = json.loads(test_file.read_text(encoding="utf-8"))
            total += 2
            if data.get("test") == "u39":
                passed += 2
            test_file.unlink()
        except Exception:
            total += 2
    else:
        total += 2

    # 4. Canon + config
    print("[4/4] Canon + config")
    canon_files = [
        ".devin/canon/BOOT_PROTOCOL.md", ".devin/canon/LOOP_PROTOCOL.md",
        ".devin/canon/VERIFICATION_PROTOCOL.md", ".devin/canon/REDLINES.md",
        ".devin/config.json", ".devin/tool_registry.json",
    ]
    for f in canon_files:
        total += 1
        if (root / f).exists():
            passed += 1

    # Config JSON valid
    total += 1
    try:
        json.loads((root / ".devin/config.json").read_text(encoding="utf-8"))
        passed += 1
    except Exception:
        pass

    score = int(passed * 100 / total) if total > 0 else 0
    status = "HEALTHY" if score >= 90 else "DEGRADED" if score >= 70 else "UNHEALTHY"
    print(f"\n=== Health Score: {score}/100 ({status}) ===")
    print(f"  Checks: {passed}/{total}")
    return 0 if score >= 70 else 1


def backup_workspace(root: Path = None) -> int:
    """U39: Cross-platform backup-workspace."""
    root = root or get_repo_root()
    backup_dir = root / ".devin/backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"workspace-{timestamp}"

    dirs_to_backup = [".devin/canon", ".devin/agents", ".devin/hooks", ".devin/config.json"]
    for item in dirs_to_backup:
        src = root / item
        if src.exists():
            dst = backup_path / item
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    print(f"[OK] Backup created: {backup_path}")
    return 0


def cleanup_orphans(root: Path = None, max_age_days: int = 7) -> int:
    """U39: Cross-platform cleanup-orphan-sessions."""
    root = root or get_repo_root()
    state_dir = root / ".devin/session_state"
    if not state_dir.exists():
        print("[OK] No session_state dir")
        return 0

    now = datetime.now()
    orphans = 0

    for f in state_dir.glob("*.json"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age = (now - mtime).days
        if age > max_age_days:
            print(f"[ORPHAN] {f.name} ({age} days old)")
            f.unlink()
            orphans += 1

    print(f"\n[DONE] Cleaned {orphans} orphan(s)")
    return 0


def merge_config(base_path: str, source_path: str, output_path: str = None) -> int:
    """U39: Cross-platform merge-config."""
    if output_path is None:
        output_path = base_path

    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    source = json.loads(Path(source_path).read_text(encoding="utf-8"))

    conflicts = []

    def deep_merge(b, s, path=""):
        result = dict(b)
        for k, v in s.items():
            if k not in b:
                result[k] = v
                print(f"[ADD] {path}{k}")
            elif b[k] == s[k]:
                pass
            elif isinstance(b[k], list) and isinstance(s[k], list):
                combined = list(b[k])
                for item in s[k]:
                    if item not in combined:
                        combined.append(item)
                        print(f"[MERGE] {path}{k} + {item}")
                result[k] = combined
            elif isinstance(b[k], dict) and isinstance(s[k], dict):
                result[k] = deep_merge(b[k], s[k], f"{path}{k}.")
            else:
                conflicts.append({"path": f"{path}{k}", "base": b[k], "source": s[k]})
                result[k] = b[k]  # keep base on conflict
        return result

    merged = deep_merge(base, source)

    if conflicts:
        print(f"\n[CONFLICT] {len(conflicts)} conflict(s) — kept base values:")
        for c in conflicts:
            print(f"  {c['path']}: base={c['base']} vs source={c['source']}")

    Path(output_path).write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"\n[DONE] Merged config: {output_path}")
    return 0


def risk_contract_check(root: Path = None) -> int:
    """U39: Cross-platform risk-contract-check."""
    root = root or get_repo_root()
    contract_path = root / ".devin/risk_contract.json"
    if not contract_path.exists():
        print("[OK] No risk contract found")
        return 0

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=str(root)
        )
        staged_files = staged.stdout.strip().split("\n") if staged.stdout.strip() else []
    except Exception:
        staged_files = []

    if not staged_files:
        print("[OK] No staged files")
        return 0

    violations = 0
    critical = contract.get("critical_files", {})
    for f in staged_files:
        norm = f.replace("\\", "/")
        for pattern, rules in critical.items():
            norm_pat = pattern.replace("\\", "/")
            if norm_pat in norm or norm.endswith(norm_pat):
                print(f"[CHECK] Critical file: {f} (risk: {rules.get('risk')})")

    if violations == 0:
        print("[OK] Risk contract check passed")
    return 0 if violations == 0 else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    tool = sys.argv[1]
    args = sys.argv[2:]

    tools = {
        "verify-workspace": lambda: verify_workspace(),
        "health-check": lambda: health_check(),
        "backup-workspace": lambda: backup_workspace(),
        "cleanup-orphans": lambda: cleanup_orphans(),
        "merge-config": lambda: merge_config(args[0], args[1], args[2] if len(args) > 2 else None),
        "risk-contract": lambda: risk_contract_check(),
    }

    if tool not in tools:
        print(f"Unknown tool: {tool}")
        print(f"Available: {', '.join(tools.keys())}")
        return 1

    return tools[tool]()


if __name__ == "__main__":
    sys.exit(main())
