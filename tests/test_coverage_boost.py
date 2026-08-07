#!/usr/bin/env python3
"""T5.x: Coverage boost tests cho các module có coverage thấp.

Target các module có coverage < 60% để kéo tổng coverage lên 80%:
- coverage_enforce (13.9%)
- coverage_matrix (20.2%)
- plan_quality_check (23%)
- hook_integrity (27.7%)
- cost_tracker (28.7%)
- schema_gate (36.9%)
- checkpoint (36.4%)
- path_zones (54.1%)
- event_bus (48.1%)
- blackboard (49%)
- dag_executor (52.1%)
- artifact_registry (54.4%)
- ahd_session (43.7%)
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
# coverage_enforce
# ===========================================================================
class TestCoverageEnforce:
    def test_parse_plan_extracts_tasks(self, tmp_path):
        from coverage_enforce import _parse_plan
        plan = tmp_path / "PLAN.md"
        plan.write_text(
            "- [ ] T01: src/foo.py (functions: bar, baz)\n"
            "- [x] T02: scripts/util.py (functions: run)\n"
            "## T03 — src/qux.py (functions: quux)\n",
            encoding="utf-8",
        )
        result = _parse_plan(plan)
        assert result["plan_name"] == "PLAN"
        assert "T01" in result["tasks"]
        assert result["tasks"]["T01"]["file"] == "src/foo.py"
        assert result["tasks"]["T01"]["function"] == "bar"
        assert "bar" in result["tasks"]["T01"]["symbols"]
        assert "baz" in result["tasks"]["T01"]["symbols"]
        assert result["tasks"]["T01"]["status"] == "planned"
        assert result["tasks"]["T02"]["status"] == "executed"

    def test_parse_plan_missing_file(self, tmp_path):
        from coverage_enforce import _parse_plan
        result = _parse_plan(tmp_path / "nope.md")
        assert result["tasks"] == {}

    def test_parse_plan_empty_file(self, tmp_path):
        from coverage_enforce import _parse_plan
        plan = tmp_path / "empty.md"
        plan.write_text("", encoding="utf-8")
        result = _parse_plan(plan)
        assert result["tasks"] == {}

    def test_load_coverage_state_missing(self, tmp_path):
        from coverage_enforce import _load_coverage_state
        state = _load_coverage_state(tmp_path / "nope.json", "plan")
        assert state["plan_name"] == "plan"
        assert state["tasks"] == {}

    def test_load_coverage_state_corrupt(self, tmp_path):
        from coverage_enforce import _load_coverage_state
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        state = _load_coverage_state(p, "plan")
        assert state["tasks"] == {}

    def test_load_coverage_state_valid(self, tmp_path):
        from coverage_enforce import _load_coverage_state
        p = tmp_path / "ok.json"
        p.write_text(json.dumps({"plan_name": "p", "tasks": {"T1": {}}}), encoding="utf-8")
        state = _load_coverage_state(p, "plan")
        assert "T1" in state["tasks"]

    def test_save_coverage_state(self, tmp_path):
        from coverage_enforce import _save_coverage_state, _load_coverage_state
        p = tmp_path / "state.json"
        _save_coverage_state(p, {"plan_name": "p", "tasks": {"T1": {"status": "executed"}}})
        loaded = _load_coverage_state(p, "p")
        assert loaded["tasks"]["T1"]["status"] == "executed"

    def test_grep_symbol_in_file_found(self, tmp_path):
        from coverage_enforce import _grep_symbol_in_file
        f = tmp_path / "mod.py"
        f.write_text("def my_func():\n    pass\n", encoding="utf-8")
        assert _grep_symbol_in_file(f, "my_func") is True

    def test_grep_symbol_in_file_not_found(self, tmp_path):
        from coverage_enforce import _grep_symbol_in_file
        f = tmp_path / "mod.py"
        f.write_text("def other():\n    pass\n", encoding="utf-8")
        assert _grep_symbol_in_file(f, "my_func") is False

    def test_grep_symbol_in_file_missing_file(self, tmp_path):
        from coverage_enforce import _grep_symbol_in_file
        assert _grep_symbol_in_file(tmp_path / "nope.py", "x") is False

    def test_grep_symbol_empty(self, tmp_path):
        from coverage_enforce import _grep_symbol_in_file
        f = tmp_path / "mod.py"
        f.write_text("def x(): pass\n", encoding="utf-8")
        assert _grep_symbol_in_file(f, "") is False

    def test_grep_symbol_class(self, tmp_path):
        from coverage_enforce import _grep_symbol_in_file
        f = tmp_path / "mod.py"
        f.write_text("class MyClass:\n    pass\n", encoding="utf-8")
        assert _grep_symbol_in_file(f, "MyClass") is True

    def test_normalize_path(self):
        from coverage_enforce import _normalize_path
        assert _normalize_path("src\\foo.py") == "src/foo.py"
        assert _normalize_path("./src/foo.py") == "src/foo.py"
        assert _normalize_path("src/foo.py") == "src/foo.py"

    def test_is_path_in_safe_zone(self):
        from coverage_enforce import _is_path_in_safe_zone
        assert _is_path_in_safe_zone("src/foo.py") is True
        assert _is_path_in_safe_zone("tests/x.py") is True

    def test_is_path_blocked(self):
        from coverage_enforce import _is_path_blocked
        assert _is_path_blocked("HLK/config.json") is True
        assert _is_path_blocked(".env") is True
        assert _is_path_blocked("src/foo.py") is False

    def test_update_coverage_marks_executed(self, tmp_path):
        from coverage_enforce import _update_coverage
        plan = {"plan_name": "p", "tasks": {
            "T1": {"file": "src/foo.py", "function": "bar", "symbols": ["bar"], "status": "planned"},
        }}
        state = {"plan_name": "p", "tasks": {}}
        # Tạo file src/foo.py với function bar
        foo = tmp_path / "src" / "foo.py"
        foo.parent.mkdir(parents=True, exist_ok=True)
        foo.write_text("def bar(): pass\n", encoding="utf-8")
        new_state = _update_coverage(state, plan, "src/foo.py", tmp_path)
        assert new_state["tasks"]["T1"]["status"] in ("executed", "verified")

    def test_update_coverage_marks_verified(self, tmp_path):
        from coverage_enforce import _update_coverage
        plan = {"plan_name": "p", "tasks": {
            "T1": {"file": "src/foo.py", "function": "bar", "symbols": ["bar"], "status": "planned"},
        }}
        state = {"plan_name": "p", "tasks": {}}
        foo = tmp_path / "src" / "foo.py"
        foo.parent.mkdir(parents=True, exist_ok=True)
        foo.write_text("def bar(): pass\n", encoding="utf-8")
        new_state = _update_coverage(state, plan, "src/foo.py", tmp_path)
        # symbol bar có trong file -> verified
        assert new_state["tasks"]["T1"]["status"] == "verified"

    def test_update_coverage_no_match(self, tmp_path):
        from coverage_enforce import _update_coverage
        plan = {"plan_name": "p", "tasks": {
            "T1": {"file": "src/foo.py", "function": "bar", "symbols": [], "status": "planned"},
        }}
        state = {"plan_name": "p", "tasks": {}}
        new_state = _update_coverage(state, plan, "other/file.py", tmp_path)
        # Không khớp -> vẫn planned
        assert new_state["tasks"]["T1"]["status"] == "planned"

    def test_update_coverage_keeps_verified(self, tmp_path):
        from coverage_enforce import _update_coverage
        plan = {"plan_name": "p", "tasks": {}}
        state = {"plan_name": "p", "tasks": {
            "T1": {"file": "src/foo.py", "function": "bar", "symbols": [], "status": "verified"},
        }}
        new_state = _update_coverage(state, plan, "src/foo.py", tmp_path)
        assert new_state["tasks"]["T1"]["status"] == "verified"

    def test_compute_gaps(self):
        from coverage_enforce import _compute_gaps
        state = {"tasks": {
            "T1": {"status": "planned"},
            "T2": {"status": "executed"},
            "T3": {"status": "planned"},
        }}
        gaps = _compute_gaps(state)
        assert "T1" in gaps
        assert "T3" in gaps
        assert "T2" not in gaps

    def test_compute_coverage(self):
        from coverage_enforce import _compute_coverage
        state = {"tasks": {
            "T1": {"status": "executed"},
            "T2": {"status": "verified"},
            "T3": {"status": "planned"},
        }}
        pct, executed, total = _compute_coverage(state)
        assert total == 3
        assert executed == 2
        assert pct == round(2 / 3 * 100, 2)

    def test_compute_coverage_empty(self):
        from coverage_enforce import _compute_coverage
        pct, executed, total = _compute_coverage({"tasks": {}})
        assert pct == 0.0
        assert executed == 0
        assert total == 0

    def test_find_plan_file_docs(self, tmp_path):
        from coverage_enforce import _find_plan_file
        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "IMPLEMENTATION_PLAN.md").write_text("# plan", encoding="utf-8")
        assert _find_plan_file(tmp_path) is not None

    def test_find_plan_file_root(self, tmp_path):
        from coverage_enforce import _find_plan_file
        (tmp_path / "IMPLEMENTATION_PLAN.md").write_text("# plan", encoding="utf-8")
        assert _find_plan_file(tmp_path) is not None

    def test_find_plan_file_missing(self, tmp_path):
        from coverage_enforce import _find_plan_file
        assert _find_plan_file(tmp_path) is None

    def test_find_plan_file_glob(self, tmp_path):
        from coverage_enforce import _find_plan_file
        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "MY_PLAN.md").write_text("# plan", encoding="utf-8")
        assert _find_plan_file(tmp_path) is not None

    def test_get_plan_state_dir(self, tmp_path):
        from coverage_enforce import _get_plan_state_dir
        d = _get_plan_state_dir(tmp_path)
        assert d.exists()
        assert d.name == "plan_state"

    def test_main_no_plan(self, capsys, monkeypatch, tmp_path):
        from coverage_enforce import main
        monkeypatch.setattr("coverage_enforce._find_plan_file", lambda _r: None)
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Write", "tool_input": {"file_path": "x.py"},
        })))
        monkeypatch.chdir(tmp_path)
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["coverage_pct"] == 0.0

    def test_main_parse_error(self, capsys, monkeypatch):
        from coverage_enforce import main
        monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["coverage_pct"] == 0.0


# ===========================================================================
# coverage_matrix
# ===========================================================================
class TestCoverageMatrix:
    def test_read_plan_missing(self, tmp_path):
        from coverage_matrix import _read_plan
        with pytest.raises(FileNotFoundError):
            _read_plan(tmp_path / "nope.md")

    def test_read_plan_empty(self, tmp_path):
        from coverage_matrix import _read_plan
        p = tmp_path / "empty.md"
        p.write_text("   ", encoding="utf-8")
        with pytest.raises(ValueError):
            _read_plan(p)

    def test_read_plan_ok(self, tmp_path):
        from coverage_matrix import _read_plan
        p = tmp_path / "plan.md"
        p.write_text("# Plan\ncontent", encoding="utf-8")
        assert "content" in _read_plan(p)

    def test_extract_section_found(self):
        from coverage_matrix import _extract_section
        text = "## Requirements\n- REQ-001\n- REQ-002\n## Other\nstuff"
        section = _extract_section(text, "Requirements")
        assert "REQ-001" in section

    def test_extract_section_not_found(self):
        from coverage_matrix import _extract_section
        assert _extract_section("no headings", "Missing") == ""

    def test_extract_section_h3(self):
        from coverage_matrix import _extract_section
        text = "### Coverage Matrix\n| REQ | Task |\n## Next"
        section = _extract_section(text, "Coverage")
        assert "REQ" in section

    def test_parse_coverage_table(self):
        from coverage_matrix import _parse_coverage_table
        text = "## Coverage\n| REQ-001 | T1, T2 |\n| REQ-002 | T3 |"
        mapping = _parse_coverage_table(text)
        assert "REQ-001" in mapping
        assert "T1" in mapping["REQ-001"]

    def test_parse_coverage_table_empty(self):
        from coverage_matrix import _parse_coverage_table
        assert _parse_coverage_table("no table") == {}

    def test_extract_file_path_explicit(self):
        from coverage_matrix import _extract_file_path
        assert _extract_file_path("file: src/foo.py") == "src/foo.py"
        assert _extract_file_path("path: `bar.py`") == "bar.py"

    def test_extract_file_path_fallback(self):
        from coverage_matrix import _extract_file_path
        assert _extract_file_path("see src/mod.py for details") == "src/mod.py"

    def test_extract_file_path_empty(self):
        from coverage_matrix import _extract_file_path
        assert _extract_file_path("no file here") == ""

    def test_extract_function(self):
        from coverage_matrix import _extract_function
        assert _extract_function("func: my_func") == "my_func"
        assert _extract_function("function: bar()") == "bar"
        assert _extract_function("no function") == ""

    def test_parse_tasks(self):
        from coverage_matrix import _parse_tasks
        text = "- T01: src/foo.py (func: bar) REQ-001\n- T02: src/baz.py (func: qux) REQ-002"
        tasks = _parse_tasks(text)
        assert len(tasks) == 2
        assert tasks[0]["id"] == "T01"
        assert tasks[0]["file_path"] == "src/foo.py"
        assert tasks[0]["function"] == "bar"
        assert "REQ-001" in tasks[0]["req_ids"]

    def test_parse_req_ids(self):
        from coverage_matrix import _parse_req_ids
        ids = _parse_req_ids("REQ-001 REQ-002 REQ_03 req-4")
        assert "REQ-001" in ids
        assert "REQ-002" in ids
        assert "REQ-003" in ids
        assert "REQ-004" in ids

    def test_generate_matrix(self, tmp_path):
        from coverage_matrix import generate_matrix
        p = tmp_path / "plan.md"
        p.write_text(
            "## Requirements\n- REQ-001: do thing\n\n"
            "- T01: src/foo.py (func: bar) REQ-001\n",
            encoding="utf-8",
        )
        result = generate_matrix(p)
        assert "matrix" in result
        assert result["task_count"] >= 1

    def test_file_exists(self, tmp_path):
        from coverage_matrix import _file_exists
        f = tmp_path / "foo.py"
        f.write_text("x", encoding="utf-8")
        assert _file_exists(tmp_path, "foo.py") is not None
        assert _file_exists(tmp_path, "nope.py") is None
        assert _file_exists(tmp_path, "") is None

    def test_grep_function_found(self, tmp_path):
        from coverage_matrix import _grep_function
        f = tmp_path / "mod.py"
        f.write_text("def my_func():\n    pass\n", encoding="utf-8")
        assert _grep_function(tmp_path, f, "my_func") is True

    def test_grep_function_not_found(self, tmp_path):
        from coverage_matrix import _grep_function
        f = tmp_path / "mod.py"
        f.write_text("def other(): pass\n", encoding="utf-8")
        assert _grep_function(tmp_path, f, "my_func") is False

    def test_grep_function_empty(self, tmp_path):
        from coverage_matrix import _grep_function
        f = tmp_path / "mod.py"
        f.write_text("def x(): pass\n", encoding="utf-8")
        assert _grep_function(tmp_path, f, "") is False

    def test_verify_matrix(self, tmp_path):
        from coverage_matrix import verify_matrix
        p = tmp_path / "plan.md"
        # Tạo file thật để verify
        foo = tmp_path / "src" / "foo.py"
        foo.parent.mkdir(parents=True)
        foo.write_text("def bar(): pass\n", encoding="utf-8")
        p.write_text(
            "## Requirements\n- REQ-001: do thing\n\n"
            "- T01: src/foo.py (func: bar) REQ-001\n",
            encoding="utf-8",
        )
        result = verify_matrix(p)
        assert "status_counts" in result
        assert "verified_at" in result

    def test_render_markdown_report(self):
        from coverage_matrix import _render_markdown_report
        data = {
            "plan_file": "/tmp/plan.md",
            "generated_at": "2026-01-01T00:00:00Z",
            "verified_at": "2026-01-01T00:01:00Z",
            "req_count": 1,
            "task_count": 1,
            "matrix": {
                "REQ-001": {
                    "task_id": "T01", "file_path": "src/foo.py",
                    "function": "bar", "status": "VERIFIED",
                    "evidence": "ok",
                },
            },
            "status_counts": {"VERIFIED": 1},
        }
        report = _render_markdown_report(data)
        assert "Coverage Matrix" in report
        assert "REQ-001" in report
        assert "VERIFIED" in report

    def test_main_no_args(self, capsys):
        from coverage_matrix import main
        old_argv = sys.argv
        sys.argv = ["coverage_matrix.py"]
        try:
            code = main()
        except SystemExit as e:
            code = e.code
        finally:
            sys.argv = old_argv
        assert code == 2

    def test_main_missing_plan(self, capsys):
        from coverage_matrix import main
        old_argv = sys.argv
        sys.argv = ["coverage_matrix.py", "nope.md"]
        try:
            code = main()
        except SystemExit as e:
            code = e.code
        finally:
            sys.argv = old_argv
        assert code == 1


# ===========================================================================
# cost_tracker
# ===========================================================================
class TestCostTracker:
    def test_estimate_cost(self):
        from cost_tracker import _estimate_cost
        cost = _estimate_cost("Bash", 4000)  # 1000 tokens output
        assert cost > 0
        # 1000 tokens * $0.015/1K + 500 tokens * $0.003/1K
        assert cost == round(0.015 + 0.0015, 6)

    def test_estimate_cost_zero(self):
        from cost_tracker import _estimate_cost
        cost = _estimate_cost("Read", 0)
        # Chỉ input overhead
        assert cost == round(0.0015, 6)

    def test_check_cost_cap_ok(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 1.0, "cost_cap": 5.0}) == 0

    def test_check_cost_cap_warn(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 4.5, "cost_cap": 5.0}) == 1

    def test_check_cost_cap_block(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 5.0, "cost_cap": 5.0}) == 2
        assert check_cost_cap({"cumulative_cost": 6.0, "cost_cap": 5.0}) == 2

    def test_check_cost_cap_zero_cap(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 100, "cost_cap": 0}) == 0
        assert check_cost_cap({"cumulative_cost": 100, "cost_cap": -1}) == 0

    def test_check_cost_cap_defaults(self):
        from cost_tracker import check_cost_cap, DEFAULT_COST_CAP
        # Không có cumulative_cost -> 0
        assert check_cost_cap({}) == 0

    def test_track_tool_cost_no_session(self, tmp_path):
        from cost_tracker import track_tool_cost
        result = track_tool_cost(tmp_path, "", "Bash", 100)
        assert result["tracked"] is False

    def test_track_tool_cost_updates_state(self, tmp_path, monkeypatch):
        import cost_tracker
        from cost_tracker import track_tool_cost
        monkeypatch.setattr(cost_tracker.ahd_session, "read_session_state", lambda _sid, _root: {})
        monkeypatch.setattr(cost_tracker.ahd_session, "update_session_state", lambda _sid, _data, _root: None)
        result = track_tool_cost(tmp_path, "sess-1", "Bash", 4000)
        assert result["tracked"] is True
        assert result["tool"] == "Bash"
        assert result["cumulative_cost"] > 0
        assert result["calls_tracked"] == 1

    def test_check_cost_cap_session_no_session(self, tmp_path):
        from cost_tracker import check_cost_cap_session
        exceeded, msg = check_cost_cap_session(tmp_path, "")
        assert exceeded is False
        assert msg == ""

    def test_check_cost_cap_session_ok(self, tmp_path, monkeypatch):
        import cost_tracker
        from cost_tracker import check_cost_cap_session
        monkeypatch.setattr(cost_tracker.ahd_session, "read_session_state", lambda _sid, _root: {"cumulative_cost": 1.0, "cost_cap": 5.0})
        monkeypatch.setattr(cost_tracker.ahd_session, "update_session_state", lambda _sid, _data, _root: None)
        exceeded, msg = check_cost_cap_session(tmp_path, "s1")
        assert exceeded is False

    def test_check_cost_cap_session_warn(self, tmp_path, monkeypatch):
        import cost_tracker
        from cost_tracker import check_cost_cap_session
        monkeypatch.setattr(cost_tracker.ahd_session, "read_session_state", lambda _sid, _root: {"cumulative_cost": 4.5, "cost_cap": 5.0})
        monkeypatch.setattr(cost_tracker.ahd_session, "update_session_state", lambda _sid, _data, _root: None)
        exceeded, msg = check_cost_cap_session(tmp_path, "s1")
        assert exceeded is False
        assert "WARNING" in msg

    def test_check_cost_cap_session_exceeded(self, tmp_path, monkeypatch):
        import cost_tracker
        from cost_tracker import check_cost_cap_session
        monkeypatch.setattr(cost_tracker.ahd_session, "read_session_state", lambda _sid, _root: {"cumulative_cost": 5.0, "cost_cap": 5.0})
        monkeypatch.setattr(cost_tracker.ahd_session, "update_session_state", lambda _sid, _data, _root: None)
        exceeded, msg = check_cost_cap_session(tmp_path, "s1")
        assert exceeded is True
        assert "EXCEEDED" in msg

    def test_set_cost_cap_no_session(self, tmp_path):
        from cost_tracker import set_cost_cap
        # Không raise, không làm gì
        set_cost_cap(tmp_path, "", 10.0)

    def test_set_cost_cap(self, tmp_path, monkeypatch):
        import cost_tracker
        from cost_tracker import set_cost_cap
        monkeypatch.setattr(cost_tracker.ahd_session, "update_session_state", lambda _sid, _data, _root: None)
        set_cost_cap(tmp_path, "s1", 10.0)


# ===========================================================================
# path_zones
# ===========================================================================
class TestPathZones:
    def test_normalize_path(self):
        from path_zones import normalize_path
        assert normalize_path("src\\foo.py") == "src/foo.py"
        assert normalize_path("./src/foo.py") == "src/foo.py"
        assert normalize_path("src/foo.py") == "src/foo.py"

    def test_get_blocked_zones(self):
        from path_zones import get_blocked_zones
        zones = get_blocked_zones()
        assert "HLK/" in zones
        assert ".env" in zones
        assert ".git/" in zones

    def test_get_safe_zones(self):
        from path_zones import get_safe_zones
        zones = get_safe_zones()
        assert "src/" in zones
        assert "tests/" in zones

    def test_is_blocked(self):
        from path_zones import is_blocked
        assert is_blocked("HLK/config.json") is True
        assert is_blocked(".env") is True
        assert is_blocked(".git/HEAD") is True
        assert is_blocked("AGENTS.md") is True
        assert is_blocked("src/foo.py") is False
        assert is_blocked("") is False

    def test_is_safe(self):
        from path_zones import is_safe
        assert is_safe("src/foo.py") is True
        assert is_safe("tests/x.py") is True
        assert is_safe("docs/plans/x.md") is True
        assert is_safe("HLK/config.json") is False
        assert is_safe("") is False

    def test_validate_path_ok(self):
        from path_zones import validate_path
        ok, reason = validate_path("src/foo.py")
        assert ok is True
        assert reason == ""

    def test_validate_path_empty(self):
        from path_zones import validate_path
        ok, reason = validate_path("")
        assert ok is False
        assert "rỗng" in reason

    def test_validate_path_traversal(self):
        from path_zones import validate_path
        ok, reason = validate_path("src/../etc/passwd")
        assert ok is False
        assert "traversal" in reason.lower()

    def test_validate_path_blocked(self):
        from path_zones import validate_path
        ok, reason = validate_path("HLK/config.json")
        assert ok is False
        assert "Blocked" in reason

    def test_validate_path_outside_safe(self):
        from path_zones import validate_path
        ok, reason = validate_path("random/location.py")
        assert ok is False
        assert "safe zone" in reason.lower()

    def test_cli_no_args(self, capsys):
        from path_zones import _cli
        code = _cli()
        assert code == 1

    def test_cli_check_ok(self, capsys):
        from path_zones import _cli
        old = sys.argv
        sys.argv = ["path_zones.py", "check", "src/foo.py"]
        try:
            code = _cli()
        finally:
            sys.argv = old
        assert code == 0

    def test_cli_check_blocked(self, capsys):
        from path_zones import _cli
        old = sys.argv
        sys.argv = ["path_zones.py", "check", "HLK/x"]
        try:
            code = _cli()
        finally:
            sys.argv = old
        assert code == 2

    def test_cli_check_no_path(self, capsys):
        from path_zones import _cli
        old = sys.argv
        sys.argv = ["path_zones.py", "check"]
        try:
            code = _cli()
        finally:
            sys.argv = old
        assert code == 1

    def test_cli_list_all(self, capsys):
        from path_zones import _cli
        old = sys.argv
        sys.argv = ["path_zones.py", "list", "all"]
        try:
            code = _cli()
        finally:
            sys.argv = old
        assert code == 0
        out = capsys.readouterr().out
        assert "Blocked" in out
        assert "Safe" in out

    def test_cli_list_blocked(self, capsys):
        from path_zones import _cli
        old = sys.argv
        sys.argv = ["path_zones.py", "list", "blocked"]
        try:
            code = _cli()
        finally:
            sys.argv = old
        assert code == 0

    def test_cli_list_safe(self, capsys):
        from path_zones import _cli
        old = sys.argv
        sys.argv = ["path_zones.py", "list", "safe"]
        try:
            code = _cli()
        finally:
            sys.argv = old
        assert code == 0

    def test_cli_unknown(self, capsys):
        from path_zones import _cli
        old = sys.argv
        sys.argv = ["path_zones.py", "bogus"]
        try:
            code = _cli()
        finally:
            sys.argv = old
        assert code == 1


# ===========================================================================
# hook_integrity
# ===========================================================================
class TestHookIntegrity:
    def test_compute_sha256(self, tmp_path):
        from hook_integrity import compute_sha256
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        h = compute_sha256(f)
        assert len(h) == 64  # SHA256 hex

    def test_get_hook_files_missing(self, tmp_path):
        from hook_integrity import get_hook_files
        # tmp_path không có .devin/hooks
        assert get_hook_files(tmp_path) == []

    def test_get_hook_files_found(self, tmp_path):
        from hook_integrity import get_hook_files
        hooks = tmp_path / ".devin" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "a.py").write_text("# a", encoding="utf-8")
        (hooks / "b.py").write_text("# b", encoding="utf-8")
        files = get_hook_files(tmp_path)
        assert len(files) == 2

    def test_generate_baseline(self, tmp_path, capsys):
        from hook_integrity import generate_baseline
        hooks = tmp_path / ".devin" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "a.py").write_text("# a", encoding="utf-8")
        code = generate_baseline(tmp_path)
        assert code == 0
        assert (tmp_path / ".devin" / "hook_hashes.json").exists()

    def test_generate_baseline_no_hooks(self, tmp_path, capsys):
        from hook_integrity import generate_baseline
        code = generate_baseline(tmp_path)
        assert code == 1

    def test_verify_integrity_no_baseline(self, tmp_path, capsys):
        from hook_integrity import verify_integrity
        code = verify_integrity(tmp_path)
        assert code == 1

    def test_verify_integrity_ok(self, tmp_path, capsys):
        from hook_integrity import generate_baseline, verify_integrity
        hooks = tmp_path / ".devin" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "a.py").write_text("# a", encoding="utf-8")
        generate_baseline(tmp_path)
        capsys.readouterr()  # clear
        code = verify_integrity(tmp_path)
        assert code == 0

    def test_verify_integrity_tampered(self, tmp_path, capsys):
        from hook_integrity import generate_baseline, verify_integrity
        hooks = tmp_path / ".devin" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "a.py").write_text("# a", encoding="utf-8")
        generate_baseline(tmp_path)
        # Tamper
        (hooks / "a.py").write_text("# modified", encoding="utf-8")
        capsys.readouterr()
        code = verify_integrity(tmp_path)
        assert code == 1

    def test_verify_integrity_missing_hook(self, tmp_path, capsys):
        from hook_integrity import generate_baseline, verify_integrity
        hooks = tmp_path / ".devin" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "a.py").write_text("# a", encoding="utf-8")
        generate_baseline(tmp_path)
        (hooks / "a.py").unlink()
        capsys.readouterr()
        code = verify_integrity(tmp_path)
        assert code == 1

    def test_show_status_no_baseline(self, tmp_path, capsys):
        from hook_integrity import show_status
        code = show_status(tmp_path)
        assert code == 0

    def test_show_status_with_baseline(self, tmp_path, capsys):
        from hook_integrity import generate_baseline, show_status
        hooks = tmp_path / ".devin" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "a.py").write_text("# a", encoding="utf-8")
        generate_baseline(tmp_path)
        capsys.readouterr()
        code = show_status(tmp_path)
        assert code == 0

    def test_extract_hook_order_no_config(self, tmp_path):
        from hook_integrity import extract_hook_order
        with pytest.raises(FileNotFoundError):
            extract_hook_order(tmp_path)

    def test_extract_hook_order_ok(self, tmp_path):
        from hook_integrity import extract_hook_order
        config = tmp_path / ".devin" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [{"hooks": [{"command": "python .devin/hooks/pre_tool_use.py"}]}],
                "PostToolUse": [{"hooks": [{"command": "python .devin/hooks/post_tool_use.py"}]}],
            }
        }), encoding="utf-8")
        order = extract_hook_order(tmp_path)
        assert "pre_tool_use" in order
        assert "post_tool_use" in order

    def test_compare_order_match(self):
        from hook_integrity import compare_order
        match, diffs = compare_order(["a", "b"], ["a", "b"])
        assert match is True
        assert diffs == []

    def test_compare_order_missing(self):
        from hook_integrity import compare_order
        match, diffs = compare_order(["a"], ["a", "b"])
        assert match is False
        assert any("MISSING" in d for d in diffs)

    def test_compare_order_extra(self):
        from hook_integrity import compare_order
        match, diffs = compare_order(["a", "b", "c"], ["a", "b"])
        assert match is False
        assert any("EXTRA" in d for d in diffs)

    def test_compare_order_wrong_order(self):
        from hook_integrity import compare_order
        match, diffs = compare_order(["b", "a"], ["a", "b"])
        assert match is False
        assert any("ORDER" in d for d in diffs)

    def test_regen_order_baseline_no_config(self, tmp_path, capsys):
        from hook_integrity import regen_order_baseline
        code = regen_order_baseline(tmp_path)
        assert code == 1

    def test_regen_order_baseline_ok(self, tmp_path, capsys):
        from hook_integrity import regen_order_baseline
        config = tmp_path / ".devin" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({
            "hooks": {"PreToolUse": [{"hooks": [{"command": "python .devin/hooks/pre_tool_use.py"}]}]}
        }), encoding="utf-8")
        code = regen_order_baseline(tmp_path)
        assert code == 0
        assert (tmp_path / ".devin" / "hook_order.json").exists()

    def test_verify_order_no_baseline(self, tmp_path, capsys):
        from hook_integrity import verify_order
        code = verify_order(tmp_path)
        assert code == 1

    def test_verify_order_ok(self, tmp_path, capsys):
        from hook_integrity import regen_order_baseline, verify_order
        config = tmp_path / ".devin" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({
            "hooks": {"PreToolUse": [{"hooks": [{"command": "python .devin/hooks/pre_tool_use.py"}]}]}
        }), encoding="utf-8")
        regen_order_baseline(tmp_path)
        capsys.readouterr()
        code = verify_order(tmp_path)
        assert code == 0

    def test_verify_order_mismatch(self, tmp_path, capsys):
        from hook_integrity import regen_order_baseline, verify_order
        config = tmp_path / ".devin" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({
            "hooks": {"PreToolUse": [{"hooks": [{"command": "python .devin/hooks/pre_tool_use.py"}]}]}
        }), encoding="utf-8")
        regen_order_baseline(tmp_path)
        # Change config
        config.write_text(json.dumps({
            "hooks": {"PreToolUse": [{"hooks": [{"command": "python .devin/hooks/post_tool_use.py"}]}]}
        }), encoding="utf-8")
        capsys.readouterr()
        code = verify_order(tmp_path)
        assert code == 1


# ===========================================================================
# checkpoint — mở rộng thêm
# ===========================================================================
class TestCheckpointExtended:
    def test_repo_root(self):
        from checkpoint import _repo_root
        root = _repo_root()
        assert root.exists()

    def test_load_json_missing(self, tmp_path):
        from checkpoint import _load_json
        assert _load_json(tmp_path / "nope.json", "default") == "default"

    def test_load_json_corrupt(self, tmp_path):
        from checkpoint import _load_json
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert _load_json(p, "default") == "default"

    def test_load_json_ok(self, tmp_path):
        from checkpoint import _load_json
        p = tmp_path / "ok.json"
        p.write_text('{"x": 1}', encoding="utf-8")
        assert _load_json(p, {}) == {"x": 1}

    def test_save_json(self, tmp_path):
        from checkpoint import _save_json
        p = tmp_path / "sub" / "out.json"
        _save_json(p, {"x": 1})
        assert p.exists()
        assert json.loads(p.read_text())["x"] == 1

    def test_checkpoints_root(self, tmp_path):
        from checkpoint import _checkpoints_root
        r = _checkpoints_root(tmp_path, "wf-1")
        assert r == tmp_path / ".devin" / "checkpoints" / "wf-1"

    def test_default_redact_patterns(self):
        from checkpoint import _default_redact_patterns
        patterns = _default_redact_patterns()
        assert len(patterns) > 0
        assert any("sk-" in p for p in patterns)

    def test_sanitize_step_id_empty(self):
        from checkpoint import _sanitize_step_id
        assert _sanitize_step_id("") == "unnamed"
        assert _sanitize_step_id("   ") == "unnamed"

    def test_sanitize_step_id_path_separator(self):
        from checkpoint import _sanitize_step_id
        assert "/" not in _sanitize_step_id("a/b/c")
        assert "\\" not in _sanitize_step_id("a\\b\\c")

    def test_sanitize_step_id_special_chars(self):
        from checkpoint import _sanitize_step_id
        result = _sanitize_step_id("hello@world!#")
        assert "@" not in result
        assert "!" not in result

    def test_sanitize_step_id_truncates(self):
        from checkpoint import _sanitize_step_id
        long = "a" * 100
        result = _sanitize_step_id(long)
        assert len(result) <= 64

    def test_to_checkpoint_state_from_state(self, tmp_path):
        from checkpoint import _to_checkpoint_state, _sanitize_step_id
        from data_models import CheckpointState
        state = CheckpointState(
            version=2, run_id="r", conversation=[], side_effects_ledger=[],
            run_metadata={}, external_handles=[],
            timestamp=datetime.now(timezone.utc), step_id="step1",
        )
        result = _to_checkpoint_state(state)
        assert result.step_id == "step1"

    def test_to_checkpoint_state_from_dict_v1(self, tmp_path):
        from checkpoint import _to_checkpoint_state
        state = {
            "version": 1,
            "run_id": "r",
            "step_id": "s1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result = _to_checkpoint_state(state)
        assert result.version == 2

    def test_to_checkpoint_state_invalid_type(self):
        from checkpoint import _to_checkpoint_state
        with pytest.raises(TypeError):
            _to_checkpoint_state(123)

    def test_load_missing_file(self, tmp_path):
        from checkpoint import load
        with pytest.raises(ValueError):
            load(tmp_path / "nope.json")

    def test_migrate_non_dict(self):
        from checkpoint import migrate
        result = migrate("not a dict")
        assert result["version"] == 2

    def test_migrate_v0(self):
        from checkpoint import migrate
        result = migrate({"version": 0})
        assert result["version"] == 2
        assert "conversation" in result
        assert "side_effects_ledger" in result

    def test_build_downstream_map(self):
        from checkpoint import _build_downstream_map
        workflow = {
            "nodes": [{"task_id": "A"}, {"task_id": "B"}, {"task_id": "C"}],
            "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}],
        }
        downstream = _build_downstream_map(workflow)
        assert "B" in downstream["A"]
        assert "C" in downstream["A"]
        assert "C" in downstream["B"]
        assert downstream["C"] == []

    def test_dependencies_for(self):
        from checkpoint import _dependencies_for
        workflow = {
            "nodes": [{"task_id": "A", "deps": ["B", "C"]}],
        }
        deps = _dependencies_for(workflow, "A")
        assert deps == ["B", "C"]
        assert _dependencies_for(workflow, "MISSING") == []

    def test_load_workflow_missing(self, tmp_path, capsys):
        from checkpoint import _load_workflow
        result = _load_workflow(tmp_path, tmp_path / "nope.json")
        assert result is None

    def test_load_workflow_corrupt(self, tmp_path, capsys):
        from checkpoint import _load_workflow
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        result = _load_workflow(tmp_path, p)
        assert result is None

    def test_load_workflow_ok(self, tmp_path):
        from checkpoint import _load_workflow
        p = tmp_path / "wf.json"
        p.write_text('{"workflow_id": "x"}', encoding="utf-8")
        result = _load_workflow(tmp_path, p)
        assert result["workflow_id"] == "x"

    def test_find_latest_checkpoint(self, tmp_path):
        from checkpoint import _find_latest_checkpoint, _save_json
        ckpt_dir = tmp_path / "ckpts"
        ckpt_dir.mkdir()
        index = {"checkpoints": [
            {"step_id": "A", "file": "a_1.json", "timestamp": "2026-01-01T00:00:00"},
            {"step_id": "A", "file": "a_2.json", "timestamp": "2026-01-02T00:00:00"},
        ]}
        _save_json(ckpt_dir / "index.json", index)
        (ckpt_dir / "a_2.json").write_text("{}", encoding="utf-8")
        result = _find_latest_checkpoint(ckpt_dir, "A")
        assert result is not None
        assert result.name == "a_2.json"

    def test_find_latest_checkpoint_missing(self, tmp_path):
        from checkpoint import _find_latest_checkpoint
        ckpt_dir = tmp_path / "ckpts"
        ckpt_dir.mkdir()
        assert _find_latest_checkpoint(ckpt_dir, "NOPE") is None

    def test_find_safe_checkpoint_before_with_deps(self, tmp_path):
        from checkpoint import _find_safe_checkpoint_before, _save_json
        ckpt_dir = tmp_path / "ckpts"
        ckpt_dir.mkdir()
        index = {"checkpoints": [
            {"step_id": "dep1", "file": "dep1.json", "timestamp": "2026-01-01T00:00:00"},
        ]}
        _save_json(ckpt_dir / "index.json", index)
        (ckpt_dir / "dep1.json").write_text("{}", encoding="utf-8")
        workflow = {
            "nodes": [{"task_id": "failed", "deps": ["dep1"]}],
            "edges": [{"from": "dep1", "to": "failed"}],
        }
        result = _find_safe_checkpoint_before(ckpt_dir, "failed", workflow)
        assert result is not None

    def test_find_safe_checkpoint_before_no_deps(self, tmp_path):
        from checkpoint import _find_safe_checkpoint_before, _save_json
        ckpt_dir = tmp_path / "ckpts"
        ckpt_dir.mkdir()
        index = {"checkpoints": [
            {"step_id": "other", "file": "other.json", "timestamp": "2026-01-01T00:00:00"},
        ]}
        _save_json(ckpt_dir / "index.json", index)
        (ckpt_dir / "other.json").write_text("{}", encoding="utf-8")
        workflow = {"nodes": [{"task_id": "failed", "deps": []}], "edges": []}
        result = _find_safe_checkpoint_before(ckpt_dir, "failed", workflow)
        assert result is not None

    def test_find_safe_checkpoint_before_empty(self, tmp_path):
        from checkpoint import _find_safe_checkpoint_before
        ckpt_dir = tmp_path / "ckpts"
        ckpt_dir.mkdir()
        workflow = {"nodes": [{"task_id": "x", "deps": []}], "edges": []}
        assert _find_safe_checkpoint_before(ckpt_dir, "x", workflow) is None

    def test_cmd_save(self, tmp_path):
        from checkpoint import cmd_save, _save_json
        workflow = {
            "workflow_id": "wf1",
            "nodes": [{"task_id": "T1", "deps": []}],
            "edges": [],
        }
        state_file = tmp_path / "state.json"
        _save_json(state_file, {"key": "value"})
        code = cmd_save(tmp_path, workflow, "wf1", "T1", str(state_file))
        assert code == 0

    def test_cmd_save_missing_state(self, tmp_path):
        from checkpoint import cmd_save
        workflow = {"workflow_id": "wf1", "nodes": [], "edges": []}
        code = cmd_save(tmp_path, workflow, "wf1", "T1", str(tmp_path / "nope.json"))
        assert code == 1

    def test_cmd_save_corrupt_state(self, tmp_path):
        from checkpoint import cmd_save
        state_file = tmp_path / "bad.json"
        state_file.write_text("{not json", encoding="utf-8")
        workflow = {"workflow_id": "wf1", "nodes": [], "edges": []}
        code = cmd_save(tmp_path, workflow, "wf1", "T1", str(state_file))
        assert code == 1

    def test_cmd_restore_no_checkpoints(self, tmp_path, capsys):
        from checkpoint import cmd_restore
        workflow = {"workflow_id": "wf1", "nodes": [], "edges": []}
        code = cmd_restore(tmp_path, workflow, "wf1", "T1")
        assert code == 1

    def test_cmd_restore_ok(self, tmp_path, capsys):
        from checkpoint import cmd_restore, cmd_save, _save_json
        workflow = {
            "workflow_id": "wf1",
            "nodes": [{"task_id": "T1", "deps": []}, {"task_id": "T2", "deps": ["T1"]}],
            "edges": [{"from": "T1", "to": "T2"}],
        }
        state_file = tmp_path / "state.json"
        _save_json(state_file, {"key": "value"})
        cmd_save(tmp_path, workflow, "wf1", "T1", str(state_file))
        capsys.readouterr()
        code = cmd_restore(tmp_path, workflow, "wf1", "T2")
        assert code == 0

    def test_cmd_list_empty(self, tmp_path, capsys):
        from checkpoint import cmd_list
        workflow = {"workflow_id": "wf1", "nodes": [], "edges": []}
        code = cmd_list(tmp_path, workflow, "wf1")
        assert code == 0

    def test_cmd_list_with_checkpoints(self, tmp_path, capsys):
        from checkpoint import cmd_list, cmd_save, _save_json
        workflow = {"workflow_id": "wf1", "nodes": [{"task_id": "T1", "deps": []}], "edges": []}
        state_file = tmp_path / "state.json"
        _save_json(state_file, {"key": "value"})
        cmd_save(tmp_path, workflow, "wf1", "T1", str(state_file))
        capsys.readouterr()
        code = cmd_list(tmp_path, workflow, "wf1")
        assert code == 0

    def test_main_no_args(self, capsys):
        from checkpoint import main
        old = sys.argv
        sys.argv = ["checkpoint.py"]
        try:
            code = main()
        except SystemExit as e:
            code = e.code
        finally:
            sys.argv = old
        # argparse yêu cầu positional arg workflow -> exit 2
        assert code in (1, 2)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
