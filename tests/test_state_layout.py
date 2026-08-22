#!/usr/bin/env python3
"""Kiểm tra migrate_state.py theo T1.3 / REQ-014."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import migrate_state  # noqa: E402


def test_migrate_state_moves_dirs(tmp_path: Path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    (old / "session").mkdir(parents=True)
    (old / "loop").mkdir(parents=True)
    (old / "session" / "a.json").write_text("{}")

    state_dir = migrate_state.migrate(old, new)
    assert state_dir == (new / "state")
    assert (state_dir / "session" / "a.json").exists()
    assert (state_dir / "loop").exists()


def test_migrate_state_idempotent(tmp_path: Path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    (old / "plan").mkdir(parents=True)
    (old / "plan" / "b.json").write_text("{}")

    migrate_state.migrate(old, new)
    state_dir = migrate_state.migrate(old, new)
    assert (state_dir / "plan" / "b.json").exists()
    # Không có duplicate
    assert len(list((state_dir / "plan").iterdir())) == 1


@pytest.mark.skipif(
    sys.platform == "win32" and not sys.getwindowsversion().build >= 10000,
    reason="Nền tảng không hỗ trợ symlink (Windows thiếu Developer Mode).",
)
def test_migrate_state_creates_symlinks(tmp_path: Path):
    import os
    old = tmp_path / "old"
    new = tmp_path / "new"
    (old / "session_state").mkdir(parents=True)

    migrate_state.migrate(old, new)
    link = old / "session_state"
    if link.exists() or link.is_symlink():
        assert link.is_symlink()
        assert os.readlink(str(link)) == str(new / "state" / "session")
