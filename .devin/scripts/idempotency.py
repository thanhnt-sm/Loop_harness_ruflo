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
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

_LEDGER_DIR = "idempotency"

_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class IdempotencyLockError(RuntimeError):
    """Lock không thể được giữ — execution phải BLOCK (fail-closed, CVE-2026-AHD-003).

    Khác RuntimeError thường: caller (dag_executor) không được retry/đánh dấu
    failed rồi tiếp tục — phải dừng execution ngay.
    """


def _sanitize_run_id(run_id: str) -> str:
    """Làm sạch run_id theo allowlist, chống path traversal (../../HLK/evil).

    Thay path separator bằng _, chỉ giữ [a-zA-Z0-9_-], giới hạn 64 ký tự.
    """
    if not run_id:
        return "default"
    rid = run_id.replace("/", "_").replace("\\", "_")
    rid = re.sub(r"[^a-zA-Z0-9_-]", "_", rid)
    rid = re.sub(r"_+", "_", rid)
    rid = rid.strip("_-.")
    if not rid:
        return "default"
    rid = rid[:64]
    if not _RUN_ID_PATTERN.match(rid):
        return "default"
    return rid


def _repo_root() -> Path:
    """Trả về repo root, ưu tiên ahd_session.get_repo_root()."""
    try:
        import ahd_session
        return ahd_session.get_repo_root()
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
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
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
        return root / ".devin"


def ledger_path(run_id: str, root: Path | None = None) -> Path:
    """Trả về đường dẫn ledger cho run_id."""
    if not run_id:
        run_id = "default"
    # Pentest fix: sanitize run_id để chống path traversal (../../HLK/evil).
    run_id = _sanitize_run_id(run_id)
    root = root or _repo_root()
    return _config_root(root) / _LEDGER_DIR / f"{run_id}.ledger.jsonl"


def _lock_path(ledger: Path) -> Path:
    """Đường dẫn lock cho ledger."""
    return ledger.with_suffix(".lock")


def _acquire_redis_lock(lock: Path) -> Any:
    """CVE-2026-AHD-003: Distributed lock qua Redis (optional).

    Kích hoạt khi env `AHD_REDIS_LOCK` được cấu hình (vd redis://localhost:6379/0).
    Trả về handle có `.release()` nếu thành công, None nếu không dùng Redis.
    """
    redis_url = os.environ.get("AHD_REDIS_LOCK", "")
    if not redis_url:
        return None
    try:
        import redis  # type: ignore  # optional extra
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        lock_name = f"ahd:idem:{lock.name}"
        acquired = r.set(lock_name, "1", nx=True, ex=30)
        if not acquired:
            raise RuntimeError(f"redis lock held: {lock_name}")

        class _RedisLockHandle:
            def __init__(self, client, name):
                self._client = client
                self._name = name

            def release(self):
                try:
                    self._client.delete(self._name)
                except Exception:
                    pass

        return _RedisLockHandle(r, lock_name)
    except ImportError:
        print("[idempotency] AHD_REDIS_LOCK set but redis client not installed; skipping", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[idempotency] redis lock unavailable, fallback file lock: {e}", file=sys.stderr)
        return None


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
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            key = entry.get("key")
            if key is not None:
                results[key] = entry.get("result")
    except (OSError, UnicodeDecodeError):
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

    # Lấy lock để tránh race condition (CVE-2026-AHD-003 fix).
    # Fail CLOSED: nếu không lấy được lock (dù bằng ahd_session hay filelock)
    # → raise RuntimeError, KHÔNG BAO GIỜ chạy unlocked. filelock là hard
    # dependency (xem pyproject.toml [project] dependencies).
    # Distributed lock (Redis) được hỗ trợ qua extra `redis` nếu AHD_REDIS_LOCK
    # được cấu hình (host dạng redis://...).
    handle = None
    lock_acquired = False

    redis_lock = _acquire_redis_lock(lock)
    if redis_lock is not None:
        handle, lock_acquired = redis_lock, True
    else:
        try:
            import ahd_session
            handle = ahd_session._acquire_lock(lock, timeout=5.0)
            lock_acquired = handle is not None
        except Exception as e:
            print(f"[idempotency] ahd_session lock unavailable, try filelock fallback: {e}", file=sys.stderr)
            handle = None

    if not lock_acquired:
        # Fallback bắt buộc: filelock (hard dependency, KHÔNG có lối thoát unlocked).
        try:
            from filelock import FileLock, Timeout  # type: ignore
            fl = FileLock(str(lock))
            fl.acquire(timeout=5.0)
            handle = fl
            lock_acquired = True
        except ImportError:
            # filelock không có -> không thể đảm bảo an toàn, raise (fail CLOSED).
            raise IdempotencyLockError(
                "idempotency.register: filelock not installed (hard dependency) "
                "and no lock could be acquired; refusing to run unlocked to "
                "prevent duplicate execution (CVE-2026-AHD-003)"
            )
        except (TimeoutError, OSError, RuntimeError) as exc:
            raise IdempotencyLockError(
                f"idempotency.register: không lấy được lock cho run_id={run_id}: {exc}"
            ) from exc

    if not lock_acquired:
        # Fail CLOSED: không proceed nếu lock vẫn chưa được giữ.
        raise IdempotencyLockError(
            f"idempotency.register: lock không được giữ cho run_id={run_id}; "
            "từ chối chạy unlocked (CVE-2026-AHD-003 fail-closed)"
        )

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
            try:
                import ahd_session
                ahd_session._release_lock(handle)
            except Exception as e:
                # Pentest fix: handle có thể là filelock FileLock trực tiếp
                # (fallback) — thử release() trực tiếp.
                print(f"[idempotency] ahd_session release failed, try direct release: {e}", file=sys.stderr)
                try:
                    handle.release()
                except (AttributeError, RuntimeError, OSError):
                    pass
