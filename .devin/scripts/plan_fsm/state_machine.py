#!/usr/bin/env python3
"""State machine: next_action + process_step cho Plan Phase."""
from __future__ import annotations

from pathlib import Path

from . import constants as C
from .classifier import classify_tier
from .missions import brainstorm_missions, dynamic_scenarios, reviewer_personas, scout_missions, technical_writer_mission
from .storage import append_history, plans_dir


def _next_action_for_state(state: dict, root: Path) -> dict:
    """Trả về next action dựa trên current state.

    Không thay đổi state, chỉ đọc.
    """
    s = state["state"]

    if s == C.STATE_INIT:
        return {
            "action": C.ACTION_DISPATCH_SCOUTS,
            "instructions": "Khởi tạo orchestrator — chuyển sang CLASSIFY.",
            "params": {"note": "sẽ classify ở process_init"},
        }

    if s == C.STATE_CLASSIFY:
        tier = classify_tier(state["task_description"])
        if tier == "S":
            return {
                "action": C.ACTION_SKIP,
                "instructions": f"S-tier task — skip Plan phase. Tier={tier}. Proceed directly to execution.",
                "params": {"tier": tier},
            }
        return {
            "action": C.ACTION_BRAINSTORM,
            "instructions": (
                f"Tier={tier}. Dispatch brainstorm subagents for multi-perspective analysis. "
                f"Generate {len(brainstorm_missions(state['task_description']))}+ angles "
                f"(fastest, safest, simplest, scale, cheapest, robust). "
                f"Launch ALL brainstorm subagents in a SINGLE response for max parallelism."
            ),
            "params": {
                "tier": tier,
                "brainstorm_missions": brainstorm_missions(state["task_description"]),
                "profile": "subagent_explore",
                "mode": "background",
            },
        }

    if s == C.STATE_BRAINSTORM:
        return {
            "action": C.ACTION_BRAINSTORM,
            "instructions": (
                "Dispatch brainstorm subagents for multi-perspective analysis. "
                "Generate 6+ angles (fastest, safest, simplest, scale, cheapest, robust). "
                "Launch ALL in a SINGLE response for max parallelism."
            ),
            "params": {
                "brainstorm_missions": brainstorm_missions(state["task_description"]),
                "profile": "subagent_explore",
                "mode": "background",
            },
        }

    if s == C.STATE_ANALYZE:
        return {
            "action": C.ACTION_WAIT_SCOUTS,
            "instructions": (
                f"Collect results from all {C.NUM_SCOUTS} SCOUT subagents using read_subagent. "
                "Aggregate findings into analysis_context. "
                "Then call --step with results to proceed to DESIGN."
            ),
            "params": {"num_scouts": C.NUM_SCOUTS},
        }

    if s == C.STATE_DESIGN:
        return {
            "action": C.ACTION_DISPATCH_ARCHITECT,
            "instructions": (
                "Dispatch 1 ARCHITECT subagent (profile: glm-executor, foreground). "
                "Input: aggregated analysis_context from SCOUTs + SDD template. "
                "Output: SOLUTION_DESIGN.md draft. "
                "Template: docs/templates/SDD_TEMPLATE.md"
            ),
            "params": {
                "profile": "glm-executor",
                "mode": "foreground",
                "template": "docs/templates/SDD_TEMPLATE.md",
                "output_file": str(plans_dir(root, state["task_slug"]) / "SOLUTION_DESIGN.md"),
            },
        }

    if s == C.STATE_REVIEW:
        return {
            "action": C.ACTION_DISPATCH_REVIEWERS,
            "instructions": (
                f"Dispatch {C.NUM_REVIEWERS} adversarial reviewers in PARALLEL "
                f"(background mode, profile: subagent_explore). "
                f"Launch ALL {C.NUM_REVIEWERS} in a SINGLE response. "
                f"Reviewers: SABOTEUR, NEW_HIRE, SECURITY_AUDITOR."
            ),
            "params": {
                "num_reviewers": C.NUM_REVIEWERS,
                "reviewers": reviewer_personas(),
                "profile": "subagent_explore",
                "mode": "background",
                "sdd_path": state.get("sdd_path"),
            },
        }

    if s == C.STATE_REVISION:
        return {
            "action": C.ACTION_DISPATCH_REVISION,
            "instructions": (
                f"Revision round {state['revision_round']}/{C.MAX_REVISION_ROUNDS}. "
                "Resume ARCHITECT subagent with blocking issues to fix. "
                "Then re-dispatch reviewers."
            ),
            "params": {
                "revision_round": state["revision_round"],
                "max_rounds": C.MAX_REVISION_ROUNDS,
                "blocking_issues": [
                    f for f in state.get("review_findings", []) if f.get("severity") == "BLOCKING"
                ],
            },
        }

    if s == C.STATE_SDD_APPROVAL:
        return {
            "action": C.ACTION_PRESENT_SDD_APPROVAL,
            "instructions": (
                "Present SOLUTION_DESIGN.md to user for approval. "
                "This is the first human gate: approve the solution design BEFORE planning. "
                "Command: python .devin/scripts/approval_gate.py <sdd_path> --interactive --artifact sd"
            ),
            "params": {
                "sdd_path": state.get("sdd_path"),
                "artifact": "sd",
                "command": f"python .devin/scripts/approval_gate.py {state.get('sdd_path', '<sdd_path>')} --interactive --artifact sd",
            },
        }

    if s == C.STATE_PLAN:
        return {
            "action": C.ACTION_DECOMPOSE_PLAN,
            "instructions": (
                "Decompose approved SDD into atomic tasks. "
                "Build dependency DAG. Generate coverage matrix. "
                "Write IMPLEMENTATION_PLAN.md using template. "
                "Template: docs/templates/PLAN_TEMPLATE.md"
            ),
            "params": {
                "template": "docs/templates/PLAN_TEMPLATE.md",
                "output_file": str(plans_dir(root, state["task_slug"]) / "IMPLEMENTATION_PLAN.md"),
                "sdd_path": state.get("sdd_path"),
            },
        }

    if s == C.STATE_GAP_SCAN:
        return {
            "action": C.ACTION_GAP_SCAN,
            "instructions": (
                "Dispatch gap-scan subagent to scan plan for missing requirements, "
                "uncovered edge cases, incomplete tasks. "
                "Profile: subagent_explore, background mode."
            ),
            "params": {
                "profile": "subagent_explore",
                "mode": "background",
                "plan_path": state.get("plan_path"),
            },
        }

    if s == C.STATE_QC:
        return {
            "action": C.ACTION_RUN_QC,
            "instructions": (
                f"QC round {state['qc_round']}/{C.MAX_QC_ROUNDS}. "
                "Run quality check on IMPLEMENTATION_PLAN.md. "
                "Command: python .devin/scripts/plan_quality_check.py <plan_path>"
            ),
            "params": {
                "qc_round": state["qc_round"],
                "max_rounds": C.MAX_QC_ROUNDS,
                "plan_path": state.get("plan_path"),
                "command": f"python .devin/scripts/plan_quality_check.py {state.get('plan_path', '<plan_path>')}",
            },
        }

    if s == C.STATE_PLAN_APPROVAL:
        return {
            "action": C.ACTION_PRESENT_PLAN_APPROVAL,
            "instructions": (
                "Present IMPLEMENTATION_PLAN.md + QUALITY_REPORT.md to user for final approval. "
                "This is the second human gate: approve the plan BEFORE execution. "
                "Command: python .devin/scripts/approval_gate.py <plan_path> --interactive --artifact plan"
            ),
            "params": {
                "plan_path": state.get("plan_path"),
                "sdd_path": state.get("sdd_path"),
                "quality_report_path": state.get("quality_report_path"),
                "artifact": "plan",
                "command": f"python .devin/scripts/approval_gate.py {state.get('plan_path', '<plan_path>')} --interactive --artifact plan",
            },
        }

    if s == C.STATE_PLAN_ENHANCE:
        enhance_round = state.get("enhance_round", 1)
        return {
            "action": C.ACTION_PLAN_ENHANCE,
            "instructions": (
                f"Plan enhancement round {enhance_round}/{C.MAX_ENHANCE_ROUNDS}. "
                "Dispatch 5 enhancement subagents in PARALLEL: "
                "1) gap-scan for missing tasks, "
                "2) adversarial-consensus review on plan, "
                "3) nuwa cognitive review (Munger/Feynman/Taleb), "
                "4) claim-grader on all claims, "
                "5) slop-detector + comment_checker. "
                "If issues found → loop back to PLAN. If clean → PLAN_APPROVAL."
            ),
            "params": {
                "enhance_round": enhance_round,
                "max_rounds": C.MAX_ENHANCE_ROUNDS,
                "plan_path": state.get("plan_path"),
                "enhancement_skills": [
                    "gap-scan",
                    "adversarial-consensus",
                    "nuwa-skill",
                    "claim-grader",
                    "slop-detector",
                ],
                "profile": "subagent_explore",
                "mode": "background",
            },
        }

    if s == C.STATE_WRITE_STATE:
        return {
            "action": C.ACTION_WRITE_PLAN_STATE,
            "instructions": (
                "Write plan state file to activate enforcement hook. "
                "Command: python .devin/scripts/approval_gate.py <plan_path> --approve --artifact plan"
            ),
            "params": {
                "plan_path": state.get("plan_path"),
                "command": f"python .devin/scripts/approval_gate.py {state.get('plan_path', '<plan_path>')} --approve --artifact plan",
            },
        }

    if s == C.STATE_DONE:
        return {
            "action": C.ACTION_DONE,
            "instructions": "Plan phase complete. Plan state written. Executor can proceed.",
            "params": {
                "sdd_path": state.get("sdd_path"),
                "plan_path": state.get("plan_path"),
                "quality_report_path": state.get("quality_report_path"),
            },
        }

    if s == C.STATE_REJECTED:
        return {
            "action": C.ACTION_DONE,
            "instructions": "Plan or SDD rejected by user. Stop.",
            "params": {"reason": state.get("rejection_reason", "unknown")},
        }

    if s == C.STATE_ESCALATE:
        return {
            "action": C.ACTION_ESCALATE,
            "instructions": (
                "Escalate to human — max rounds exceeded without convergence. "
                "Present unresolved issues and ask for guidance."
            ),
            "params": {
                "reason": state.get("escalate_reason", "unknown"),
                "unresolved_issues": state.get("review_findings", []),
            },
        }

    return {"action": "unknown", "instructions": f"Unknown state: {s}", "params": {}}


