#!/usr/bin/env python3
"""Lock utilities for ahd_session — inter-process file locking.

Provides:
- _safe_mkdir: Safe directory creation handling Python 3.13 Linux FileExistsError
- _acquire_lock: Multi-strategy lock acquisition (filelock, fcntl/msvcrt, sentinel)
- _release_lock: Lock release for all lock types
- LockAcquireError: Exception raised when lock cannot be acquired
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any


class LockAcquireError(Exception):
    """Ném khi không thể lấy được file lock trong thời gian chờ."""


def _safe_mkdir(path: Path, parents: bool = True) -> None:
    """Tạo thư mục an toàn — handle FileExistsError trên Linux Python 3.13.

    Python 3.13 trên Linux có thể ném FileExistsError khi mkdir(exist_ok=True)
    nếu path là symlink hoặc có race condition giữa các process.
    Dùng os.makedirs thay vì pathlib.mkdir để tránh bug.
    """
    try:
        os.makedirs(str(path), exist_ok=True)
    except FileExistsError:
        # Dir đã tồn tại (có thể là symlink) — OK nếu là dir
        if not path.is_dir():
            raise


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