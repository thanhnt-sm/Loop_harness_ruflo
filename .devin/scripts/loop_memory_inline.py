#!/usr/bin/env python3
"""loop_memory_inline.py — U13 Inline call interface.

This module provides run_inline for importing and calling directly
without subprocess overhead.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

try:
    import ahd_session
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session

# Import _safe_regenerate from fallback module
from loop_memory_fallback import _safe_regenerate  # type: ignore[import-not-found]

_inline_lock = threading.Lock()


def run_inline(root: Path, session_id: str = "", status: str = "") -> tuple[bool, str]:
    """U13: Inline call interface — import and call directly, no subprocess.

    Returns (success, error_message). Use this instead of:
        subprocess.run(["python", ".devin/scripts/loop_memory_sync.py", ...])

    Example:
        from loop_memory_sync import run_inline
        ok, err = run_inline(root, session_id="s-123", status="in_progress")
        if not ok:
            # fallback was written, check loop_state_fallback.md
            print(f"Failed: {err}")
    """
    with _inline_lock:
        try:
            _safe_regenerate(root, session_id, status)
            return True, ""
        except Exception as e:
            error_msg = f"{e}"
            print(f"[loop_memory_sync] ERROR: {error_msg}", file=sys.stderr)
            return False, error_msg