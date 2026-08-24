#!/usr/bin/env python3
"""plan_dispatch_grep.py — File discovery via grep/rg/findstr.

Module for finding files matching patterns across the repository.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    import ahd_session
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session


def _get_repo_root() -> Path:
    """Find the main repo root."""
    return ahd_session.get_repo_root()


ROOT = _get_repo_root()


def _grep_files(pattern: str, path: str = ".") -> list[str]:
    """Find files matching a pattern (import/reference grep).

    Thử `rg` trước, nếu thất bại thì fallback `grep` (Unix) hoặc `findstr` (Windows).
    """
    candidates = [
        ["rg", "-l", "--no-heading", pattern, path],
    ]
    if sys.platform == "win32":
        candidates.append(["findstr", "/M", "/S", f"/C:{pattern}", f"{path}\\*"])
    else:
        candidates.append(["grep", "-lR", "--", pattern, path])

    for cmd in candidates:
        try:
            r = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=10, cwd=str(ROOT)
            )
            if r.returncode in (0, 1):
                out = [f.strip() for f in r.stdout.strip().split("\n") if f.strip()]
                if out or r.returncode == 0:
                    return out
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return []


def _expand_file_hints(files_hint: list[str]) -> set[str]:
    """Given explicit file hints, expand to include files that import/reference them.

    For each file in the hint, grep for its module name to find dependents.
    This catches the "I'm changing base.py but 10 files import it" case.
    """
    touched = set(files_hint)

    for f in files_hint:
        # Derive module name from path (e.g. adapters/base.py -> "base" or "from .base")
        p = Path(f)
        if p.suffix == ".py":
            mod_name = p.stem
            # Find files that import this module
            importers = _grep_files(
                rf"(from \. import {mod_name}|from \.{mod_name}|import {mod_name}|from \.\.\.{mod_name})",
            )
            touched.update(importers)
        elif f.endswith(".json"):
            # Find files that reference this JSON path
            ref = p.name
            refs = _grep_files(re.escape(ref))
            touched.update(refs)

    return touched