#!/usr/bin/env python3
"""Kiểm thử cho schema_gate.py."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(tool_name, tool_input, tool_output=None):
    # Chạy schema_gate.py với JSON qua stdin
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "hooks" / "schema_gate.py")]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    payload = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_output": tool_output if tool_output is not None else "",
    }
    result = subprocess.run(
        cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    return result


def test_write_to_src_allowed():
    # Ghi file trong src/ được phép
    res = _run("write", {"file_path": "src/app.py", "content": "x = 1"})
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["passed"] is True


def test_write_to_tests_allowed():
    # Ghi file trong tests/ được phép
    res = _run("write", {"file_path": "tests/test_app.py", "content": "x = 1"})
    assert res.returncode == 0


def test_write_to_blocked_config_blocked():
    # Sửa .devin/config.json bị chặn
    res = _run("write", {"file_path": ".devin/config.json", "content": "{}"})
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["passed"] is False
    assert "Blocked zone" in data["reason"]


def test_write_to_hook_blocked():
    # Sửa hook bị chặn
    res = _run("write", {"file_path": ".devin/hooks/plan_enforce.py", "content": "x"})
    assert res.returncode == 1


def test_path_traversal_blocked():
    # Path traversal bị chặn
    res = _run("write", {"file_path": "docs/plans/../secrets/file.py", "content": "x"})
    assert res.returncode == 1


def test_absolute_outside_repo_blocked():
    # Đường dẫn tuyệt đối ngoài repo bị chặn
    res = _run("write", {"file_path": "C:/Windows/outside.py", "content": "x"})
    assert res.returncode == 1


def test_secret_scan_blocked():
    # Secret trong output bị chặn
    res = _run(
        "write",
        {"file_path": "src/app.py", "content": "x"},
        tool_output="ghp_1234567890abcdef1234567890abcdef1234",
    )
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["gate"] == "secret_scan"


def test_missing_required_field_blocked():
    # Write thiếu content bị chặn
    res = _run("write", {"file_path": "src/app.py"})
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["gate"] == "required_fields"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
