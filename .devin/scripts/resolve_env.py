#!/usr/bin/env python3
"""resolve_env.py — U24: Resolve environment variables in paths.

Devin CLI config.json may contain %APPDATA%, %USERPROFILE%, etc.
These are not automatically expanded by the CLI. This module provides
functions to resolve them at runtime.

Usage (inline):
    from resolve_env import resolve_path
    resolved = resolve_path("%APPDATA%\\nvm\\v18.20.0\\node_modules")
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Pattern for Windows-style %VAR% expansion
_WIN_ENV_PATTERN = re.compile(r"%(\w+)%")

# Pattern for Unix-style $VAR expansion
_UNIX_ENV_PATTERN = re.compile(r"\$(\w+)")


def resolve_path(path: str) -> str:
    """U24: Resolve environment variables in a path string.

    Supports both Windows (%VAR%) and Unix ($VAR) style variables.
    Unknown variables are left as-is (not expanded).

    Examples:
        resolve_path("%APPDATA%\\nvm") → "C:\\Users\\user\\AppData\\Roaming\\nvm"
        resolve_path("$HOME/.config") → "/home/user/.config"
        resolve_path("%UNKNOWN%\\path") → "%UNKNOWN%\\path" (left as-is)
    """
    if not path:
        return path

    # Resolve Windows-style %VAR%
    def _win_replacer(match: re.Match) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name)
        return value if value is not None else match.group(0)

    result = _WIN_ENV_PATTERN.sub(_win_replacer, path)

    # Resolve Unix-style $VAR
    def _unix_replacer(match: re.Match) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name)
        return value if value is not None else match.group(0)

    result = _UNIX_ENV_PATTERN.sub(_unix_replacer, result)

    return result


def resolve_path_or_none(path: str) -> Path | None:
    """U24: Resolve env vars and return Path object, or None if path doesn't exist."""
    resolved = resolve_path(path)
    p = Path(resolved)
    return p if p.exists() else None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="U24: Resolve environment variables in paths")
    ap.add_argument("path", help="Path with env vars to resolve")
    args = ap.parse_args()
    print(resolve_path(args.path))
