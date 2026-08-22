#!/usr/bin/env python3
"""Test FSM Zero-Command Max — kiểm tra 3 state mới + convergence + mission generation.

Chạy: python -m pytest tests/test_fsm_zero_command_max.py -v
Hoặc:  python tests/test_fsm_zero_command_max.py
"""
import sys
from pathlib import Path

# Thêm .devin/scripts vào path để import plan_fsm
_scripts_dir = Path(__file__).parent.parent / ".devin" / "scripts"
sys.path.insert(0, str(_scripts_dir))

from plan_fsm import constants as C
from plan_fsm.missions import (
    brainstorm_missions,
    dynamic_scenarios,
    reviewer_personas,
    scout_missions,
)
from plan_fsm.state_machine import (
    _handle_brainstorm,
    _handle_gap_scan,
    _handle_plan_enhance,
    _handle_qc,
    _handle_review,
    process_step,
)


# ---------------------------------------------------------------------------
# REQ-001: Constants
# ---------------------------------------------------------------------------

def test_constants_values():
    """Test constants import, values đúng."""
    assert C.NUM_SCOUTS == 8, f"NUM_SCOUTS must be 8, got {C.NUM_SCOUTS}"
    assert C.NUM_REVIEWERS == 6, f"NUM_REVIEWERS must be 6, got {C.NUM_REVIEWERS}"
    assert C.MAX_REVISION_ROUNDS == 7, f"MAX_REVISION_ROUNDS must be 7, got {C.MAX_REVISION_ROUNDS}"
    assert C.MAX_QC_ROUNDS == 7, f"MAX_QC_ROUNDS must be 7, got {C.MAX_QC_ROUNDS}"
    assert C.MAX_ENHANCE_ROUNDS == 3, f"MAX_ENHANCE_ROUNDS must be 3, got {C.MAX_ENHANCE_ROUNDS}"


def test_constants_new_states_exist():
    """Test 3 state mới + 3 action mới tồn tại."""
    assert C.STATE_BRAINSTORM == "BRAINSTORM"
    assert C.STATE_GAP_SCAN == "GAP_SCAN"
    assert C.STATE_PLAN_ENHANCE == "PLAN_ENHANCE"
    assert C.ACTION_BRAINSTORM == "brainstorm"
    assert C.ACTION_GAP_SCAN == "gap_scan"
    assert C.ACTION_PLAN_ENHANCE == "plan_enhance"


def test_constants_state_phase_has_new_entries():
    """Test STATE_PHASE dict có 3 entry mới."""
    assert C.STATE_BRAINSTORM in C.STATE_PHASE
    assert C.STATE_GAP_SCAN in C.STATE_PHASE
    assert C.STATE_PLAN_ENHANCE in C.STATE_PHASE


# ---------------------------------------------------------------------------
# REQ-002: Scout missions
# ---------------------------------------------------------------------------

def test_scout_missions_count():
    """Test scout_missions() trả 8 missions."""
    missions = scout_missions("test task")
    assert len(missions) == 8, f"Expected 8 scouts, got {len(missions)}"


def test_scout_missions_all_have_web_search():
    """Test mọi mission có web_search trong tools."""
    missions = scout_missions("test task")
    for m in missions:
        assert "web_search" in m["tools"], f"Scout {m['id']} missing web_search in tools"


def test_scout_missions_new_ids():
    """Test SCOUT-6, SCOUT-7, SCOUT-8 có mission rõ ràng."""
    missions = scout_missions("test task")
    ids = [m["id"] for m in missions]
    assert "SCOUT-6" in ids, "Missing SCOUT-6"
    assert "SCOUT-7" in ids, "Missing SCOUT-7"
    assert "SCOUT-8" in ids, "Missing SCOUT-8"
    for m in missions:
        if m["id"] in ("SCOUT-6", "SCOUT-7", "SCOUT-8"):
            assert len(m["mission"]) > 20, f"{m['id']} mission too short"


# ---------------------------------------------------------------------------
# REQ-003: Reviewer personas + dynamic scenarios + brainstorm
# ---------------------------------------------------------------------------

def test_reviewer_personas_count():
    """Test reviewer_personas() trả 6 dict."""
    reviewers = reviewer_personas()
    assert len(reviewers) == 6, f"Expected 6 reviewers, got {len(reviewers)}"


