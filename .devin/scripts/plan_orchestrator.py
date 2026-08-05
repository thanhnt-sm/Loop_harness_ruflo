#!/usr/bin/env python3
"""plan_orchestrator.py — FSM orchestrator cho Plan Phase.

Script này điều phối toàn bộ Plan Phase theo state machine (FSM):
  INIT → CLASSIFY → ANALYZE → DESIGN → REVIEW → REVISION → PLAN → QC → APPROVAL → WRITE_STATE → DONE

Cách dùng (agent tương tác qua CLI):
  # Bước 1: Khởi tạo — phân loại tier, trả next action
  python plan_orchestrator.py --init --task "<task description>"

  # Bước 2: Sau mỗi action, agent gọi --step với results để nhận next action
  python plan_orchestrator.py --step --state <state.json> --results <results.json>

  # Bước 3: Kiểm tra trạng thái hiện tại
  python plan_orchestrator.py --status --state <state.json>

State file: .devin/plan_state/<task_slug>_orchestrator.json
Output files: docs/plans/<task_slug>/SOLUTION_DESIGN.md, IMPLEMENTATION_PLAN.md, QUALITY_REPORT.md

Exit codes:
  0 = state updated thành công
  1 = error
  2 = invalid args
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Bước 0: Ép stdout/stderr dùng UTF-8 (tránh lỗi cp1258 trên Windows)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Danh sách trạng thái FSM
STATE_INIT = "INIT"
STATE_CLASSIFY = "CLASSIFY"
STATE_ANALYZE = "ANALYZE"
STATE_DESIGN = "DESIGN"
STATE_REVIEW = "REVIEW"
STATE_REVISION = "REVISION"
STATE_PLAN = "PLAN"
STATE_QC = "QC"
STATE_APPROVAL = "APPROVAL"
STATE_WRITE_STATE = "WRITE_STATE"
STATE_DONE = "DONE"
STATE_REJECTED = "REJECTED"
STATE_ESCALATE = "ESCALATE"

# Action types — chỉ định agent cần làm gì
ACTION_DISPATCH_SCOUTS = "dispatch_scouts"
ACTION_WAIT_SCOUTS = "wait_scouts"
ACTION_DISPATCH_ARCHITECT = "dispatch_architect"
ACTION_DISPATCH_REVIEWERS = "dispatch_reviewers"
ACTION_DISPATCH_REVISION = "dispatch_revision"
ACTION_DECOMPOSE_PLAN = "decompose_plan"
ACTION_RUN_QC = "run_qc"
ACTION_PRESENT_APPROVAL = "present_approval"
ACTION_WRITE_PLAN_STATE = "write_plan_state"
ACTION_DONE = "done"
ACTION_SKIP = "skip"
ACTION_ESCALATE = "escalate"

# Số SCOUT và reviewer
NUM_SCOUTS = 5
NUM_REVIEWERS = 3
MAX_REVISION_ROUNDS = 3
MAX_QC_ROUNDS = 3


def _repo_root() -> Path:
    """Tìm repo root — đi lên cho đến khi thấy .devin/"""
    p = Path.cwd()
    for parent in [p] + list(p.parents):
        if (parent / ".devin").is_dir():
            return parent
    return p


def _slugify(text: str) -> str:
    """Tạo slug từ task description — lowercase, hyphen-separated."""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60] if slug else "task"


def _state_dir(root: Path) -> Path:
    """Trả về thư mục plan_state. Tạo nếu chưa tồn tại."""
    sd = root / ".devin" / "plan_state"
    sd.mkdir(parents=True, exist_ok=True)
    return sd


def _plans_dir(root: Path, task_slug: str) -> Path:
    """Trả về thư mục docs/plans/<task_slug>/. Tạo nếu chưa tồn tại."""
    pd = root / "docs" / "plans" / task_slug
    pd.mkdir(parents=True, exist_ok=True)
    return pd


def _state_path(root: Path, task_slug: str) -> Path:
    """Trả về đường dẫn state file cho orchestrator."""
    return _state_dir(root) / f"{task_slug}_orchestrator.json"


def _load_state(state_path: Path) -> dict:
    """Đọc state file. Trả state rỗng nếu chưa có."""
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state_path: Path, state: dict) -> None:
    """Ghi state file JSON."""
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _classify_tier(task_description: str) -> str:
    """
    Phân loại task tier dựa trên description.
    S: <50 chars, 1 file, no verification, no destructive op
    M: 1-3 files, simple logic, 30min-2h
    L: Multiple files, needs research, 2h+
    XL: Architecture change, security-critical, multi-system
    Default: M (fail-closed).
    """
    if not task_description:
        return "M"
    desc = task_description.lower().strip()
    # S-tier indicators
    s_indicators = [
        len(desc) < 50,
        any(kw in desc for kw in ["typo", "rename", "update date", "fix spelling"]),
        any(kw in desc for kw in ["s-tier", "trivial", "one line", "1 line"]),
    ]
    # XL-tier indicators
    xl_indicators = [
        any(kw in desc for kw in ["architecture", "refactor", "migrate", "rewrite"]),
        any(kw in desc for kw in ["security", "auth", "encryption", "compliance"]),
        any(kw in desc for kw in ["multi-system", "cross-service", "distributed"]),
        len(desc) > 300,
    ]
    # L-tier indicators
    l_indicators = [
        any(kw in desc for kw in ["multiple files", "several files", "multiple modules", "integration", "database"]),
        any(kw in desc for kw in ["performance", "cache", "migration", "api design"]),
        len(desc) > 150,
    ]
    if sum(xl_indicators) >= 2:
        return "XL"
    if sum(l_indicators) >= 2:
        return "L"
    if sum(s_indicators) >= 2:
        return "S"
    return "M"


def _create_initial_state(task_description: str, root: Path) -> dict:
    """Tạo state ban đầu cho orchestrator."""
    task_slug = _slugify(task_description)
    state = {
        "task_description": task_description,
        "task_slug": task_slug,
        "state": STATE_INIT,
        "tier": None,
        "round": 0,
        "revision_round": 0,
        "qc_round": 0,
        "scout_results": [],
        "sdd_path": None,
        "review_findings": [],
        "plan_path": None,
        "quality_report_path": None,
        "approval_status": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }
    return state


def _append_history(state: dict, action: str, detail: str) -> None:
    """Ghi lịch sử action vào state."""
    state["history"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state["state"],
            "action": action,
            "detail": detail,
        }
    )
    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def _next_action(state: dict, root: Path) -> dict:
    """
    Xác định next action dựa trên current state.
    Trả về dict {action, instructions, params} cho agent.
    """
    s = state["state"]

    # INIT → CLASSIFY
    if s == STATE_INIT:
        state["state"] = STATE_CLASSIFY
        _append_history(state, "init", "Khởi tạo orchestrator")
        # Fall through to CLASSIFY

    # CLASSIFY → ANALYZE hoặc SKIP
    if state["state"] == STATE_CLASSIFY:
        tier = _classify_tier(state["task_description"])
        state["tier"] = tier
        state["state"] = STATE_ANALYZE if tier != "S" else STATE_DONE
        _append_history(state, "classify", f"Tier={tier}")
        if tier == "S":
            return {
                "action": ACTION_SKIP,
                "instructions": f"S-tier task — skip Plan phase. Tier={tier}. Proceed directly to execution.",
                "params": {"tier": tier},
            }
        return {
            "action": ACTION_DISPATCH_SCOUTS,
            "instructions": (
                f"Tier={tier}. Dispatch {NUM_SCOUTS} SCOUT subagents in PARALLEL "
                f"(background mode, profile: subagent_explore). "
                f"Launch ALL {NUM_SCOUTS} in a SINGLE response for max parallelism. "
                f"Each SCOUT has a specific mission — see params below."
            ),
            "params": {
                "tier": tier,
                "num_scouts": NUM_SCOUTS,
                "scout_missions": _scout_missions(state["task_description"]),
                "profile": "subagent_explore",
                "mode": "background",
            },
        }

    # ANALYZE → DESIGN (sau khi có scout results)
    if s == STATE_ANALYZE:
        return {
            "action": ACTION_WAIT_SCOUTS,
            "instructions": (
                f"Collect results from all {NUM_SCOUTS} SCOUT subagents using read_subagent. "
                f"Aggregate findings into analysis_context. "
                f"Then call --step with results to proceed to DESIGN."
            ),
            "params": {
                "num_scouts": NUM_SCOUTS,
            },
        }

    # DESIGN → REVIEW
    if s == STATE_DESIGN:
        return {
            "action": ACTION_DISPATCH_ARCHITECT,
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
                "output_file": str(
                    _plans_dir(root, state["task_slug"]) / "SOLUTION_DESIGN.md"
                ),
            },
        }

    # REVIEW → PLAN hoặc REVISION
    if s == STATE_REVIEW:
        return {
            "action": ACTION_DISPATCH_REVIEWERS,
            "instructions": (
                f"Dispatch {NUM_REVIEWERS} adversarial reviewers in PARALLEL "
                f"(background mode, profile: subagent_explore). "
                f"Launch ALL {NUM_REVIEWERS} in a SINGLE response. "
                f"Reviewers: SABOTEUR, NEW_HIRE, SECURITY_AUDITOR."
            ),
            "params": {
                "num_reviewers": NUM_REVIEWERS,
                "reviewers": _reviewer_personas(),
                "profile": "subagent_explore",
                "mode": "background",
                "sdd_path": state.get("sdd_path"),
            },
        }

    # REVISION → REVIEW
    if s == STATE_REVISION:
        return {
            "action": ACTION_DISPATCH_REVISION,
            "instructions": (
                f"Revision round {state['revision_round']}/{MAX_REVISION_ROUNDS}. "
                f"Resume ARCHITECT subagent with blocking issues to fix. "
                f"Then re-dispatch reviewers."
            ),
            "params": {
                "revision_round": state["revision_round"],
                "max_rounds": MAX_REVISION_ROUNDS,
                "blocking_issues": [
                    f for f in state.get("review_findings", []) if f.get("severity") == "BLOCKING"
                ],
            },
        }

    # PLAN → QC
    if s == STATE_PLAN:
        return {
            "action": ACTION_DECOMPOSE_PLAN,
            "instructions": (
                "Decompose SDD into atomic tasks. "
                "Build dependency DAG. Generate coverage matrix. "
                "Write IMPLEMENTATION_PLAN.md using template. "
                "Template: docs/templates/PLAN_TEMPLATE.md"
            ),
            "params": {
                "template": "docs/templates/PLAN_TEMPLATE.md",
                "output_file": str(
                    _plans_dir(root, state["task_slug"]) / "IMPLEMENTATION_PLAN.md"
                ),
                "sdd_path": state.get("sdd_path"),
            },
        }

    # QC → APPROVAL hoặc DESIGN (loop)
    if s == STATE_QC:
        return {
            "action": ACTION_RUN_QC,
            "instructions": (
                f"QC round {state['qc_round']}/{MAX_QC_ROUNDS}. "
                f"Run quality check on IMPLEMENTATION_PLAN.md. "
                f"Command: python .devin/scripts/plan_quality_check.py <plan_path>"
            ),
            "params": {
                "qc_round": state["qc_round"],
                "max_rounds": MAX_QC_ROUNDS,
                "plan_path": state.get("plan_path"),
                "command": f"python .devin/scripts/plan_quality_check.py {state.get('plan_path', '<plan_path>')}",
            },
        }

    # APPROVAL → WRITE_STATE hoặc REJECTED hoặc DESIGN
    if s == STATE_APPROVAL:
        return {
            "action": ACTION_PRESENT_APPROVAL,
            "instructions": (
                "Present plan summary to user for approval. "
                "Use interactive approval gate. "
                "Command: python .devin/scripts/approval_gate.py <plan_path> --interactive"
            ),
            "params": {
                "plan_path": state.get("plan_path"),
                "sdd_path": state.get("sdd_path"),
                "quality_report_path": state.get("quality_report_path"),
                "command": f"python .devin/scripts/approval_gate.py {state.get('plan_path', '<plan_path>')} --interactive",
            },
        }

    # WRITE_STATE → DONE
    if s == STATE_WRITE_STATE:
        return {
            "action": ACTION_WRITE_PLAN_STATE,
            "instructions": (
                "Write plan state file to activate enforcement hook. "
                "Command: python .devin/scripts/approval_gate.py <plan_path> --approve"
            ),
            "params": {
                "plan_path": state.get("plan_path"),
                "command": f"python .devin/scripts/approval_gate.py {state.get('plan_path', '<plan_path>')} --approve",
            },
        }

    # DONE
    if s == STATE_DONE:
        return {
            "action": ACTION_DONE,
            "instructions": "Plan phase complete. Plan state written. Executor can proceed.",
            "params": {
                "sdd_path": state.get("sdd_path"),
                "plan_path": state.get("plan_path"),
                "quality_report_path": state.get("quality_report_path"),
            },
        }

    # REJECTED
    if s == STATE_REJECTED:
        return {
            "action": ACTION_DONE,
            "instructions": "Plan rejected by user. Stop.",
            "params": {"reason": state.get("rejection_reason", "unknown")},
        }

    # ESCALATE
    if s == STATE_ESCALATE:
        return {
            "action": ACTION_ESCALATE,
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


def _scout_missions(task_description: str) -> list[dict]:
    """Tạo work orders cho 5 SCOUT subagents."""
    return [
        {
            "id": "SCOUT-1",
            "mission": (
                f"Scan codebase structure for task: '{task_description}'. "
                "Map directory tree, module boundaries, entry points, build system. "
                "Output: structure map + dependency graph."
            ),
            "tools": ["grep", "glob", "read"],
        },
        {
            "id": "SCOUT-2",
            "mission": (
                f"Find relevant files + dependencies for: '{task_description}'. "
                "Trace call paths, locate interfaces, identify blast radius. "
                "Output: file list with relevance rationale."
            ),
            "tools": ["grep", "glob", "read"],
        },
        {
            "id": "SCOUT-3",
            "mission": (
                f"Research cutting-edge solutions for: '{task_description}'. "
                "Use web_search for patterns, libraries, prior art, pitfalls. "
                "Output: external research brief with citations."
            ),
            "tools": ["web_search", "webfetch"],
        },
        {
            "id": "SCOUT-4",
            "mission": (
                f"Analyze test coverage gaps for: '{task_description}'. "
                "Find existing tests, untested paths, test infrastructure. "
                "Output: coverage gap report."
            ),
            "tools": ["grep", "glob", "read", "exec"],
        },
        {
            "id": "SCOUT-5",
            "mission": (
                f"Check constraints for: '{task_description}'. "
                "Security policies, performance budgets, compatibility matrix, compliance. "
                "Output: constraint ledger."
            ),
            "tools": ["grep", "read", "exec"],
        },
    ]


def _reviewer_personas() -> list[dict]:
    """Tạo work orders cho 3 adversarial reviewers."""
    return [
        {
            "id": "SABOTEUR",
            "persona": "Hostile attacker",
            "question": "How do I break this design? What inputs crash it? What edge cases fail?",
        },
        {
            "id": "NEW_HIRE",
            "persona": "Junior engineer, first day",
            "question": "Can I understand this design without asking anyone? Where is it ambiguous?",
        },
        {
            "id": "SECURITY_AUDITOR",
            "persona": "OWASP-aligned auditor",
            "question": "Scan for OWASP Top 10 risks. What attack surfaces does this design open?",
        },
    ]


def _process_step(state: dict, root: Path, results: dict) -> dict:
    """
    Xử lý results từ agent và chuyển state.
    Trả về next action.
    """
    s = state["state"]
    action = results.get("action", "")

    # ANALYZE: nhận scout results → chuyển DESIGN
    if s == STATE_ANALYZE and action == ACTION_WAIT_SCOUTS:
        scout_results = results.get("scout_results", [])
        state["scout_results"] = scout_results
        state["state"] = STATE_DESIGN
        _append_history(state, "analyze_complete", f"Collected {len(scout_results)} scout results")
        return _next_action(state, root)

    # DESIGN: nhận SDD draft → chuyển REVIEW
    if s == STATE_DESIGN and action == ACTION_DISPATCH_ARCHITECT:
        sdd_path = results.get("sdd_path", "")
        state["sdd_path"] = sdd_path
        state["state"] = STATE_REVIEW
        _append_history(state, "design_complete", f"SDD written: {sdd_path}")
        return _next_action(state, root)

    # REVIEW: nhận review findings → chuyển PLAN hoặc REVISION
    if s == STATE_REVIEW and action == ACTION_DISPATCH_REVIEWERS:
        findings = results.get("findings", [])
        state["review_findings"] = findings
        blocking = [f for f in findings if f.get("severity") == "BLOCKING"]
        if blocking and state["revision_round"] < MAX_REVISION_ROUNDS:
            state["revision_round"] += 1
            state["state"] = STATE_REVISION
            _append_history(
                state,
                "review_complete",
                f"{len(blocking)} blocking issues, revision round {state['revision_round']}",
            )
        elif blocking and state["revision_round"] >= MAX_REVISION_ROUNDS:
            state["state"] = STATE_ESCALATE
            state["escalate_reason"] = (
                f"Max {MAX_REVISION_ROUNDS} revision rounds exceeded, {len(blocking)} blocking issues remain"
            )
            _append_history(state, "review_complete", "Max rounds exceeded, escalating")
        else:
            state["state"] = STATE_PLAN
            _append_history(state, "review_complete", f"No blocking issues, {len(findings)} advisory")
        return _next_action(state, root)

    # REVISION: nhận revised SDD → chuyển REVIEW
    if s == STATE_REVISION and action == ACTION_DISPATCH_REVISION:
        sdd_path = results.get("sdd_path", state.get("sdd_path"))
        state["sdd_path"] = sdd_path
        state["state"] = STATE_REVIEW
        _append_history(state, "revision_complete", f"SDD revised: {sdd_path}")
        return _next_action(state, root)

    # PLAN: nhận plan path → chuyển QC
    if s == STATE_PLAN and action == ACTION_DECOMPOSE_PLAN:
        plan_path = results.get("plan_path", "")
        state["plan_path"] = plan_path
        state["qc_round"] = max(state.get("qc_round", 0), 1)
        state["state"] = STATE_QC
        _append_history(state, "plan_complete", f"Plan written: {plan_path}")
        return _next_action(state, root)

    # QC: nhận quality check result → chuyển APPROVAL hoặc DESIGN (loop)
    if s == STATE_QC and action == ACTION_RUN_QC:
        qc_result = results.get("qc_result", {})
        all_pass = qc_result.get("all_pass", False)
        quality_report_path = qc_result.get("report_path", "")
        state["quality_report_path"] = quality_report_path
        if all_pass:
            state["state"] = STATE_APPROVAL
            _append_history(state, "qc_complete", "All 10 dimensions PASS")
        elif state["qc_round"] < MAX_QC_ROUNDS:
            state["qc_round"] += 1
            state["state"] = STATE_DESIGN
            _append_history(
                state,
                "qc_complete",
                f"QC FAIL, looping to DESIGN (round {state['qc_round']})",
            )
        else:
            state["state"] = STATE_ESCALATE
            state["escalate_reason"] = (
                f"Max {MAX_QC_ROUNDS} QC rounds exceeded, dimensions still failing"
            )
            _append_history(state, "qc_complete", "Max QC rounds exceeded, escalating")
        return _next_action(state, root)

    # APPROVAL: nhận approval decision → chuyển WRITE_STATE hoặc REJECTED hoặc DESIGN
    if s == STATE_APPROVAL and action == ACTION_PRESENT_APPROVAL:
        decision = results.get("decision", "")
        if decision == "approved":
            state["approval_status"] = "approved"
            state["state"] = STATE_WRITE_STATE
            _append_history(state, "approval", "Approved")
        elif decision == "rejected":
            state["approval_status"] = "rejected"
            state["rejection_reason"] = results.get("reason", "")
            state["state"] = STATE_REJECTED
            _append_history(state, "approval", f"Rejected: {results.get('reason', '')}")
        elif decision == "changes_requested":
            state["approval_status"] = "changes_requested"
            modifications = results.get("modifications", "")
            # Loop back to DESIGN or PLAN depending on what needs changing
            state["state"] = STATE_DESIGN
            _append_history(state, "approval", f"Changes requested: {modifications}")
        else:
            return {
                "action": "error",
                "instructions": f"Invalid approval decision: {decision}",
                "params": {},
            }
        return _next_action(state, root)

    # WRITE_STATE: plan state written → DONE
    if s == STATE_WRITE_STATE and action == ACTION_WRITE_PLAN_STATE:
        state["state"] = STATE_DONE
        _append_history(state, "write_state_complete", "Plan state written, enforcement hook activated")
        return _next_action(state, root)

    # Unknown state/action
    return {
        "action": "error",
        "instructions": f"Cannot process action '{action}' in state '{s}'",
        "params": {"state": s, "action": action},
    }


def cmd_init(task_description: str) -> dict:
    """--init: Khởi tạo orchestrator state, trả next action."""
    root = _repo_root()
    state = _create_initial_state(task_description, root)
    state_path = _state_path(root, state["task_slug"])
    _save_state(state_path, state)
    next_action = _next_action(state, root)
    _save_state(state_path, state)
    return {
        "state_file": str(state_path),
        "task_slug": state["task_slug"],
        "tier": state["tier"],
        "current_state": state["state"],
        "next_action": next_action,
    }


def cmd_step(state_file: str, results_file: str) -> dict:
    """--step: Xử lý results, chuyển state, trả next action."""
    root = _repo_root()
    state_path = Path(state_file)
    state = _load_state(state_path)
    if not state:
        return {"error": f"Cannot load state file: {state_file}"}
    try:
        results = json.loads(Path(results_file).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Cannot load results file: {results_file}: {e}"}
    next_action = _process_step(state, root, results)
    _save_state(state_path, state)
    return {
        "state_file": str(state_path),
        "current_state": state["state"],
        "next_action": next_action,
    }


def cmd_status(state_file: str) -> dict:
    """--status: Trả trạng thái hiện tại."""
    state = _load_state(Path(state_file))
    if not state:
        return {"error": f"Cannot load state file: {state_file}"}
    root = _repo_root()
    next_action = _next_action(state, root)
    return {
        "state_file": state_file,
        "current_state": state["state"],
        "tier": state.get("tier"),
        "round": state.get("round", 0),
        "revision_round": state.get("revision_round", 0),
        "qc_round": state.get("qc_round", 0),
        "sdd_path": state.get("sdd_path"),
        "plan_path": state.get("plan_path"),
        "quality_report_path": state.get("quality_report_path"),
        "approval_status": state.get("approval_status"),
        "next_action": next_action,
    }


def _parse_args(argv: list[str]) -> dict:
    """Parse CLI args thủ công."""
    args = {
        "init": False,
        "step": False,
        "status": False,
        "task": "",
        "state": "",
        "results": "",
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--init":
            args["init"] = True
        elif a == "--step":
            args["step"] = True
        elif a == "--status":
            args["status"] = True
        elif a == "--task":
            i += 1
            if i < len(argv):
                args["task"] = argv[i]
        elif a == "--state":
            i += 1
            if i < len(argv):
                args["state"] = argv[i]
        elif a == "--results":
            i += 1
            if i < len(argv):
                args["results"] = argv[i]
        i += 1
    return args


def main() -> int:
    """Entry point CLI."""
    args = _parse_args(sys.argv[1:])

    if args["init"]:
        if not args["task"]:
            print("Usage: python plan_orchestrator.py --init --task \"<task description>\"", file=sys.stderr)
            return 2
        result = cmd_init(args["task"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args["step"]:
        if not args["state"] or not args["results"]:
            print("Usage: python plan_orchestrator.py --step --state <state.json> --results <results.json>", file=sys.stderr)
            return 2
        result = cmd_step(args["state"], args["results"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if "error" not in result else 1

    if args["status"]:
        if not args["state"]:
            print("Usage: python plan_orchestrator.py --status --state <state.json>", file=sys.stderr)
            return 2
        result = cmd_status(args["state"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if "error" not in result else 1

    print("Usage: python plan_orchestrator.py --init|--step|--status [options]", file=sys.stderr)
    print("  --init --task \"<task>\"           Khởi tạo Plan phase", file=sys.stderr)
    print("  --step --state <f> --results <f>  Xử lý results, chuyển state", file=sys.stderr)
    print("  --status --state <f>              Kiểm tra trạng thái", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
