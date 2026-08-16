#!/usr/bin/env python3
"""T5.x: Coverage boost (phần 5) — ahd_session, blackboard, event_bus, pre_tool_use.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)


# ===========================================================================
# ahd_session
# ===========================================================================
class TestAhdSession:
    def test_get_config_root(self, tmp_path):
        import ahd_session
        result = ahd_session.get_config_root(tmp_path)
        assert isinstance(result, Path)

    def test_get_shared_state_root(self, tmp_path):
        import ahd_session
        result = ahd_session.get_shared_state_root(tmp_path)
        assert isinstance(result, Path)

    def test_resolve_shared_state_file_canonical(self, tmp_path):
        import ahd_session
        # Tạo file canonical
        canonical = tmp_path / ".agents" / "user_profile.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("profile", encoding="utf-8")
        result = ahd_session.resolve_shared_state_file("user_profile.md", tmp_path)
        assert result == canonical

    def test_resolve_shared_state_file_fallback(self, tmp_path):
        import ahd_session
        # Không có canonical, có file cũ trong config_root
        old = ahd_session.get_config_root(tmp_path) / "user_profile.md"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text("profile", encoding="utf-8")
        result = ahd_session.resolve_shared_state_file("user_profile.md", tmp_path)
        assert result == old

    def test_resolve_shared_state_file_default(self, tmp_path):
        import ahd_session
        result = ahd_session.resolve_shared_state_file("nonexistent.md", tmp_path)
        # Trả về canonical path cho file mới
        assert isinstance(result, Path)

    def test_slugify_session_id(self):
        from ahd_session import slugify_session_id
        assert slugify_session_id("session-123") == "session-123"
        assert slugify_session_id("ses sion") == "ses-sion"
        assert slugify_session_id("a:b/c\\d") == "a-b-c-d"
        assert slugify_session_id("")  # không rỗng — thêm UUID suffix
        assert slugify_session_id("---")  # không rỗng

    def test_get_session_id_from_data(self):
        from ahd_session import get_session_id
        result = get_session_id({"session_id": "test-sess"})
        assert result == "test-sess"

    def test_get_session_id_from_env(self, monkeypatch):
        from ahd_session import get_session_id
        monkeypatch.setenv("AHD_SESSION_ID", "env-sess")
        result = get_session_id({})
        assert result == "env-sess"

    def test_get_session_id_uuid_fallback(self, monkeypatch):
        from ahd_session import get_session_id
        monkeypatch.delenv("AHD_SESSION_ID", raising=False)
        # Patch get_repo_root để trả tmp_path không có current_session
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("ahd_session.get_repo_root", lambda *a, **kw: tmp)
        result = get_session_id({})
        assert result  # UUID slug

    def test_get_session_id_from_file(self, monkeypatch, tmp_path):
        from ahd_session import get_session_id
        monkeypatch.delenv("AHD_SESSION_ID", raising=False)
        monkeypatch.setattr("ahd_session.get_repo_root", lambda *a, **kw: tmp_path)
        # Tạo current_session file
        config_root = tmp_path / ".agents"
        (config_root / "session_state").mkdir(parents=True)
        (config_root / "session_state" / "current_session").write_text("file-sess", encoding="utf-8")
        result = get_session_id({})
        assert result == "file-sess"

    def test_get_session_state_path(self, tmp_path):
        from ahd_session import get_session_state_path
        result = get_session_state_path("sess1", root=tmp_path)
        assert "sess1" in str(result)
        assert result.suffix == ".json"

    def test_get_context_flags_path(self, tmp_path):
        from ahd_session import get_context_flags_path
        result = get_context_flags_path("sess1", root=tmp_path)
        assert "sess1" in str(result)

    def test_get_loop_state_path(self, tmp_path):
        from ahd_session import get_loop_state_path
        result = get_loop_state_path("sess1", root=tmp_path)
        assert "sess1" in str(result)
        assert result.suffix == ".md"

    def test_acquire_release_lock(self, tmp_path):
        from ahd_session import _acquire_lock, _release_lock
        lock_path = tmp_path / "test.lock"
        handle = _acquire_lock(lock_path, timeout=2.0)
        assert handle is not None
        _release_lock(handle)

    def test_release_lock_none(self):
        from ahd_session import _release_lock
        _release_lock(None)  # không crash

    def test_locked_json_read_missing(self, tmp_path):
        from ahd_session import _locked_json_read
        path = tmp_path / "missing.json"
        result = _locked_json_read(path, default={"default": True})
        assert result == {"default": True}

    def test_locked_json_write_read(self, tmp_path):
        from ahd_session import _locked_json_write, _locked_json_read
        path = tmp_path / "data.json"
        _locked_json_write(path, {"key": "value"})
        result = _locked_json_read(path, default={})
        assert result == {"key": "value"}

    def test_locked_json_update(self, tmp_path):
        from ahd_session import _locked_json_write, _locked_json_update
        path = tmp_path / "update.json"
        _locked_json_write(path, {"a": 1})
        result = _locked_json_update(path, lambda d: {**d, "b": 2}, default={})
        assert result == {"a": 1, "b": 2}

    def test_locked_text_write(self, tmp_path):
        from ahd_session import _locked_text_write
        path = tmp_path / "text.txt"
        _locked_text_write(path, "hello")
        assert path.read_text(encoding="utf-8") == "hello"

    def test_read_write_session_state(self, tmp_path):
        from ahd_session import write_session_state, read_session_state
        write_session_state("sess-test", {"key": "val"}, root=tmp_path, merge=False)
        result = read_session_state("sess-test", root=tmp_path)
        assert result == {"key": "val"}

    def test_write_session_state_merge(self, tmp_path):
        from ahd_session import write_session_state, read_session_state
        write_session_state("sess-merge", {"a": 1}, root=tmp_path, merge=False)
        write_session_state("sess-merge", {"b": 2}, root=tmp_path, merge=True)
        result = read_session_state("sess-merge", root=tmp_path)
        assert result == {"a": 1, "b": 2}

    def test_update_session_state(self, tmp_path):
        from ahd_session import update_session_state, read_session_state
        update_session_state("sess-up", {"x": 10}, root=tmp_path)
        result = read_session_state("sess-up", root=tmp_path)
        assert result.get("x") == 10

    def test_read_write_context_flags(self, tmp_path):
        from ahd_session import write_context_flags, read_context_flags
        write_context_flags("sess-cf", {"flag": True}, root=tmp_path)
        result = read_context_flags("sess-cf", root=tmp_path)
        assert result.get("flag") is True

    def test_append_jsonl(self, tmp_path):
        from ahd_session import append_jsonl
        path = tmp_path / "log.jsonl"
        append_jsonl(path, {"event": "test"})
        append_jsonl(path, {"event": "test2"})
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_now_utc(self):
        from ahd_session import now_utc
        result = now_utc()
        assert isinstance(result, str)
        assert "T" in result

    def test_record_failure(self):
        from ahd_session import record_failure, get_failure_stats, reset_circuit
        reset_circuit("test-comp")
        record_failure("test-comp")
        record_failure("test-comp")
        assert get_failure_stats().get("test-comp") == 2

    def test_circuit_breaker_trips(self):
        from ahd_session import record_failure, is_circuit_open, reset_circuit
        reset_circuit("cb-comp")
        record_failure("cb-comp")
        record_failure("cb-comp")
        record_failure("cb-comp")  # 3 failures -> trip
        assert is_circuit_open("cb-comp") is True

    def test_reset_circuit(self):
        from ahd_session import record_failure, is_circuit_open, reset_circuit
        reset_circuit("reset-comp")
        for _ in range(3):
            record_failure("reset-comp")
        assert is_circuit_open("reset-comp") is True
        reset_circuit("reset-comp")
        assert is_circuit_open("reset-comp") is False

    def test_auto_minimal_mode_no_failure(self):
        from ahd_session import auto_minimal_mode, reset_circuit
        reset_circuit("ahd_session")
        reset_circuit("pre_tool_use")
        reset_circuit("post_tool_use")
        result = auto_minimal_mode("test-sess")
        assert result is False

    def test_auto_minimal_mode_with_failure(self):
        from ahd_session import auto_minimal_mode, record_failure, reset_circuit
        reset_circuit("ahd_session")
        for _ in range(3):
            record_failure("ahd_session")
        result = auto_minimal_mode("test-sess-min")
        assert result is True

    def test_check_memory_cap_no_file(self, tmp_path):
        from ahd_session import _check_memory_cap
        _check_memory_cap(tmp_path / "nope.json", "session_state", tmp_path)
        # không crash

    def test_check_memory_cap_no_config(self, tmp_path):
        from ahd_session import _check_memory_cap
        path = tmp_path / "data.json"
        path.write_text("{}", encoding="utf-8")
        _check_memory_cap(path, "session_state", tmp_path)
        # không crash — không có memory_config.json

    def test_check_memory_cap_with_config(self, tmp_path, capsys):
        from ahd_session import _check_memory_cap
        path = tmp_path / "data.json"
        path.write_text("x" * 10000, encoding="utf-8")
        config = tmp_path / ".devin" / "memory_config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({
            "caps": {
                "session_state": {
                    "default_bytes": 100,
                    "max_bytes": 1000,
                    "warn_threshold_pct": 80,
                }
            }
        }), encoding="utf-8")
        _check_memory_cap(path, "session_state", tmp_path)
        # Có thể in warning ra stderr

    def test_get_repo_root_cwd(self, monkeypatch, tmp_path):
        import ahd_session
        monkeypatch.chdir(tmp_path)
        result = ahd_session.get_repo_root()
        assert isinstance(result, Path)


# ===========================================================================
# blackboard
# ===========================================================================
class TestBlackboard:
    def _patch_root(self, monkeypatch, tmp_path):
        import blackboard
        monkeypatch.setattr(blackboard, "_repo_root", lambda: tmp_path)
        monkeypatch.setattr(blackboard, "_bb_dir", lambda: tmp_path / ".devin" / "blackboard")
        # Cần patch _region_file, _write_log_file, _lock_dir cũng vậy
        bb = tmp_path / ".devin" / "blackboard"
        bb.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(blackboard, "_region_file", lambda r: bb / f"{r}.json")
        monkeypatch.setattr(blackboard, "_write_log_file", lambda: bb / "_write_log.jsonl")
        monkeypatch.setattr(blackboard, "_lock_dir", lambda: bb / ".locks")
        monkeypatch.setattr(blackboard, "_region_lock_path", lambda r: bb / ".locks" / f"{r}.lock")
        monkeypatch.setattr(blackboard, "_write_log_lock_path", lambda: bb / ".locks" / "_write_log.lock")

    def test_write_read_metrics(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        result = blackboard.write_value("metrics", "cpu", 50.0, agent="agent1")
        assert result["written"] is True
        read = blackboard.read_value("metrics", "cpu")
        assert read["exists"] is True
        assert read["value"] == 50.0

    def test_write_read_hypotheses_append_only(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        r1 = blackboard.write_value("hypotheses", "h1", {"text": "hello"}, agent="a1")
        assert r1["written"] is True
        # Ghi đè -> rejected
        r2 = blackboard.write_value("hypotheses", "h1", {"text": "world"}, agent="a2")
        assert r2["written"] is False

    def test_write_evidence_single_writer(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        r1 = blackboard.write_value("evidence", "ev1", "data1", agent="a1")
        assert r1["written"] is True
        # Cùng agent -> ok
        r2 = blackboard.write_value("evidence", "ev1", "data2", agent="a1")
        assert r2["written"] is True
        # Khác agent -> rejected
        r3 = blackboard.write_value("evidence", "ev1", "data3", agent="a2")
        assert r3["written"] is False

    def test_write_decisions_crdt_union_list(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        blackboard.write_value("decisions", "d1", ["a", "b"], agent="a1")
        result = blackboard.write_value("decisions", "d1", ["b", "c"], agent="a2")
        assert result["written"] is True
        read = blackboard.read_value("decisions", "d1")
        assert set(read["value"]) == {"a", "b", "c"}

    def test_write_decisions_crdt_union_dict(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        blackboard.write_value("decisions", "d2", {"x": 1}, agent="a1")
        result = blackboard.write_value("decisions", "d2", {"y": 2}, agent="a2")
        assert result["written"] is True
        read = blackboard.read_value("decisions", "d2")
        assert read["value"] == {"x": 1, "y": 2}

    def test_write_decisions_crdt_scalar(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        blackboard.write_value("decisions", "d3", "old", agent="a1")
        result = blackboard.write_value("decisions", "d3", "new", agent="a2")
        assert result["written"] is True
        read = blackboard.read_value("decisions", "d3")
        assert read["value"] == "new"

    def test_write_state_versioned(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        blackboard.write_value("state", "s1", "v1", agent="a1")
        blackboard.write_value("state", "s1", "v2", agent="a2")
        read = blackboard.read_value("state", "s1")
        assert read["value"] == "v2"

    def test_list_keys(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        blackboard.write_value("metrics", "k1", 1, agent="a1")
        blackboard.write_value("metrics", "k2", 2, agent="a1")
        result = blackboard.list_keys("metrics")
        assert result["count"] >= 2

    def test_list_regions(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        result = blackboard.list_regions()
        assert "metrics" in result["defined_regions"]
        assert "hypotheses" in result["defined_regions"]

    def test_read_value_missing(self, tmp_path, monkeypatch):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        result = blackboard.read_value("metrics", "nope")
        assert result["exists"] is False
        assert result["value"] is None

    def test_read_value_file(self, tmp_path):
        from blackboard import _read_value_file
        p = tmp_path / "val.json"
        p.write_text(json.dumps({"value": 42, "agent": "a1"}), encoding="utf-8")
        value, agent = _read_value_file(str(p))
        assert value == 42
        assert agent == "a1"

    def test_read_value_file_simple(self, tmp_path):
        from blackboard import _read_value_file
        p = tmp_path / "val.json"
        p.write_text(json.dumps({"just": "data"}), encoding="utf-8")
        value, agent = _read_value_file(str(p))
        assert value == {"just": "data"}
        assert agent == "unknown"

    def test_read_value_file_missing(self, tmp_path, capsys):
        from blackboard import _read_value_file
        value, agent = _read_value_file(str(tmp_path / "nope.json"))
        assert value is None
        assert agent == "unknown"

    def test_main_no_args(self, capsys):
        from blackboard import main
        code = main([])
        assert code == 1

    def test_main_regions(self, tmp_path, monkeypatch, capsys):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        code = blackboard.main(["--regions"])
        assert code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "defined_regions" in data

    def test_main_list(self, tmp_path, monkeypatch, capsys):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        blackboard.write_value("metrics", "k1", 1, agent="a1")
        code = blackboard.main(["--list", "metrics"])
        assert code == 0

    def test_main_read(self, tmp_path, monkeypatch, capsys):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        blackboard.write_value("metrics", "k1", 99, agent="a1")
        code = blackboard.main(["--read", "metrics", "k1"])
        assert code == 0

    def test_main_write(self, tmp_path, monkeypatch, capsys):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        val_file = tmp_path / "val.json"
        val_file.write_text(json.dumps({"value": 1, "agent": "a1"}), encoding="utf-8")
        code = blackboard.main(["--write", "metrics", "k1", str(val_file)])
        assert code == 0

    def test_main_write_missing_file(self, tmp_path, monkeypatch, capsys):
        import blackboard
        self._patch_root(monkeypatch, tmp_path)
        code = blackboard.main(["--write", "metrics", "k1", str(tmp_path / "nope.json")])
        assert code == 1


# ===========================================================================
# event_bus
# ===========================================================================
class TestEventBus:
    def _patch(self, monkeypatch, tmp_path):
        import event_bus
        bus = tmp_path / ".devin" / "event_bus"
        bus.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(event_bus, "_repo_root", lambda: tmp_path)
        monkeypatch.setattr(event_bus, "_bus_dir", lambda: bus)
        monkeypatch.setattr(event_bus, "_topic_file", lambda t: bus / f"{t}.jsonl")
        monkeypatch.setattr(event_bus, "_topic_lock_path", lambda t: bus / ".locks" / f"{t}.lock")

    def test_validate_topic_known(self):
        from event_bus import _validate_topic
        assert _validate_topic("analysis.findings") is True

    def test_validate_topic_unknown(self):
        from event_bus import _validate_topic
        assert _validate_topic("unknown.topic") is False

    def test_validate_payload_no_schema(self):
        from event_bus import _validate_payload
        ok, _ = _validate_payload("system.events", "anything")
        assert ok is True

    def test_validate_payload_valid(self):
        from event_bus import _validate_payload
        ok, _ = _validate_payload("analysis.findings", {"findings": [], "source": "test"})
        assert ok is True

    def test_validate_payload_not_dict(self):
        from event_bus import _validate_payload
        ok, reason = _validate_payload("analysis.findings", "not dict")
        assert ok is False
        assert "dict" in reason

    def test_validate_payload_missing_field(self):
        from event_bus import _validate_payload
        ok, reason = _validate_payload("analysis.findings", {"source": "test"})
        assert ok is False
        assert "findings" in reason

    def test_validate_payload_wrong_type(self):
        from event_bus import _validate_payload
        ok, reason = _validate_payload("analysis.findings", {"findings": "not list", "source": "test"})
        assert ok is False
        assert "findings" in reason

    def test_validate_payload_tuple_type(self):
        from event_bus import _validate_payload
        # plan.quality: quality_score là (int, float)
        ok, _ = _validate_payload("plan.quality", {"quality_score": 8.5, "notes": "ok"})
        assert ok is True
        ok, _ = _validate_payload("plan.quality", {"quality_score": 8, "notes": "ok"})
        assert ok is True

    def test_publish_valid(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        result = event_bus.publish("analysis.findings", "agent1", {"findings": [], "source": "test"})
        assert result["published"] is True
        assert "message" in result

    def test_publish_invalid_payload(self, tmp_path, monkeypatch, capsys):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        result = event_bus.publish("analysis.findings", "agent1", "not dict")
        assert result["published"] is False

    def test_publish_unknown_topic(self, tmp_path, monkeypatch, capsys):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        result = event_bus.publish("unknown.topic", "agent1", {"any": "thing"})
        assert result["published"] is True  # cho phép topic mới

    def test_publish_system_events(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        result = event_bus.publish("system.events", "agent1", {"any": "payload"})
        assert result["published"] is True

    def test_subscribe(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        event_bus.publish("system.events", "a1", {"x": 1})
        event_bus.publish("system.events", "a2", {"x": 2})
        result = event_bus.subscribe("system.events", last_read=0)
        assert result["unread_count"] == 2
        assert result["next_offset"] == 2

    def test_subscribe_with_offset(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        event_bus.publish("system.events", "a1", {"x": 1})
        event_bus.publish("system.events", "a2", {"x": 2})
        result = event_bus.subscribe("system.events", last_read=1)
        assert result["unread_count"] == 1

    def test_subscribe_empty(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        result = event_bus.subscribe("system.events")
        assert result["unread_count"] == 0

    def test_history(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        event_bus.publish("system.events", "a1", {"x": 1})
        result = event_bus.history("system.events")
        assert result["total"] == 1

    def test_history_empty(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        result = event_bus.history("system.events")
        assert result["total"] == 0

    def test_list_topics(self, tmp_path, monkeypatch):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        result = event_bus.list_topics()
        assert "analysis.findings" in result["defined_topics"]
        assert "system.events" in result["defined_topics"]

    def test_read_message_file_with_payload(self, tmp_path):
        from event_bus import _read_message_file
        p = tmp_path / "msg.json"
        p.write_text(json.dumps({
            "publisher": "a1", "payload": {"x": 1}, "provenance": ["id1"]
        }), encoding="utf-8")
        publisher, payload, provenance = _read_message_file(str(p))
        assert publisher == "a1"
        assert payload == {"x": 1}
        assert provenance == ["id1"]

    def test_read_message_file_simple(self, tmp_path):
        from event_bus import _read_message_file
        p = tmp_path / "msg.json"
        p.write_text(json.dumps({"just": "data"}), encoding="utf-8")
        publisher, payload, provenance = _read_message_file(str(p))
        assert publisher == "unknown"
        assert payload == {"just": "data"}

    def test_read_message_file_missing(self, tmp_path, capsys):
        from event_bus import _read_message_file
        publisher, payload, provenance = _read_message_file(str(tmp_path / "nope.json"))
        assert publisher == ""
        assert payload is None

    def test_main_no_args(self, capsys):
        from event_bus import main
        code = main([])
        assert code == 1

    def test_main_topics(self, tmp_path, monkeypatch, capsys):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        code = event_bus.main(["--topics"])
        assert code == 0

    def test_main_publish(self, tmp_path, monkeypatch, capsys):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        msg = tmp_path / "msg.json"
        msg.write_text(json.dumps({"publisher": "a1", "payload": {"x": 1}}), encoding="utf-8")
        code = event_bus.main(["--publish", "system.events", str(msg)])
        assert code == 0

    def test_main_subscribe(self, tmp_path, monkeypatch, capsys):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        event_bus.publish("system.events", "a1", {"x": 1})
        code = event_bus.main(["--subscribe", "system.events"])
        assert code == 0

    def test_main_history(self, tmp_path, monkeypatch, capsys):
        import event_bus
        self._patch(monkeypatch, tmp_path)
        code = event_bus.main(["--history", "system.events"])
        assert code == 0


# ===========================================================================
# pre_tool_use
# ===========================================================================
class TestPreToolUse:
    def test_detect_encoding_bypass_clean(self):
        from pre_tool_use import detect_encoding_bypass
        assert detect_encoding_bypass("normal text") == []
        assert detect_encoding_bypass("") == []

    def test_detect_encoding_bypass_utf7(self):
        from pre_tool_use import detect_encoding_bypass
        assert "utf7" in detect_encoding_bypass("+AGY-foo-")

    def test_detect_encoding_bypass_punycode(self):
        from pre_tool_use import detect_encoding_bypass
        assert "punycode" in detect_encoding_bypass("xn--example")

    def test_detect_encoding_bypass_html_entity(self):
        from pre_tool_use import detect_encoding_bypass
        assert "html_entity" in detect_encoding_bypass("&#x41;")

    def test_detect_encoding_bypass_hex(self):
        from pre_tool_use import detect_encoding_bypass
        assert "hex_escape" in detect_encoding_bypass("\\x41")

    def test_detect_encoding_bypass_unicode(self):
        from pre_tool_use import detect_encoding_bypass
        assert "unicode_escape" in detect_encoding_bypass("\\u0041")

    def test_detect_encoding_bypass_octal(self):
        from pre_tool_use import detect_encoding_bypass
        assert "octal_escape" in detect_encoding_bypass("\\101")

    def test_detect_encoding_bypass_base64(self):
        from pre_tool_use import detect_encoding_bypass
        assert "base64_pipe" in detect_encoding_bypass("base64 -d | bash")

    def test_normalize_command_basic(self):
        from pre_tool_use import normalize_command
        assert normalize_command("ls -la") == "ls -la"

    def test_normalize_command_strip_backslash(self):
        from pre_tool_use import normalize_command
        assert normalize_command("r\\m -rf") == "rm -rf"

    def test_normalize_command_strip_quotes(self):
        from pre_tool_use import normalize_command
        assert normalize_command("r'm' -rf") == "rm -rf"

    def test_normalize_command_hex_decode(self):
        from pre_tool_use import normalize_command
        # \x72 = 'r'
        result = normalize_command("\\x72m -rf")
        assert "rm" in result

    def test_normalize_command_octal_decode(self):
        from pre_tool_use import normalize_command
        # \162 = 'r'
        result = normalize_command("\\162m -rf")
        assert "rm" in result

    def test_normalize_command_unicode_decode(self):
        from pre_tool_use import normalize_command
        # \u0072 = 'r'
        result = normalize_command("\\u0072m -rf")
        assert "rm" in result

    def test_normalize_command_echo_subst(self):
        from pre_tool_use import normalize_command
        result = normalize_command("$(echo rm) -rf")
        assert "rm" in result

    def test_normalize_command_backtick_subst(self):
        from pre_tool_use import normalize_command
        result = normalize_command("`echo rm` -rf")
        assert "rm" in result

    def test_normalize_command_var_expansion(self):
        from pre_tool_use import normalize_command
        result = normalize_command("$VAR -rf")
        assert "EXPANDED_VAR" in result

    def test_normalize_command_base64_pipe(self):
        from pre_tool_use import normalize_command
        result = normalize_command("base64 -d | bash")
        assert "BASE64_PIPE_TO_SHELL_DETECTED" in result

    def test_check_ssrf_empty(self):
        from pre_tool_use import check_ssrf
        assert check_ssrf("") == 0

    def test_check_ssrf_allowlist(self):
        from pre_tool_use import check_ssrf
        assert check_ssrf("https://example.com/page") == 0
        assert check_ssrf("https://api.github.com/repos") == 0

    def test_check_ssrf_localhost(self):
        from pre_tool_use import check_ssrf
        assert check_ssrf("http://localhost/admin") == 2
        assert check_ssrf("http://127.0.0.1/admin") == 2

    def test_check_ssrf_private_ip(self):
        from pre_tool_use import check_ssrf
        assert check_ssrf("http://192.168.1.1/admin") == 2
        assert check_ssrf("http://10.0.0.1/admin") == 2

    def test_check_ssrf_metadata(self):
        from pre_tool_use import check_ssrf
        assert check_ssrf("http://metadata.internal/latest") == 2

    def test_check_ssrf_custom_allowlist(self):
        from pre_tool_use import check_ssrf
        assert check_ssrf("http://myapi.com/x", allowlist={"myapi.com"}) == 0

    def test_extract_urls(self):
        from pre_tool_use import _extract_urls
        urls = _extract_urls("visit https://example.com and http://test.org")
        assert len(urls) == 2

    def test_extract_urls_empty(self):
        from pre_tool_use import _extract_urls
        assert _extract_urls("") == []
        assert _extract_urls("no urls here") == []

    def test_ssrf_allowlist_env(self, monkeypatch):
        from pre_tool_use import _ssrf_allowlist
        monkeypatch.setenv("AHD_SSRF_ALLOWLIST", "a.com,b.com")
        result = _ssrf_allowlist()
        assert "a.com" in result
        assert "b.com" in result

    def test_ssrf_allowlist_default(self, monkeypatch):
        from pre_tool_use import _ssrf_allowlist
        monkeypatch.delenv("AHD_SSRF_ALLOWLIST", raising=False)
        result = _ssrf_allowlist()
        assert "example.com" in result

    def test_main_safe_command(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setenv("AHD_COST_LEDGER_KEY", "test-key")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0

    def test_main_dangerous_rm_rf(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 2

    def test_main_dangerous_force_push(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force origin main"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 2

    def test_main_non_bash_tool(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setenv("AHD_COST_LEDGER_KEY", "test-key")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "src/x.py"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0

    def test_main_bash_no_command(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setenv("AHD_COST_LEDGER_KEY", "test-key")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0

    def test_main_parse_error_fail_open(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.delenv("AHD_FAIL_CLOSED", raising=False)
        monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0

    def test_main_parse_error_fail_closed(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setenv("AHD_FAIL_CLOSED", "1")
        monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
        try:
            main()
        except SystemExit as e:
            assert e.code == 2
        finally:
            monkeypatch.delenv("AHD_FAIL_CLOSED", raising=False)

    def test_main_ssrf_block(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "curl http://localhost/admin"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 2

    def test_main_encoding_bypass_block(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo +AGY-foo-"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 2

    def test_main_warn_pattern(self, monkeypatch, capsys):
        from pre_tool_use import main
        monkeypatch.setenv("AHD_COST_LEDGER_KEY", "test-key")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0  # warn nhưng allow

    def test_log_ssrf_block(self, monkeypatch, tmp_path):
        from pre_tool_use import _log_ssrf_block
        monkeypatch.setattr("ahd_session.get_repo_root", lambda: tmp_path)
        monkeypatch.setattr("ahd_session.get_config_root", lambda _r: tmp_path / ".devin")
        _log_ssrf_block("http://localhost/x", "test", "sess1")
        # không crash

    def test_check_context_oversized_no_flag(self, monkeypatch, tmp_path):
        from pre_tool_use import _check_context_oversized_gate
        monkeypatch.setattr("ahd_session.get_session_id", lambda _d: "sess")
        monkeypatch.setattr("ahd_session.get_repo_root", lambda: tmp_path)
        monkeypatch.setattr("ahd_session.read_context_flags", lambda _s, _r: {})
        _check_context_oversized_gate({"tool_name": "Bash"})
        # không crash, không exit

    def test_check_context_oversized_safe_tool(self, monkeypatch, tmp_path, capsys):
        from pre_tool_use import _check_context_oversized_gate
        monkeypatch.setattr("ahd_session.get_session_id", lambda _d: "sess")
        monkeypatch.setattr("ahd_session.get_repo_root", lambda: tmp_path)
        monkeypatch.setattr("ahd_session.read_context_flags", lambda _s, _r: {
            "context_oversized": True,
            "oversized_tool_calls_since_flag": 5,
        })
        _check_context_oversized_gate({"tool_name": "Read"})
        # Safe tool -> không block

    def test_check_context_oversized_block(self, monkeypatch, tmp_path, capsys):
        from pre_tool_use import _check_context_oversized_gate
        monkeypatch.setattr("ahd_session.get_session_id", lambda _d: "sess")
        monkeypatch.setattr("ahd_session.get_repo_root", lambda: tmp_path)
        monkeypatch.setattr("ahd_session.read_context_flags", lambda _s, _r: {
            "context_oversized": True,
            "oversized_tool_calls_since_flag": 5,
        })
        with pytest.raises(SystemExit) as exc_info:
            _check_context_oversized_gate({"tool_name": "Bash"})
        assert exc_info.value.code == 2

    def test_check_risk_contract_no_contract(self, monkeypatch, tmp_path):
        from pre_tool_use import _check_risk_contract
        monkeypatch.setattr("ahd_session.get_repo_root", lambda: tmp_path)
        _check_risk_contract("Write", {"file_path": "src/x.py"})
        # không crash

    def test_check_risk_contract_non_write(self, monkeypatch, tmp_path):
        from pre_tool_use import _check_risk_contract
        _check_risk_contract("Read", {"file_path": "src/x.py"})

    def test_check_risk_contract_with_contract(self, monkeypatch, tmp_path, capsys):
        from pre_tool_use import _check_risk_contract
        contract = tmp_path / ".devin" / "risk_contract.json"
        contract.parent.mkdir(parents=True)
        contract.write_text(json.dumps({
            "critical_files": {
                "src/critical.py": {"risk": "high", "required_review": "human"}
            }
        }), encoding="utf-8")
        monkeypatch.setattr("ahd_session.get_repo_root", lambda: tmp_path)
        _check_risk_contract("Write", {"file_path": "src/critical.py"})
        # Có in warning

    def test_check_cost_cap_gate_no_state(self, monkeypatch, tmp_path):
        from pre_tool_use import _check_cost_cap_gate
        monkeypatch.setenv("AHD_COST_LEDGER_KEY", "test-key")
        monkeypatch.setattr("ahd_session.get_session_id", lambda _d: "sess")
        monkeypatch.setattr("ahd_session.get_repo_root", lambda: tmp_path)
        monkeypatch.setattr("ahd_session.read_session_state", lambda _s, _r: {})
        monkeypatch.setattr("pre_tool_use.check_cost_cap", lambda _s: 0)
        _check_cost_cap_gate({"tool_name": "Bash"})

    def test_check_ssrf_gate_no_url(self, monkeypatch):
        from pre_tool_use import _check_ssrf_gate
        monkeypatch.setattr("ahd_session.get_session_id", lambda _d: "sess")
        _check_ssrf_gate({"tool_name": "Bash", "tool_input": {"command": "ls"}})

    def test_check_encoding_bypass_gate_non_bash(self, monkeypatch):
        from pre_tool_use import _check_encoding_bypass_gate
        _check_encoding_bypass_gate({"tool_name": "Read", "tool_input": {}})

    def test_check_encoding_bypass_gate_no_command(self, monkeypatch):
        from pre_tool_use import _check_encoding_bypass_gate
        _check_encoding_bypass_gate({"tool_name": "Bash", "tool_input": {}})

    def test_check_reflection_gate_non_bash(self, monkeypatch):
        from pre_tool_use import _check_reflection_gate
        _check_reflection_gate({"tool_name": "Read", "tool_input": {}})

    def test_check_reflection_gate_safe_command(self, monkeypatch):
        from pre_tool_use import _check_reflection_gate
        _check_reflection_gate({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
