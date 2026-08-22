"""Unit tests cho cost_tracker — T13: Adaptive Cost Reduction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))
from cost_tracker import _adaptive_reduce


def test_50pct_reduce():
    """Cost 50% → action=reduce, max_subagents=3."""
    state = {"cumulative_cost": 5.0, "cost_cap": 10.0}
    result = _adaptive_reduce(state)
    assert result["action"] == "reduce"
    assert result["max_subagents"] == 3


def test_80pct_degraded():
    """Cost 80% → action=degraded, max_subagents=0."""
    state = {"cumulative_cost": 8.0, "cost_cap": 10.0}
    result = _adaptive_reduce(state)
    assert result["action"] == "degraded"
    assert result["max_subagents"] == 0


def test_100pct_stop():
    """Cost 100% → action=stop."""
    state = {"cumulative_cost": 10.0, "cost_cap": 10.0}
    result = _adaptive_reduce(state)
    assert result["action"] == "stop"


def test_normal():
    """Cost < 50% → action=normal, max_subagents=5."""
    state = {"cumulative_cost": 2.0, "cost_cap": 10.0}
    result = _adaptive_reduce(state)
    assert result["action"] == "normal"
    assert result["max_subagents"] == 5


if __name__ == "__main__":
    tests = [test_50pct_reduce, test_80pct_degraded, test_100pct_stop, test_normal]
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
