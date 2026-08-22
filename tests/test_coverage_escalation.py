"""Unit tests cho coverage_enforce — T06: Coverage Escalation."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "hooks"))

from coverage_enforce import _check_coverage_threshold


def test_block_session_end():
    """Coverage < 80% → action=block."""
    os.environ.pop("AHD_COVERAGE_OVERRIDE", None)
    result = _check_coverage_threshold(50.0, threshold=80.0)
    assert result["action"] == "block"
    assert not result["meets_threshold"]


def test_override():
    """Coverage < 80% + AHD_COVERAGE_OVERRIDE=1 → action=override."""
    os.environ["AHD_COVERAGE_OVERRIDE"] = "1"
    result = _check_coverage_threshold(50.0, threshold=80.0)
    assert result["action"] == "override"
    os.environ.pop("AHD_COVERAGE_OVERRIDE", None)


def test_meets_threshold():
    """Coverage >= 80% → action=allow."""
    result = _check_coverage_threshold(85.0, threshold=80.0)
    assert result["action"] == "allow"
    assert result["meets_threshold"]


if __name__ == "__main__":
    tests = [test_block_session_end, test_override, test_meets_threshold]
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
