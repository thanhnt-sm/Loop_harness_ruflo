"""Coverage cho phần legacy/hardening của loop_memory_sync (U06/U13/U14/U21):
regenerate registry, fallback, front-matter, stale detection, archive, limits.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
HOOKS = SCRIPTS.parent / "hooks"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HOOKS))

import ahd_session  # noqa: E402
import loop_memory_sync as lms  # noqa: E402


def _mk_session(root: Path, sid: str, status: str, hb_ts: str) -> None:
    ahd_session.write_session_state(sid, {
        "session_id": sid,
        "status": status,
        "goal": f"goal {sid}",
        "last_heartbeat": hb_ts,
        "last_state_write": hb_ts,
        "tags": ["t1", "t2", "t3"],
        "owned_files": ["a.py", "b.py"],
    }, root)


def _fresh_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _old_ts() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()


class TestLoopMemoryHelpers:
    def test_parse_front_matter(self):
        assert lms._parse_front_matter("no fm") == {}
        assert lms._parse_front_matter("---\nno close") == {}
        fm = lms._parse_front_matter(
            "---\nstatus: completed\ngoal: \"x\"\ncount: 3\n---\nbody")
        assert fm["status"] == "completed"
        assert fm["goal"] == "x"
        assert fm["count"] == 3

    def test_read_loop_state_md(self, tmp_path):
        p = tmp_path / "nope.md"
        assert lms._read_loop_state_md(p) == ({}, "")
        f = tmp_path / "lstate.md"
        f.write_text("---\nstatus: in_progress\n---\n\nbody text", encoding="utf-8")
        fm, body = lms._read_loop_state_md(f)
        assert fm["status"] == "in_progress"
        assert "body text" in body

    def test_is_stale(self):
        assert lms._is_stale({}) is True
        assert lms._is_stale({"last_heartbeat": _fresh_ts()}) is False
        assert lms._is_stale({"last_state_write": _fresh_ts()}) is False
        assert lms._is_stale({"last_heartbeat": _old_ts()}) is True
        assert lms._is_stale({"last_heartbeat": "not-a-date"}) is True

    def test_write_fallback(self, tmp_path):
        _mk_session(tmp_path, "sess-a", "in_progress", _fresh_ts())
        lms._write_fallback(tmp_path, "registry_write", "boom")
        reg = tmp_path / ".agents" / "loop_state_fallback.md"
        assert reg.exists()
        assert "boom" in reg.read_text(encoding="utf-8")
        snap = tmp_path / ".agents" / "loop_state_fallback" / "sess-a.json"
        assert snap.exists()
        assert json.loads(snap.read_text(encoding="utf-8"))["session_id"] == "sess-a"


class TestLoopMemoryRegistry:
    def test_build_registry_and_stale_marking(self, tmp_path):
        _mk_session(tmp_path, "s1", "in_progress", _fresh_ts())
        _mk_session(tmp_path, "s2", "completed", _fresh_ts())
        _mk_session(tmp_path, "s3", "in_progress", _old_ts())  # stale
        # file json hỏng + current_session không tính
        bad = tmp_path / ".agents" / "session_state" / "broken.json"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("{oops", encoding="utf-8")
        ahd_session.write_session_state(
            "current_session", {"session_id": "current_session"}, tmp_path)
        sessions, active = lms._build_registry(tmp_path)
        assert len(active) == 2  # s1, s3 (stale -> suspected_crashed vẫn active)
        s3 = ahd_session.read_session_state("s3", tmp_path)
        assert s3.get("status") == "suspected_crashed"

    def test_enforce_active_session_limit(self, tmp_path):
        for i in range(1, 6):
            _mk_session(tmp_path, f"s{i}", "in_progress",
                        (datetime.now(timezone.utc) -
                         timedelta(minutes=i)).isoformat())
        sessions, _ = lms._build_registry(tmp_path)
        out = lms._enforce_active_session_limit(tmp_path, sessions)
        statuses = {s["session_id"]: s["status"] for s in out}
        assert statuses["s5"] == "queued"  # cũ nhất bị queue
        assert ahd_session.read_session_state("s5", tmp_path)["status"] == "queued"

    def test_regenerate_full_flow(self, tmp_path):
        _mk_session(tmp_path, "live", "in_progress", _fresh_ts())
        _mk_session(tmp_path, "done", "completed", _fresh_ts())
        lms.regenerate(tmp_path)
        reg = tmp_path / ".agents" / "loop_state.md"
        text = reg.read_text(encoding="utf-8")
        assert "active_sessions" in text
        assert "| live |" in text
        assert "| done |" in text

    def test_regenerate_set_status_completed(self, tmp_path):
        _mk_session(tmp_path, "task-x", "in_progress", _fresh_ts())
        lms.regenerate(tmp_path, "task-x", "completed")
        st = ahd_session.read_session_state("task-x", tmp_path)
        assert st["status"] == "completed"
        assert st.get("state_written") is True

    def test_archive_completed_flow(self, tmp_path):
        # 4 completed -> chỉ giữ 3 recent, cái cũ nhất bị archive
        for i in range(4):
            _mk_session(tmp_path, f"old-done-{i}", "completed",
                        (datetime.now(timezone.utc) -
                         timedelta(hours=i)).isoformat())
        loop_dir = tmp_path / ".agents" / "loop_state"
        loop_dir.mkdir(parents=True, exist_ok=True)
        for i in range(4):
            (loop_dir / f"old-done-{i}.md").write_text(
                "---\nstatus: completed\ngoal: g\n---\nbody", encoding="utf-8")
        lms.regenerate(tmp_path)
        archive = tmp_path / ".agents" / "loop_state_archive" / "old-done-3.md"
        assert archive.exists()
        # registry không còn liệt kê session bị archive
        text = (tmp_path / ".agents" / "loop_state.md").read_text(encoding="utf-8")
        assert "old-done-3" not in text

    def test_run_inline_ok(self, tmp_path):
        _mk_session(tmp_path, "inline", "in_progress", _fresh_ts())
        ok, err = lms.run_inline(tmp_path)
        assert ok is True and err == ""
        assert (tmp_path / ".agents" / "loop_state.md").exists()

    def test_cleanup_loop_state_dir(self, tmp_path):
        _mk_session(tmp_path, "c1", "completed", _fresh_ts())
        loop_dir = tmp_path / ".agents" / "loop_state"
        loop_dir.mkdir(parents=True, exist_ok=True)
        # Tạo nhiều hơn MAX_LOOP_STATE_FILES file completed cũ
        for i in range(12):
            (loop_dir / f"old{i}.md").write_text(
                f"---\nstatus: completed\ngoal: g{i}\n---\nbody", encoding="utf-8")
        lms.regenerate(tmp_path)
        remaining = [f for f in loop_dir.glob("*.md")]
        assert len(remaining) <= lms.MAX_LOOP_STATE_FILES
        assert len(list((tmp_path / ".agents" / "loop_state_archive").glob("*.md"))) >= 2

    def test_safe_regenerate_error_writes_fallback(self, tmp_path, monkeypatch):
        def boom(root, session_id="", status=""):
            raise RuntimeError("primary broke")

        monkeypatch.setattr(lms, "regenerate", boom)
        with pytest.raises(RuntimeError):
            lms._safe_regenerate(tmp_path)
        reg = tmp_path / ".agents" / "loop_state_fallback.md"
        assert reg.exists()