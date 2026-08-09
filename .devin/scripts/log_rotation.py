#!/usr/bin/env python3
"""U44: Audit log size limits + rotation.

Rotates audit logs when they exceed size limit. Keeps last N rotated logs.

Usage:
    python .devin/scripts/log_rotation.py --rotate
    python .devin/scripts/log_rotation.py --status
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# U44: Config
MAX_LOG_SIZE_BYTES = 1024 * 1024  # 1MB
MAX_ROTATED_FILES = 5  # Keep last 5 rotated logs
LOG_DIRS = [".devin/logs", "HLK/logs"]
LOG_PATTERNS = ["*.log", "*.jsonl"]


def rotate_log(log_path: Path, max_rotated: int = MAX_ROTATED_FILES) -> bool:
    """Rotate a single log file if it exceeds size limit (atomic rename + O_TRUNC)."""
    if not log_path.exists():
        return False

    size = log_path.stat().st_size
    if size <= MAX_LOG_SIZE_BYTES:
        return False

    # Lock để tránh appender ghi trong quá trình rotate.
    lock_path = log_path.with_suffix(f"{log_path.suffix}.lock" if log_path.suffix else ".lock")
    lock = None
    try:
        # Thử dùng ahd_session lock nếu có; nếu không thì bỏ qua (best-effort).
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
            import ahd_session
            lock = ahd_session._acquire_lock(lock_path, timeout=5.0)
        except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
            lock = None

        # Rotate: log → log.1, log.1 → log.2, etc. dùng os.replace (atomic trên cùng FS).
        for i in range(max_rotated - 1, 0, -1):
            old = log_path.with_suffix(f".{i}.log" if not log_path.suffix else f".{i}{log_path.suffix}")
            new = log_path.with_suffix(f".{i+1}.log" if not log_path.suffix else f".{i+1}{log_path.suffix}")
            if old.exists():
                os.replace(old, new)

        # Move current to .1 bằng os.replace (atomic)
        rotated = log_path.with_suffix(f".1{log_path.suffix}" if log_path.suffix else ".1.log")
        os.replace(log_path, rotated)

        # Truncate original bằng open O_TRUNC (atomic create empty file)
        with open(log_path, "w", encoding="utf-8") as _:
            pass

        print(f"[ROTATED] {log_path} ({size} bytes → rotated to {rotated})")
        return True
    except (OSError, UnicodeDecodeError) as e:
        print(f"[log_rotation] ERROR rotating {log_path}: {e}", file=sys.stderr)
        return False
    finally:
        if lock is not None:
            try:
                import ahd_session
                ahd_session._release_lock(lock)
            except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
                pass


def rotate_all(root: Path) -> int:
    """Rotate all logs that exceed size limit."""
    rotated = 0

    for log_dir_rel in LOG_DIRS:
        log_dir = root / log_dir_rel
        if not log_dir.exists():
            continue

        for pattern in LOG_PATTERNS:
            for log_file in log_dir.glob(pattern):
                if rotate_log(log_file):
                    rotated += 1

    if rotated == 0:
        print("[OK] No logs need rotation")
    else:
        print(f"\n[DONE] Rotated {rotated} log(s)")

    return rotated


def show_status(root: Path) -> int:
    """Show log sizes."""
    found = 0
    for log_dir_rel in LOG_DIRS:
        log_dir = root / log_dir_rel
        if not log_dir.exists():
            continue

        for pattern in LOG_PATTERNS:
            for log_file in sorted(log_dir.glob(pattern)):
                size = log_file.stat().st_size
                pct = int(size * 100 / MAX_LOG_SIZE_BYTES)
                status = "OK" if size <= MAX_LOG_SIZE_BYTES else "ROTATE"
                print(f"  [{status}] {log_file.relative_to(root)}: {size} bytes ({pct}%)")
                found += 1

    if found == 0:
        print("[STATUS] No logs found")
    return 0


def main():
    import argparse
    ap = argparse.ArgumentParser(description="U44: Audit log rotation")
    ap.add_argument("--rotate", action="store_true", help="Rotate oversized logs")
    ap.add_argument("--status", action="store_true", help="Show log sizes")
    ap.add_argument("--root", default=".", help="Repo root")

    args = ap.parse_args()
    root = Path(args.root).resolve()

    if args.rotate:
        rotate_all(root)
    elif args.status:
        show_status(root)
    else:
        ap.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
