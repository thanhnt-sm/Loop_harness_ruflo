#!/usr/bin/env python3
"""_platform_utils.py — Cross-platform helpers (Windows + macOS + Linux).

Mục đích: cung cấp helpers chuẩn để scripts chạy được trên cả 3 OS mà KHÔNG
cần tách file riêng. Sử dụng `sys.platform` (cross-platform) thay vì `os.name`.

Spec: docs/plans/deploy-everywhere.md section 4

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional
__all__ = [
    "ensure_utf8_output",
    "get_python_cmd",
    "is_linux",
    "is_macos",
    "is_posix",
    "is_windows",
    "make_executable",
    "normalize_path",
    "run_python",
    "safe_chmod",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


# === Python command detection (cross-platform) ===
# Windows: "py" hoặc "python"
# macOS/Linux: "python3" (preferred) hoặc "python"
if sys.platform == "win32":
    DEFAULT_PYTHON_CMD = "py"
else:
    # POSIX: prefer python3, fallback to python
    import shutil
    DEFAULT_PYTHON_CMD = "python3" if shutil.which("python3") else "python"


def get_python_cmd() -> str:
    """Trả về Python command cho platform hiện tại. Override qua env AHD_PYTHON_CMD."""
    return os.environ.get("AHD_PYTHON_CMD", DEFAULT_PYTHON_CMD)


# === Platform detection helpers ===
def is_windows() -> bool:
    """Check nếu đang chạy trên Windows."""
    return sys.platform == "win32"


def is_macos() -> bool:
    """Check nếu đang chạy trên macOS."""
    return sys.platform == "darwin"


def is_linux() -> bool:
    """Check nếu đang chạy trên Linux."""
    return sys.platform.startswith("linux")


def is_posix() -> bool:
    """Check nếu đang chạy trên POSIX (macOS + Linux)."""
    return sys.platform != "win32"


# === Subprocess wrapper ===
def run_python(
    args: list[str],
    timeout: int = 60,
    cwd: Optional[str | Path] = None,
    env: Optional[dict] = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Chạy Python subprocess với command đúng cho platform.

    Args:
        args: list arguments cho Python (không bao gồm "py"/"python3")
        timeout: timeout in seconds
        cwd: working directory
        env: env vars (merge với os.environ)
        **kwargs: pass to subprocess.run
    """
    cmd = [get_python_cmd()] + list(args)
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        env=full_env,
        **kwargs,
    )


# === Path utilities ===
def normalize_path(path: str | Path) -> str:
    """Convert path sang absolute POSIX path (forward slashes).

    Hữu ích khi cần pass path cho shell command cross-platform.
    """
    p = Path(path).resolve()
    # pathlib dùng OS-native separator; convert manually
    s = str(p)
    if is_windows():
        # Convert "C:\\foo\\bar" -> "/c/foo/bar" (POSIX style for Windows)
        # hoặc giữ nguyên nếu dùng cho Windows command
        return s.replace("\\", "/")
    return s


def safe_chmod(path: str | Path, mode: int) -> None:
    """chmod chỉ trên POSIX, no-op trên Windows."""
    if is_posix():
        os.chmod(path, mode)


def make_executable(path: str | Path) -> None:
    """Set executable bit (0o755) cho POSIX. No-op trên Windows."""
    safe_chmod(path, 0o755)


# === Encoding helpers ===
def ensure_utf8_output() -> None:
    """Reconfigure stdout/stderr sang UTF-8 (Windows cần thiết)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    print(f"Python cmd: {get_python_cmd()}")
    print(f"Platform: {sys.platform}")
    print(f"Windows: {is_windows()}, macOS: {is_macos()}, Linux: {is_linux()}, POSIX: {is_posix()}")
    print(f"normalize_path('.\\foo'): {normalize_path('./foo')}")
