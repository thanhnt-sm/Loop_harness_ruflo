"""Unit tests cho baseline_validator.py — T05: Baseline Validation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))
from baseline_validator import validate_baseline, default_baseline, DIMENSIONS


def test_valid_baseline():
    """Baseline with 12 dimensions, variance > threshold → valid=True."""
    samples = []
    for i in range(20):
        sample = {dim: float(i * 10 + hash(dim) % 100) for dim in DIMENSIONS}
        samples.append(sample)
    baseline = {"samples": samples}
    result = validate_baseline(baseline)
    assert result["valid"] is True, f"Expected valid, got: {result}"


def test_poisoned_baseline():
    """Baseline with variance < threshold (all same values) → valid=False."""
    samples = [{dim: 5.0 for dim in DIMENSIONS} for _ in range(20)]
    baseline = {"samples": samples}
    result = validate_baseline(baseline)
    assert result["valid"] is False
    assert "poisoned" in result["reason"].lower() or "variance" in result["reason"].lower()


def test_insufficient_samples():
    """Baseline with < 10 samples → valid=False."""
    baseline = {"samples": [{dim: 1.0 for dim in DIMENSIONS}]}
    result = validate_baseline(baseline)
    assert result["valid"] is False
    assert "insufficient" in result["reason"].lower() or "samples" in result["reason"].lower()


def test_default_baseline():
    """default_baseline() trả dict có 'default': True."""
    default = default_baseline()
    assert default.get("default") is True
    assert "samples" in default


if __name__ == "__main__":
    tests = [test_valid_baseline, test_poisoned_baseline, test_insufficient_samples, test_default_baseline]
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
