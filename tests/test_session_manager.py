#!/usr/bin/env python3
"""T2-02: Tests fail-closed cho session_manager._count_active_sessions.

Phủ:
- Đếm session active bình thường.
- Unexpected exception → fail-closed (return MAX_ACTIVE_SESSIONS) thay vì 0.
- cmd_init block khi đạt limit; tạo OK khi dưới limit.
- slugify chặn path traversal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402
import session_manager as sm  # noqa: E402


def _seed_session(tmp_path: Path, sid: str, status: str):
    cfg = tmp_path / "cfg"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "session_state").mkdir(parents=True, exist_ok=True)
    (cfg / "session_state" / f"{sid}.json").write_text(
        json.dumps({"session_id": sid, "status": status}), encoding="utf-8",
    )


@pytest.fixture
def cfg_root(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "session_state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sm.ahd_session, "get_config_root", lambda root: cfg)
    return cfg


class TestCountActive:
    def test_counts_only_active(self, cfg_root):
        _seed_session(cfg_root.parent, "s1", "in_progress")
        _seed_session(cfg_root.parent, "s2", "completed")
        _seed_session(cfg_root.parent, "s3", "crashed")
        assert sm._count_active_sessions(cfg_root.parent) == 2

    def test_empty_dir(self, cfg_root):
        assert sm._count_active_sessions(cfg_root.parent) == 0

    def test_fail_closed_on_unexpected_error(self, cfg_root, monkeypatch):
        _seed_session(cfg_root.parent, "s1", "in_progress")

        def boom(*a, **k):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(sm.json, "loads", boom)
        assert sm._count_active_sessions(cfg_root.parent) == sm.MAX_ACTIVE_SESSIONS

    def test_empty_when_config_root_missing(self, tmp_path, monkeypatch):
        # Session dir chưa tồn tại = chưa có session nào (trạng thái hợp lệ, không phải lỗi).
        monkeypatch.setattr(sm.ahd_session, "get_config_root", lambda root: tmp_path / "nope")
        assert sm._count_active_sessions(tmp_path) == 0


class TestCmdInit:
    def test_blocks_at_limit_without_force(self, cfg_root, monkeypatch):
        monkeypatch.setattr(sm, "_count_active_sessions", lambda root: sm.MAX_ACTIVE_SESSIONS)
        args = sm.argparse.Namespace(session_id="x", goal="", force=False,
                                     complexity="M", status=None)
        rc = sm.cmd_init(args)
        assert rc == 1

    def test_queues_at_limit_with_force(self, cfg_root, monkeypatch):
        monkeypatch.setattr(sm, "_count_active_sessions", lambda root: sm.MAX_ACTIVE_SESSIONS)
        args = sm.argparse.Namespace(session_id="x", goal="", force=True,
                                     complexity="M", status=None)
        rc = sm.cmd_init(args)
        assert rc == 0

    def test_creates_below_limit(self, cfg_root, monkeypatch):
        monkeypatch.setattr(sm, "_count_active_sessions", lambda root: 0)
        args = sm.argparse.Namespace(session_id="x", goal="", force=False,
                                     complexity="M", status=None)
        rc = sm.cmd_init(args)
        assert rc == 0


class TestSlugify:
    def test_prevents_traversal(self):
        assert "/" not in sm.ahd_session.slugify_session_id("../../etc/passwd")
        assert "\\" not in sm.ahd_session.slugify_session_id("..\\..\\etc")
        assert sm.ahd_session.slugify_session_id("..") != ".."

    def test_unknown_on_empty(self):
        s = sm.ahd_session.slugify_session_id("")
        assert s.startswith("unknown-")