def test_reviewer_personas_new_ids():
    """Test 3 reviewer mới: ARCHITECT, CODE_REVIEWER, GIT_WORKFLOW_MASTER."""
    reviewers = reviewer_personas()
    ids = [r["id"] for r in reviewers]
    assert "ARCHITECT" in ids, "Missing ARCHITECT reviewer"
    assert "CODE_REVIEWER" in ids, "Missing CODE_REVIEWER reviewer"
    assert "GIT_WORKFLOW_MASTER" in ids, "Missing GIT_WORKFLOW_MASTER reviewer"


def test_dynamic_scenarios_database():
    """Test dynamic_scenarios cho database task trả non-empty."""
    scenarios = dynamic_scenarios("database migration task")
    assert len(scenarios) > 0, "Expected non-empty scenarios for database task"
    ids = [s["id"] for s in scenarios]
    assert "DATA_CORRUPTION_ATTACKER" in ids, "Missing DATA_CORRUPTION_ATTACKER"


def test_dynamic_scenarios_api():
    """Test dynamic_scenarios cho API task."""
    scenarios = dynamic_scenarios("build REST API endpoint")
    assert len(scenarios) > 0
    ids = [s["id"] for s in scenarios]
    assert "RATE_LIMIT_BREAKER" in ids


def test_dynamic_scenarios_auth():
    """Test dynamic_scenarios cho auth task."""
    scenarios = dynamic_scenarios("add JWT auth login")
    assert len(scenarios) > 0
    ids = [s["id"] for s in scenarios]
    assert "PRIVILEGE_ESCALATION_TESTER" in ids


def test_dynamic_scenarios_generic_fallback():
    """Test dynamic_scenarios cho task không match domain → generic scenarios."""
    scenarios = dynamic_scenarios("update README documentation")
    assert len(scenarios) > 0, "Generic fallback should return at least 1 scenario"


def test_brainstorm_missions_count():
    """Test brainstorm_missions() trả 5+ góc nhìn."""
    missions = brainstorm_missions("auth task")
    assert len(missions) >= 5, f"Expected 5+ brainstorm angles, got {len(missions)}"


def test_brainstorm_missions_angles():
    """Test brainstorm có các góc nhìn đa dạng."""
    missions = brainstorm_missions("auth task")
    angles = [m["angle"] for m in missions]
    assert any("fast" in a.lower() for a in angles), "Missing fastest angle"
    assert any("safe" in a.lower() for a in angles), "Missing safest angle"
    assert any("simple" in a.lower() for a in angles), "Missing simplest angle"


# ---------------------------------------------------------------------------
# REQ-004: BRAINSTORM state transition
# ---------------------------------------------------------------------------

def _make_test_state(task_desc="test task", **kwargs):
    """Tạo state dict chuẩn cho test."""
    base = {
        "task_description": task_desc,
        "task_slug": "test-task",
        "state": C.STATE_BRAINSTORM,
        "revision_round": 0,
        "qc_round": 0,
        "enhance_round": 0,
        "history": [],
    }
    base.update(kwargs)
    return base


def test_brainstorm_to_analyze_transition():
    """Test FSM CLASSIFY → BRAINSTORM → ANALYZE."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_BRAINSTORM
    results = {"action": C.ACTION_BRAINSTORM, "brainstorm_results": [{"angle": "fastest"}, {"angle": "safest"}]}
    next_action = _handle_brainstorm(state, results, root)
    assert state["state"] == C.STATE_ANALYZE, f"Expected ANALYZE, got {state['state']}"
    assert next_action["action"] == C.ACTION_DISPATCH_SCOUTS
    assert len(state["brainstorm_results"]) == 2


# ---------------------------------------------------------------------------
# REQ-005: GAP_SCAN state transition
# ---------------------------------------------------------------------------

def test_gap_scan_to_qc_transition():
    """Test FSM PLAN → GAP_SCAN → QC."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_GAP_SCAN
    state["plan_path"] = "docs/plans/test/IMPLEMENTATION_PLAN.md"
    results = {"action": C.ACTION_GAP_SCAN, "gap_findings": [{"gap": "missing test for X"}]}
    _handle_gap_scan(state, results, root)
    assert state["state"] == C.STATE_QC, f"Expected QC, got {state['state']}"
    assert len(state["gap_findings"]) == 1


# ---------------------------------------------------------------------------
# REQ-006: PLAN_ENHANCE state transition
# ---------------------------------------------------------------------------

