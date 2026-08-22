"""Unit tests cho cross_family_verify.py — T09: Cross-Family Verification."""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".devin" / "hooks" / "cross_family_verify.py"


def _run_hook(input_data: dict) -> dict:
    """Chạy hook với stdin input, trả parsed JSON output."""
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout, "stderr": result.stderr, "code": result.returncode}


def test_same_family_warning():
    """M-tier + same family → advisory warning (allow)."""
    data = {
        "tool_name": "Write",
        "session_state": {"tier": "M", "producer_model": "glm-5.2", "verifier_model": "glm-4.6"},
    }
    result = _run_hook(data)
    assert result.get("allow") is True
    assert "advisory" in result.get("reason", "").lower() or "same family" in result.get("reason", "").lower()


def test_xl_block_same_family():
    """XL-tier + same family → block (exit 2)."""
    data = {
        "tool_name": "Write",
        "session_state": {"tier": "XL", "producer_model": "glm-5.2", "verifier_model": "glm-4.6"},
    }
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(data),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    parsed = json.loads(result.stdout)
    assert parsed.get("allow") is False


def test_cross_family_ok():
    """Cross-family → allow."""
    data = {
        "tool_name": "Write",
        "session_state": {"tier": "XL", "producer_model": "glm-5.2", "verifier_model": "claude-4"},
    }
    result = _run_hook(data)
    assert result.get("allow") is True


if __name__ == "__main__":
    tests = [test_same_family_warning, test_xl_block_same_family, test_cross_family_ok]
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