def _classify_action(state: dict, root: Path) -> dict:
    """Classify + trả action đầu tiên cho init/CLASSIFY."""
    tier = classify_tier(state["task_description"])
    state["tier"] = tier
    # S-tier → skip Plan phase. M-tier+ → BRAINSTORM trước khi ANALYZE.
    state["state"] = C.STATE_BRAINSTORM if tier != "S" else C.STATE_DONE
    append_history(state, "classify", f"Tier={tier}")
    if tier == "S":
        return {
            "action": C.ACTION_SKIP,
            "instructions": f"S-tier task — skip Plan phase. Tier={tier}. Proceed directly to execution.",
            "params": {"tier": tier},
        }
    return {
        "action": C.ACTION_BRAINSTORM,
        "instructions": (
            f"Tier={tier}. Dispatch brainstorm subagents for multi-perspective analysis. "
            f"Generate {len(brainstorm_missions(state['task_description']))}+ angles "
            f"(fastest, safest, simplest, scale, cheapest, robust). "
            f"Launch ALL brainstorm subagents in a SINGLE response for max parallelism."
        ),
        "params": {
            "tier": tier,
            "brainstorm_missions": brainstorm_missions(state["task_description"]),
            "profile": "subagent_explore",
            "mode": "background",
        },
    }


