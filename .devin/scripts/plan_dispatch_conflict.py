#!/usr/bin/env python3
"""plan_dispatch_conflict.py — Conflict detection and ownership allocation.

Module for detecting file ownership conflicts between subtasks and
allocating files to workers as disjoint sets.
"""

from __future__ import annotations

from collections import defaultdict


def _detect_conflicts(subtasks: list[dict]) -> list[dict]:
    """Detect files touched by multiple subtasks."""
    file_to_subtasks: dict[str, list[str]] = defaultdict(list)

    for st in subtasks:
        for f in st.get("_expanded_files", []):
            file_to_subtasks[f].append(st["id"])

    conflicts = []
    for f, sts in file_to_subtasks.items():
        if len(sts) > 1:
            conflicts.append({
                "file": f,
                "subtasks": sts,
                "resolution": "serialize",
                "suggested_order": sts,  # first-listed goes first
            })

    return conflicts


def _allocate_ownership(subtasks: list[dict], conflicts: list[dict]) -> dict:
    """Allocate files to workers as disjoint sets.

    Files in conflict -> assigned to the first subtask that touches them (serialized).
    Other subtasks must wait for that subtask to finish before touching the file.
    Files not in conflict -> owned by the single subtask that touches them.
    """
    conflict_files = {c["file"] for c in conflicts}
    conflict_owner = {}
    for c in conflicts:
        # First subtask in suggested_order owns the file
        conflict_owner[c["file"]] = c["suggested_order"][0]

    allocation = {}
    for st in subtasks:
        owned = []
        shared = []
        for f in st.get("_expanded_files", []):
            if f in conflict_files:
                if conflict_owner[f] == st["id"]:
                    owned.append(f)  # This subtask owns the conflicting file
                else:
                    shared.append(f)  # Must wait for the owner
            else:
                owned.append(f)
        allocation[st["id"]] = {
            "owned_files": sorted(set(owned)),
            "shared_files": sorted(set(shared)),
        }

    return allocation


def _active_session_conflicts(subtasks: list[dict], active_sessions: list[dict]) -> list[dict]:
    """Detect new subtasks that overlap with active session owned_files/affected_files.

    If `affected_files` is not already recorded in session_state, derive it by
    expanding the session's `owned_files` with `_expand_file_hints`.
    """
    try:
        from .plan_dispatch_grep import _expand_file_hints
    except ImportError:  # pragma: no cover - fallback for direct script execution
        from plan_dispatch_grep import _expand_file_hints

    conflicts = []
    for s in active_sessions:
        s.setdefault("_expanded_affected", set(s.get("affected_files", [])))
        if not s["_expanded_affected"] and s.get("owned_files"):
            s["_expanded_affected"] = _expand_file_hints(list(s.get("owned_files", [])))
    for st in subtasks:
        for s in active_sessions:
            owned = set(s.get("owned_files", []))
            affected = set(s.get("_expanded_affected", []))
            touched = set(st.get("_expanded_files", []))
            overlap = (owned | affected) & touched
            if overlap:
                conflicts.append({
                    "file": list(overlap)[0],
                    "subtasks": [st["id"], s.get("session_id", "")],
                    "resolution": "wait_for_session",
                    "suggested_order": [s.get("session_id", ""), st["id"]],
                    "depends_on_session": s.get("session_id", ""),
                    "reason": f"active session {s.get('session_id', '')} owns/affects {overlap}",
                })
    return conflicts