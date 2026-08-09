#!/usr/bin/env python3
"""Kiểm thử validate input cho apply_ahd_patch.py (T3.1 / REQ-011)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import apply_ahd_patch  # noqa: E402


def test_validate_sha_accepts_hex_7_to_40():
    assert apply_ahd_patch.validate_sha("abcd123") is True
    assert apply_ahd_patch.validate_sha("abcd1234567890abcd1234567890abcd123456") is True


def test_validate_sha_rejects_invalid():
    assert apply_ahd_patch.validate_sha("xyz1234") is False
    assert apply_ahd_patch.validate_sha("abcd12") is False
    # 41 ký tự, vượt quá 40
    assert apply_ahd_patch.validate_sha("abcd1234567890abcd1234567890abcd123456789") is False
    assert apply_ahd_patch.validate_sha("") is False


def test_validate_worktree_path_rejects_absolute_and_traversal(tmp_path: Path):
    repo = tmp_path
    assert apply_ahd_patch.validate_worktree_path("/etc/passwd", repo) is None
    assert apply_ahd_patch.validate_worktree_path("../.env", repo) is None
    assert apply_ahd_patch.validate_worktree_path("sub/../../.env", repo) is None


def test_validate_worktree_path_accepts_relative_subdir(tmp_path: Path):
    repo = tmp_path
    (repo / "worktrees").mkdir()
    result = apply_ahd_patch.validate_worktree_path("worktrees/ahd", repo)
    assert result is not None
    assert result == repo / "worktrees" / "ahd"


def test_guard_main_branch_blocks_main(tmp_git_repo: Path):
    import update_common
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_git_repo
    apply_ahd_patch.REPO_ROOT = tmp_git_repo
    try:
        ok, branch = apply_ahd_patch.guard_main_branch(force=False)
        assert ok is False
        assert branch == "main"

        ok, branch = apply_ahd_patch.guard_main_branch(force=True)
        assert ok is True
        assert branch == "main"
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old
