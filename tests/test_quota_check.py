"""Unit tests cho quota_check.py — T02: Subagent Quota Fallback."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))

from quota_check import check_quota, should_switch_to_degraded, is_degraded_mode, degraded_mode_requirements


def test_quota_available():
    """Mock quota check returns available=True → FSM proceeds with dispatch."""
    os.environ["AHD_QUOTA_FORCE"] = "available"
    result = check_quota()
    assert result["available"] is True
    assert should_switch_to_degraded(result) is False
    os.environ.pop("AHD_QUOTA_FORCE", None)


def test_quota_exhausted_degraded():
    """Mock quota check returns available=False → degraded mode flag set."""
    os.environ["AHD_QUOTA_FORCE"] = "exhausted"
    result = check_quota()
    assert result["available"] is False
    assert should_switch_to_degraded(result) is True
    # Simulate FSM setting degraded mode
    state = {}
    if should_switch_to_degraded(result):
        state["degraded_mode"] = True
    assert is_degraded_mode(state) is True
    os.environ.pop("AHD_QUOTA_FORCE", None)


def test_degraded_mode_requirements():
    """Degraded mode phải require adversarial self-review với 3+ perspectives."""
    reqs = degraded_mode_requirements()
    assert len(reqs) >= 4
    # Phải có 3 personas
    reqs_text = " ".join(reqs)
    assert "Saboteur" in reqs_text
    assert "Security Auditor" in reqs_text
    assert "Architect" in reqs_text
    # Phải require self-review
    assert "self_review" in reqs_text.lower() or "self-review" in reqs_text.lower()


def test_default_available():
    """Default (no env) → available=True."""
    os.environ.pop("AHD_QUOTA_FORCE", None)
    result = check_quota()
    assert result["available"] is True


if __name__ == "__main__":
    tests = [
        test_quota_available, test_quota_exhausted_degraded,
        test_degraded_mode_requirements, test_default_available,
    ]
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
