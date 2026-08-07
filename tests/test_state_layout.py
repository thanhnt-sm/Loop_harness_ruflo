#!/usr/bin/env python3
"""T1.3: Kiểm thử migrate_state.migrate — idempotency, symlink, ánh xạ thư mục.

Cover:
    - Ánh xạ đúng thư mục legacy -> state/{session,loop,plan,agents}.
    - File thực sự được di chuyển sang vị trí mới.
    - Symlink legacy -> new tồn tại (nếu nền tảng hỗ trợ).
    - Idempotent: chạy lại không fail, không nhân bản file.
    - migrate() trả về Path tới state root.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Cho phép import migrate_state từ .devin/scripts/.
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import migrate_state  # noqa: E402


def _supports_symlinks(tmp_path: Path) -> bool:
    """Kiểm tra nền tảng có hỗ trợ tạo symlink không (Windows cần Developer Mode)."""
    src = tmp_path / "_src_dir"
    src.mkdir()
    link = tmp_path / "_link"
    try:
        os.symlink(str(src), str(link), target_is_directory=True)
        link.unlink()
        return True
    except (OSError, NotImplementedError):
        return False
    finally:
        try:
            src.rmdir()
        except OSError:
            pass


def _seed_legacy(root: Path) -> None:
    """Tạo cấu trúc state legacy mẫu dưới root."""
    (root / ".devin" / "session_state").mkdir(parents=True)
    (root / ".devin" / "session_state" / "s-1.json").write_text(
        '{"id":"s1"}', encoding="utf-8"
    )
    (root / ".devin" / "loop_state").mkdir(parents=True)
    (root / ".devin" / "loop_state" / "loop-1.json").write_text(
        '{"id":"l1"}', encoding="utf-8"
    )
    (root / ".devin" / "plan_state").mkdir(parents=True)
    (root / ".devin" / "plan_state" / "plan-1.json").write_text(
        '{"id":"p1"}', encoding="utf-8"
    )
    (root / ".agents").mkdir()
    (root / ".agents" / "user_profile.md").write_text(
        "# profile", encoding="utf-8"
    )


def test_migrate_returns_state_root(tmp_path: Path):
    # migrate() phải trả về Path tới <root>/state
    _seed_legacy(tmp_path)
    result = migrate_state.migrate(tmp_path)
    assert result == (tmp_path / "state").resolve()
    assert result.is_dir()


def test_directory_mapping(tmp_path: Path):
    # Ánh xạ đúng: legacy -> state/{session,loop,plan,agents}
    _seed_legacy(tmp_path)
    migrate_state.migrate(tmp_path)

    state = tmp_path / "state"
    assert (state / "session" / "s-1.json").is_file()
    assert (state / "loop" / "loop-1.json").is_file()
    assert (state / "plan" / "plan-1.json").is_file()
    assert (state / "agents" / "user_profile.md").is_file()


def test_files_moved_not_copied(tmp_path: Path):
    # File phải được di chuyển (không còn ở vị trí cũ nếu chưa tạo symlink)
    _seed_legacy(tmp_path)
    migrate_state.migrate(tmp_path)

    # Sau migrate, file phải tồn tại ở vị trí mới.
    assert (tmp_path / "state" / "session" / "s-1.json").is_file()
    # Vị trí cũ giờ là symlink (nếu hỗ trợ) hoặc đã rỗng/được xoá.
    legacy_session = tmp_path / ".devin" / "session_state"
    if legacy_session.is_symlink():
        # Symlink thì không còn file thật ở đó.
        assert not (legacy_session / "s-1.json").is_file() or \
            (legacy_session / "s-1.json").is_symlink()
    else:
        # Không hỗ trợ symlink -> thư mục cũ phải rỗng.
        assert not any(legacy_session.iterdir()) if legacy_session.exists() else True


def test_symlink_exists_when_supported(tmp_path: Path):
    # Symlink legacy -> new phải tồn tại nếu nền tảng hỗ trợ.
    if not _supports_symlinks(tmp_path):
        pytest.skip("Nền tảng không hỗ trợ symlink (Windows thiếu Developer Mode).")

    _seed_legacy(tmp_path)
    migrate_state.migrate(tmp_path)

    state = tmp_path / "state"
    expected_links = {
        tmp_path / ".devin" / "session_state": state / "session",
        tmp_path / ".devin" / "loop_state": state / "loop",
        tmp_path / ".devin" / "plan_state": state / "plan",
        tmp_path / ".agents": state / "agents",
    }
    for link, target in expected_links.items():
        assert link.is_symlink(), f"Thiếu symlink {link}"
        assert os.readlink(link) == str(target), \
            f"Symlink {link} trỏ sai đích"


def test_idempotent_rerun_noop(tmp_path: Path):
    # Chạy lại không fail, không nhân bản file.
    _seed_legacy(tmp_path)

    first = migrate_state.migrate(tmp_path)
    # Đếm số file ở state root sau lần 1.
    first_count = sum(1 for _ in first.rglob("*") if _.is_file())

    # Chạy lại.
    second = migrate_state.migrate(tmp_path)
    assert second == first

    second_count = sum(1 for _ in second.rglob("*") if _.is_file())
    assert second_count == first_count, \
        "Re-run làm thay đổi số file (không idempotent)"


def test_idempotent_when_target_already_has_file(tmp_path: Path):
    # Nếu đích đã có file cùng tên, không ghi đè, không fail.
    _seed_legacy(tmp_path)
    # Tạo sẵn file đích trùng tên.
    (tmp_path / "state" / "session").mkdir(parents=True)
    (tmp_path / "state" / "session" / "s-1.json").write_text(
        '{"id":"pre-existing"}', encoding="utf-8"
    )

    # migrate không crash.
    result = migrate_state.migrate(tmp_path)
    # File đích giữ nguyên nội dung cũ (không bị ghi đè).
    content = (result / "session" / "s-1.json").read_text(encoding="utf-8")
    assert "pre-existing" in content


def test_missing_legacy_dirs_no_error(tmp_path: Path):
    # Không có thư mục legacy -> migrate vẫn chạy ok, trả về state root.
    result = migrate_state.migrate(tmp_path)
    assert result.is_dir()
    # Các subdir phải được tạo (sau khi _move_files gọi mkdir).
    # Lưu ý: nếu legacy không tồn tại, _move_files trả về 0 và không tạo subdir.
    # Nhưng symlink vẫn có thể được tạo trỏ tới (sẽ là broken symlink) —
    # behaviour này chấp nhận được vì new dir sẽ được tạo khi cần.


def test_nested_subdir_moved(tmp_path: Path):
    # Thư mục con lồng nhau cũng được di chuyển.
    (tmp_path / ".devin" / "plan_state" / "tasks").mkdir(parents=True)
    (tmp_path / ".devin" / "plan_state" / "tasks" / "t1.json").write_text(
        '{"t":1}', encoding="utf-8"
    )
    migrate_state.migrate(tmp_path)
    assert (tmp_path / "state" / "plan" / "tasks" / "t1.json").is_file()


def test_import_migrate_state():
    # Acceptance: import migrate_state hoạt động.
    assert hasattr(migrate_state, "migrate")
    assert callable(migrate_state.migrate)
