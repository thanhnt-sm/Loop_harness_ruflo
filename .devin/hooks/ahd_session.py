#!/usr/bin/env python3
"""Shared session helpers for Agent Harness Deploy runtime hooks and scripts.

Provides:
- session_id resolution with fallback chain
- filesystem-safe slugification
- repo root discovery
- locked read/write of session_state JSON
- locked file read/write utilities
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class LockAcquireError(Exception):
    """Ném khi không thể lấy được file lock trong thời gian chờ."""


def _safe_mkdir(path: Path, parents: bool = True) -> None:
    """Tạo thư mục an toàn — handle FileExistsError trên Linux Python 3.13.

    Python 3.13 trên Linux có thể ném FileExistsError khi mkdir(exist_ok=True)
    nếu path là symlink hoặc có race condition giữa các process.
    """
    try:
        path.mkdir(parents=parents, exist_ok=True)
    except FileExistsError:
        # Dir đã tồn tại (có thể là symlink) — OK
        if not path.is_dir():
            raise


def get_config_root(root: Path) -> Path:
    """Determine the config root directory for runtime state files.

    When deployed, this file lives at ``<config_root>/scripts/ahd_session.py`` or
    ``<config_root>/hooks/ahd_session.py``. The config root is ``parent.parent``.
    In the source repo (``.devin/scripts/ahd_session.py``) the parent.parent
    is ``core/assets/runtime/`` which is NOT a config root, so we fall back to
    ``root / ".agents"``.

    This is what makes the harness work across tools with different config roots:
    Antigravity uses ``.devin/``, Claude Code uses ``.claude/``, Codex uses
    ``.codex/``, etc. The canonical text references ``.devin/`` as a placeholder;
    at runtime this function resolves it to the actual deployed config root.

    Logic:
    - If passed `root` is the real repo root (from get_repo_root()), do deployed config root detection
    - Otherwise, use the passed `root` directly (test isolation)
    - Priority for test roots: .devin > .agents > session_state/loop_state > fallback to .agents
    """
    # Get the real repo root for comparison
    try:
        real_repo_root = get_repo_root()
    except Exception:
        real_repo_root = None

    # Xác định config root dựa trên marker thư mục trong `root`,
    # không dùng Path(__file__) để tránh lỗi khi get_repo_root bị monkeypatch trong test.
    # Ưu tiên: root/.devin > root/.agents > root/session_state > fallback root/.agents.
    if (root / ".devin" / "session_state").is_dir() or (root / ".devin" / "loop_state").is_dir():
        return root / ".devin"
    if (root / ".agents" / "session_state").is_dir() or (root / ".agents" / "loop_state").is_dir():
        return root / ".agents"
    if (root / "session_state").is_dir() or (root / "loop_state").is_dir():
        return root
    # Nếu thư mục .devin/.agents tồn tại nhưng chưa có session_state/loop_state
    # (bootstrap) thì vẫn ưu tiên theo thứ tự trên.
    if (root / ".devin").is_dir():
        return root / ".devin"
    if (root / ".agents").is_dir():
        return root / ".agents"

    # Fallback
    return root / ".agents"


def get_shared_state_root(root: Path) -> Path:
    """Return the canonical shared-state root (``<root>/.agents``).

    Shared state files (user_profile.md, knowledge_distill.md,
    handoff_letter.md, context_quick_lookup.md) live at ``.agents/`` and are
    shared across all tools. Per-tool session state (loop_state.md,
    session_state/, context_flags/) lives at the tool's config root.

    Backward compatibility: if a shared state file exists in the tool's config
    root but not in ``.agents/``, this function still returns ``.agents/``.
    The caller should use ``resolve_shared_state_file()`` for automatic
    migration fallback.
    """
    return root / ".agents"


def resolve_shared_state_file(filename: str, root: Path) -> Path:
    """Resolve a shared state file path with backward-compat fallback.

    Checks ``.devin/<filename>`` first (canonical location).
    Falls back to ``<config_root>/<filename>`` (old AHD location) if the
    canonical path doesn't exist but the old one does.

    Does NOT copy — callers that need to persist should write to
    ``get_shared_state_root(root) / filename``.
    """
    canonical = get_shared_state_root(root) / filename
    if canonical.exists():
        return canonical
    old = get_config_root(root) / filename
    if old.exists():
        return old
    return canonical  # default to canonical for new file creation


def _lock_relpath(root: Path) -> Path:
    """Return the repo-level lock file path (for registry writes)."""
    return get_config_root(root) / "tmp" / "ahd_session.lock"


def _session_lock_relpath(root: Path, session_id: str) -> Path:
    """U14: Return a per-session lock file path.

    Per-session locks eliminate contention when multiple sessions
    write to different session_state files concurrently.
    """
    slug = slugify_session_id(session_id)
    return get_config_root(root) / "tmp" / f"ahd_session.{slug}.lock"


# U47: Cache for git rev-parse result (avoid repeated subprocess calls)
_REPO_ROOT_CACHE: Optional[Path] = None
_REPO_ROOT_CACHE_LOCK = threading.RLock()


def get_repo_root(start_from: Optional[Path] = None) -> Path:
    """Find the main repo root.

    1. Try git rev-parse --show-toplevel.
    2. Walk up from start_from (default cwd) for .git, .agents, AGENTS.md, pyproject.toml, README.md.
    3. Fallback to cwd.

    U47: Caches result to avoid repeated git rev-parse subprocess calls.
    """
    global _REPO_ROOT_CACHE
    with _REPO_ROOT_CACHE_LOCK:
        if _REPO_ROOT_CACHE is not None and start_from is None:
            return _REPO_ROOT_CACHE

    cwd = Path(start_from) if start_from else Path.cwd()
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=str(cwd)
        )
        if r.returncode == 0 and r.stdout.strip():
            result = Path(r.stdout.strip())
            if start_from is None:
                with _REPO_ROOT_CACHE_LOCK:
                    _REPO_ROOT_CACHE = result
            return result
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    # Không dùng .agents làm marker vì thư mục home của user cũng có thể có .agents,
    # gây nhầm repo root khi chạy test trong tmp_path không phải git repo.
    for parent in [cwd, *cwd.parents]:
        for marker in (".git", "AGENTS.md", "pyproject.toml", "README.md"):
            if (parent / marker).exists():
                if start_from is None:
                    with _REPO_ROOT_CACHE_LOCK:
                        _REPO_ROOT_CACHE = parent
                return parent
    if start_from is None:
        with _REPO_ROOT_CACHE_LOCK:
            _REPO_ROOT_CACHE = cwd
    return cwd


def slugify_session_id(sid: str, max_len: int = 64) -> str:
    """Make a filesystem-safe session id slug.

    U14 redteam: empty session_id gets random UUID suffix to avoid
    collision on per-session lock files.
    """
    if not sid:
        sid = f"unknown-{uuid.uuid4().hex[:8]}"
    # Replace separators and illegal chars
    sid = re.sub(r"[:/\\\s|<>\"'?*\"]+", "-", sid)
    sid = re.sub(r"-+", "-", sid)
    sid = sid.strip("-.")
    if not sid:
        sid = f"unknown-{uuid.uuid4().hex[:8]}"
    sid = sid[:max_len]
    return sid


def get_session_id(data: Optional[Dict[str, Any]] = None, env_prefix: str = "AHD") -> str:
    """Resolve session_id with fallback chain.

    1. tool input `data["session_id"]`
    2. env var `{env_prefix}_SESSION_ID`
    3. file `.devin/session_state/current_session`
    4. UUID
    """
    data = data or {}
    sid = data.get("session_id", "")
    if sid:
        return slugify_session_id(sid)

    sid = os.environ.get(f"{env_prefix}_SESSION_ID", "")
    if sid:
        return slugify_session_id(sid)

    # Racy fallback: read current_session file
    try:
        root = get_repo_root()
        current_file = get_config_root(root) / "session_state" / "current_session"
        if current_file.exists():
            sid = current_file.read_text(encoding="utf-8").strip()
            if sid:
                return slugify_session_id(sid)
    except (OSError, ValueError):
        pass

    return slugify_session_id(str(uuid.uuid4()))


def get_session_state_path(session_id: str, root: Optional[Path] = None) -> Path:
    """Return path to session_state JSON."""
    root = root or get_repo_root()
    return get_config_root(root) / "session_state" / f"{slugify_session_id(session_id)}.json"


def get_context_flags_path(session_id: str, root: Optional[Path] = None) -> Path:
    """Return per-session context_flags path."""
    root = root or get_repo_root()
    return get_config_root(root) / "context_flags" / f"{slugify_session_id(session_id)}.json"


def get_loop_state_path(session_id: str, root: Optional[Path] = None) -> Path:
    """Return per-session loop_state markdown path."""
    root = root or get_repo_root()
    return get_config_root(root) / "loop_state" / f"{slugify_session_id(session_id)}.md"


def _get_lock_path(root: Path) -> Path:
    """Return a repo-level lock file path (for registry writes)."""
    return _lock_relpath(root)


def _get_session_lock_path(root: Path, session_id: str) -> Path:
    """U14: Return a per-session lock file path (for session_state writes)."""
    return _session_lock_relpath(root, session_id)


def _acquire_lock(lock_path: Path, timeout: float = 10.0) -> Any:
    """Lấy một khóa liên tiến trình (inter-process lock).

    Thứ tự ưu tiên:
    1. filelock (đa nền tảng, đáng tin cậy).
    2. fcntl (Linux/macOS) hoặc msvcrt (Windows) với giới hạn thời gian.
    3. file sentinel với cờ O_CREAT|O_EXCL như giải pháp cuối cùng.

    Nếu hết thời gian chờ hoặc gặp lỗi nghiêm trọng, ném ``LockAcquireError``.
    """
    _safe_mkdir(lock_path.parent)
    deadline = time.time() + timeout

    # Bước 1: Thử dùng filelock nếu có.
    try:
        from filelock import FileLock, Timeout

        fl = FileLock(str(lock_path))
        try:
            fl.acquire(timeout=timeout)
            return fl
        except Timeout:
            raise LockAcquireError(
                f"Không thể lấy khóa {lock_path} sau {timeout}s (filelock)"
            )
    except LockAcquireError:
        raise
    except (OSError, ValueError, ImportError):
        pass

    # Bước 2: Dùng khóa gợi ý của hệ điều hành, có thời gian chờ.
    if sys.platform == "win32":
        try:
            import msvcrt

            f = open(lock_path, "wb")
            f.write(b"lock")
            f.flush()
            f.seek(0)
            while time.time() < deadline:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    return f
                except (OSError, IOError):
                    time.sleep(0.05)
            f.close()
            raise LockAcquireError(
                f"Không thể lấy khóa {lock_path} sau {timeout}s (msvcrt)"
            )
        except LockAcquireError:
            raise
        except (OSError, ValueError, ImportError) as exc:
            try:
                f.close()
            except (OSError, ValueError):
                pass
            raise LockAcquireError(
                f"Không thể lấy khóa {lock_path} (msvcrt): {exc}"
            ) from exc
    else:
        try:
            import fcntl

            f = open(lock_path, "w+")
            f.seek(0)
            while time.time() < deadline:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return f
                except (OSError, IOError):
                    time.sleep(0.05)
            f.close()
            raise LockAcquireError(
                f"Không thể lấy khóa {lock_path} sau {timeout}s (fcntl)"
            )
        except LockAcquireError:
            raise
        except (OSError, ValueError, ImportError) as exc:
            try:
                f.close()
            except (OSError, ValueError):
                pass
            raise LockAcquireError(
                f"Không thể lấy khóa {lock_path} (fcntl): {exc}"
            ) from exc

    # Bước 3: Giải pháp cuối cùng — sentinel O_CREAT|O_EXCL.
    try:
        pid = os.getpid()
        start = time.time()
        while time.time() - start < timeout:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(pid).encode("utf-8"))
                os.close(fd)
                return lock_path
            except FileExistsError:
                time.sleep(0.05)
            except (OSError, ValueError):
                break
        raise LockAcquireError(
            f"Không thể lấy khóa {lock_path} sau {timeout}s (sentinel)"
        )
    except LockAcquireError:
        raise
    except (OSError, ValueError) as exc:
        raise LockAcquireError(
            f"Không thể lấy khóa {lock_path} (sentinel): {exc}"
        ) from exc


def _release_lock(handle: Any) -> None:
    """Giải phóng một khóa được tạo bởi ``_acquire_lock``."""
    if handle is None:
        return
    try:
        if hasattr(handle, "release"):
            # Bước 1: filelock handle có method release() riêng.
            handle.release()
        elif hasattr(handle, "close"):
            # Bước 2: Đưa con trỏ về đầu file trước khi mở khóa (Windows cần vị trí cố định).
            try:
                handle.seek(0)
            except (OSError, ValueError):
                pass
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except (OSError, ValueError, ImportError):
                pass
            try:
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except (OSError, ValueError, ImportError):
                pass
            handle.close()
        elif isinstance(handle, Path):
            # Bước 3: sentinel lock được biểu diễn bằng đường dẫn.
            try:
                handle.unlink()
            except (OSError, ValueError):
                pass
    except (OSError, ValueError):
        pass


def _locked_json_read(path: Path, default: Any = None, session_id: str = "") -> Any:
    """Read a JSON file with a lock.

    U14: If session_id is provided, uses per-session lock (no contention
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

    U14: If session_id is provided, uses per-session lock. If not, repo-level.
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

    U14: If session_id is provided, uses per-session lock. If not, repo-level.
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


def read_session_state(session_id: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """Read session_state JSON with per-session lock (U14)."""
    path = get_session_state_path(session_id, root)
    return _locked_json_read(path, default={}, session_id=session_id)


def write_session_state(session_id: str, data: Dict[str, Any], root: Optional[Path] = None, merge: bool = True) -> None:
    """Write session_state JSON with per-session lock (U14).

    If merge=True, merge with existing data under the same lock. This lets
    `post_tool_use` update `last_heartbeat` without overwriting `current_subtask`
    set by `loop-memory`, and prevents lost updates under concurrent writes.

    U34: Warns when session_state approaches or exceeds configured cap.
    """
    path = get_session_state_path(session_id, root)
    if merge:
        _locked_json_update(path, lambda existing: {**(existing or {}), **data}, default={}, session_id=session_id)
    else:
        _locked_json_write(path, data, session_id=session_id)

    # U34: Check memory cap and warn
    _check_memory_cap(path, "session_state", root)


def _check_memory_cap(path: Path, cap_name: str, root: Optional[Path] = None) -> None:
    """U34: Warn when file size approaches or exceeds configured cap.

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


def update_session_state(session_id: str, fields: Dict[str, Any], root: Optional[Path] = None) -> None:
    """Merge fields into session_state without overwriting unrelated fields."""
    write_session_state(session_id, fields, root, merge=True)


def write_context_flags(session_id: str, data: Dict[str, Any], root: Optional[Path] = None) -> None:
    """Write per-session context_flags.json with per-session lock (U14)."""
    path = get_context_flags_path(session_id, root)
    _locked_json_update(path, lambda existing: {**(existing or {}), **data}, default={}, session_id=session_id)


def read_context_flags(session_id: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """Read per-session context_flags.json with per-session lock (U14)."""
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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# U67: Antifragility — failure tracking + circuit breakers

# In-memory failure counters per component
_FAILURE_COUNTERS: dict[str, int] = {}
_CIRCUIT_BREAKER_THRESHOLD = 3
_TRIPPED_BREAKERS: set[str] = set()
_CIRCUIT_LOCK = threading.RLock()


def record_failure(component: str, session_id: str = "") -> None:
    """U67: Record a component failure. Trips circuit breaker on 3 failures."""
    with _CIRCUIT_LOCK:
        _FAILURE_COUNTERS[component] = _FAILURE_COUNTERS.get(component, 0) + 1
        if _FAILURE_COUNTERS[component] >= _CIRCUIT_BREAKER_THRESHOLD:
            _TRIPPED_BREAKERS.add(component)
        tripped = list(_TRIPPED_BREAKERS)
        counts = dict(_FAILURE_COUNTERS)

    # Also persist to session_state for cross-session visibility
    try:
        root = get_repo_root()
        state_path = get_session_state_path(session_id, root)
        _locked_json_update(
            state_path,
            lambda existing: {
                **(existing or {}),
                "circuit_breakers_tripped": tripped,
                "failure_counts": counts,
            },
            default={},
            session_id=session_id,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        pass


def is_circuit_open(component: str) -> bool:
    """U67: Check if circuit breaker is tripped for a component."""
    with _CIRCUIT_LOCK:
        return component in _TRIPPED_BREAKERS


def reset_circuit(component: str) -> None:
    """U67: Reset circuit breaker for a component (manual override)."""
    with _CIRCUIT_LOCK:
        _TRIPPED_BREAKERS.discard(component)
        _FAILURE_COUNTERS.pop(component, None)


def get_failure_stats() -> dict[str, int]:
    """U67: Get current failure counts for all components."""
    with _CIRCUIT_LOCK:
        return dict(_FAILURE_COUNTERS)


def auto_minimal_mode(session_id: str, root: Optional[Path] = None) -> bool:
    """U67: Auto-activate minimal mode if critical components fail.

    Returns True if minimal mode should be activated.
    """
    critical_components = ["ahd_session", "pre_tool_use", "post_tool_use"]
    failed_critical = [c for c in critical_components if is_circuit_open(c)]
    if failed_critical:
        try:
            state_path = get_session_state_path(session_id, root)
            _locked_json_update(
                state_path,
                lambda existing: {
                    **(existing or {}),
                    "minimal_mode_auto": True,
                    "minimal_mode_reason": f"Circuit breakers tripped: {failed_critical}",
                },
                default={},
                session_id=session_id,
            )
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return True
    return False
