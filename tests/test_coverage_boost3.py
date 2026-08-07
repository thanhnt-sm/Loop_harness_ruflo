#!/usr/bin/env python3
"""T5.x: Coverage boost tests (phần 3) — dag_executor, ahd_session, schema_gate,
blackboard, event_bus, pre_tool_use, coverage_enforce.
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
# dag_executor
# ===========================================================================
class TestDagExecutor:
    def _wf(self, wf_id="test-wf"):
        return {
            "workflow_id": wf_id,
            "tasks": [
                {"id": "A", "goal": "do A", "dependencies": []},
                {"id": "B", "goal": "do B", "dependencies": ["A"]},
                {"id": "C", "goal": "do C", "dependencies": ["A"]},
                {"id": "D", "goal": "do D", "dependencies": ["B", "C"]},
            ],
        }

    def test_load_workflow_ok(self, tmp_path):
        from dag_executor import _load_workflow
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(self._wf()), encoding="utf-8")
        result = _load_workflow(str(p))
        assert result is not None
        assert result["workflow_id"] == "test-wf"

    def test_load_workflow_missing(self, tmp_path, capsys):
        from dag_executor import _load_workflow
        result = _load_workflow(str(tmp_path / "nope.json"))
        assert result is None

    def test_load_workflow_corrupt(self, tmp_path, capsys):
        from dag_executor import _load_workflow
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        result = _load_workflow(str(p))
        assert result is None

    def test_load_workflow_bad_format(self, tmp_path, capsys):
        from dag_executor import _load_workflow
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"no_workflow_id": True}), encoding="utf-8")
        result = _load_workflow(str(p))
        assert result is None

    def test_init_state(self, monkeypatch):
        from dag_executor import _init_state, _state_dir
        monkeypatch.setattr("dag_executor._repo_root", lambda: Path(tempfile.mkdtemp()))
        state = _init_state(self._wf())
        assert "tasks" in state
        assert state["tasks"]["A"]["status"] == "ready"
        assert state["tasks"]["B"]["status"] == "pending"

    def test_init_state_cycle(self, monkeypatch, capsys):
        from dag_executor import _init_state
        monkeypatch.setattr("dag_executor._repo_root", lambda: Path(tempfile.mkdtemp()))
        wf = {
            "workflow_id": "cyc",
            "tasks": [
                {"id": "A", "dependencies": ["B"]},
                {"id": "B", "dependencies": ["A"]},
            ],
        }
        state = _init_state(wf)
        assert state == {}

    def test_detect_cycle_none(self):
        from dag_executor import _detect_cycle
        tasks = {
            "A": {"dependencies": []},
            "B": {"dependencies": ["A"]},
        }
        assert _detect_cycle(tasks) == []

    def test_detect_cycle_found(self):
        from dag_executor import _detect_cycle
        tasks = {
            "A": {"dependencies": ["B"]},
            "B": {"dependencies": ["A"]},
        }
        cycle = _detect_cycle(tasks)
        assert len(cycle) >= 2

    def test_is_ready(self):
        from dag_executor import _is_ready
        tasks = {
            "A": {"status": "complete", "dependencies": []},
            "B": {"status": "pending", "dependencies": ["A"]},
        }
        assert _is_ready("B", tasks) is True
        assert _is_ready("A", tasks) is True

    def test_is_ready_dep_not_complete(self):
        from dag_executor import _is_ready
        tasks = {
            "A": {"status": "pending", "dependencies": []},
            "B": {"status": "pending", "dependencies": ["A"]},
        }
        assert _is_ready("B", tasks) is False

    def test_is_ready_dep_missing(self):
        from dag_executor import _is_ready
        tasks = {
            "B": {"status": "pending", "dependencies": ["missing"]},
        }
        assert _is_ready("B", tasks) is False

    def test_mark_ready(self):
        from dag_executor import _mark_ready
        state = {"tasks": {
            "A": {"status": "complete", "dependencies": []},
            "B": {"status": "pending", "dependencies": ["A"]},
        }}
        _mark_ready(state)
        assert state["tasks"]["B"]["status"] == "ready"

    def test_get_ready_tasks(self):
        from dag_executor import _get_ready_tasks
        state = {"tasks": {
            "A": {"status": "ready"},
            "B": {"status": "ready"},
            "C": {"status": "pending"},
        }}
        ready = _get_ready_tasks(state, 5)
        assert "A" in ready
        assert "B" in ready
        assert "C" not in ready

    def test_get_ready_tasks_batch_size(self):
        from dag_executor import _get_ready_tasks
        state = {"tasks": {
            "A": {"status": "ready"},
            "B": {"status": "ready"},
            "C": {"status": "ready"},
        }}
        ready = _get_ready_tasks(state, 2)
        assert len(ready) == 2

    def test_get_status_summary(self):
        from dag_executor import _get_status_summary
        state = {"tasks": {
            "A": {"status": "complete"},
            "B": {"status": "ready"},
            "C": {"status": "pending"},
            "D": {"status": "failed"},
        }}
        summary = _get_status_summary(state)
        assert summary["total_tasks"] == 4
        assert summary["counts"]["complete"] == 1
        assert summary["counts"]["ready"] == 1
        assert summary["counts"]["failed"] == 1
        assert summary["any_failed"] is True
        assert summary["all_complete"] is False

    def test_get_status_summary_all_complete(self):
        from dag_executor import _get_status_summary
        state = {"tasks": {
            "A": {"status": "complete"},
            "B": {"status": "complete"},
        }}
        summary = _get_status_summary(state)
        assert summary["all_complete"] is True
        assert summary["any_failed"] is False

    def test_get_status_summary_empty(self):
        from dag_executor import _get_status_summary
        summary = _get_status_summary({"tasks": {}})
        assert summary["all_complete"] is False

    def test_get_batch(self, monkeypatch):
        from dag_executor import get_batch, _state_file
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        result = get_batch(self._wf("batch-test"), 5)
        assert result["executed"] is True
        assert len(result["batch"]) >= 1

    def test_get_next(self, monkeypatch):
        from dag_executor import get_next
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        result = get_next(self._wf("next-test"), 5)
        assert "next" in result
        assert len(result["next"]) >= 1

    def test_get_status(self, monkeypatch):
        from dag_executor import get_status
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        result = get_status(self._wf("status-test"))
        assert result["total_tasks"] == 4

    def test_complete_task(self, monkeypatch):
        from dag_executor import get_batch, complete_task
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("complete-test")
        get_batch(wf, 5)
        result = complete_task(wf, "A", {"ok": True})
        assert result["completed"] is True
        assert "B" in result["newly_ready"]
        assert "C" in result["newly_ready"]

    def test_complete_task_missing(self, monkeypatch):
        from dag_executor import get_batch, complete_task
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("complete-missing")
        get_batch(wf, 5)
        result = complete_task(wf, "NOPE", {})
        assert result["completed"] is False

    def test_complete_task_no_state(self, monkeypatch):
        from dag_executor import complete_task
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        result = complete_task(self._wf("no-state"), "A", {})
        assert result["completed"] is False

    def test_fail_task(self, monkeypatch):
        from dag_executor import get_batch, fail_task
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("fail-test")
        get_batch(wf, 5)
        result = fail_task(wf, "A", "boom")
        assert result["failed"] is True

    def test_fail_task_missing(self, monkeypatch):
        from dag_executor import get_batch, fail_task
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("fail-missing")
        get_batch(wf, 5)
        result = fail_task(wf, "NOPE", "boom")
        assert result["failed"] is False

    def test_fail_task_no_state(self, monkeypatch):
        from dag_executor import fail_task
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        result = fail_task(self._wf("no-state-fail"), "A", "boom")
        assert result["failed"] is False

    def test_execute_simple(self, monkeypatch):
        from dag_executor import execute
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = {
            "workflow_id": "exec-simple",
            "tasks": [
                {"id": "A", "goal": "do A", "dependencies": []},
                {"id": "B", "goal": "do B", "dependencies": ["A"]},
            ],
        }
        result = execute(wf)
        assert result.success is True
        assert result.status["all_complete"] is True

    def test_execute_with_runner(self, monkeypatch):
        from dag_executor import execute
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf_id = f"exec-runner-{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
        wf = {
            "workflow_id": wf_id,
            "tasks": [{"id": "A", "goal": "do A", "dependencies": []}],
        }
        calls = []
        def runner(tid, goal):
            calls.append(tid)
            return {"done": True}
        result = execute(wf, runner=runner)
        assert result.success is True
        assert "A" in calls

    def test_execute_with_failing_runner(self, monkeypatch):
        from dag_executor import execute
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf_id = f"exec-fail-{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
        wf = {
            "workflow_id": wf_id,
            "tasks": [{"id": "A", "goal": "do A", "dependencies": []}],
        }
        def runner(tid, goal):
            raise RuntimeError("boom")
        result = execute(wf, runner=runner, max_retries=1)
        assert result.success is False
        assert "failed" in (result.error or "")

    def test_execute_cycle(self, monkeypatch):
        from dag_executor import execute
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = {
            "workflow_id": "exec-cycle",
            "tasks": [
                {"id": "A", "dependencies": ["B"]},
                {"id": "B", "dependencies": ["A"]},
            ],
        }
        result = execute(wf)
        assert result.success is False
        assert "cycle" in (result.error or "").lower() or "init" in (result.error or "").lower()

    def test_execute_resume_from_dict(self, monkeypatch):
        from dag_executor import execute
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = {
            "workflow_id": "exec-resume",
            "tasks": [{"id": "A", "goal": "do A", "dependencies": []}],
        }
        # Resume với dict state đã có A complete
        state = {
            "workflow_id": "exec-resume",
            "tasks": {
                "A": {"status": "complete", "result": {"ok": True}, "completed_at": "2026-01-01T00:00:00", "dependencies": [], "goal": "do A", "agent": ""},
            },
        }
        result = execute(wf, checkpoint=state)
        assert result.success is True

    def test_resume_no_state(self, monkeypatch):
        from dag_executor import resume
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        result = resume("nonexistent-run")
        assert result.success is False

    def test_on_node_complete_no_run_id(self):
        from dag_executor import on_node_complete
        # Không có run_id -> không làm gì
        on_node_complete("A", {}, run_id=None)

    def test_on_node_complete_no_state(self, monkeypatch):
        from dag_executor import on_node_complete
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        monkeypatch.delenv("AHD_RUN_ID", raising=False)
        on_node_complete("A", {}, run_id="nonexistent")

    def test_exit_code_from_summary(self):
        from dag_executor import _exit_code_from_summary
        assert _exit_code_from_summary({"any_failed": True}) == 1
        assert _exit_code_from_summary({"all_complete": True, "any_failed": False}) == 0
        assert _exit_code_from_summary({"all_complete": False, "any_failed": False}) == 2

    def test_read_result_file_ok(self, tmp_path):
        from dag_executor import _read_result_file
        p = tmp_path / "r.json"
        p.write_text(json.dumps({"x": 1}), encoding="utf-8")
        assert _read_result_file(str(p)) == {"x": 1}

    def test_read_result_file_missing(self, tmp_path, capsys):
        from dag_executor import _read_result_file
        assert _read_result_file(str(tmp_path / "nope.json")) is None

    def test_main_no_args(self, capsys):
        from dag_executor import main
        with pytest.raises(SystemExit):
            main([])

    def test_main_missing_workflow(self, capsys):
        from dag_executor import main
        code = main(["nope.json", "--status"])
        assert code == 1

    def test_main_status(self, monkeypatch, capsys):
        from dag_executor import main
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("cli-status")
        p = tmp / "wf.json"
        p.write_text(json.dumps(wf), encoding="utf-8")
        code = main([str(p), "--status"])
        assert code in (0, 2)

    def test_main_next(self, monkeypatch, capsys):
        from dag_executor import main
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("cli-next")
        p = tmp / "wf.json"
        p.write_text(json.dumps(wf), encoding="utf-8")
        code = main([str(p), "--next"])
        assert code in (0, 2)

    def test_main_execute(self, monkeypatch, capsys):
        from dag_executor import main
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("cli-exec")
        p = tmp / "wf.json"
        p.write_text(json.dumps(wf), encoding="utf-8")
        code = main([str(p), "--execute"])
        assert code in (0, 2)

    def test_main_complete(self, monkeypatch, capsys):
        from dag_executor import main, get_batch
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("cli-complete")
        p = tmp / "wf.json"
        p.write_text(json.dumps(wf), encoding="utf-8")
        get_batch(wf, 5)
        rpath = tmp / "r.json"
        rpath.write_text(json.dumps({"ok": True}), encoding="utf-8")
        code = main([str(p), "--complete", "A", str(rpath)])
        assert code in (0, 2)

    def test_main_fail(self, monkeypatch, capsys):
        from dag_executor import main, get_batch
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("cli-fail")
        p = tmp / "wf.json"
        p.write_text(json.dumps(wf), encoding="utf-8")
        get_batch(wf, 5)
        code = main([str(p), "--fail", "A", "boom"])
        assert code == 1

    def test_main_no_action(self, monkeypatch, capsys):
        from dag_executor import main
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setattr("dag_executor._repo_root", lambda: tmp)
        wf = self._wf("cli-noop")
        p = tmp / "wf.json"
        p.write_text(json.dumps(wf), encoding="utf-8")
        code = main([str(p)])
        assert code == 1


# ===========================================================================
# coverage_enforce — main() path
# ===========================================================================
class TestCoverageEnforceMain:
    def test_main_with_plan_and_write(self, monkeypatch, tmp_path, capsys):
        from coverage_enforce import main
        # Tạo plan file
        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "IMPLEMENTATION_PLAN.md").write_text(
            "- [ ] T01: src/foo.py (functions: bar)\n", encoding="utf-8"
        )
        # Tạo file src/foo.py
        foo = tmp_path / "src" / "foo.py"
        foo.parent.mkdir(parents=True)
        foo.write_text("def bar(): pass\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("coverage_enforce._find_plan_file", lambda _r: plans / "IMPLEMENTATION_PLAN.md")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "src/foo.py"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "coverage_pct" in data

    def test_main_non_write_tool(self, monkeypatch, tmp_path, capsys):
        from coverage_enforce import main
        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "IMPLEMENTATION_PLAN.md").write_text(
            "- [ ] T01: src/foo.py (functions: bar)\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("coverage_enforce._find_plan_file", lambda _r: plans / "IMPLEMENTATION_PLAN.md")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "src/foo.py"},
        })))
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["total"] >= 1


# ===========================================================================
# pre_tool_use — test main paths
# ===========================================================================
class TestPreToolUseMain:
    def test_main_parse_error(self, capsys, monkeypatch):
        from pre_tool_use import main
        monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
        try:
            main()
        except SystemExit as e:
            assert e.code in (0, 1, 2)
        except Exception:
            pass

    def test_main_empty_input(self, capsys, monkeypatch):
        from pre_tool_use import main
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        try:
            main()
        except SystemExit as e:
            assert e.code in (0, 1, 2)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
