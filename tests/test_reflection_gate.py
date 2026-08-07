#!/usr/bin/env python3
"""Kiểm thử reflection_gate.py — T4.9 (REQ-012).

Các ca kiểm thử:
1. reflect trả ReflectVerdict đầy đủ trường.
2. Action destructive (delete/force_push/drop/reset_hard) -> block + human confirm.
3. Action read an toàn -> không block.
4. Multi-level: intra/inter/foresight hoạt động đúng.
5. Action chạm vùng nhạy cảm (.env, HLK/) -> block ở cấp inter.
6. Level không hợp lệ raise ValueError.
7. check_reflection helper xử lý dict input.
8. Tích hợp pre_tool_use: rm -rf bị block bởi reflection gate.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from data_models import Action, ReflectVerdict  # noqa: E402
from reflection_gate import reflect, check_reflection, REFLECTION_LEVELS  # noqa: E402


def _action(category: str = "read", target: str = "/tmp/file", destructive: bool = False) -> Action:
    return Action(
        id="test-1",
        category=category,  # type: ignore[arg-type]
        target=target,
        args={},
        destructive=destructive,
    )


def test_reflect_returns_verdict():
    """reflect trả ReflectVerdict đầy đủ trường."""
    verdict = reflect(_action(), level="intra")
    assert isinstance(verdict, ReflectVerdict)
    assert verdict.action_id == "test-1"
    assert verdict.level == "intra"
    assert isinstance(verdict.block, bool)
    assert isinstance(verdict.reason, str)


@pytest.mark.parametrize("category", ["delete", "force_push", "drop", "reset_hard"])
def test_destructive_actions_blocked_with_human_confirm(category):
    """Action destructive -> block + human_confirm_required."""
    verdict = reflect(_action(category=category, destructive=True), level="intra")
    assert verdict.block is True
    assert verdict.human_confirm_required is True


def test_read_action_not_blocked():
    """Action read -> không block ở mọi cấp."""
    for level in REFLECTION_LEVELS:
        verdict = reflect(_action(category="read"), level=level)
        assert verdict.block is False


def test_write_action_not_blocked_intra():
    """Action write (không destructive) -> không block ở cấp intra."""
    verdict = reflect(_action(category="write", target="src/file.py"), level="intra")
    assert verdict.block is False


def test_write_path_traversal_blocked_intra():
    """Action write chứa '..' -> block ở cấp intra."""
    verdict = reflect(_action(category="write", target="../etc/passwd"), level="intra")
    assert verdict.block is True


def test_inter_blocks_sensitive_zones():
    """Action chạm vùng nhạy cảm (.env, HLK/) -> block ở cấp inter."""
    for target in ("path/.env", "HLK/config.json", "credentials/secret", "secrets/key", ".git/config"):
        verdict = reflect(_action(category="write", target=target), level="inter")
        assert verdict.block is True, f"phải block target {target}"
        assert verdict.human_confirm_required is True


def test_foresight_blocks_destructive():
    """Cấp foresight: destructive -> block + human confirm."""
    verdict = reflect(_action(category="delete", destructive=True), level="foresight")
    assert verdict.block is True
    assert verdict.human_confirm_required is True
    assert "irreversible" in verdict.reason.lower() or "data loss" in verdict.reason.lower()


def test_invalid_level_raises():
    """Level không hợp lệ raise ValueError."""
    with pytest.raises(ValueError):
        reflect(_action(), level="invalid")
    with pytest.raises(ValueError):
        reflect(_action(), level="")


def test_invalid_action_raises():
    """action không phải Action raise TypeError."""
    with pytest.raises(TypeError):
        reflect("not-an-action", level="intra")  # type: ignore[arg-type]


def test_check_reflection_helper_dict_input():
    """check_reflection xử lý dict input, trả ReflectVerdict hoặc None."""
    # Dict destructive -> verdict block
    verdict = check_reflection({
        "id": "a1",
        "category": "delete",
        "target": "/tmp/x",
        "destructive": True,
    })
    assert verdict is not None
    assert verdict.block is True
    # Dict không có category -> None
    assert check_reflection({"id": "x"}) is None
    # Dict category không hợp lệ -> None
    assert check_reflection({"category": "invalid_cat"}) is None


def test_check_reflection_none_for_non_dict():
    """check_reflection trả None cho input không phải dict."""
    assert check_reflection(None) is None  # type: ignore[arg-type]
    assert check_reflection("string") is None  # type: ignore[arg-type]


# --- Integration test với pre_tool_use.py ---

def _run_pre_tool(command: str) -> subprocess.CompletedProcess:
    """Chạy pre_tool_use.py với command, trả kết quả."""
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "hooks" / "pre_tool_use.py")]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        cmd,
        input=json.dumps({"tool_name": "exec", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def test_pre_tool_reflection_blocks_drop_table():
    """Integration: 'drop table' bị block bởi reflection gate (hoặc dangerous pattern)."""
    res = _run_pre_tool("echo 'drop table users' | psql")
    # reflection gate sẽ block drop category
    assert res.returncode == 2
    # Có thể block bởi dangerous pattern hoặc reflection gate — cả hai đều exit 2
    assert "BLOCKED" in res.stderr


def test_pre_tool_safe_command_allowed():
    """Integration: lệnh an toàn vẫn được phép (exit 0)."""
    res = _run_pre_tool("git status")
    assert res.returncode == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
