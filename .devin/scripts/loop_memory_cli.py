#!/usr/bin/env python3
"""loop_memory_cli.py — CLI entry point for loop_memory_sync."""
from __future__ import annotations

import argparse
import sys

try:
    import ahd_session
except ImportError:  # pragma: no cover
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session

from loop_memory_fallback import _safe_regenerate  # type: ignore[import-not-found]


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate loop_state.md registry")
    ap.add_argument("--session", default="", help="Session ID to update")
    ap.add_argument("--status", default="", help="Status to set (completed, crashed, in_progress)")
    args = ap.parse_args()

    root = ahd_session.get_repo_root()
    # U06: Use safe wrapper with fallback
    try:
        _safe_regenerate(root, args.session, args.status)
    except Exception as e:
        print(f"[loop_memory_sync] ERROR: primary write failed, fallback written. Detail: {e}", file=sys.stderr)
        return 1
    return 0