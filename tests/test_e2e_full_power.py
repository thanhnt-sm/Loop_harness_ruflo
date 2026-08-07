#!/usr/bin/env python3
"""T5.6 — E2E test: full `/full-power` run trên fixture M-tier (REQ-025).

Mô phỏng đầy đủ 5 giai đoạn của một run `/full-power`:
  Plan -> Approve -> Execute -> Verify -> Report

Cụ thể:
  1. PLAN     : plan_fsm.cmd_init khởi tạo orchestrator state cho một task M-tier.
  2. APPROVE  : approval_gate.cmd_approve duyệt SDD + plan (2 gate).
  3. EXECUTE  : dag_executor.execute chạy một workflow DAG (mix serial/parallel),
                checkpoint mỗi batch, idempotency ledger chống duplicate side-effect.
  4. VERIFY   : abc_checklist.evaluate chấm điểm task/result/trace.
  5. REPORT   : tổng hợp báo cáo cuối (success + metrics).

Kịch bản crash + resume:
  - Lần 1: chạy execute với runner raise KeyboardInterrupt giữa chừng (giả lập kill).
  - Kiểm tra completed work không mất + checkpoint đã ghi.
  - Resume: dag_executor.resume hoàn thành nốt, không có side-effect trùng lặp.

Tuân thủ safe zone (tests/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts", ".devin/scripts/plan_fsm"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture M-tier: một task mô tả đầy đủ acceptance criteria + workflow DAG
# ---------------------------------------------------------------------------

_M_TIER_TASK = (
    "Implement context projection engine for the loop harness. "
    "Acceptance criteria: viewport must be <= K chunks, substrate unchanged, "
    "token reduction >= 25%. Must pass test_context_projection.py."
)

_PLAN_MD = """# Implementation Plan

## Task table

