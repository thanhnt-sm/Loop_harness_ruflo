"""Unit tests cho path_resolver.py — T03: Cross-Platform Path Resolver."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "scripts"))
from path_resolver import python_executable, venv_dir, repo_root


def test_windows_path():
    """sys.platform=win32 → returns .venv/Scripts/python.exe."""
    with patch.object(sys, "platform", "win32"):
        # Clear cache
        python_executable.cache_clear()
        venv_dir.cache_clear()
        result = python_executable()
        assert "Scripts" in result
        assert "python.exe" in result


def test_unix_path():
    """sys.platform=linux → returns .venv/bin/python."""
    with patch.object(sys, "platform", "linux"):
        python_executable.cache_clear()
        venv_dir.cache_clear()
        result = python_executable()
        assert "bin" in result
        assert "python" in result
        assert not result.endswith(".exe")


def test_cached():
    """python_executable() phải cache result (lru_cache)."""
    python_executable.cache_clear()
    r1 = python_executable()
    r2 = python_executable()
    assert r1 == r2
    # Cache info phải cho thấy hit
    assert python_executable.cache_info().hits >= 1


if __name__ == "__main__":
    tests = [test_windows_path, test_unix_path, test_cached]
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
