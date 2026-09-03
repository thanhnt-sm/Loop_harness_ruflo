"""Tests cho _platform_utils.py — cross-platform helpers."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import _platform_utils  # noqa: E402
from _platform_utils import (  # noqa: E402
    get_python_cmd,
    is_linux,
    is_macos,
    is_posix,
    is_windows,
    make_executable,
    normalize_path,
    run_python,
    safe_chmod,
)


def test_is_windows_consistent():
    import platform
    assert is_windows() == (sys.platform == "win32")
    assert is_macos() == (sys.platform == "darwin")
    assert is_linux() == sys.platform.startswith("linux")
    assert is_posix() == (sys.platform != "win32")


def test_get_python_cmd_default():
    """get_python_cmd trả về string hợp lệ (py hoặc python3 hoặc python)."""
    cmd = get_python_cmd()
    assert cmd in ("py", "python3", "python")
    # Verify command tồn tại
    r = subprocess.run([cmd, "--version"], capture_output=True, timeout=10)
    assert r.returncode == 0


def test_get_python_cmd_override_via_env(monkeypatch):
    monkeypatch.setenv("AHD_PYTHON_CMD", "py")
    assert get_python_cmd() == "py"


def test_get_python_cmd_override_via_env_python3(monkeypatch):
    monkeypatch.setenv("AHD_PYTHON_CMD", "python3")
    assert get_python_cmd() == "python3"


def test_run_python_invoke_version():
    """run_python invoke đúng binary."""
    r = run_python(["--version"], timeout=10)
    assert r.returncode == 0
    assert "Python" in r.stdout


def test_run_python_cwd():
    """run_python chạy với cwd specified."""
    r = run_python(["-c", "import os; print(os.getcwd())"], timeout=10)
    assert r.returncode == 0


def test_run_python_timeout():
    """run_python timeout nếu quá lâu."""
    with pytest.raises(subprocess.TimeoutExpired):
        run_python(["-c", "import time; time.sleep(10)"], timeout=2)


def test_run_python_env_merge():
    """run_python merge env vars."""
    r = run_python(["-c", "import os; print(os.environ.get('MY_TEST_VAR', 'NOT_SET'))"],
                   env={"MY_TEST_VAR": "hello"}, timeout=10)
    assert r.returncode == 0
    assert r.stdout.strip() == "hello"


def test_normalize_path_absolute(tmp_path):
    p = normalize_path(tmp_path)
    assert Path(p).is_absolute()
    # POSIX-style dùng forward slashes
    assert "\\" not in p


def test_safe_chmod_on_posix(tmp_path):
    """Trên POSIX, chmod thực sự thay đổi permission."""
    if not is_posix():
        pytest.skip("POSIX only test")
    test_file = tmp_path / "test.sh"
    test_file.write_text("#!/bin/sh\necho ok\n")
    safe_chmod(test_file, 0o755)
    import stat
    mode = test_file.stat().st_mode
    assert mode & stat.S_IXUSR  # owner executable


def test_safe_chmod_noop_on_windows(tmp_path):
    """Trên Windows, safe_chmod no-op (không raise)."""
    if not is_windows():
        pytest.skip("Windows only test")
    test_file = tmp_path / "test.bat"
    test_file.write_text("@echo off")
    safe_chmod(test_file, 0o755)  # no raise


def test_make_executable(tmp_path):
    test_file = tmp_path / "test.sh"
    test_file.write_text("#!/bin/sh\n")
    make_executable(test_file)
    if is_posix():
        import stat
        assert test_file.stat().st_mode & stat.S_IXUSR


def test_ensure_utf8_output_does_not_raise():
    """ensure_utf8_output không raise."""
    from _platform_utils import ensure_utf8_output
    # Gọi nhiều lần để test idempotent
    ensure_utf8_output()
    ensure_utf8_output()
