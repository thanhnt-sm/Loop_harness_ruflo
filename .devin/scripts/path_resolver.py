#!/usr/bin/env python3
"""path_resolver.py — Cross-platform path resolver cho AHD.

V3 fix: Windows dùng .venv/Scripts/python.exe, Unix dùng .venv/bin/python.
Tất cả skills/scripts dùng module này thay vì hardcoded .venv/bin/python.
"""
from __future__ import annotations

import functools
import sys
from pathlib import Path


@functools.lru_cache(maxsize=1)
def repo_root() -> Path:
    """Tìm repo root — đi lên cho đến khi thấy .devin/."""
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


@functools.lru_cache(maxsize=1)
def venv_dir() -> Path:
    """Trả về thư mục venv cho platform hiện tại."""
    root = repo_root()
    if sys.platform == "win32":
        return root / ".venv" / "Scripts"
    return root / ".venv" / "bin"


@functools.lru_cache(maxsize=1)
def python_executable() -> str:
    """Trả về đường dẫn Python executable cho platform hiện tại.

    Windows: .venv/Scripts/python.exe
    Unix: .venv/bin/python
    """
    venv = venv_dir()
    if sys.platform == "win32":
        return str(venv / "python.exe")
    return str(venv / "python")


@functools.lru_cache(maxsize=1)
def python_executable_escaped() -> str:
    """Trả về Python executable với path separators escape cho shell."""
    return python_executable().replace("\\", "/")


if __name__ == "__main__":
    print(f"Platform: {sys.platform}")
    print(f"Python: {python_executable()}")
    print(f"Venv dir: {venv_dir()}")
