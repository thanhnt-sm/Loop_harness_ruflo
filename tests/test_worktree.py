#!/usr/bin/env python3
"""T2-01/T2-03: Tests bảo mật + clean-up cho worktree.py.

Phủ:
- Validate worker_id (chặn path traversal / ký tự đặc biệt).
- Containment target trong .worktrees/.
- Guard rmtree/merge/remove khi path state ngoài .worktrees.
- Không tạo/ghi gì khi vi phạm.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import worktree  # noqa: E402


def _ok_state(worker_id: str, path: Path) -> dict:
    return {"worktrees": {worker_id: {"path": str(path), "branch": "b", "status": "active", "session_id": ""}}}


class TestValidateWorkerId:
    def test_accepts_simple(self):
        assert worktree._validate_worker_id("builder-a") is True
        assert worktree._validate_worker_id("wt-a1b2c3d4-builder-a") is True

    def test_rejects_path_traversal(self):
        assert worktree._validate_worker_id("../evil") is False
        assert worktree._validate_worker_id("../../../../tmp/evil") is False
        assert worktree._validate_worker_id("..") is False

    def test_rejects_separators_and_special(self):
        assert worktree._validate_worker_id("a/b") is False
        assert worktree._validate_worker_id("a\\b") is False
        assert worktree._validate_worker_id("a b") is False
        assert worktree._validate_worker_id("a!b") is False
        assert worktree._validate_worker_id("a#b") is False
        assert worktree._validate_worker_id("-builder") is False

    def test_rejects_empty_and_too_long(self):
        assert worktree._validate_worker_id("") is False
        assert worktree._validate_worker_id("x" * 65) is False
        assert worktree._validate_worker_id("x" * 64) is True


class TestWorktreeTargetContainment:
    def test_keeps_inside(self, monkeypatch):
        monkeypatch.setattr(worktree, "WORKTREE_DIR", REPO_ROOT / ".worktrees")
        t = worktree._worktree_target("builder-a")
        assert t is not None
        t.resolve().relative_to((REPO_ROOT / ".worktrees").resolve())

    def test_blocks_outside(self, monkeypatch):
        monkeypatch.setattr(worktree, "WORKTREE_DIR", REPO_ROOT / ".worktrees")
        assert worktree._worktree_target("../../../../tmp/evil") is None


class TestCmdCreateGuard:
    def test_create_rejects_traversal(self, monkeypatch):
        called = []

        def fake_git(*args, **kwargs):
            called.append(args)
            return (0, "", "")

        monkeypatch.setattr(worktree, "_git", fake_git)
        monkeypatch.setattr(worktree, "_save_state", lambda s: None)
        monkeypatch.setattr(worktree, "_update_session_state_worktrees", lambda *a, **k: None)
        rc = worktree.cmd_create("../../../../tmp/evil")
        assert rc == 2
        assert called == []  # không chạy git

    def test_create_rejects_special(self, monkeypatch):
        called = []

        def fake_git(*args, **kwargs):
            called.append(args)
            return (0, "", "")

        monkeypatch.setattr(worktree, "_git", fake_git)
        monkeypatch.setattr(worktree, "_save_state", lambda s: None)
        monkeypatch.setattr(worktree, "_update_session_state_worktrees", lambda *a, **k: None)
        rc = worktree.cmd_create("a b")
        assert rc == 2
        assert called == []


class TestMergeRemoveGuard:
    def test_merge_refuses_path_outside_worktrees(self, monkeypatch, tmp_path):
        evil = tmp_path / "evil"
        evil.mkdir(exist_ok=True)
        state = _ok_state("w1", evil)
        monkeypatch.setattr(worktree, "_load_state", lambda: state)
        monkeypatch.setattr(worktree, "_save_state", lambda s: None)
        monkeypatch.setattr(worktree, "_update_session_state_worktrees", lambda *a, **k: None)
        monkeypatch.setattr(worktree, "WORKTREE_DIR", REPO_ROOT / ".worktrees")
        rc = worktree.cmd_merge("w1")
        assert rc == 1
        assert state["worktrees"]["w1"]["status"] == "path-error"

    def test_merge_does_not_rmtree_outside(self, monkeypatch, tmp_path):
        import shutil
        evil = tmp_path / "evil"
        evil.mkdir(exist_ok=True)
        state = _ok_state("w1", evil)
        monkeypatch.setattr(worktree, "_load_state", lambda: state)
        monkeypatch.setattr(worktree, "_save_state", lambda s: None)
        monkeypatch.setattr(worktree, "WORKTREE_DIR", REPO_ROOT / ".worktrees")
        fake_rmtree = None

        def boom(*a, **k):
            nonlocal fake_rmtree
            fake_rmtree = True

        monkeypatch.setattr(shutil, "rmtree", boom)
        worktree.cmd_merge("w1")
        assert fake_rmtree is None

    def test_remove_refuses_path_outside_worktrees(self, monkeypatch, tmp_path):
        evil = tmp_path / "evil"
        evil.mkdir(exist_ok=True)
        state = _ok_state("w1", evil)
        monkeypatch.setattr(worktree, "_load_state", lambda: state)
        monkeypatch.setattr(worktree, "_save_state", lambda s: None)
        monkeypatch.setattr(worktree, "WORKTREE_DIR", REPO_ROOT / ".worktrees")
        rc = worktree.cmd_remove("w1")
        assert rc == 1
        assert state["worktrees"]["w1"]["status"] == "path-error"

    def test_merge_inside_still_works(self, monkeypatch, tmp_path):
        wt = (REPO_ROOT / ".worktrees").resolve()
        inside = wt / "builder-a"
        inside.mkdir(parents=True, exist_ok=True)
        state = _ok_state("w1", inside)
        monkeypatch.setattr(worktree, "_load_state", lambda: state)
        monkeypatch.setattr(worktree, "_save_state", lambda s: None)
        monkeypatch.setattr(worktree, "_update_session_state_worktrees", lambda *a, **k: None)
        monkeypatch.setattr(worktree, "WORKTREE_DIR", wt)
        monkeypatch.setattr(worktree, "_git", lambda *a, **k: (0, "main", ""))
        rc = worktree.cmd_merge("w1")
        assert rc == 0  # path guard không chặn path hợp lệ trong .worktrees
        assert "w1" not in state["worktrees"]


class TestWorktreeLifecycle:
    """Happy-path lifecycle với git repo thật (tmp) — create/list/merge/remove/clean/main."""

    @pytest.fixture
    def wt_env(self, tmp_path, monkeypatch):
        import subprocess as sp
        repo = tmp_path / "repo"
        repo.mkdir()
        git = ["git", "-c", "user.email=t@test", "-c", "user.name=t"]
        sp.run(git + ["init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        sp.run(git + ["commit", "--allow-empty", "-m", "init"], cwd=repo, check=True, capture_output=True)
        wt = repo / ".worktrees"
        wt.mkdir()
        monkeypatch.setattr(worktree, "WORKTREE_DIR", wt)
        monkeypatch.setattr(worktree, "WORKTREE_STATE", wt / ".worktree_state.json")
        real_git = worktree._git
        monkeypatch.setattr(worktree, "_git", lambda *a, **k: real_git(*a, cwd=repo, **k))
        return repo

    def test_create_list_merge_remove(self, wt_env, capsys):
        assert worktree.cmd_create("builder-a") == 0
        state = worktree._load_state()
        assert "builder-a" in state["worktrees"]
        assert state["worktrees"]["builder-a"]["status"] == "active"
        assert (wt_env / ".worktrees" / "builder-a").exists()

        assert worktree.cmd_list() == 0
        out = capsys.readouterr().out
        assert "builder-a" in out

        assert worktree.cmd_merge("builder-a") == 0
        assert "builder-a" not in worktree._load_state()["worktrees"]

        assert worktree.cmd_create("builder-b") == 0
        assert worktree.cmd_remove("builder-b") == 0
        assert "builder-b" not in worktree._load_state()["worktrees"]

    def test_create_duplicate_returns_1(self, wt_env):
        assert worktree.cmd_create("dup") == 0
        assert worktree.cmd_create("dup") == 1

    def test_merge_missing_returns_1(self, wt_env):
        assert worktree.cmd_merge("nope") == 1

    def test_clean_empty_and_with_entries(self, wt_env, capsys):
        assert worktree.cmd_clean() == 0
        capsys.readouterr()
        assert worktree.cmd_create("c1") == 0
        assert worktree.cmd_clean() == 0
        assert worktree._load_state()["worktrees"] == {}

    def test_main_cli_dispatch(self, wt_env, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["worktree.py", "create", "cli-worker"])
        assert worktree.main() == 0
        monkeypatch.setattr(sys, "argv", ["worktree.py", "list"])
        assert worktree.main() == 0
        monkeypatch.setattr(sys, "argv", ["worktree.py", "remove", "cli-worker"])
        assert worktree.main() == 0
        monkeypatch.setattr(sys, "argv", ["worktree.py", "clean"])
        assert worktree.main() == 0
