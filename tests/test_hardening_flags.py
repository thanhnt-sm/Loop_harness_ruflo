"""Unit tests cho hardening_flags.py — T15: Feature Flags."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))
from hardening_flags import is_enabled, all_flags, ALL_FLAGS


def test_default_enabled():
    """Mặc định tất cả flags = True (enabled)."""
    # Xóa env override
    for flag in ALL_FLAGS:
        os.environ.pop(f"AHD_HARDENING_DISABLE_{flag}", None)
    for flag in ALL_FLAGS:
        assert is_enabled(flag) is True, f"{flag} should be enabled by default"


def test_disable_flag():
    """AHD_HARDENING_DISABLE_<FLAG>=1 → disabled."""
    os.environ["AHD_HARDENING_DISABLE_V01_DAG_SCHEMA"] = "1"
    assert is_enabled("V01_DAG_SCHEMA") is False
    os.environ.pop("AHD_HARDENING_DISABLE_V01_DAG_SCHEMA", None)


def test_all_flags():
    """all_flags() trả dict với 14 flags."""
    flags = all_flags()
    assert len(flags) == 14
    for flag in ALL_FLAGS:
        assert flag in flags


if __name__ == "__main__":
    tests = [test_default_enabled, test_disable_flag, test_all_flags]
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
