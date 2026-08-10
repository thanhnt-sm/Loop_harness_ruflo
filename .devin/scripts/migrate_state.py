#!/usr/bin/env python3
"""Migration script chuyển layout state cũ sang unified `state/`.

Di chuyển các thư mục legacy `session_state`, `loop_state`, `plan_state`, `agents_state`
(có thể nằm ở old_root hoặc old_root/.devin) vào `<new_root>/state/` và tạo symlink
backward-compatible.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


# Legacy source names -> state/ target names
LEGACY_MAP = {
    "session_state": "session",
    "loop_state": "loop",
    "plan_state": "plan",
    "agents_state": "agents",
    "session": "session",
    "loop": "loop",
    "plan": "plan",
    "agents": "agents",
}


def _move_files(src: Path, dst: Path) -> int:
    """Di chuyển nội dung từ src sang dst, đệ quy, skip nếu đã tồn tại.

    Trả về số lượng item đã di chuyển (0 nếu src không tồn tại hoặc lỗi).
    """
    if not src.exists():
        return 0

    try:
        items = list(src.iterdir())
    except OSError:
        return 0

    try:
        dst.mkdir(parents=True, exist_ok=True)
    except OSError:
        return 0

    moved = 0
    for item in items:
        dest = dst / item.name
        if item.is_dir() and not item.is_symlink():
            try:
                dest.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue
            moved += _move_files(item, dest)
        else:
            if dest.exists() or dest.is_symlink():
                continue
            try:
                shutil.move(str(item), str(dest))
                moved += 1
            except OSError:
                pass

    # Xoá thư mục nguồn nếu đã rỗng để có thể tạo symlink backward-compatible
    try:
        if src.is_dir() and not any(src.iterdir()):
            src.rmdir()
    except OSError:
        pass
    return moved


def _create_symlink(link: Path, target: Path) -> bool:
    """Tạo symlink link -> target. Trả về True nếu đã có/có thể tạo, False nếu lỗi.

    - Nếu link là file thật (không phải symlink) -> False.
    - Nếu symlink trỏ sai target -> xoá và tạo lại.
    - Nếu symlink đúng -> True.
    """
    if link.exists() and not link.is_symlink():
        return False

    if link.is_symlink():
        try:
            current = os.readlink(str(link))
        except OSError:
            current = None
        if current == str(target):
            return True
        try:
            link.unlink()
        except OSError:
            pass

    try:
        is_dir = target.is_dir() or not target.exists()
        os.symlink(str(target), str(link), target_is_directory=is_dir)
        return True
    except (OSError, NotImplementedError):
        return False


def _list_legacy_dirs(old_root: Path) -> dict[str, Path]:
    """Tìm các thư mục legacy cần migrate."""
    roots = [old_root, old_root / ".devin"]
    found: dict[str, Path] = {}
    for legacy_name, target_name in LEGACY_MAP.items():
        for root in roots:
            p = root / legacy_name
            if p.exists() and not p.is_symlink() and target_name not in found:
                found[target_name] = p
                break
    return found


def migrate(
    old_root: str | Path,
    new_root: str | Path | None = None,
) -> Path:
    """Di chuyển state legacy vào `<new_root>/state/`.

    Idempotent: chạy lại không duplicate.
    """
    old_root = Path(old_root).resolve()
    if new_root is None:
        new_root = old_root
    new_root = Path(new_root).resolve()
    state_dir = new_root / "state"

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Không thể tạo state dir {state_dir}: {exc}") from exc

    legacy_dirs = _list_legacy_dirs(old_root)

    for target_name, legacy_path in legacy_dirs.items():
        target_path = state_dir / target_name
        _move_files(legacy_path, target_path)

        link = old_root / target_name
        if not link.exists() and not link.is_symlink():
            _create_symlink(link, target_path)

        dotdevin_link = old_root / ".devin" / f"{target_name}_state"
        if not dotdevin_link.exists() and not dotdevin_link.is_symlink():
            _create_symlink(dotdevin_link, target_path)

    return state_dir


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-root", default=".", help="Thư mục gốc chứa state legacy")
    parser.add_argument("--new-root", default=None, help="Thư mục gốc chứa state/ mới (mặc định = old-root)")
    args = parser.parse_args()

    new_root = args.new_root
    if new_root is None:
        new_root = args.old_root

    try:
        if args.new_root is None:
            state_dir = migrate(args.old_root)
        else:
            state_dir = migrate(args.old_root, args.new_root)
        print(f"[OK] Unified state dir: {state_dir}")
        return 0
    except OSError as exc:
        print(f"[ERROR] {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