| Task ID | Description | File Path | Function | Acceptance Criteria |
|---------|-------------|-----------|----------|---------------------|
| T1 | Build projection core | `.devin/scripts/context_projection.py` | `project` | viewport <= K |
| T2 | Add relevance scoring | `.devin/scripts/context_projection.py` | `_score_chunk` | score > 0 |
| T3 | Write tests | `tests/test_context_projection.py` | `test_project` | pass |
"""


def _make_workflow_m_tier() -> dict:
    """DAG cho M-tier fixture: 5 task mix serial/parallel.

    Cấu trúc:
        plan_t1 -> build_t2 -> build_t3  (chuỗi chính)
        build_t2 -> test_t4              (song song với build_t3 sau t2)
        build_t3, test_t4 -> report_t5   (join cuối)
    """
    tasks = [
        {"id": "plan_t1", "goal": "Plan projection engine", "dependencies": []},
        {"id": "build_t2", "goal": "Build projection core", "dependencies": ["plan_t1"]},
        {"id": "build_t3", "goal": "Add relevance scoring", "dependencies": ["plan_t1"]},
        {"id": "test_t4", "goal": "Write tests for projection", "dependencies": ["build_t2"]},
        {"id": "report_t5", "goal": "Generate final report", "dependencies": ["build_t3", "test_t4"]},
    ]
    return {"workflow_id": "e2e-full-power-mtier", "tasks": tasks}


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    """Đổi repo root sang tmp_path để không ghi vào workspace thật."""
    devin_dir = tmp_path / ".devin"
    for sub in ("plan_state", "checkpoints", "idempotency", "plan_fsm", "audit"):
        (devin_dir / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    import dag_executor
    monkeypatch.setattr(dag_executor, "_repo_root", lambda: tmp_path)
    monkeypatch.delenv("AHD_RUN_ID", raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# Helper: đọc ledger idempotency
# ---------------------------------------------------------------------------

def _ledger_entries(root: Path, run_id: str) -> list[dict]:
    path = root / ".devin" / "idempotency" / f"{run_id}.ledger.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Phase 1: PLAN — plan_fsm.cmd_init
# ---------------------------------------------------------------------------

def test_phase_plan_initializes_orchestrator_state(patched_root, monkeypatch):
    """PLAN phase: cmd_init tạo state file + trả next_action != rỗng."""
    # plan_fsm.storage.repo_root dùng ahd_session.get_repo_root qua import chain.
    from plan_fsm import cli as plan_cli

    result = plan_cli.cmd_init(_M_TIER_TASK)
    assert "state_file" in result
    assert result["task_slug"]
    assert result["tier"] in ("S", "M", "L", "XL")
    assert result["current_state"]
    assert result["next_action"]
    # State file phải được ghi xuống disk.
    assert Path(result["state_file"]).exists()


# ---------------------------------------------------------------------------
# Phase 2: APPROVE — approval_gate.cmd_approve (SDD + plan)
# ---------------------------------------------------------------------------

def test_phase_approve_sdd_and_plan_gates(patched_root, tmp_path):
    """APPROVE phase: 2 gate (SDD + plan) được duyệt thành công."""
    import approval_gate

    # Tạo SDD + plan giả lập trong docs/plans/<slug>/
    slug_dir = patched_root / "docs" / "plans" / "e2e-mtier-task"
    slug_dir.mkdir(parents=True, exist_ok=True)
    sdd_path = slug_dir / "SOLUTION_DESIGN.md"
    plan_path = slug_dir / "IMPLEMENTATION_PLAN.md"
    sdd_path.write_text("# SDD\n\n## 1. Context\n\nBuild projection engine.\n", encoding="utf-8")
    plan_path.write_text(_PLAN_MD, encoding="utf-8")

    # Duyệt SDD
    sd_state = approval_gate.cmd_approve(
        sdd_path, reviewer="e2e-test", comments="SDD ok", artifact="sd"
    )
    assert sd_state["status"] == "approved"

    # Duyệt plan
    plan_state = approval_gate.cmd_approve(
        plan_path, reviewer="e2e-test", comments="plan ok", artifact="plan"
    )
    assert plan_state["status"] == "approved"


# ---------------------------------------------------------------------------
# Phase 3: EXECUTE — dag_executor full run + crash + resume
# ---------------------------------------------------------------------------

def test_phase_execute_full_dag_completes(patched_root):
    """EXECUTE phase: chạy DAG 5 task đến khi all_complete."""
    import dag_executor

    wf = _make_workflow_m_tier()
    result = dag_executor.execute(wf, batch_size=2)
    assert result.success is True
    assert result.status["all_complete"] is True
    assert result.status["total_tasks"] == 5
    # Mọi task có result.
    for tid in ("plan_t1", "build_t2", "build_t3", "test_t4", "report_t5"):
        assert tid in result.results


def test_phase_execute_crash_midway_then_resume(patched_root):
    """EXECUTE phase: crash mid-run -> resume, không mất completed work.

    Quy trình:
      1. Chạy execute với runner raise KeyboardInterrupt tại build_t2 (lần 1).
      2. Sau crash: plan_t1 phải đã complete, checkpoint đã ghi.
      3. Resume: mọi task complete, không có side-effect trùng lặp.
    """
    import dag_executor

    call_counts: dict[str, int] = {}

    def killable_runner(task_id: str, goal: str):
        call_counts[task_id] = call_counts.get(task_id, 0) + 1
        # Giả lập kill khi bắt đầu build_t2 lần đầu.
        if task_id == "build_t2" and call_counts.get("build_t2", 0) == 1:
            raise KeyboardInterrupt("giả lập crash mid-run")
        return {"ok": True, "task_id": task_id, "goal": goal}

    wf = _make_workflow_m_tier()
    # Lần 1 — kỳ vọng bị KeyboardInterrupt.
    with pytest.raises(KeyboardInterrupt):
        dag_executor.execute(wf, batch_size=2, runner=killable_runner, max_retries=0)

    # Sau crash: plan_t1 phải đã complete (không mất completed work).
    state = dag_executor._load_state("e2e-full-power-mtier")
    assert state is not None, "state phải được lưu trước khi crash"
    assert state["tasks"]["plan_t1"]["status"] == "complete"
    # Checkpoint đã ghi.
    ckpt_dir = patched_root / ".devin" / "checkpoints" / "e2e-full-power-mtier"
    assert ckpt_dir.exists()
    assert list(ckpt_dir.glob("*.json"))

    # Resume — hoàn thành nốt.
    result = dag_executor.resume("e2e-full-power-mtier", runner=killable_runner, max_retries=0)
    assert result.success is True
    assert result.status["all_complete"] is True
    assert result.status["total_tasks"] == 5

    # Idempotency: mỗi task chỉ 1 entry ledger (không duplicate side-effect).
    entries = _ledger_entries(patched_root, "e2e-full-power-mtier")
    keys = [e.get("key") for e in entries]
    assert len(keys) == len(set(keys)), "ledger có key trùng — duplicate side-effect"
    expected = {f"e2e-full-power-mtier:{t}" for t in
                ("plan_t1", "build_t2", "build_t3", "test_t4", "report_t5")}
    assert set(keys) == expected


# ---------------------------------------------------------------------------
# Phase 4: VERIFY — abc_checklist.evaluate
# ---------------------------------------------------------------------------

def test_phase_verify_abc_checklist_passes():
    """VERIFY phase: abc_checklist đánh giá PASS cho task + result + trace tốt."""
    import abc_checklist

    task = (
        "Implement context projection. Acceptance criteria: viewport <= K chunks, "
        "substrate unchanged, token reduction >= 25%."
    )
    result = {"status": "success", "output": "all tests passed OK"}
    trace = [
        {"status": "success", "step": "plan"},
        {"status": "success", "step": "build"},
        {"status": "success", "step": "test"},
    ]
    report = abc_checklist.evaluate(task, result, trace, run_id="e2e-mtier")
    assert report.task_valid is True
    assert report.outcome_valid is True
    assert report.process_score >= 0.6
    assert report.pass_ is True


def test_phase_verify_abc_checklist_blocks_on_bad_outcome():
    """VERIFY phase: abc_checklist block khi outcome không đạt."""
    import abc_checklist

    task = "Do something. Acceptance criteria: must pass."
    result = {"status": "failed", "error": "tests failed"}
    trace = [{"status": "failed"}]
    report = abc_checklist.evaluate(task, result, trace, run_id="e2e-mtier-bad")
    assert report.pass_ is False


# ---------------------------------------------------------------------------
# Phase 5: REPORT — tổng hợp báo cáo cuối
# ---------------------------------------------------------------------------

def test_phase_report_aggregates_success_metrics(patched_root):
    """REPORT phase: tổng hợp báo cáo cuối với success + metrics từ execute + verify."""
    import abc_checklist
    import dag_executor

    wf = _make_workflow_m_tier()
    exec_result = dag_executor.execute(wf, batch_size=3)
    assert exec_result.success

    task = _M_TIER_TASK
    trace = [{"status": "success"} for _ in range(5)]
    abc_report = abc_checklist.evaluate(
        task, {"status": "success", "output": "OK"}, trace, run_id="e2e-mtier"
    )

    final_report = {
        "run_id": "e2e-full-power-mtier",
        "phases": {
            "plan": "completed",
            "approve": "approved",
            "execute": {
                "success": exec_result.success,
                "total_tasks": exec_result.status["total_tasks"],
                "all_complete": exec_result.status["all_complete"],
            },
            "verify": {
                "pass": abc_report.pass_,
                "process_score": abc_report.process_score,
            },
            "report": "completed",
        },
        "overall_success": exec_result.success and abc_report.pass_,
    }
    assert final_report["overall_success"] is True
    assert final_report["phases"]["execute"]["all_complete"] is True
    assert final_report["phases"]["verify"]["pass"] is True


# ---------------------------------------------------------------------------
# Full chain: Plan -> Approve -> Execute -> Verify -> Report trong 1 test
# ---------------------------------------------------------------------------

def test_full_power_chain_plan_approve_execute_verify_report(patched_root, tmp_path):
    """E2E: full chain 5 phase liên tiếp trên M-tier fixture."""
    import abc_checklist
    import approval_gate
    import dag_executor
    from plan_fsm import cli as plan_cli

    # Phase 1: PLAN
    plan_result = plan_cli.cmd_init(_M_TIER_TASK)
    assert plan_result["state_file"]
    assert plan_result["next_action"]

    # Phase 2: APPROVE (SDD + plan)
    slug_dir = patched_root / "docs" / "plans" / plan_result["task_slug"]
    slug_dir.mkdir(parents=True, exist_ok=True)
    sdd_path = slug_dir / "SOLUTION_DESIGN.md"
    plan_path = slug_dir / "IMPLEMENTATION_PLAN.md"
    sdd_path.write_text("# SDD\n\n## 1. Context\n\nBuild projection engine.\n", encoding="utf-8")
    plan_path.write_text(_PLAN_MD, encoding="utf-8")
    assert approval_gate.cmd_approve(sdd_path, reviewer="e2e", comments="ok", artifact="sd")["status"] == "approved"
    assert approval_gate.cmd_approve(plan_path, reviewer="e2e", comments="ok", artifact="plan")["status"] == "approved"

    # Phase 3: EXECUTE
    wf = _make_workflow_m_tier()
    exec_result = dag_executor.execute(wf, batch_size=2)
    assert exec_result.success and exec_result.status["all_complete"]

    # Phase 4: VERIFY
    trace = [{"status": "success"} for _ in range(5)]
    abc_report = abc_checklist.evaluate(
        _M_TIER_TASK, {"status": "success", "output": "OK"}, trace, run_id="e2e-mtier"
    )
    assert abc_report.pass_ is True

    # Phase 5: REPORT
    final = {
        "run_id": "e2e-full-power-mtier",
        "overall_success": exec_result.success and abc_report.pass_,
        "tasks_completed": exec_result.status["total_tasks"],
    }
    assert final["overall_success"] is True
    assert final["tasks_completed"] == 5