def next_action(state: dict, root: Path) -> dict:
    """Trả next action cho state hiện tại."""
    s = state.get("state")
    if s == C.STATE_INIT:
        state["state"] = C.STATE_CLASSIFY
        append_history(state, "init", "Khởi tạo orchestrator")
        s = C.STATE_CLASSIFY
    if s == C.STATE_CLASSIFY:
        return _classify_action(state, root)
    return _next_action_for_state(state, root)


def _handle_analyze(state: dict, results: dict, root: Path) -> dict:
    scout_results = results.get("scout_results", [])
    state["scout_results"] = scout_results
    state["state"] = C.STATE_DESIGN
    append_history(state, "analyze_complete", f"Collected {len(scout_results)} scout results")
    return next_action(state, root)


def _handle_brainstorm(state: dict, results: dict, root: Path) -> dict:
    """Xử lý kết quả brainstorm → chuyển sang ANALYZE (dispatch SCOUTs)."""
    brainstorm_results = results.get("brainstorm_results", [])
    state["brainstorm_results"] = brainstorm_results
    state["state"] = C.STATE_ANALYZE
    append_history(state, "brainstorm_complete", f"Collected {len(brainstorm_results)} brainstorm angles")
    # Trả action dispatch_scouts cho ANALYZE
    return {
        "action": C.ACTION_DISPATCH_SCOUTS,
        "instructions": (
            f"Brainstorm complete. Now dispatch {C.NUM_SCOUTS} SCOUT subagents in PARALLEL "
            f"(background mode, profile: subagent_explore). "
            f"Launch ALL {C.NUM_SCOUTS} in a SINGLE response for max parallelism."
        ),
        "params": {
            "num_scouts": C.NUM_SCOUTS,
            "scout_missions": scout_missions(state["task_description"]),
            "profile": "subagent_explore",
            "mode": "background",
        },
    }


