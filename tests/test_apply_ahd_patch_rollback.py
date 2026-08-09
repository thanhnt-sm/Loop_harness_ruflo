#!/usr/bin/env python3
"""Kiểm thử targeted rollback (T3.6 / REQ-005)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import apply_ahd_patch  # noqa: E402
import update_common  # noqa: E402


def test_rollback_patched_files_reverts_only_modified_files(tmp_git_repo: Path):
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_git_repo
    apply_ahd_patch.REPO_ROOT = tmp_git_repo
    try:
        import subprocess

        # tracked files
        f1 = tmp_git_repo / "file1.md"
        f2 = tmp_git_repo / "file2.md"
        f1.write_text("original1\n", encoding="utf-8")
        f2.write_text("original2\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_git_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add files"], cwd=tmp_git_repo, check=True, capture_output=True)

        # modify both
        f1.write_text("changed1\n", encoding="utf-8")
        f2.write_text("changed2\n", encoding="utf-8")

        # rollback only f1
        apply_ahd_patch.rollback_patched_files(["file1.md"])
        assert f1.read_text(encoding="utf-8") == "original1\n"
        assert f2.read_text(encoding="utf-8") == "changed2\n"
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old
