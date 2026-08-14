#!/usr/bin/env python3
"""fsm_model_check.py — Model checker (TLC-equivalent) cho TLA+ specs.

Task 3.6 (SECURITY_REMEDIATION_PLAN.md): formal FSM verification.
Không có Java/TLC trong môi trường -> duyệt toàn bộ không gian trạng thái
hữu hạn (DFS exhaustive) và kiểm chứng:

Plan Orchestrator (specs/plan_orchestrator.tla):
  S1 Safety     : WRITE_STATE chỉ reachable khi plan_approved
  S2 Liveness   : mọi đường chạy cuối cùng tới DONE/REJECTED/ESCALATE
  S3 Convergence: revision/QC/enhance/approval counters bị chặn (loop hữu hạn)

State Router (specs/state_router.tla):
  R1 Safety     : EXECUTE chỉ sau APPROVE (approved=TRUE)
  R2 Deadlock   : mọi state (trừ DONE) có >= 1 edge enabled
  R3 Liveness   : mọi đường chạy cuối cùng tới DONE

Usage:
  python .devin/scripts/fsm_model_check.py [--verbose]
Exit 0 nếu mọi property PASS, 1 nếu có FAIL.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Plan Orchestrator FSM (mirror specs/plan_orchestrator.tla + state_machine.py)
# ---------------------------------------------------------------------------

MAX_REVISION = 7
MAX_QC = 7
MAX_ENHANCE = 3
MAX_APPROVAL = 7

TERMINAL = frozenset({"DONE", "REJECTED", "ESCALATE"})


@dataclass(frozen=True)
class OrcState:
    state: str
    revision_round: int = 0
    qc_round: int = 0
    enhance_round: int = 0
    approval_round: int = 0
    stall_count: int = 0
    plan_approved: bool = False


def orc_transitions(s: OrcState) -> list[OrcState]:
    """Mirror Next relation — nondeterministic branches được mở rộng đầy đủ.

    QUAN TRỌNG: counters carry qua mọi transition (giống state dict thật),
    chỉ field bị code thay đổi mới được sửa. approval_round KHÔNG reset khi
    approved (monotonic — nếu reset, approve/changes xen kẽ loop vô hạn).
    """
    def to(new_state: str, **kw) -> OrcState:
        base = dict(
            state=new_state,
            revision_round=s.revision_round,
            qc_round=s.qc_round,
            enhance_round=s.enhance_round,
            approval_round=s.approval_round,
            stall_count=s.stall_count,
            plan_approved=s.plan_approved,
        )
        base.update(kw)
        return OrcState(**base)
    st = s.state
    out: list[OrcState] = []
    if st == "INIT":
        out.append(to("CLASSIFY"))
    elif st == "CLASSIFY":
        out.append(to("BRAINSTORM"))            # tier != S
        out.append(to("DONE"))                  # S-tier skip
    elif st == "BRAINSTORM":
        out.append(to("ANALYZE"))
    elif st == "ANALYZE":
        out.append(to("DESIGN"))
    elif st == "DESIGN":
        out.append(to("REVIEW"))
    elif st == "REVIEW":
        out.append(to("SDD_APPROVAL"))          # clean
        if s.revision_round < MAX_REVISION:
            out.append(to("REVISION", revision_round=s.revision_round + 1, stall_count=0))
            out.append(to("REVISION", revision_round=s.revision_round + 1,
                          stall_count=s.stall_count + 1))
        out.append(to("ESCALATE"))              # still_blocking / stall >= 2
    elif st == "REVISION":
        out.append(to("REVIEW"))
    elif st == "SDD_APPROVAL":
        out.append(to("PLAN"))                  # approved
        out.append(to("REJECTED"))              # rejected
        if s.approval_round < MAX_APPROVAL:
            out.append(to("DESIGN", approval_round=s.approval_round + 1))
        else:
            out.append(to("ESCALATE"))
    elif st == "PLAN":
        out.append(to("GAP_SCAN", qc_round=max(s.qc_round, 1)))
    elif st == "GAP_SCAN":
        out.append(to("QC"))
    elif st == "QC":
        out.append(to("PLAN_ENHANCE", qc_round=s.qc_round + 1,
                      enhance_round=max(s.enhance_round, 1)))               # pass
        if s.qc_round < MAX_QC:
            out.append(to("PLAN", qc_round=s.qc_round + 1))                 # fail, loop
        else:
            out.append(to("ESCALATE"))                                      # fail, max
    elif st == "PLAN_ENHANCE":
        out.append(to("PLAN_APPROVAL"))                                     # clean
        if s.enhance_round < MAX_ENHANCE:
            out.append(to("PLAN", enhance_round=s.enhance_round + 1))       # blocking, loop
        else:
            out.append(to("ESCALATE"))                                      # blocking, max
    elif st == "PLAN_APPROVAL":
        out.append(to("WRITE_STATE", plan_approved=True))                   # approved
        out.append(to("REJECTED"))                                          # rejected
        if s.approval_round < MAX_APPROVAL:
            out.append(to("DESIGN", approval_round=s.approval_round + 1))   # target=sdd
            out.append(to("PLAN", approval_round=s.approval_round + 1))     # target=plan
        else:
            out.append(to("ESCALATE"))
    elif st == "WRITE_STATE":
        assert s.plan_approved, "WRITE_STATE mà chưa approved -> vi phạm Safety S1"
        out.append(to("DONE"))
    # terminal: không có transition (liveness yêu cầu tới đây và dừng)
    return out


# ---------------------------------------------------------------------------
# State Router FSM (mirror specs/state_router.tla + state_router.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouterState:
    step: str
    findings: int = 0
    design: bool = False
    plan: bool = False
    quality_score: float = 0.0
    approved: bool = False
    tasks_remaining: int = 0
    verify_rounds: int = 0
    design_rounds: int = 0
    all_gates_pass: bool = False
    done: bool = False


MAX_DESIGN_ROUNDS = 5


def router_transitions(s: RouterState) -> list[RouterState]:
    """Mirror EDGES — counters carry qua mọi transition.

    QUALITY_CHECK->DESIGN loop bị chặn bởi design_rounds (tương đương
    MAX_LOOP_ITERATIONS hardening, Task 3.9) — sau max rounds, thoát qua
    APPROVE để không deadlock.
    """
    def to(new_step: str, **kw) -> RouterState:
        base = dict(
            step=new_step,
            findings=s.findings,
            design=s.design,
            plan=s.plan,
            quality_score=s.quality_score,
            approved=s.approved,
            tasks_remaining=s.tasks_remaining,
            verify_rounds=s.verify_rounds,
            design_rounds=s.design_rounds,
            all_gates_pass=s.all_gates_pass,
            done=s.done,
        )
        base.update(kw)
        return RouterState(**base)

    out: list[RouterState] = []
    st = s.step
    if st == "ANALYZE":
        if s.findings < 5:
            out.append(to("ANALYZE", findings=s.findings + 1))
        else:
            out.append(to("DESIGN"))
    elif st == "DESIGN":
        out.append(to("PLAN", design=True))
    elif st == "PLAN":
        out.append(to("QUALITY_CHECK", plan=True))
    elif st == "QUALITY_CHECK":
        if s.design_rounds < MAX_DESIGN_ROUNDS:
            out.append(to("DESIGN", design_rounds=s.design_rounds + 1))  # score < 0.8, loop
        else:
            out.append(to("APPROVE"))                                    # max rounds, thoát
        out.append(to("APPROVE"))                                        # score >= 0.8
    elif st == "APPROVE":
        out.append(to("DISPATCH", approved=True))
        out.append(to("DONE", done=True))                                # reject
    elif st == "DISPATCH":
        out.append(to("EXECUTE", tasks_remaining=3))
    elif st == "EXECUTE":
        if s.tasks_remaining > 0:
            rem = s.tasks_remaining - 1
            out.append(to("VERIFY" if rem == 0 else "EXECUTE", tasks_remaining=rem))
    elif st == "VERIFY":
        out.append(to("REPORT", all_gates_pass=True))
        if s.verify_rounds < 5:
            out.append(to("EXECUTE", verify_rounds=s.verify_rounds + 1, tasks_remaining=3))
        else:
            out.append(to("REPORT", all_gates_pass=False))               # max verify rounds
    elif st == "REPORT":
        out.append(to("DONE", done=True))
    return out


# ---------------------------------------------------------------------------
# Exhaustive exploration
# ---------------------------------------------------------------------------

def explore(start, transitions, terminals: frozenset) -> tuple[set, list[tuple]]:
    """DFS toàn bộ không gian trạng thái.

    Trả về (reachable, violations):
      violations = list[(state, rule_name)] với rule:
        - 'safety'  : safety property vi phạm tại state
        - 'deadlock': state non-terminal không có transition
        - 'cycle'   : state nằm trong cycle không thoát được (liveness fail)
    """
    reachable: set = set()
    violations: list[tuple] = []
    stack = [start]
    on_stack: set = set()
    finished: set = set()

    def visit(node):
        if node in finished or node in on_stack:
            return
        on_stack.add(node)
        succ = transitions(node)
        cur = node.state if hasattr(node, "state") else node.step
        if cur not in terminals and not succ:
            violations.append((node, "deadlock"))
        for nxt in succ:
            if nxt in on_stack:
                violations.append((node, "cycle"))
            else:
                visit(nxt)
        on_stack.discard(node)
        finished.add(node)
        reachable.add(node)

    visit(start)
    return reachable, violations


def check_orchestrator(verbose: bool = False) -> list[str]:
    fails: list[str] = []
    start = OrcState("INIT")
    reachable, violations = explore(start, orc_transitions, TERMINAL)

    for node, rule in violations:
        if rule == "cycle":
            fails.append(f"[Orchestrator] LIVENESS FAIL: cycle tại {node.state} (rounds="
                         f"r{node.revision_round} q{node.qc_round} e{node.enhance_round} "
                         f"a{node.approval_round})")
        elif rule == "deadlock":
            fails.append(f"[Orchestrator] DEADLOCK FAIL: {node.state} không có transition")

    for node in reachable:
        if node.state == "WRITE_STATE" and not node.plan_approved:
            fails.append("[Orchestrator] SAFETY FAIL: WRITE_STATE không plan_approved")
        if node.state not in TERMINAL and node not in [n for v, _ in violations for n in []]:
            pass  # liveness cycle đã bắt ở trên

    if verbose:
        print(f"[Orchestrator] reachable states: {len(reachable)}")
    return fails


def check_router(verbose: bool = False) -> list[str]:
    fails: list[str] = []
    start = RouterState("ANALYZE")
    reachable, violations = explore(start, router_transitions, frozenset({"DONE"}))

    for node, rule in violations:
        if rule == "cycle":
            fails.append(f"[Router] LIVENESS FAIL: cycle tại {node.step}")
        elif rule == "deadlock":
            fails.append(f"[Router] DEADLOCK FAIL: {node.step} không có transition")

    for node in reachable:
        if node.step in ("EXECUTE", "DISPATCH") and not node.approved:
            fails.append(f"[Router] SAFETY FAIL: {node.step} mà chưa approved")
        if node.done and node.step != "DONE":
            fails.append(f"[Router] SAFETY FAIL: done=TRUE nhưng step={node.step}")

    if verbose:
        print(f"[Router] reachable states: {len(reachable)}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description="Model check TLA+ specs (TLC-equivalent)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    fails: list[str] = []
    fails += check_orchestrator(args.verbose)
    fails += check_router(args.verbose)

    if fails:
        for f in fails:
            print(f"FAIL: {f}", file=sys.stderr)
        print(f"Model check FAILED: {len(fails)} violation(s)", file=sys.stderr)
        return 1
    print("Model check PASSED: Safety / Liveness / Convergence / No-deadlock — all OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())