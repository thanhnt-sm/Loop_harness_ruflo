#!/usr/bin/env python3
"""T5.1: Kiểm thử plan_fsm module — state transition, classifier tier,
mission dispatch, storage.

Bao phủ:
- classifier.classify_tier cho S/M/L/XL + edge cases.
- storage.slugify, state_dir, plans_dir, state_path, load/save_state,
  create_initial_state, append_history.
- state_machine.next_action + process_step cho mọi state (INIT, CLASSIFY,
  ANALYZE, DESIGN, REVIEW, REVISION, SDD_APPROVAL, PLAN, QC,
  PLAN_APPROVAL, WRITE_STATE, DONE, REJECTED, ESCALATE).
- missions.scout_missions, reviewer_personas, technical_writer_mission,
  requirement_analyst_mission, missions_summary.
- cli.cmd_init, cmd_step, cmd_status, _parse_args, main.
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

from plan_fsm import classifier as clf  # noqa: E402
from plan_fsm import constants as C  # noqa: E402
from plan_fsm import missions  # noqa: E402
from plan_fsm import storage  # noqa: E402
from plan_fsm import state_machine as sm  # noqa: E402
from plan_fsm.cli import cmd_init, cmd_status, cmd_step, main, _parse_args  # noqa: E402


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("desc,expected", [
    ("fix typo", "S"),
    ("rename variable", "S"),
    ("s-tier trivial one line", "S"),
    ("", "M"),
    ("add login form with validation", "M"),
    ("multiple files integration database migration", "L"),
    ("performance cache api design multiple modules", "L"),
    ("refactor architecture migrate rewrite security compliance", "XL"),
    ("architecture security multi-system cross-service distributed " + "x" * 300, "XL"),
])
def test_classify_tier(desc, expected):
    assert clf.classify_tier(desc) == expected


def test_classify_tier_default_m():
    # Description vừa đủ, không khớc indicator nào -> M (fail-closed)
    assert clf.classify_tier("a normal task") == "M"


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def test_slugify_basic():
    assert storage.slugify("Add JWT Auth") == "add-jwt-auth"
    assert storage.slugify("Fix typo!!") == "fix-typo"
    assert storage.slugify("") == "task"
    assert storage.slugify("___") == "task"


def test_slugify_truncates():
    long = "a" * 100
    slug = storage.slugify(long)
    assert len(slug) <= 60


def test_state_dir_and_plans_dir(tmp_path):
    sd = storage.state_dir(tmp_path)
    assert sd == tmp_path / ".devin" / "plan_state"
    assert sd.exists()

    pd = storage.plans_dir(tmp_path, "my-task")
    assert pd == tmp_path / "docs" / "plans" / "my-task"
    assert pd.exists()


def test_state_path(tmp_path):
    sp = storage.state_path(tmp_path, "my-task")
    assert sp.name == "my-task_orchestrator.json"


def test_load_save_state_round_trip(tmp_path):
    sp = tmp_path / "state.json"
    state = {"foo": "bar", "n": 42}
    storage.save_state(sp, state)
    loaded = storage.load_state(sp)
    assert loaded == state


def test_load_state_missing_returns_empty(tmp_path):
    assert storage.load_state(tmp_path / "nope.json") == {}


def test_load_state_corrupt_returns_empty(tmp_path):
    sp = tmp_path / "bad.json"
    sp.write_text("{not json", encoding="utf-8")
    assert storage.load_state(sp) == {}


def test_create_initial_state(tmp_path):
    state = storage.create_initial_state("Add feature X", tmp_path)
    assert state["state"] == "INIT"
    assert state["tier"] is None
    assert state["task_slug"] == "add-feature-x"
    assert state["revision_round"] == 0
    assert state["qc_round"] == 0
    assert state["history"] == []
    assert "created_at" in state


def test_append_history(tmp_path):
    state = storage.create_initial_state("test task", tmp_path)
    storage.append_history(state, "act1", "detail1")
    assert len(state["history"]) == 1
    assert state["history"][0]["action"] == "act1"
    assert state["history"][0]["detail"] == "detail1"
    # updated_at phải được cập nhật
    assert state["updated_at"] >= state["created_at"]


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------
def test_scout_missions_count():
    missions_list = missions.scout_missions("do something")
    assert len(missions_list) == C.NUM_SCOUTS
    ids = [m["id"] for m in missions_list]
    assert ids == [f"SCOUT-{i}" for i in range(1, C.NUM_SCOUTS + 1)]
    for m in missions_list:
        assert "mission" in m
        assert "tools" in m


def test_reviewer_personas_count():
    personas = missions.reviewer_personas()
    assert len(personas) == C.NUM_REVIEWERS
    ids = {p["id"] for p in personas}
    assert ids == {"SABOTEUR", "NEW_HIRE", "SECURITY_AUDITOR"}


def test_technical_writer_mission():
    m = missions.technical_writer_mission("task X", "/path/sdd.md")
    assert m["id"] == "TECHNICAL_WRITER"
    assert "/path/sdd.md" in m["mission"]


def test_requirement_analyst_mission():
    m = missions.requirement_analyst_mission("task X", "/sdd.md", "/plan.md")
    assert m["id"] == "REQUIREMENT_ANALYST"
    assert "/sdd.md" in m["mission"]
    assert "/plan.md" in m["mission"]


def test_missions_summary():
    s = missions.missions_summary()
    assert s["num_scouts"] == C.NUM_SCOUTS
    assert s["num_reviewers"] == C.NUM_REVIEWERS
    assert s["has_technical_writer"] is True
    assert s["has_requirement_analyst"] is True


# ---------------------------------------------------------------------------
# State machine — next_action cho mọi state
# ---------------------------------------------------------------------------
def _make_state(state_name="ANALYZE", **kwargs):
    base = {
        "task_description": "test task",
        "task_slug": "test-task",
        "state": state_name,
        "tier": "M",
        "round": 0,
        "revision_round": 0,
        "qc_round": 1,
        "scout_results": [],
        "sdd_path": "/path/sdd.md",
        "sdd_approved": False,
        "review_findings": [],
        "plan_path": "/path/plan.md",
        "quality_report_path": "/qr.md",
        "plan_approved": False,
        "approval_status": None,
        "history": [],
    }
    base.update(kwargs)
    return base


def test_next_action_init_transitions_through_classify(tmp_path):
    state = _make_state("INIT")
    action = sm.next_action(state, tmp_path)
    # INIT -> CLASSIFY -> ANALYZE (M-tier) trong một lần gọi next_action
    assert state["state"] in (C.STATE_CLASSIFY, C.STATE_ANALYZE, C.STATE_DONE)
    # M-tier -> dispatch_scouts
    assert action["action"] == C.ACTION_DISPATCH_SCOUTS


def test_next_action_classify_s_tier_skips(tmp_path):
    state = _make_state("CLASSIFY", task_description="fix typo")
    action = sm.next_action(state, tmp_path)
    assert state["tier"] == "S"
    assert state["state"] == C.STATE_DONE
    assert action["action"] == C.ACTION_SKIP


def test_next_action_classify_m_tier_dispatches_scouts(tmp_path):
    state = _make_state("CLASSIFY", task_description="add feature with logic")
    action = sm.next_action(state, tmp_path)
    assert state["tier"] == "M"
    assert state["state"] == C.STATE_ANALYZE
    assert action["action"] == C.ACTION_DISPATCH_SCOUTS
    assert action["params"]["num_scouts"] == C.NUM_SCOUTS


def test_next_action_analyze(tmp_path):
    state = _make_state("ANALYZE")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_WAIT_SCOUTS


def test_next_action_design(tmp_path):
    state = _make_state("DESIGN")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_DISPATCH_ARCHITECT
    assert "SOLUTION_DESIGN.md" in action["params"]["output_file"]


def test_next_action_review(tmp_path):
    state = _make_state("REVIEW")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_DISPATCH_REVIEWERS
    assert action["params"]["num_reviewers"] == C.NUM_REVIEWERS


def test_next_action_revision(tmp_path):
    state = _make_state("REVISION", revision_round=2)
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_DISPATCH_REVISION
    assert action["params"]["revision_round"] == 2


def test_next_action_sdd_approval(tmp_path):
    state = _make_state("SDD_APPROVAL")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_PRESENT_SDD_APPROVAL


def test_next_action_plan(tmp_path):
    state = _make_state("PLAN")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_DECOMPOSE_PLAN


def test_next_action_qc(tmp_path):
    state = _make_state("QC", qc_round=1)
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_RUN_QC


def test_next_action_plan_approval(tmp_path):
    state = _make_state("PLAN_APPROVAL")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_PRESENT_PLAN_APPROVAL


def test_next_action_write_state(tmp_path):
    state = _make_state("WRITE_STATE")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_WRITE_PLAN_STATE


def test_next_action_done(tmp_path):
    state = _make_state("DONE")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_DONE


def test_next_action_rejected(tmp_path):
    state = _make_state("REJECTED", rejection_reason="too big")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_DONE
    assert action["params"]["reason"] == "too big"


def test_next_action_escalate(tmp_path):
    state = _make_state("ESCALATE", escalate_reason="max rounds")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == C.ACTION_ESCALATE


def test_next_action_unknown_state(tmp_path):
    state = _make_state("UNKNOWN_STATE")
    action = sm.next_action(state, tmp_path)
    assert action["action"] == "unknown"


# ---------------------------------------------------------------------------
# process_step — chuyển state qua results
# ---------------------------------------------------------------------------
def test_process_step_analyze_to_design(tmp_path):
    state = _make_state("ANALYZE")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_WAIT_SCOUTS,
        "scout_results": [{"id": "s1"}],
    })
    assert state["state"] == C.STATE_DESIGN
    assert len(state["scout_results"]) == 1
    assert result["action"] == C.ACTION_DISPATCH_ARCHITECT


def test_process_step_design_to_review(tmp_path):
    state = _make_state("DESIGN")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_DISPATCH_ARCHITECT,
        "sdd_path": "/new/sdd.md",
    })
    assert state["state"] == C.STATE_REVIEW
    assert state["sdd_path"] == "/new/sdd.md"


def test_process_step_review_no_blocking_to_approval(tmp_path):
    state = _make_state("REVIEW")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_DISPATCH_REVIEWERS,
        "findings": [{"severity": "ADVISORY"}],
    })
    assert state["state"] == C.STATE_SDD_APPROVAL


def test_process_step_review_blocking_to_revision(tmp_path):
    state = _make_state("REVIEW", revision_round=0)
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_DISPATCH_REVIEWERS,
        "findings": [{"severity": "BLOCKING"}],
    })
    assert state["state"] == C.STATE_REVISION
    assert state["revision_round"] == 1


def test_process_step_review_max_rounds_escalate(tmp_path):
    state = _make_state("REVIEW", revision_round=C.MAX_REVISION_ROUNDS)
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_DISPATCH_REVIEWERS,
        "findings": [{"severity": "BLOCKING"}],
    })
    assert state["state"] == C.STATE_ESCALATE


def test_process_step_revision_back_to_review(tmp_path):
    state = _make_state("REVISION")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_DISPATCH_REVISION,
        "sdd_path": "/revised/sdd.md",
    })
    assert state["state"] == C.STATE_REVIEW


def test_process_step_sdd_approval_approved(tmp_path):
    state = _make_state("SDD_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_SDD_APPROVAL,
        "decision": "approved",
    })
    assert state["state"] == C.STATE_PLAN
    assert state["sdd_approved"] is True


def test_process_step_sdd_approval_rejected(tmp_path):
    state = _make_state("SDD_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_SDD_APPROVAL,
        "decision": "rejected",
        "reason": "bad",
    })
    assert state["state"] == C.STATE_REJECTED


def test_process_step_sdd_approval_changes_requested(tmp_path):
    state = _make_state("SDD_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_SDD_APPROVAL,
        "decision": "changes_requested",
        "modifications": "more detail",
    })
    assert state["state"] == C.STATE_DESIGN


def test_process_step_sdd_approval_invalid_decision(tmp_path):
    state = _make_state("SDD_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_SDD_APPROVAL,
        "decision": "bogus",
    })
    assert result["action"] == "error"


def test_process_step_plan_to_qc(tmp_path):
    state = _make_state("PLAN")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_DECOMPOSE_PLAN,
        "plan_path": "/new/plan.md",
    })
    assert state["state"] == C.STATE_QC
    assert state["plan_path"] == "/new/plan.md"
    assert state["qc_round"] >= 1


def test_process_step_qc_pass_to_approval(tmp_path):
    state = _make_state("QC", qc_round=1)
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_RUN_QC,
        "qc_result": {"all_pass": True, "report_path": "/qr.md"},
    })
    assert state["state"] == C.STATE_PLAN_APPROVAL


def test_process_step_qc_fail_loop_to_plan(tmp_path):
    state = _make_state("QC", qc_round=1)
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_RUN_QC,
        "qc_result": {"all_pass": False, "report_path": "/qr.md"},
    })
    assert state["state"] == C.STATE_PLAN
    assert state["qc_round"] == 2


def test_process_step_qc_max_rounds_escalate(tmp_path):
    state = _make_state("QC", qc_round=C.MAX_QC_ROUNDS)
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_RUN_QC,
        "qc_result": {"all_pass": False, "report_path": "/qr.md"},
    })
    assert state["state"] == C.STATE_ESCALATE


def test_process_step_plan_approval_approved(tmp_path):
    state = _make_state("PLAN_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_PLAN_APPROVAL,
        "decision": "approved",
    })
    assert state["state"] == C.STATE_WRITE_STATE
    assert state["plan_approved"] is True


def test_process_step_plan_approval_rejected(tmp_path):
    state = _make_state("PLAN_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_PLAN_APPROVAL,
        "decision": "rejected",
        "reason": "no",
    })
    assert state["state"] == C.STATE_REJECTED


def test_process_step_plan_approval_changes_requested_plan(tmp_path):
    state = _make_state("PLAN_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_PLAN_APPROVAL,
        "decision": "changes_requested",
        "target": "plan",
        "modifications": "x",
    })
    assert state["state"] == C.STATE_PLAN


def test_process_step_plan_approval_changes_requested_sdd(tmp_path):
    state = _make_state("PLAN_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_PLAN_APPROVAL,
        "decision": "changes_requested",
        "target": "sdd",
        "modifications": "x",
    })
    assert state["state"] == C.STATE_DESIGN


def test_process_step_plan_approval_invalid(tmp_path):
    state = _make_state("PLAN_APPROVAL")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_PRESENT_PLAN_APPROVAL,
        "decision": "bogus",
    })
    assert result["action"] == "error"


def test_process_step_write_state_to_done(tmp_path):
    state = _make_state("WRITE_STATE")
    result = sm.process_step(state, tmp_path, {
        "action": C.ACTION_WRITE_PLAN_STATE,
    })
    assert state["state"] == C.STATE_DONE


def test_process_step_wrong_action_for_state(tmp_path):
    state = _make_state("ANALYZE")
    result = sm.process_step(state, tmp_path, {
        "action": "wrong_action",
    })
    assert result["action"] == "error"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_cmd_init_creates_state_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "repo_root", lambda: tmp_path)
    data = cmd_init("test cli task")
    assert data["task_slug"] == "test-cli-task"
    assert data["current_state"] in (C.STATE_DONE, C.STATE_ANALYZE)
    assert Path(data["state_file"]).exists()


def test_cmd_step_processes_results(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "repo_root", lambda: tmp_path)
    init_data = cmd_init("step task")
    state_file = init_data["state_file"]
    # Ghi results file
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps({
        "action": C.ACTION_WAIT_SCOUTS,
        "scout_results": [],
    }), encoding="utf-8")
    data = cmd_step(state_file, str(results_path))
    assert data["current_state"] == C.STATE_DESIGN


def test_cmd_step_missing_state_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "repo_root", lambda: tmp_path)
    results_path = tmp_path / "r.json"
    results_path.write_text("{}", encoding="utf-8")
    data = cmd_step(str(tmp_path / "nope.json"), str(results_path))
    assert "error" in data


def test_cmd_step_bad_results_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "repo_root", lambda: tmp_path)
    init_data = cmd_init("bad results")
    data = cmd_step(init_data["state_file"], str(tmp_path / "nope.json"))
    assert "error" in data


def test_cmd_status(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "repo_root", lambda: tmp_path)
    init_data = cmd_init("status task")
    status = cmd_status(init_data["state_file"])
    assert status["current_state"] in (C.STATE_DONE, C.STATE_ANALYZE)
    assert "next_action" in status


def test_cmd_status_missing_file(tmp_path):
    data = cmd_status(str(tmp_path / "nope.json"))
    assert "error" in data


def test_parse_args():
    args = _parse_args(["--init", "--task", "my task"])
    assert args["init"] is True
    assert args["task"] == "my task"

    args = _parse_args(["--step", "--state", "s.json", "--results", "r.json"])
    assert args["step"] is True
    assert args["state"] == "s.json"
    assert args["results"] == "r.json"

    args = _parse_args(["--status", "--state", "s.json"])
    assert args["status"] is True


def test_main_no_args_returns_2(capsys):
    code = main([])
    assert code == 2


def test_main_init(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "repo_root", lambda: tmp_path)
    code = main(["--init", "--task", "main task"])
    assert code == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