def test_plan_enhance_to_approval_transition():
    """Test FSM QC → PLAN_ENHANCE → PLAN_APPROVAL khi clean."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_PLAN_ENHANCE
    state["enhance_round"] = 1
    results = {"action": C.ACTION_PLAN_ENHANCE, "enhance_findings": [{"severity": "ADVISORY"}]}
    _handle_plan_enhance(state, results, root)
    assert state["state"] == C.STATE_PLAN_APPROVAL, f"Expected PLAN_APPROVAL, got {state['state']}"


def test_plan_enhance_loops_to_plan_on_blocking():
    """Test PLAN_ENHANCE loop lại PLAN khi có blocking issues."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_PLAN_ENHANCE
    state["enhance_round"] = 1
    results = {"action": C.ACTION_PLAN_ENHANCE, "enhance_findings": [{"severity": "BLOCKING"}]}
    _handle_plan_enhance(state, results, root)
    assert state["state"] == C.STATE_PLAN, f"Expected PLAN (loop), got {state['state']}"
    assert state["enhance_round"] == 2


def test_plan_enhance_escalate_on_max_rounds():
    """Test PLAN_ENHANCE escalate khi max rounds."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_PLAN_ENHANCE
    state["enhance_round"] = C.MAX_ENHANCE_ROUNDS
    results = {"action": C.ACTION_PLAN_ENHANCE, "enhance_findings": [{"severity": "BLOCKING"}]}
    _handle_plan_enhance(state, results, root)
    assert state["state"] == C.STATE_ESCALATE, f"Expected ESCALATE, got {state['state']}"


# ---------------------------------------------------------------------------
# REQ-007: Convergence check
# ---------------------------------------------------------------------------

def test_convergence_escalate_on_stall():
    """Test 2 vòng liên tiếp không giảm BLOCKING → escalate."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_REVIEW
    state["revision_round"] = 2
    state["last_blocking_count"] = 3
    state["convergence_stall_count"] = 1  # Đã stall 1 lần trước đó
    results = {"action": C.ACTION_DISPATCH_REVIEWERS, "findings": [
        {"severity": "BLOCKING"}, {"severity": "BLOCKING"}, {"severity": "BLOCKING"}
    ]}
    _handle_review(state, results, root)
    assert state["state"] == C.STATE_ESCALATE, f"Expected ESCALATE on stall, got {state['state']}"


def test_convergence_continue_when_decreasing():
    """Test vẫn giảm BLOCKING → tiếp tục revision."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_REVIEW
    state["revision_round"] = 1
    state["last_blocking_count"] = 5
    results = {"action": C.ACTION_DISPATCH_REVIEWERS, "findings": [
        {"severity": "BLOCKING"}, {"severity": "BLOCKING"}, {"severity": "ADVISORY"}
    ]}
    _handle_review(state, results, root)
    assert state["state"] == C.STATE_REVISION, f"Expected REVISION (still decreasing), got {state['state']}"
    assert state["revision_round"] == 2


def test_convergence_stall_warning_first_time():
    """Test lần đầu không giảm → stall warning, cho thêm 1 cơ hội."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_REVIEW
    state["revision_round"] = 1
    state["last_blocking_count"] = 3
    state["convergence_stall_count"] = 0
    results = {"action": C.ACTION_DISPATCH_REVIEWERS, "findings": [
        {"severity": "BLOCKING"}, {"severity": "BLOCKING"}, {"severity": "BLOCKING"}
    ]}
    _handle_review(state, results, root)
    assert state["state"] == C.STATE_REVISION, f"Expected REVISION (stall warning), got {state['state']}"
    assert state.get("convergence_stall_count") == 1


# ---------------------------------------------------------------------------
# REQ-006 bổ sung: QC → PLAN_ENHANCE transition
# ---------------------------------------------------------------------------