def _handle_design(state: dict, results: dict, root: Path) -> dict:
    sdd_path = results.get("sdd_path", "")
    state["sdd_path"] = sdd_path
    state["state"] = C.STATE_REVIEW
    append_history(state, "design_complete", f"SDD written: {sdd_path}")
    return next_action(state, root)


def _handle_review(state: dict, results: dict, root: Path) -> dict:
    findings = results.get("findings", [])
    state["review_findings"] = findings
    blocking = [f for f in findings if f.get("severity") == "BLOCKING"]
    current_blocking_count = len(blocking)
    last_blocking_count = state.get("last_blocking_count", 0)

    # Convergence check: nếu 2 vòng liên tiếp không giảm BLOCKING → escalate
    # Nếu vẫn giảm → tiếp tục đến max 7 vòng
    if blocking and state["revision_round"] < C.MAX_REVISION_ROUNDS:
        if current_blocking_count < last_blocking_count:
            # Vẫn có tiến triển → tiếp tục revision
            state["last_blocking_count"] = current_blocking_count
            state["revision_round"] += 1
            state["state"] = C.STATE_REVISION
            append_history(
                state,
                "review_complete",
                f"{current_blocking_count} blocking issues (down from {last_blocking_count}), revision round {state['revision_round']}",
            )
        elif state.get("convergence_stall_count", 0) >= 1:
            # 2 vòng liên tiếp không giảm → escalate
            state["state"] = C.STATE_ESCALATE
            state["escalate_reason"] = (
                f"Convergence stall: {current_blocking_count} blocking issues not decreasing for 2 rounds"
            )
            append_history(state, "review_complete", "Convergence stall, escalating")
        else:
            # Lần đầu không giảm → ghi nhận, cho thêm 1 cơ hội
            state["last_blocking_count"] = current_blocking_count
            state["convergence_stall_count"] = state.get("convergence_stall_count", 0) + 1
            state["revision_round"] += 1
            state["state"] = C.STATE_REVISION
            append_history(
                state,
                "review_complete",
                f"{current_blocking_count} blocking issues (no decrease), revision round {state['revision_round']} (stall warning)",
            )
    elif blocking and state["revision_round"] >= C.MAX_REVISION_ROUNDS:
        state["state"] = C.STATE_ESCALATE
        state["escalate_reason"] = (
            f"Max {C.MAX_REVISION_ROUNDS} revision rounds exceeded, {current_blocking_count} blocking issues remain"
        )
        append_history(state, "review_complete", "Max rounds exceeded, escalating")
    else:
        state["state"] = C.STATE_SDD_APPROVAL
        state["last_blocking_count"] = 0
        state["convergence_stall_count"] = 0
        append_history(state, "review_complete", f"No blocking issues, {len(findings)} advisory")
    return next_action(state, root)


def _handle_revision(state: dict, results: dict, root: Path) -> dict:
    sdd_path = results.get("sdd_path", state.get("sdd_path"))
    state["sdd_path"] = sdd_path
    state["state"] = C.STATE_REVIEW
    append_history(state, "revision_complete", f"SDD revised: {sdd_path}")
    return next_action(state, root)


