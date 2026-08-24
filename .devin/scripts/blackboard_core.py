#!/usr/bin/env python3
"""blackboard_core.py — Core blackboard logic.

load/save region, 5 resolvers, read/write/list operations.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# Import constants (REGION_RULES, RESOLVERS, _sanitize_region, _REGION_PATTERN)
from blackboard_constants import (
    REGION_RULES,
    RESOLVERS,
    _sanitize_region,
    _REGION_PATTERN,
)

# Add hooks to sys.path for file-lock from ahd_session.py
from pathlib import Path
_Here = Path(__file__).resolve().parent
sys.path.insert(0, str(_Here.parent / "hooks"))
from ahd_session import _acquire_lock, _release_lock, LockAcquireError  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Lazy imports for path utilities (to avoid circular import with blackboard.py)
# ---------------------------------------------------------------------------

def _get_path_utils():
    """Lazy import path utilities from main blackboard module."""
    import blackboard
    return {
        "_repo_root": blackboard._repo_root,
        "_bb_dir": blackboard._bb_dir,
        "_region_file": blackboard._region_file,
        "_write_log_file": blackboard._write_log_file,
        "_lock_dir": blackboard._lock_dir,
        "_region_lock_path": blackboard._region_lock_path,
        "_write_log_lock_path": blackboard._write_log_lock_path,
    }


# No caching - fetch fresh each time to respect monkeypatches in tests
def _path_utils():
    return _get_path_utils()


# ---------------------------------------------------------------------------
# Hàm tiện ích
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Trả về timestamp ISO 8601 hiện tại (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def _load_region(region: str) -> dict:
    """Tải nội dung region từ file JSON.

    Bước 1: Nếu file không tồn tại → trả dict rỗng.
    Bước 2: Đọc + parse JSON. Nếu lỗi → trả dict rỗng.
    Bước 3: Trả về dict dữ liệu region.
    """
    f = _path_utils()["_region_file"](region)
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[blackboard] Lỗi đọc region {region}: {exc}", file=sys.stderr)
        return {}


def _save_region(region: str, data: dict) -> bool:
    """Lưu nội dung region vào file JSON."""
    f = _path_utils()["_region_file"](region)
    try:
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return True
    except OSError as exc:
        print(f"[blackboard] Lỗi ghi region {region}: {exc}", file=sys.stderr)
        return False


def _log_write(region: str, key: str, agent: str,
               old_value: Any, new_value: Any, conflict: bool,
               resolution: str) -> None:
    """Ghi một mục vào nhật ký ghi (write log).

    Mỗi mục: timestamp, agent, region, key, old_value, new_value,
    conflict (có xung đột không), resolution (cách giải quyết).
    """
    entry = {
        "id": str(uuid4()),
        "timestamp": _now_iso(),
        "agent": agent,
        "region": region,
        "key": key,
        "old_value": old_value,
        "new_value": new_value,
        "conflict": conflict,
        "resolution": resolution,
    }
    f = _path_utils()["_write_log_file"]()
    lock = None
    try:
        lock = _acquire_lock(_path_utils()["_write_log_lock_path"]())
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[blackboard] Lỗi ghi write log: {exc}", file=sys.stderr)
    finally:
        _release_lock(lock)


# ---------------------------------------------------------------------------
# Các quy tắc giải quyết xung đột (Resolvers)
# ---------------------------------------------------------------------------

def _resolve_append_only(region: str, key: str, agent: str,
                         data: dict, new_value: Any) -> tuple[bool, str, dict]:
    """Quy tắc append-only: chỉ thêm key mới, không ghi đè key đã có.

    Bước 1: Nếu key đã tồn tại → xung đột, từ chối ghi.
    Bước 2: Nếu key mới → thêm vào, không xung đột.
    """
    if key in data:
        _log_write(region, key, agent, data[key], new_value,
                   conflict=True, resolution="rejected_append_only")
        return False, f"Xung đột append-only: key '{key}' đã tồn tại trong region '{region}'", data
    data[key] = new_value
    _log_write(region, key, agent, None, new_value,
               conflict=False, resolution="appended")
    return True, "Đã thêm mới (append-only)", data


def _resolve_single_writer(region: str, key: str, agent: str,
                           data: dict, new_value: Any) -> tuple[bool, str, dict]:
    """Quy tắc single-writer: mỗi agent chỉ ghi key của mình.

    Bước 1: Nếu key mới → ghi, ghi nhận agent là chủ sở hữu.
    Bước 2: Nếu key đã có và cùng agent → ghi đè (agent là chủ sở hữu).
    Bước 3: Nếu key đã có nhưng khác agent → xung đột, từ chối.
    """
    existing = data.get(key)
    if existing is None:
        # Key mới → ghi kèm metadata chủ sở hữu.
        data[key] = {"_owner": agent, "value": new_value}
        _log_write(region, key, agent, None, new_value,
                   conflict=False, resolution="created_single_writer")
        return True, f"Đã tạo key '{key}' (chủ sở hữu: {agent})", data
    # Key đã có → kiểm tra chủ sở hữu.
    if isinstance(existing, dict) and "_owner" in existing:
        owner = existing["_owner"]
        if owner == agent:
            old_val = existing.get("value")
            existing["value"] = new_value
            _log_write(region, key, agent, old_val, new_value,
                       conflict=False, resolution="updated_single_writer")
            return True, f"Đã cập nhật key '{key}' (chủ sở hữu: {agent})", data
        _log_write(region, key, agent, existing.get("value"), new_value,
                   conflict=True, resolution="rejected_single_writer")
        return False, (
            f"Xung đột single-writer: key '{key}' thuộc agent '{owner}', "
            f"agent '{agent}' không được ghi đè"
        ), data
    # Dữ liệu cũ không có _owner → coi như xung đột.
    _log_write(region, key, agent, existing, new_value,
               conflict=True, resolution="rejected_no_owner")
    return False, f"Xung đột: key '{key}' không có chủ sở hữu rõ ràng", data


def _resolve_crdt_union(region: str, key: str, agent: str,
                        data: dict, new_value: Any) -> tuple[bool, str, dict]:
    """Quy tắc CRDT union: gộp tập hợp, last-write-wins cho vô hướng.

    Bước 1: Nếu key mới → ghi trực tiếp.
    Bước 2: Nếu giá trị cũ + mới đều là list → gộp (union) không trùng.
    Bước 3: Nếu giá trị cũ + mới đều là dict → gộp key-value (mới đè cũ).
    Bước 4: Nếu là vô hướng (str, int, float, bool) → last-write-wins.
    """
    if key not in data:
        data[key] = new_value
        _log_write(region, key, agent, None, new_value,
                   conflict=False, resolution="created_crdt")
        return True, f"Đã tạo key '{key}' (CRDT)", data
    old_value = data[key]
    # Gộp list (union giữ thứ tự, bỏ trùng).
    if isinstance(old_value, list) and isinstance(new_value, list):
        merged = list(old_value)
        for item in new_value:
            if item not in merged:
                merged.append(item)
        data[key] = merged
        _log_write(region, key, agent, old_value, merged,
                   conflict=False, resolution="merged_list_union")
        return True, f"Đã gộp list (union) cho key '{key}'", data
    # Gộp dict.
    if isinstance(old_value, dict) and isinstance(new_value, dict):
        merged = dict(old_value)
        merged.update(new_value)
        data[key] = merged
        _log_write(region, key, agent, old_value, merged,
                   conflict=False, resolution="merged_dict_union")
        return True, f"Đã gộp dict (union) cho key '{key}'", data
    # Vô hướng → last-write-wins.
    data[key] = new_value
    _log_write(region, key, agent, old_value, new_value,
               conflict=(old_value != new_value),
               resolution="last_write_wins")
    return True, f"Đã ghi đè (last-write-wins) cho key '{key}'", data


def _resolve_versioned(region: str, key: str, agent: str,
                       data: dict, new_value: Any) -> tuple[bool, str, dict]:
    """Quy tắc versioned: mỗi lần ghi tăng version, giữ lịch sử đầy đủ.

    Cấu trúc lưu: {key: {"current": value, "versions": [{version, value, timestamp, agent}]}}
    """
    if key not in data:
        data[key] = {
            "current": new_value,
            "versions": [
                {"version": 1, "value": new_value,
                 "timestamp": _now_iso(), "agent": agent}
            ],
        }
        _log_write(region, key, agent, None, new_value,
                   conflict=False, resolution="created_versioned")
        return True, f"Đã tạo key '{key}' (version 1)", data
    entry = data[key]
    if not isinstance(entry, dict) or "versions" not in entry:
        # Dữ liệu cũ không đúng cấu trúc → khởi tạo lại.
        entry = {"current": new_value, "versions": []}
        data[key] = entry
    next_version = len(entry["versions"]) + 1
    entry["versions"].append({
        "version": next_version,
        "value": new_value,
        "timestamp": _now_iso(),
        "agent": agent,
    })
    old_value = entry.get("current")
    entry["current"] = new_value
    _log_write(region, key, agent, old_value, new_value,
               conflict=False, resolution=f"versioned_v{next_version}")
    return True, f"Đã ghi version {next_version} cho key '{key}'", data


def _resolve_last_write_wins(region: str, key: str, agent: str,
                             data: dict, new_value: Any) -> tuple[bool, str, dict]:
    """Quy tắc last-write-wins: ghi đè luôn, giữ giá trị mới nhất."""
    old_value = data.get(key)
    data[key] = new_value
    _log_write(region, key, agent, old_value, new_value,
               conflict=(old_value is not None and old_value != new_value),
               resolution="last_write_wins")
    return True, f"Đã ghi (last-write-wins) cho key '{key}'", data


# ---------------------------------------------------------------------------
# Khởi tạo RESOLVERS mapping (sau khi các hàm resolver đã được định nghĩa)
# ---------------------------------------------------------------------------

RESOLVERS.update({
    "append_only": _resolve_append_only,
    "single_writer": _resolve_single_writer,
    "crdt_union": _resolve_crdt_union,
    "versioned": _resolve_versioned,
    "last_write_wins": _resolve_last_write_wins,
})


# ---------------------------------------------------------------------------
# Các thao tác chính (Public API)
# ---------------------------------------------------------------------------

def read_value(region: str, key: str) -> dict:
    """Đọc giá trị của key trong region, có file-lock để tránh đọc giữa chừng."""
    lock = None
    try:
        lock = _acquire_lock(_path_utils()["_region_lock_path"](region), timeout=5.0)
        data = _load_region(region)
        if key not in data:
            return {"region": region, "key": key, "value": None, "exists": False}
        value = data[key]
        # Với single_writer, trả value bên trong wrapper.
        if isinstance(value, dict) and "_owner" in value:
            value = value.get("value")
        # Với versioned, trả current.
        if isinstance(value, dict) and "current" in value and "versions" in value:
            value = value.get("current")
        return {"region": region, "key": key, "value": value, "exists": True}
    except LockAcquireError as exc:
        print(f"[blackboard] Không lấy được khóa region {region}: {exc}", file=sys.stderr)
        return {"region": region, "key": key, "value": None, "exists": False, "error": str(exc)}
    finally:
        _release_lock(lock)


def write_value(region: str, key: str, value: Any, agent: str = "unknown") -> dict:
    """Ghi giá trị vào region với quy tắc giải quyết xung đột + file-lock."""
    lock = None
    try:
        lock = _acquire_lock(_path_utils()["_region_lock_path"](region), timeout=5.0)
        rule = REGION_RULES.get(region, "last_write_wins")
        resolver = RESOLVERS.get(rule, _resolve_last_write_wins)
        data = _load_region(region)
        ok, reason, data = resolver(region, key, agent, data, value)
        if ok:
            saved = _save_region(region, data)
            if not saved:
                return {"written": False, "region": region, "key": key, "rule": rule, "reason": "Lỗi lưu file region"}
        return {
            "written": ok,
            "region": region,
            "key": key,
            "rule": rule,
            "reason": reason,
        }
    except LockAcquireError as exc:
        print(f"[blackboard] Không lấy được khóa region {region}: {exc}", file=sys.stderr)
        return {"written": False, "region": region, "key": key, "reason": f"Không lấy được khóa: {exc}"}
    finally:
        _release_lock(lock)


def list_keys(region: str) -> dict:
    """Liệt kê tất cả key trong region (có khóa)."""
    lock = None
    try:
        lock = _acquire_lock(_path_utils()["_region_lock_path"](region), timeout=5.0)
        data = _load_region(region)
        keys = list(data.keys())
        return {"region": region, "keys": keys, "count": len(keys)}
    except LockAcquireError as exc:
        print(f"[blackboard] Không lấy được khóa region {region}: {exc}", file=sys.stderr)
        return {"region": region, "keys": [], "count": 0, "error": str(exc)}
    finally:
        _release_lock(lock)


def list_regions() -> dict:
    """Liệt kê tất cả region đã định nghĩa + region đã có file lưu trữ."""
    defined = list(REGION_RULES.keys())
    # Thêm region đã có file nhưng không trong danh sách.
    existing = set()
    bb = _path_utils()["_bb_dir"]()
    if bb.exists():
        for f in bb.glob("*.json"):
            if f.stem != "_write_log":
                existing.add(f.stem)
    extra = sorted(existing - set(defined))
    rules = {r: REGION_RULES.get(r, "last_write_wins")
             for r in defined + extra}
    return {
        "defined_regions": defined,
        "additional_regions": extra,
        "rules": rules,
        "total": len(defined) + len(extra),
    }


# Export public API
__all__ = [
    "read_value",
    "write_value",
    "list_keys",
    "list_regions",
    "_load_region",
    "_save_region",
    "_log_write",
    "_resolve_append_only",
    "_resolve_single_writer",
    "_resolve_crdt_union",
    "_resolve_versioned",
    "_resolve_last_write_wins",
    "LockAcquireError",
    "_acquire_lock",
    "_release_lock",
]