def test_qc_pass_to_plan_enhance():
    """Test QC pass → PLAN_ENHANCE (không phải PLAN_APPROVAL trực tiếp)."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_QC
    state["qc_round"] = 1
    results = {"action": C.ACTION_RUN_QC, "qc_result": {"all_pass": True, "report_path": "qr.md"}}
    _handle_qc(state, results, root)
    assert state["state"] == C.STATE_PLAN_ENHANCE, f"Expected PLAN_ENHANCE, got {state['state']}"


# ---------------------------------------------------------------------------
# REQ-008-014: File content checks (grep-based)
# ---------------------------------------------------------------------------

def _read_file(path):
    p = Path(__file__).resolve().parent.parent / path
    if not p.exists():
        print(f"DEBUG: _read_file('{path}') -> {p} does not exist", file=sys.stderr)
        print(f"DEBUG: __file__={__file__}", file=sys.stderr)
        print(f"DEBUG: parent.parent={Path(__file__).resolve().parent.parent}", file=sys.stderr)
        print(f"DEBUG: cwd={Path.cwd()}", file=sys.stderr)
        return ""
    return p.read_text(encoding="utf-8")


def test_full_power_skill_has_3_phases():
    """Test full-power SKILL.md có 3 phase mới."""
    content = _read_file(".devin/skills/full-power/SKILL.md")
    assert "BRAINSTORM" in content, "Missing BRAINSTORM in full-power SKILL.md"
    assert "GAP_SCAN" in content or "GAP-SCAN" in content, "Missing GAP_SCAN in full-power SKILL.md"
    assert "PLAN_ENHANCE" in content, "Missing PLAN_ENHANCE in full-power SKILL.md"


def test_full_power_skill_wires_5_skills():
    """Test full-power SKILL.md wire 5 skills vào EXECUTE."""
    content = _read_file(".devin/skills/full-power/SKILL.md")
    for skill in ["tdd", "systematic_debugging", "auditor", "fable-judge", "graph-verify"]:
        assert skill in content, f"Missing {skill} in full-power SKILL.md"


def test_plan_skill_has_3_steps():
    """Test plan SKILL.md có 3 step mới."""
    content = _read_file(".devin/skills/plan/SKILL.md")
    assert "BRAINSTORM" in content, "Missing BRAINSTORM in plan SKILL.md"
    assert "GAP_SCAN" in content or "GAP-SCAN" in content, "Missing GAP_SCAN in plan SKILL.md"
    assert "PLAN_ENHANCE" in content, "Missing PLAN_ENHANCE in plan SKILL.md"


def test_adversarial_consensus_has_6_personas():
    """Test adversarial-consensus SKILL.md có 6 personas."""
    content = _read_file(".devin/skills/adversarial-consensus/SKILL.md")
    for persona in ["Saboteur", "New Hire", "Security Auditor", "Architect", "Code Reviewer", "Git Workflow"]:
        assert persona in content, f"Missing {persona} in adversarial-consensus SKILL.md"


def test_agents_md_has_3_phases():
    """Test AGENTS.md có 3 phase mới."""
    content = _read_file("AGENTS.md")
    assert "BRAINSTORM" in content, "Missing BRAINSTORM in AGENTS.md"
    assert "GAP_SCAN" in content or "GAP-SCAN" in content, "Missing GAP_SCAN in AGENTS.md"
    assert "PLAN_ENHANCE" in content, "Missing PLAN_ENHANCE in AGENTS.md"


def test_devin_agents_md_updated():
    """Test .devin/AGENTS.md có reference đến flow mới."""
    content = _read_file(".devin/AGENTS.md")
    assert "BRAINSTORM" in content or "brainstorm" in content, "Missing brainstorm ref in .devin/AGENTS.md"


def test_commander_md_has_3_states():
    """Test COMMANDER.md có 3 state mới."""
    content = _read_file(".devin/agents/COMMANDER.md")
    assert content, f"COMMANDER.md is empty or missing. Path: {Path(__file__).parent.parent / '.devin/agents/COMMANDER.md'}"
    assert "BRAINSTORM" in content, "Missing BRAINSTORM in COMMANDER.md"
    assert "GAP_SCAN" in content or "GAP-SCAN" in content, "Missing GAP_SCAN in COMMANDER.md"
    assert "PLAN_ENHANCE" in content, "Missing PLAN_ENHANCE in COMMANDER.md"


def test_dispatch_templates_has_3_new():
    """Test DISPATCH_TEMPLATES.md có 3 template mới."""
    content = _read_file(".devin/agents/DISPATCH_TEMPLATES.md")
    assert content, f"DISPATCH_TEMPLATES.md is empty or missing. Path: {Path(__file__).parent.parent / '.devin/agents/DISPATCH_TEMPLATES.md'}"
    assert "Brainstormer" in content or "brainstormer" in content, "Missing Brainstormer template"
    assert "Dynamic Scenario" in content or "dynamic scenario" in content, "Missing Dynamic Scenario template"
    assert "Plan Enhancer" in content or "plan enhancer" in content, "Missing Plan Enhancer template"


# ---------------------------------------------------------------------------
# Process step integration
# ---------------------------------------------------------------------------

def test_process_step_brainstorm():
    """Test process_step wire BRAINSTORM handler."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_BRAINSTORM
    results = {"action": C.ACTION_BRAINSTORM, "brainstorm_results": []}
    result = process_step(state, root, results)
    assert result["action"] != "error", f"process_step returned error: {result}"