def _handle_sdd_approval(state: dict, results: dict, root: Path) -> dict:
    decision = results.get("decision", "")
    if decision == "approved":
        state["sdd_approved"] = True
        state["state"] = C.STATE_PLAN
        append_history(state, "sdd_approval", "SDD approved")
    elif decision == "rejected":
        state["approval_status"] = "rejected"
        state["rejection_reason"] = results.get("reason", "")
        state["state"] = C.STATE_REJECTED
        append_history(state, "sdd_approval", f"SDD rejected: {results.get('reason', '')}")
    elif decision == "changes_requested":
        state["approval_status"] = "changes_requested"
        modifications = results.get("modifications", "")
        # TLA+ spec-derived convergence bound: tối đa MAX_APPROVAL_ROUNDS lần
        # changes_requested liên tiếp, sau đó ESCALATE (không loop vô hạn).
        approval_round = state.get("approval_round", 0) + 1
        state["approval_round"] = approval_round
        if approval_round >= C.MAX_APPROVAL_ROUNDS:
            state["state"] = C.STATE_ESCALATE
            state["escalate_reason"] = (
                f"Max {C.MAX_APPROVAL_ROUNDS} approval rounds exceeded, "
                f"changes still requested"
            )
            append_history(state, "sdd_approval", "Max approval rounds exceeded, escalating")
        else:
            state["state"] = C.STATE_DESIGN
            append_history(state, "sdd_approval", f"SDD changes requested: {modifications}")
    else:
        return {"action": "error", "instructions": f"Invalid SDD approval decision: {decision}", "params": {}}
    return next_action(state, root)


def _handle_plan(state: dict, results: dict, root: Path) -> dict:
    plan_path = results.get("plan_path", "")
    state["plan_path"] = plan_path
    state["qc_round"] = max(state.get("qc_round", 0), 1)
    # PLAN → GAP_SCAN → QC (thay vì PLAN → QC trực tiếp)
    state["state"] = C.STATE_GAP_SCAN
    append_history(state, "plan_complete", f"Plan written: {plan_path}, moving to GAP_SCAN")
    return next_action(state, root)


def _handle_gap_scan(state: dict, results: dict, root: Path) -> dict:
    """Xử lý kết quả gap scan → chuyển sang QC."""
    gap_findings = results.get("gap_findings", [])
    state["gap_findings"] = gap_findings
    state["state"] = C.STATE_QC
    append_history(state, "gap_scan_complete", f"Found {len(gap_findings)} gaps")
    return next_action(state, root)


def _handle_qc(state: dict, results: dict, root: Path) -> dict:
    qc_result = results.get("qc_result", {})
    all_pass = qc_result.get("all_pass", False)
    quality_report_path = qc_result.get("report_path", "")
    state["quality_report_path"] = quality_report_path
    if all_pass:
        # QC pass → PLAN_ENHANCE (nâng cấp tối đa trước khi duyệt)
        state["enhance_round"] = max(state.get("enhance_round", 0), 1)
        state["state"] = C.STATE_PLAN_ENHANCE
        append_history(state, "qc_complete", "All 10 dimensions PASS, moving to PLAN_ENHANCE")
    elif state["qc_round"] < C.MAX_QC_ROUNDS:
        state["qc_round"] += 1
        state["state"] = C.STATE_PLAN
        append_history(state, "qc_complete", f"QC FAIL, looping to PLAN (round {state['qc_round']})")
    else:
        state["state"] = C.STATE_ESCALATE
        state["escalate_reason"] = (
            f"Max {C.MAX_QC_ROUNDS} QC rounds exceeded, dimensions still failing"
        )
        append_history(state, "qc_complete", "Max QC rounds exceeded, escalating")
    return next_action(state, root)


def _handle_plan_enhance(state: dict, results: dict, root: Path) -> dict:
    """Xử lý kết quả plan enhancement → PLAN_APPROVAL hoặc loop lại PLAN."""
    enhance_findings = results.get("enhance_findings", [])
    state["enhance_findings"] = enhance_findings
    blocking_enhance = [f for f in enhance_findings if f.get("severity") == "BLOCKING"]
    enhance_round = state.get("enhance_round", 1)

    if blocking_enhance and enhance_round < C.MAX_ENHANCE_ROUNDS:
        # Có blocking issues → loop lại PLAN để sửa
        state["enhance_round"] = enhance_round + 1
        state["state"] = C.STATE_PLAN
        append_history(
            state,
            "enhance_complete",
            f"{len(blocking_enhance)} blocking enhance issues, looping to PLAN (round {state['enhance_round']})",
        )
    elif blocking_enhance and enhance_round >= C.MAX_ENHANCE_ROUNDS:
        # Max enhance rounds → escalate
        state["state"] = C.STATE_ESCALATE
        state["escalate_reason"] = (
            f"Max {C.MAX_ENHANCE_ROUNDS} enhance rounds exceeded, {len(blocking_enhance)} blocking issues remain"
        )
        append_history(state, "enhance_complete", "Max enhance rounds exceeded, escalating")
    else:
        # Clean → PLAN_APPROVAL
        state["state"] = C.STATE_PLAN_APPROVAL
        append_history(state, "enhance_complete", f"Enhancement clean, {len(enhance_findings)} advisory only")
    return next_action(state, root)


