#!/usr/bin/env python3
"""plan_dispatch_worktree.py — Worktree assignment and active session detection.

Module for assigning worktree names to subtasks and reading active
session metadata from the loop state registry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import ahd_session
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session


def _get_active_sessions(root: Path) -> list[dict]:
    """Read loop_state.md registry and return active session metadata."""
    sessions = []
    registry = ahd_session.get_config_root(root) / "loop_state.md"
    if not registry.exists():
        return sessions
    # Very tolerant: look for "| <sid> | ... | active |" or "| in_progress |"
    in_active = False
    for line in registry.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Active sessions"):
            in_active = True
            continue
        if in_active and line.startswith("## "):
            break
        if in_active and line.startswith("|") and "session_id" not in line:
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]
            if not parts:
                continue
            sid = parts[0]
            if sid in ("session_id", "---"):
                continue
            ss = ahd_session.get_config_root(root) / "session_state" / f"{sid}.json"
            if ss.exists():
                try:
                    data = json.loads(ss.read_text(encoding="utf-8"))
                    sessions.append(data)
                except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError):
                    pass
    return sessions


def _assign_worktrees(subtasks: list[dict], allocation: dict, session_id: str = "") -> dict:
    """Assign a worker id (builder-a, builder-b, ...). worktree.py will prefix with session_id."""
    worktree_map = {}
    wt_idx = 0
    for st in subtasks:
        wt_name = f"builder-{chr(ord('a') + wt_idx)}"
        worktree_map[st["id"]] = wt_name
        wt_idx += 1
    return worktree_map