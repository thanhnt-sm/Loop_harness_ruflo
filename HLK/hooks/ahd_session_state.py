#!/usr/bin/env python3
"""Locked JSON/text read/write utilities for ahd_session.

Provides:
- _locked_json_read: Read JSON file with lock
- _locked_json_write: Write JSON file with lock
- _locked_json_update: Read, update, write JSON under same lock
- _locked_text_write: Write text file with repo-level lock
- read_session_state: Read session_state JSON with per-session lock
- write_session_state: Write session_state JSON with per-session lock
- update_session_state: Merge fields into session_state
- write_context_flags: Write per-session context_flags.json
- read_context_flags: Read per-session context_flags.json
- append_jsonl: Append JSON line to jsonl file with lock
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ahd_session_id import get_repo_root
from ahd_session_lock import _acquire_lock, _release_lock, _safe_mkdir
from ahd_session_paths import _get_lock_path, _get_session_lock_path, get_context_flags_path, get_session_state_path


def _locked_json_read(path: Path, default: Any = None, session_id: str = "") -> Any:
    """Read a JSON file with a lock.

    If session_id is provided, uses per-session lock (no contention
    with other sessions). If not, uses repo-level lock (for registry).
    """
    root = get_repo_root(path.parent if path.is_absolute() else None)
    lock_path = _get_session_lock_path(root, session_id) if session_id else _get_lock_path(root)
    lock = _acquire_lock(lock_path)
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return default
    except (json.JSONDecodeError, OSError):
        return default
    finally:
        _release_lock(lock)


def _locked_json_write(path: Path, data: Any, session_id: str = "") -> None:
    """Write a JSON file with a lock.

    If session_id is provided, uses per-session lock. If not, repo-level.
    """
    root = get_repo_root(path.parent if path.is_absolute() else None)
    lock_path = _get_session_lock_path(root, session_id) if session_id else _get_lock_path(root)
    lock = _acquire_lock(lock_path)
    try:
        _safe_mkdir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        _release_lock(lock)


def _locked_json_update(path: Path, update_fn, default: Any = None, session_id: str = "") -> Any:
    """Read a JSON file, apply update_fn under the same lock, and write it back.

    If session_id is provided, uses per-session lock. If not, repo-level.
    """
    root = get_repo_root(path.parent if path.is_absolute() else None)
    lock_path = _get_session_lock_path(root, session_id) if session_id else _get_lock_path(root)
    lock = _acquire_lock(lock_path)
    try:
        data = default
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        data = update_fn(data)
        _safe_mkdir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return data
    finally:
        _release_lock(lock)


def _locked_text_write(path: Path, text: str) -> None:
    """Write a text file with a repo-level lock."""
    root = get_repo_root(path.parent if path.is_absolute() else None)
    lock = _acquire_lock(_get_lock_path(root))
    try:
        _safe_mkdir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        _release_lock(lock)


def _check_memory_cap(path: Path, cap_name: str, root: Optional[Path] = None) -> None:
    """Warn when file size approaches or exceeds configured cap.

    Non-blocking — only logs warning to stderr.
    """
    try:
        if not path.exists():
            return

        # Load memory config
        repo_root = root or get_repo_root()
        config_path = repo_root / ".devin" / "memory_config.json"
        if not config_path.exists():
            return

        config = json.loads(config_path.read_text(encoding="utf-8"))
        cap_entry = config.get("caps", {}).get(cap_name)
        if not cap_entry:
            return

        file_size = path.stat().st_size
        default_bytes = cap_entry.get("default_bytes", 4096)
        max_bytes = cap_entry.get("max_bytes", 65536)
        warn_pct = cap_entry.get("warn_threshold_pct", 80)

        warn_threshold = int(default_bytes * warn_pct / 100)

        if file_size > max_bytes:
            print(
                f"[U34 Memory] WARNING: {path.name} exceeds max cap "
                f"({file_size} > {max_bytes} bytes). Consider truncating oldest entries.",
                file=sys.stderr,
            )
        elif file_size > warn_threshold:
            pct = int(file_size * 100 / default_bytes)
            print(
                f"[U34 Memory] WARNING: {path.name} approaching cap "
                f"({file_size}/{default_bytes} bytes, {pct}%).",
                file=sys.stderr,
            )
    except (OSError, ValueError):
        pass  # non-blocking


def read_session_state(session_id: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """Read session_state JSON with per-session lock."""
    path = get_session_state_path(session_id, root)
    return _locked_json_read(path, default={}, session_id=session_id)


def write_session_state(session_id: str, data: Dict[str, Any], root: Optional[Path] = None, merge: bool = True) -> None:
    """Write session_state JSON with per-session lock.

    If merge=True, merge with existing data under the same lock. This lets
    `post_tool_use` update `last_heartbeat` without overwriting `current_subtask`
    set by `loop-memory`, and prevents lost updates under concurrent writes.
    """
    path = get_session_state_path(session_id, root)
    if merge:
        _locked_json_update(path, lambda existing: {**(existing or {}), **data}, default={}, session_id=session_id)
    else:
        _locked_json_write(path, data, session_id=session_id)

    # Check memory cap and warn
    _check_memory_cap(path, "session_state", root)


def update_session_state(session_id: str, fields: Dict[str, Any], root: Optional[Path] = None) -> None:
    """Merge fields into session_state without overwriting unrelated fields."""
    write_session_state(session_id, fields, root, merge=True)


def write_context_flags(session_id: str, data: Dict[str, Any], root: Optional[Path] = None) -> None:
    """Write per-session context_flags.json with per-session lock."""
    path = get_context_flags_path(session_id, root)
    _locked_json_update(path, lambda existing: {**(existing or {}), **data}, default={}, session_id=session_id)


def read_context_flags(session_id: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """Read per-session context_flags.json with per-session lock."""
    path = get_context_flags_path(session_id, root)
    return _locked_json_read(path, default={}, session_id=session_id)


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append a JSON line to a jsonl file with lock."""
    root = get_repo_root(path.parent if path.is_absolute() else None)
    lock = _acquire_lock(_get_lock_path(root))
    try:
        _safe_mkdir(path.parent)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        _release_lock(lock)