#!/usr/bin/env python3
"""T1.3: Migration script gộp state layout cũ về unified `state/`.

Gộp các thư mục state legacy:
    .devin/session_state/  -> state/session/
    .devin/loop_state/     -> state/loop/
    .devin/plan_state/     -> state/plan/
    .agents/               -> state/agents/

Hành vi:
    - Di chuyển file từ thư mục cũ sang thư mục mới dưới `state/`.
    - Tạo symlink (liên kết tượng trưng) từ vị trí cũ -> vị trí mới để giữ
      tương thích ngược trong 1 release.
    - Idempotent (có thể chạy lại): nếu đích đã tồn tại thì bỏ qua, không fail,
      không nhân bản file.
    - Xử lý lỗi I/O: ghi log tiếng Việt, không crash im lặng.

CLI:
    python .devin/scripts/migrate_state.py --old-root <path>
    In ra đường dẫn thư mục state mới.

Tuân thủ: file < 500 dòng, comment tiếng Việt, không đụng HLK/security/.env.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# Bảng ánh xạ: thư mục legacy (tương đối so với old_root) -> thư mục mới
# (tương đối so với new_root = old_root / "state").
# Thư mục mới dùng tên ngắn gọn, thống nhất dưới state/.
LEGACY_TO_NEW: dict[str, str] = {
    ".devin/session_state": "session",
    ".devin/loop_state": "loop",
    ".devin/plan_state": "plan",
    ".agents": "agents",
}


def _move_files(src_dir: Path, dst_dir: Path) -> int:
    """Di chuyển toàn bộ file từ src_dir sang dst_dir.

    Trả về số file đã di chuyển thực sự. Bỏ qua file đã tồn tại ở đích
    (idempotent). Nếu src_dir không tồn tại thì trả về 0.

    Bước 1: Kiểm tra src_dir tồn tại.
    Bước 2: Tạo dst_dir nếu chưa có.
    Bước 3: Duyệt từng entry trong src_dir:
        - Nếu là file: đích chưa có thì move, đã có thì bỏ qua.
        - Nếu là thư mục con: đệ quy di chuyển.
    """
    if not src_dir.exists():
        return 0

    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[WARN] Không tạo được thư mục đích {dst_dir}: {exc}",
              file=sys.stderr)
        return 0

    moved = 0
    try:
        for entry in src_dir.iterdir():
            dst_entry = dst_dir / entry.name
            if entry.is_dir() and not entry.is_symlink():
                # Thư mục con: đệ quy để giữ cấu trúc.
                moved += _move_files(entry, dst_entry)
                # Sau khi đệ quy rỗng, xoá thư mục con rỗng (nếu còn).
                try:
                    if entry.exists() and not any(entry.iterdir()):
                        entry.rmdir()
                except OSError:
                    pass
            elif entry.is_file() or entry.is_symlink():
                if dst_entry.exists():
                    # Đích đã có -> idempotent skip.
                    continue
                try:
                    shutil.move(str(entry), str(dst_entry))
                    moved += 1
                except OSError as exc:
                    print(f"[WARN] Không di chuyển được {entry} -> {dst_entry}: {exc}",
                          file=sys.stderr)
            else:
                # Loại entry khác (socket, fifo...) -> bỏ qua an toàn.
                continue
    except OSError as exc:
        print(f"[WARN] Lỗi khi duyệt {src_dir}: {exc}", file=sys.stderr)

    return moved


def _create_symlink(link_path: Path, target: Path) -> bool:
    """Tạo symlink từ link_path trỏ tới target.

    Trả về True nếu symlink đã tồn tại hoặc tạo thành công.
    Trả về False nếu không thể tạo (thiếu quyền trên Windows, v.v.).

    Bước 1: Nếu link_path đã là symlink trỏ đúng target -> đã sẵn sàng.
    Bước 2: Nếu link_path tồn tại (file/thư mục thật) -> bỏ qua, không ghi đè.
    Bước 3: Thử os.symlink; nếu lỗi quyền/nền tảng -> trả về False.
    """
    if link_path.is_symlink():
        try:
            if os.readlink(link_path) == str(target):
                return True
        except OSError:
            pass
        # Symlink sai hướng -> xoá rồi tạo lại.
        try:
            link_path.unlink()
        except OSError as exc:
            print(f"[WARN] Không xoá được symlink cũ {link_path}: {exc}",
                  file=sys.stderr)
            return False

    if link_path.exists() and not link_path.is_symlink():
        # Đã là file/thư mục thật -> không ghi đè để tránh mất dữ liệu.
        return False

    try:
        os.symlink(str(target), str(link_path), target_is_directory=True)
        return True
    except (OSError, NotImplementedError) as exc:
        # Windows thường cần Developer Mode / admin để tạo symlink.
        print(f"[WARN] Không tạo được symlink {link_path} -> {target}: {exc}",
              file=sys.stderr)
        return False


def migrate(old_root: Path) -> Path:
    """Gộp state legacy về unified `state/` dưới old_root.

    Tham số:
        old_root: Path tới thư mục gốc chứa các thư mục legacy
                  (.devin/session_state, .devin/loop_state, .devin/plan_state,
                   .agents).

    Trả về:
        Path tới thư mục state mới (old_root / "state").

    Bước 1: Resolve old_root, xác định new_root = old_root / "state".
    Bước 2: Tạo new_root.
    Bước 3: Với mỗi cặp (legacy, new) trong LEGACY_TO_NEW:
        - Di chuyển file từ legacy sang new.
        - Nếu legacy đã rỗng hoặc không tồn tại, tạo symlink legacy -> new
          để tương thích ngược.
    Bước 4: Trả về new_root.
    """
    old_root = Path(old_root).resolve()
    new_root = old_root / "state"

    try:
        new_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[ERROR] Không tạo được thư mục state mới {new_root}: {exc}",
              file=sys.stderr)
        raise

    for legacy_rel, new_rel in LEGACY_TO_NEW.items():
        legacy_dir = old_root / legacy_rel
        new_dir = new_root / new_rel

        # Bước 3a: Di chuyển file (idempotent).
        _move_files(legacy_dir, new_dir)

        # Bước 3b: Tạo symlink legacy -> new nếu legacy đã rỗng/không tồn tại.
        # Chỉ tạo symlink khi legacy không còn file thật (tránh che khuất dữ
        # liệu chưa migrate). Nếu legacy là symlink rồi thì _create_symlink tự
        # xử lý.
        legacy_has_real_content = (
            legacy_dir.exists()
            and not legacy_dir.is_symlink()
            and any(legacy_dir.iterdir())
        )
        if not legacy_has_real_content:
            # Đảm bảo thư mục cha của legacy tồn tại (.devin luôn có, .agents
            # cũng vậy, nhưng phòng hờ).
            try:
                legacy_dir.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            # Nếu legacy_dir là thư mục rỗng, xoá trước khi tạo symlink.
            if legacy_dir.exists() and not legacy_dir.is_symlink():
                try:
                    legacy_dir.rmdir()
                except OSError as exc:
                    print(f"[WARN] Không xoá được thư mục rỗng {legacy_dir}: "
                          f"{exc}", file=sys.stderr)
                    continue
            _create_symlink(legacy_dir, new_dir)

    return new_root


def main() -> int:
    """CLI stub: nhận --old-root, chạy migrate, in ra new root."""
    # Ép stdout/stderr dùng UTF-8 để in tiếng Việt an toàn trên Windows console
    # (tránh UnicodeEncodeError khi argparse in --help chứa tiếng Việt).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(
        description="T1.3: Gộp state legacy về unified state/ layout."
    )
    ap.add_argument(
        "--old-root",
        default=".",
        help="Thư mục gốc chứa .devin/ và .agents/ (mặc định: thư mục hiện tại).",
    )
    args = ap.parse_args()

    try:
        new_root = migrate(Path(args.old_root))
    except OSError as exc:
        print(f"[FAIL] Migration thất bại: {exc}", file=sys.stderr)
        return 1

    print(str(new_root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