def test_process_step_gap_scan():
    """Test process_step wire GAP_SCAN handler."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_GAP_SCAN
    results = {"action": C.ACTION_GAP_SCAN, "gap_findings": []}
    result = process_step(state, root, results)
    assert result["action"] != "error", f"process_step returned error: {result}"


def test_process_step_plan_enhance():
    """Test process_step wire PLAN_ENHANCE handler."""
    root = Path(__file__).parent.parent
    state = _make_test_state()
    state["state"] = C.STATE_PLAN_ENHANCE
    state["enhance_round"] = 1
    results = {"action": C.ACTION_PLAN_ENHANCE, "enhance_findings": []}
    result = process_step(state, root, results)
    assert result["action"] != "error", f"process_step returned error: {result}"


# ---------------------------------------------------------------------------
# Main runner (cho chạy không cần pytest)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        ("test_constants_values", test_constants_values),
        ("test_constants_new_states_exist", test_constants_new_states_exist),
        ("test_constants_state_phase_has_new_entries", test_constants_state_phase_has_new_entries),
        ("test_scout_missions_count", test_scout_missions_count),
        ("test_scout_missions_all_have_web_search", test_scout_missions_all_have_web_search),
        ("test_scout_missions_new_ids", test_scout_missions_new_ids),
        ("test_reviewer_personas_count", test_reviewer_personas_count),
        ("test_reviewer_personas_new_ids", test_reviewer_personas_new_ids),
        ("test_dynamic_scenarios_database", test_dynamic_scenarios_database),
        ("test_dynamic_scenarios_api", test_dynamic_scenarios_api),
        ("test_dynamic_scenarios_auth", test_dynamic_scenarios_auth),
        ("test_dynamic_scenarios_generic_fallback", test_dynamic_scenarios_generic_fallback),
        ("test_brainstorm_missions_count", test_brainstorm_missions_count),
        ("test_brainstorm_missions_angles", test_brainstorm_missions_angles),
        ("test_brainstorm_to_analyze_transition", test_brainstorm_to_analyze_transition),
        ("test_gap_scan_to_qc_transition", test_gap_scan_to_qc_transition),
        ("test_plan_enhance_to_approval_transition", test_plan_enhance_to_approval_transition),
        ("test_plan_enhance_loops_to_plan_on_blocking", test_plan_enhance_loops_to_plan_on_blocking),
        ("test_plan_enhance_escalate_on_max_rounds", test_plan_enhance_escalate_on_max_rounds),
        ("test_convergence_escalate_on_stall", test_convergence_escalate_on_stall),
        ("test_convergence_continue_when_decreasing", test_convergence_continue_when_decreasing),
        ("test_convergence_stall_warning_first_time", test_convergence_stall_warning_first_time),
        ("test_qc_pass_to_plan_enhance", test_qc_pass_to_plan_enhance),
        ("test_full_power_skill_has_3_phases", test_full_power_skill_has_3_phases),
        ("test_full_power_skill_wires_5_skills", test_full_power_skill_wires_5_skills),
        ("test_plan_skill_has_3_steps", test_plan_skill_has_3_steps),
        ("test_adversarial_consensus_has_6_personas", test_adversarial_consensus_has_6_personas),
        ("test_agents_md_has_3_phases", test_agents_md_has_3_phases),
        ("test_devin_agents_md_updated", test_devin_agents_md_updated),
        ("test_commander_md_has_3_states", test_commander_md_has_3_states),
        ("test_dispatch_templates_has_3_new", test_dispatch_templates_has_3_new),
        ("test_process_step_brainstorm", test_process_step_brainstorm),
        ("test_process_step_gap_scan", test_process_step_gap_scan),
        ("test_process_step_plan_enhance", test_process_step_plan_enhance),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {name}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
