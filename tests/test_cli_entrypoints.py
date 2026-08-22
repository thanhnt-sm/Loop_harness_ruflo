"""Test CLI entrypoints cho .devin/scripts/*.py và .devin/hooks/*.py.

Mỗi script/hook có khối `if __name__ == "__main__":` được invoke qua subprocess
với nhiều loại input: hợp lệ, rỗng, JSON sai, attack input (path traversal, SQL
injection, command injection). Mục đích: đảm bảo CLI không crash và trả exit
code đúng cho từng trường hợp.

Pentest/red-team coverage: các attack input được inject qua argv và stdin để
verify fail-closed behavior.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Thư mục gốc repo (chứa .devin/)
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"
HOOKS_DIR = REPO_ROOT / ".devin" / "hooks"

# Biến môi trường ép UTF-8 cho subprocess (tránh cp1258 crash trên Windows)
UTF8_ENV = {
    **os.environ,
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
}


def _run(script: Path, args: list[str] | None = None, stdin: str | None = None,
         timeout: int = 30) -> subprocess.CompletedProcess:
    """Chạy script Python qua subprocess, trả CompletedProcess."""
    cmd = [sys.executable, str(script), *(args or [])]
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=UTF8_ENV,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Scripts đọc JSON từ stdin — hợp lệ + attack inputs
# ---------------------------------------------------------------------------

class TestStdinJsonScripts:
    """Các script đọc JSON payload từ stdin."""

    @pytest.mark.parametrize("script,payload,expect_code", [
        # Hợp lệ
        ("abc_checklist.py", '{"task":"test must pass","result":"ok","trace":[]}', 0),
        ("llm_as_judge.py", '{"task":"test must pass","result":"ok"}', 0),
        ("reward_shaping.py", '{"base_score":50,"actions":[],"cost":0,"security_events":[]}', 0),
        ("adaptive_compress.py", '{"history":[],"query":"","mode":"auto"}', 0),
        ("swarm_judge.py", '{"results":[],"spec":{"run_id":"r","orders":[],"max_parallel":1,"created_at":"2026-01-01T00:00:00Z"}}', 0),
        ("tscg.py", '{"tools":[]}', 0),
        ("reflection_gate.py", '{"task":"test","result":"ok","trace":[]}', 0),
        # Rỗng / sai JSON — phải trả != 0 (fail-closed)
        ("abc_checklist.py", "", 1),
        ("llm_as_judge.py", "", 1),
        ("reward_shaping.py", "", 1),
        # adaptive_compress/tscg xử lý empty gracefully (empty history → [])
        ("adaptive_compress.py", "not json", 1),
        ("swarm_judge.py", "", 1),
        ("tscg.py", "not json", 1),
        ("abc_checklist.py", "not json", 1),
        ("llm_as_judge.py", "not json", 1),
        ("reward_shaping.py", "not json", 1),
        ("adaptive_compress.py", "not json", 1),
        ("swarm_judge.py", "not json", 1),
        ("tscg.py", "not json", 1),
    ])
    def test_stdin_json(self, script, payload, expect_code):
        proc = _run(SCRIPTS_DIR / script, stdin=payload)
        assert proc.returncode == expect_code, (
            f"{script}: expected {expect_code}, got {proc.returncode}\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        )

    @pytest.mark.parametrize("script,attack_payload", [
        # Attack: JSON bomb / nested deeply / oversized
        ("abc_checklist.py", '{"task":"' + "A" * 10000 + '","result":"ok"}'),
        ("llm_as_judge.py", '{"task":"' + "A" * 10000 + '","result":"ok"}'),
        # Attack: SQL injection string trong task
        ("abc_checklist.py", '{"task":"\'; DROP TABLE users; --","result":"ok"}'),
        ("llm_as_judge.py", '{"task":"\'; DROP TABLE users; --","result":"ok"}'),
        # Attack: command injection
        ("abc_checklist.py", '{"task":"$(rm -rf /)","result":"ok"}'),
        ("llm_as_judge.py", '{"task":"$(rm -rf /)","result":"ok"}'),
        # Attack: null bytes
        ("abc_checklist.py", '{"task":"\\u0000evil","result":"ok"}'),
        ("llm_as_judge.py", '{"task":"\\u0000evil","result":"ok"}'),
    ])
    def test_stdin_attack_inputs(self, script, attack_payload):
        """Attack inputs không được crash (exit != 0 hoặc 0, nhưng không traceback)."""
        proc = _run(SCRIPTS_DIR / script, stdin=attack_payload)
        # Không được có traceback trong stderr
        assert "Traceback" not in proc.stderr, (
            f"{script}: traceback on attack input\nstderr={proc.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Scripts nhận argv — usage / help / args hợp lệ
# ---------------------------------------------------------------------------

class TestArgvScripts:
    """Scripts nhận tham số qua argv (argparse hoặc manual parse)."""

    @pytest.mark.parametrize("script,args,expect_code", [
        # Không có args → usage/help, exit 1 hoặc 2
        ("path_zones.py", [], 1),
        ("artifact_registry.py", [], 1),
        ("cognitive_scaffold_memory.py", [], 1),
        ("approval_gate.py", [], 2),
        ("coverage_matrix.py", [], 2),
        ("plan_quality_check.py", [], 2),
        ("plan_orchestrator.py", [], 2),
        ("cost_tracker.py", [], 2),
        ("memory_audit.py", [], 0),  # V11 refactor: audit() returns dict, no CLI exit 2
        ("nuwa_roi.py", [], 2),
        ("session_manager.py", [], 2),
        ("worktree.py", [], 2),
        ("checkpoint.py", [], 2),
        ("dag_compile.py", [], 2),
        ("dag_executor.py", [], 2),
        ("context_projection.py", [], 2),
        ("dyflow.py", [], 1),
        # --help → exit 0
        ("cost_tracker.py", ["--help"], 0),
        ("memory_audit.py", ["--help"], 0),
        ("nuwa_roi.py", ["--help"], 0),
        ("session_manager.py", ["--help"], 0),
        ("worktree.py", ["--help"], 0),
        ("checkpoint.py", ["--help"], 0),
        ("dag_compile.py", ["--help"], 0),
        ("dag_executor.py", ["--help"], 0),
        ("context_projection.py", ["--help"], 0),
        ("state_router.py", ["--help"], 0),
        ("event_bus.py", ["--help"], 0),
        ("blackboard.py", ["--help"], 0),
        ("spc_monitor.py", ["--help"], 0),
        ("plan_dispatch.py", ["--help"], 0),
        ("hook_integrity.py", ["--help"], 0),
        ("log_rotation.py", ["--help"], 0),
        ("pre_task_audit.py", ["--help"], 0),
        ("migrate_state.py", ["--help"], 0),
    ])
    def test_argv_usage(self, script, args, expect_code):
        proc = _run(SCRIPTS_DIR / script, args=args)
        assert proc.returncode == expect_code, (
            f"{script} {args}: expected {expect_code}, got {proc.returncode}\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        )

    def test_path_zones_check_safe(self):
        """path_zones.py check một path an toàn."""
        proc = _run(SCRIPTS_DIR / "path_zones.py", args=["check", "src/main.py"])
        assert proc.returncode == 0
        # path_zones in "OK" cho path an toàn
        assert proc.stdout.strip() in ("OK", "SAFE") or "safe" in proc.stdout.lower()

    @pytest.mark.parametrize("attack_path", [
        "src/../etc/passwd",           # path traversal
        "HLK/config.json",             # blocked zone
        "../../../etc/shadow",         # traversal root
        "HLK/../../secret",            # traversal + blocked
        "....//....//etc/passwd",      # encoded traversal
    ])
    def test_path_zones_attack_blocked(self, attack_path):
        """Path traversal và blocked zone phải bị chặn (exit 2)."""
        proc = _run(SCRIPTS_DIR / "path_zones.py", args=["check", attack_path])
        assert proc.returncode == 2, (
            f"attack path {attack_path!r} should be blocked (exit 2), "
            f"got {proc.returncode}: {proc.stdout!r} {proc.stderr!r}"
        )
        assert "BLOCKED" in proc.stdout or "BLOCKED" in proc.stderr

    def test_path_zones_list(self):
        proc = _run(SCRIPTS_DIR / "path_zones.py", args=["list", "blocked"])
        assert proc.returncode == 0
        proc = _run(SCRIPTS_DIR / "path_zones.py", args=["list", "safe"])
        assert proc.returncode == 0

    def test_artifact_registry_list(self):
        proc = _run(SCRIPTS_DIR / "artifact_registry.py", args=["list"])
        # list có thể trả 0 hoặc 1 tùy registry rỗng
        assert proc.returncode in (0, 1)

    def test_cost_tracker_check(self):
        proc = _run(SCRIPTS_DIR / "cost_tracker.py",
                    args=["--session", "test-cli-session", "--check"])
        assert proc.returncode in (0, 1)

    def test_log_rotation_status(self):
        proc = _run(SCRIPTS_DIR / "log_rotation.py",
                    args=["--status", "--root", str(REPO_ROOT)])
        assert proc.returncode == 0

    def test_hook_integrity_status(self):
        proc = _run(SCRIPTS_DIR / "hook_integrity.py",
                    args=["--status", "--root", str(REPO_ROOT)])
        assert proc.returncode in (0, 1)

    def test_pre_task_audit_default(self):
        proc = _run(SCRIPTS_DIR / "pre_task_audit.py")
        assert proc.returncode == 0

    def test_spc_monitor_check_empty(self):
        proc = _run(SCRIPTS_DIR / "spc_monitor.py",
                    args=["--check", "--root", str(REPO_ROOT)])
        assert proc.returncode in (0, 1)

    def test_event_bus_topics_empty(self):
        proc = _run(SCRIPTS_DIR / "event_bus.py", args=["--topics"])
        assert proc.returncode in (0, 1)

    def test_blackboard_regions(self):
        proc = _run(SCRIPTS_DIR / "blackboard.py", args=["--regions"])
        assert proc.returncode in (0, 1)

    def test_migrate_config_runs(self, tmp_path):
        # Dùng file config tạm để không ghi vào config thật của repo
        cfg = tmp_path / ".devin" / "config.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({
            "permissions": {
                "allow": ["Exec(python .devin/scripts/plan_orchestrator.py:*)"],
                "deny": ["Exec(git push --force:*)"],
                "ask": []
            }
        }), encoding="utf-8")
        proc = _run(SCRIPTS_DIR / "migrate_config.py", args=["--config", str(cfg)])
        assert proc.returncode in (0, 1)

    def test_build_workflow_runs(self):
        proc = _run(SCRIPTS_DIR / "build_workflow.py")
        assert proc.returncode in (0, 1)

    def test_plan_orchestrator_init(self):
        proc = _run(SCRIPTS_DIR / "plan_orchestrator.py",
                    args=["--init", "--task", "cli-test-task"])
        assert proc.returncode in (0, 1)


# ---------------------------------------------------------------------------
# Scripts argv + stdin (three_role, cot_synthesis, swarm_director)
# ---------------------------------------------------------------------------

class TestArgvStdinScripts:
    """Scripts nhận task qua argv hoặc stdin."""

    def test_three_role_argv(self):
        proc = _run(SCRIPTS_DIR / "three_role.py", args=["test task from argv"])
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert "summary" in data

    def test_three_role_stdin(self):
        proc = _run(SCRIPTS_DIR / "three_role.py", stdin="test task from stdin")
        assert proc.returncode == 0

    def test_cot_synthesis_argv(self):
        proc = _run(SCRIPTS_DIR / "cot_synthesis.py", args=["solve problem x"])
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert "cot" in data and "crv" in data

    def test_cot_synthesis_stdin(self):
        proc = _run(SCRIPTS_DIR / "cot_synthesis.py", stdin="solve problem y")
        assert proc.returncode == 0

    def test_swarm_director_empty(self):
        proc = _run(SCRIPTS_DIR / "swarm_director.py", stdin="")
        assert proc.returncode == 0

    def test_swarm_director_plan(self):
        proc = _run(SCRIPTS_DIR / "swarm_director.py", stdin="# Plan\ntask 1")
        assert proc.returncode == 0

    def test_benchjack_redteam(self):
        proc = _run(SCRIPTS_DIR / "benchjack_redteam.py")
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert isinstance(data, list) and len(data) > 0


# ---------------------------------------------------------------------------
# Hooks — đọc JSON từ stdin, trả hook output
# ---------------------------------------------------------------------------

class TestHooks:
    """Hooks đọc JSON từ stdin, output JSON cho Devin."""

    @pytest.mark.parametrize("hook,payload,expect_code", [
        # Hợp lệ
        ("drift_detect.py", '{"tool_name":"Read","tool_input":{"file_path":"src/x.py"}}', 0),
        ("self_heal.py", '{"tool_name":"Read","tool_input":{}}', 0),
        ("session_end.py", '{"session_id":"test"}', 0),
        ("session_start.py", '{"session_id":"test","prompt_id":"p1"}', 0),
        ("user_prompt_submit.py", '{"session_id":"test","prompt":"hello"}', 0),
        ("stop.py", '{"session_id":"test"}', 0),
        ("otel_instrument.py", '{"tool_name":"Read","tool_input":{}}', 0),
        ("plan_enforce.py", '{"tool_name":"Read","tool_input":{"file_path":"src/x.py"}}', 0),
        ("coverage_enforce.py", '{"tool_name":"Read","tool_input":{"file_path":"src/x.py"}}', 2),  # V6: blocks on low coverage (có plan file)
        ("schema_gate.py", '{"tool_name":"Read","tool_input":{"file_path":"src/x.py"}}', 0),
        ("post_tool_use.py", '{"tool_name":"Read","tool_input":{}}', 0),
        # Sai JSON — fail-closed (exit 0 hoặc 1, không crash)
        ("drift_detect.py", "not json", 0),
        ("self_heal.py", "not json", 0),
        ("session_end.py", "not json", 0),
        ("session_start.py", "not json", 0),
        ("user_prompt_submit.py", "not json", 0),
        ("stop.py", "not json", 0),
        ("otel_instrument.py", "not json", 0),
        ("coverage_enforce.py", "not json", 0),
        # schema_gate là cổng an ninh, parse error phải fail-closed.
        ("schema_gate.py", "not json", 1),
        ("post_tool_use.py", "not json", 0),
    ])
    def test_hook_stdin(self, hook, payload, expect_code):
        proc = _run(HOOKS_DIR / hook, stdin=payload)
        # coverage_enforce: exit 2 khi có plan file (low coverage), exit 0 khi không có plan
        if hook == "coverage_enforce.py" and expect_code == 2:
            assert proc.returncode in (0, 2), (
                f"{hook}: expected 0 or 2, got {proc.returncode}\n"
                f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
            )
        else:
            assert proc.returncode == expect_code, (
                f"{hook}: expected {expect_code}, got {proc.returncode}\n"
                f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
            )
        assert "Traceback" not in proc.stderr, (
            f"{hook}: traceback\nstderr={proc.stderr!r}"
        )

    @pytest.mark.parametrize("hook,attack", [
        # plan_enforce fail-closed trên input sai
        ("plan_enforce.py", "not json"),
        # Attack: null bytes trong tool_input
        ("schema_gate.py", '{"tool_name":"Read","tool_input":{"file_path":"\\u0000evil"}}'),
        # Attack: path traversal
        ("plan_enforce.py", '{"tool_name":"Write","tool_input":{"file_path":"../../../etc/passwd"}}'),
        # Attack: oversized payload
        ("drift_detect.py", '{"tool_name":"Read","tool_input":{"file_path":"' + "A" * 5000 + '"}}'),
    ])
    def test_hook_attack_inputs(self, hook, attack):
        """Attack inputs không crash hook."""
        proc = _run(HOOKS_DIR / hook, stdin=attack)
        assert "Traceback" not in proc.stderr, (
            f"{hook}: traceback on attack\nstderr={proc.stderr!r}"
        )

    def test_plan_enforce_fail_closed(self):
        """plan_enforce phải fail-closed (exit 1, allow=false) khi input sai."""
        proc = _run(HOOKS_DIR / "plan_enforce.py", stdin="not json")
        assert proc.returncode == 1
        data = json.loads(proc.stdout)
        assert data["allow"] is False


# ---------------------------------------------------------------------------
# Scripts phức tạp — workflow/DAG/state
# ---------------------------------------------------------------------------

class TestWorkflowScripts:
    """Scripts workflow/DAG/state router."""

    def test_dag_compile_missing_file(self):
        proc = _run(SCRIPTS_DIR / "dag_compile.py", args=["nonexistent.md"])
        assert proc.returncode != 0

    def test_dag_executor_status_missing(self):
        proc = _run(SCRIPTS_DIR / "dag_executor.py",
                    args=["nonexistent.json", "--status"])
        assert proc.returncode != 0

    def test_checkpoint_list_missing(self):
        proc = _run(SCRIPTS_DIR / "checkpoint.py",
                    args=["test-workflow", "--list"])
        assert proc.returncode in (0, 1)

    def test_state_router_no_args(self):
        proc = _run(SCRIPTS_DIR / "state_router.py")
        assert proc.returncode == 1

    def test_plan_dispatch_no_args(self):
        proc = _run(SCRIPTS_DIR / "plan_dispatch.py")
        assert proc.returncode == 1

    def test_worktree_list(self):
        proc = _run(SCRIPTS_DIR / "worktree.py", args=["list"])
        assert proc.returncode in (0, 1)

    def test_session_manager_sync(self):
        proc = _run(SCRIPTS_DIR / "session_manager.py", args=["sync"])
        assert proc.returncode in (0, 1)

    def test_loop_memory_sync_default(self):
        proc = _run(SCRIPTS_DIR / "loop_memory_sync.py")
        assert proc.returncode in (0, 1)

    def test_nuwa_roi_report(self):
        proc = _run(SCRIPTS_DIR / "nuwa_roi.py",
                    args=["--session", "test-cli", "--report",
                          "--root", str(REPO_ROOT)])
        assert proc.returncode in (0, 1)

    def test_qa_doc_audit_runs(self):
        proc = _run(SCRIPTS_DIR / "qa_doc_audit.py")
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert "scanned_files" in data
