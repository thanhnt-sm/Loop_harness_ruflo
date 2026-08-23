#!/usr/bin/env python3
"""blackboard.py — Shared blackboard for multi-agent coordination (entry point).

Regions (conflict resolution):
  hypotheses   — append-only
  evidence     — single-writer
  decisions    — CRDT union
  state        — versioned writes
  findings     — append-only
  metrics      — last-write-wins

CLI:
  python blackboard.py --read <region> <key>
  python blackboard.py --write <region> <key> <value.json>
  python blackboard.py --list <region>
  python blackboard.py --regions

Storage: .devin/blackboard/<region>.json, .devin/blackboard/_write_log.jsonl
Exit: 0=success, 1=conflict/error
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import re

# ---------------------------------------------------------------------------
# Path utilities (defined here so test monkeypatch works)
# ---------------------------------------------------------------------------

# Pattern allowlist cho region: chỉ chữ số, chữ cái, dấu chấm, gạch dưới, gạch ngang.
_REGION_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")


def _sanitize_region(region: str) -> str:
    """Làm sạch region để chống path traversal qua tên file.

    Bước 1: Thay path separator ('/', '\\') bằng '_'.
    Bước 2: Loại bỏ ký tự ngoài allowlist.
    Bước 3: Sụp đổ nhiều dấu '_' liên tiếp và cắt đầu/cuối.
    Bước 4: Nếu chứa '..' hoặc không khớp pattern -> 'invalid'.
    """
    if not region:
        return "invalid"
    safe = region.replace("/", "_").replace("\\", "_")
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    safe = re.sub(r"_+", "_", safe).strip("_-. ")
    if not safe or ".." in safe or not _REGION_PATTERN.match(safe):
        return "invalid"
    return safe


def _repo_root() -> Path:
    """Tìm thư mục gốc repo (chứa thư mục .devin)."""
    here = Path(__file__).resolve().parent  # .../.devin/scripts
    return here.parent.parent               # repo root


def _bb_dir() -> Path:
    """Trả về thư mục .devin/blackboard, tự tạo nếu thiếu."""
    d = _repo_root() / ".devin" / "blackboard"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _region_file(region: str) -> Path:
    """Trả về đường dẫn file JSON cho region.

    Pentest fix: sanitize region trước khi join path; đảm bảo file nằm trong _bb_dir().
    """
    safe = _sanitize_region(region)
    bb = _bb_dir()
    f = bb / f"{safe}.json"
    try:
        f.resolve().relative_to(bb.resolve())
    except ValueError:
        return bb / "invalid.json"
    return f


def _write_log_file() -> Path:
    """Trả về đường dẫn file nhật ký ghi (write log)."""
    return _bb_dir() / "_write_log.jsonl"


def _lock_dir() -> Path:
    """Thư mục chứa file-lock của từng region + write log."""
    d = _bb_dir() / ".locks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _region_lock_path(region: str) -> Path:
    """Trả về đường dẫn file-lock cho một region."""
    safe = _sanitize_region(region)
    d = _lock_dir()
    f = d / f"{safe}.lock"
    try:
        f.resolve().relative_to(d.resolve())
    except ValueError:
        return d / "invalid.lock"
    return f


def _write_log_lock_path() -> Path:
    """Trả về đường dẫn file-lock cho write log."""
    return _lock_dir() / "_write_log.lock"


# ---------------------------------------------------------------------------
# REGION_RULES (shared with constants module)
# ---------------------------------------------------------------------------

REGION_RULES: dict[str, str] = {
    "hypotheses": "append_only",
    "evidence": "single_writer",
    "decisions": "crdt_union",
    "state": "versioned",
    "findings": "append_only",
    "metrics": "last_write_wins",
}

# Type cho resolver functions
ResolverFunc = Callable[[str, str, str, dict, Any], tuple[bool, str, dict]]

# RESOLVERS will be populated by core module after it defines resolver functions
RESOLVERS: dict[str, ResolverFunc] = {}


# ---------------------------------------------------------------------------
# Re-export public API from core module
# ---------------------------------------------------------------------------

from blackboard_core import (
    read_value,
    write_value,
    list_keys,
    list_regions,
    LockAcquireError,
    _load_region,
    _save_region,
    _log_write,
    _resolve_append_only,
    _resolve_single_writer,
    _resolve_crdt_union,
    _resolve_versioned,
    _resolve_last_write_wins,
    _acquire_lock,
    _release_lock,
)

# Re-export CLI main and _read_value_file
from blackboard_cli import main, _read_value_file

# Re-export constants
from blackboard_constants import RESOLVERS as _CONST_RESOLVERS

# Sync RESOLVERS between modules
RESOLVERS.update(_CONST_RESOLVERS)
_CONST_RESOLVERS.update(RESOLVERS)

if __name__ == "__main__":
    sys.exit(main())