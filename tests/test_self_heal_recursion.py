"""Unit tests cho self_heal — T14: Recursion Guard."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "hooks"))
from self_heal import _check_recursion_depth, MAX_SELF_HEAL_DEPTH


def test_depth_3_blocked():
    """self_heal_depth >= MAX_SELF_HEAL_DEPTH → blocked=True, action=escalate."""
    data = {"session_state": {"self_heal_depth": 3}}
    result = _check_recursion_depth(data)
    assert result["blocked"] is True
    assert result["result"]["action"] == "escalate"
    assert "recursion_limit" in result["result"]["reason"]


def test_depth_0_allowed():
    """self_heal_depth=0 → blocked=False."""
    data = {"session_state": {"self_heal_depth": 0}}
    result = _check_recursion_depth(data)
    assert result["blocked"] is False


def test_depth_at_max():
    """self_heal_depth == MAX_SELF_HEAL_DEPTH → blocked=True."""
    data = {"session_state": {"self_heal_depth": MAX_SELF_HEAL_DEPTH}}
    result = _check_recursion_depth(data)
    assert result["blocked"] is True


def test_no_session_state():
    """Không có session_state → depth=0 → blocked=False."""
    data = {}
    result = _check_recursion_depth(data)
    assert result["blocked"] is False


if __name__ == "__main__":
    tests = [test_depth_3_blocked, test_depth_0_allowed, test_depth_at_max, test_no_session_state]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
