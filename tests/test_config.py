#!/usr/bin/env python3
"""Kiểm thử cấu hình .devin/config.json."""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_config_is_valid_json():
    # config.json phải parse được
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    assert "permissions" in config
    assert "hooks" in config


def test_plan_enforce_registered_for_write_and_edit():
    # Hook plan_enforce chỉ được gắn cho matcher write và edit
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    hooks = config.get("hooks", {}).get("PreToolUse", [])
    matched = {h.get("matcher"): h for h in hooks}
    assert "write" in matched
    assert "edit" in matched
    assert "exec" not in matched or all(
        "plan_enforce" not in (cmd.get("command", "") for cmd in matched["exec"].get("hooks", []))
        for _ in [0]
    )
    for m in ("write", "edit"):
        commands = [cmd.get("command", "") for cmd in matched[m].get("hooks", [])]
        assert any("plan_enforce.py" in c for c in commands)


def test_deny_list_has_destructive_patterns():
    # deny list phải chứa các lệnh nguy hiểm
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    deny = config.get("permissions", {}).get("deny", [])
    patterns = ["rm -rf", "git push --force", "git push -f", "git reset --hard", "git clean -fd"]
    for p in patterns:
        assert any(p in d.lower() for d in deny), f"deny list thiếu pattern: {p}"


def test_core_scripts_allowed():
    # Các script cốt lõi phải nằm trong allow list
    config = json.loads((REPO_ROOT / ".devin" / "config.json").read_text(encoding="utf-8"))
    allow = config.get("permissions", {}).get("allow", [])
    required = [
        "Exec(python .devin/scripts/plan_orchestrator.py:*)",
        "Exec(python .devin/scripts/approval_gate.py:*)",
        "Exec(python .devin/scripts/plan_quality_check.py:*)",
    ]
    for r in required:
        assert r in allow, f"allow list thiếu: {r}"


def test_python_scripts_compile():
    # Kiểm tra tất cả script Python không có lỗi cú pháp
    scripts_dir = REPO_ROOT / ".devin" / "scripts"
    hooks_dir = REPO_ROOT / ".devin" / "hooks"
    for f in list(scripts_dir.glob("*.py")) + list(hooks_dir.glob("*.py")):
        result = subprocess.run([sys.executable, "-m", "py_compile", str(f)], capture_output=True, text=True)
        assert result.returncode == 0, f"Syntax error in {f}: {result.stderr}"
