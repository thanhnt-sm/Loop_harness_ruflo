#!/usr/bin/env python3
"""idempotency.py — Idempotency ledger cho durable execution.

Mỗi thao tác được đánh key duy nhất theo run_id. Nếu key đã tồn tại,
register trả kết quả đã cache thay vì chạy lại op.

Đường dẫn ledger mặc định:
    .devin/idempotency/<run_id>.ledger.jsonl
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

_LEDGER_DIR = "idempotency"


def _repo_root() -> Path:
    """Trả về repo root, ưu tiên ahd_session.get_repo_root()."""
    try:
        import ahd_session
        return ahd_session.get_repo_root()
    except Exception:
        p = Path(__file__).resolve().parent
        for parent in [p, *p.parents]:
            if (parent / ".devin").is_dir():
                return parent
        return p


def _config_root(root: Path) -> Path:
    """Trả về config root (thường là .devin)."""
    try:
        import ahd_session
        return ahd_session.get_config_root(root)
    except Exception:
        return root / ".devin"


def ledger_path(run_id: str, root: Path | None = None) -> Path:
    """Trả về đường dẫn ledger cho run_id."""
    if not run_id:
        run_id = "default"
    root = root or _repo_root()
    return _config_root(root) / _LEDGER_DIR / f"{run_id}.ledger.jsonl"


def _lock_path(ledger: Path) -> Path:
    """Đường dẫn lock cho ledger."""
    return ledger.with_suffix(".lock")


def _read_ledger(path: Path) -> dict[str, Any]:
    """Đọc toàn bộ ledger và trả dict key -> result."""
    results: dict[str, Any] = {}
    if not path.exists():
        return results
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            key = entry.get("key")
            if key is not None:
                results[key] = entry.get("result")
    except Exception:
        pass
    return results


def _run_id() -> str:
    """Lấy run_id từ env hoặc mặc định."""
    return os.environ.get("AHD_RUN_ID", "default")


def lookup(key: str, run_id: str | None = None) -> Optional[Any]:
    """Tìm kết quả đã cache cho key.

    Trả về None nếu key chưa tồn tại.
    """
    if run_id is None:
        run_id = _run_id()
    path = ledger_path(run_id)
    ledger = _read_ledger(path)
    return ledger.get(key)


def register(
    key: str,
    op: Callable[..., Any],
    *args,
    run_id: str | None = None,
    **kwargs,
) -> Any:
    """Đăng ký / thực thi một thao tác với idempotency.

    - Nếu key đã có trong ledger: trả kết quả đã cache.
    - Nếu chưa: chạy op(*args, **kwargs), ghi kết quả và trả về.
    """
    if not key:
        raise ValueError("idempotency key must not be empty")
    if run_id is None:
        run_id = _run_id()

    path = ledger_path(run_id)
    lock = _lock_path(path)

    # Lấy lock để tránh race condition
    try:
        import ahd_session
        handle = ahd_session._acquire_lock(lock, timeout=5.0)
    except Exception:
        handle = None

    try:
        ledger = _read_ledger(path)
        if key in ledger:
            return ledger[key]

        result = op(*args, **kwargs)

        # Ghi entry mới
        entry = {
            "key": key,
            "result": result,
            "timestamp": time.time(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            try:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            except TypeError:
                # Nếu result không serializable, lưu string representation
                entry["result"] = str(result)
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return result
    finally:
        if handle is not None:
            ahd_session._release_lock(handle)