def _handle_plan_approval(state: dict, results: dict, root: Path) -> dict:
    decision = results.get("decision", "")
    target = results.get("target", "plan")  # 'sdd' hoặc 'plan'
    if decision == "approved":
        state["plan_approved"] = True
        state["approval_status"] = "approved"
        state["state"] = C.STATE_WRITE_STATE
        append_history(state, "plan_approval", "Plan approved")
    elif decision == "rejected":
        state["approval_status"] = "rejected"
        state["rejection_reason"] = results.get("reason", "")
        state["state"] = C.STATE_REJECTED
        append_history(state, "plan_approval", f"Plan rejected: {results.get('reason', '')}")
    elif decision == "changes_requested":
        state["approval_status"] = "changes_requested"
        modifications = results.get("modifications", "")
        # TLA+ spec-derived convergence bound: tối đa MAX_APPROVAL_ROUNDS lần
        # changes_requested liên tiếp, sau đó ESCALATE (không loop vô hạn).
        approval_round = state.get("approval_round", 0) + 1
        state["approval_round"] = approval_round
        if approval_round >= C.MAX_APPROVAL_ROUNDS:
            state["state"] = C.STATE_ESCALATE
            state["escalate_reason"] = (
                f"Max {C.MAX_APPROVAL_ROUNDS} approval rounds exceeded, "
                f"changes still requested"
            )
            append_history(state, "plan_approval", "Max approval rounds exceeded, escalating")
        else:
            # Nếu user yêu cầu sửa SDD → quay về DESIGN; nếu sửa plan → quay về PLAN
            state["state"] = C.STATE_DESIGN if target == "sdd" else C.STATE_PLAN
            append_history(state, "plan_approval", f"Plan changes requested ({target}): {modifications}")
    else:
        return {"action": "error", "instructions": f"Invalid plan approval decision: {decision}", "params": {}}
    return next_action(state, root)


def _handle_write_state(state: dict, results: dict, root: Path) -> dict:
    state["state"] = C.STATE_DONE
    append_history(state, "write_state_complete", "Plan state written, enforcement hook activated")
    return next_action(state, root)


def process_step(state: dict, root: Path, results: dict) -> dict:
    """Xử lý results từ agent và chuyển state."""
    s = state["state"]
    action = results.get("action", "")

    if s == C.STATE_BRAINSTORM and action == C.ACTION_BRAINSTORM:
        return _handle_brainstorm(state, results, root)
    if s == C.STATE_ANALYZE and action == C.ACTION_WAIT_SCOUTS:
        return _handle_analyze(state, results, root)
    if s == C.STATE_DESIGN and action == C.ACTION_DISPATCH_ARCHITECT:
        return _handle_design(state, results, root)
    if s == C.STATE_REVIEW and action == C.ACTION_DISPATCH_REVIEWERS:
        return _handle_review(state, results, root)
    if s == C.STATE_REVISION and action == C.ACTION_DISPATCH_REVISION:
        return _handle_revision(state, results, root)
    if s == C.STATE_SDD_APPROVAL and action == C.ACTION_PRESENT_SDD_APPROVAL:
        return _handle_sdd_approval(state, results, root)
    if s == C.STATE_PLAN and action == C.ACTION_DECOMPOSE_PLAN:
        return _handle_plan(state, results, root)
    if s == C.STATE_GAP_SCAN and action == C.ACTION_GAP_SCAN:
        return _handle_gap_scan(state, results, root)
    if s == C.STATE_QC and action == C.ACTION_RUN_QC:
        return _handle_qc(state, results, root)
    if s == C.STATE_PLAN_ENHANCE and action == C.ACTION_PLAN_ENHANCE:
        return _handle_plan_enhance(state, results, root)
    if s == C.STATE_PLAN_APPROVAL and action == C.ACTION_PRESENT_PLAN_APPROVAL:
        return _handle_plan_approval(state, results, root)
    if s == C.STATE_WRITE_STATE and action == C.ACTION_WRITE_PLAN_STATE:
        return _handle_write_state(state, results, root)

    return {
        "action": "error",
        "instructions": f"Cannot process action '{action}' in state '{s}'",
        "params": {"state": s, "action": action},
    }
