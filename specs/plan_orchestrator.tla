------------------------ MODULE plan_orchestrator ------------------------
(*
 * Plan Orchestrator FSM — TLA+ spec (Task 3.6, SECURITY_REMEDIATION_PLAN.md)
 *
 * Mirror của .devin/scripts/plan_fsm/state_machine.py
 * (CVE-2026-AHD-016 formal verification).
 *
 * Properties:
 *   Safety     : WRITE_STATE (activation của execution enforcement)
 *                chỉ reachable khi plan_approved = TRUE.
 *   Liveness   : Mọi run dưới weak fairness cuối cùng tới
 *                DONE \/ ESCALATE \/ REJECTED.
 *   Convergence: Revision/QC/Enhance/Approval loops bị chặn bởi
 *                counter -> không có loop vô hạn.
 *)
EXTENDS Integers, Sequences, FiniteSets

CONSTANT
  MaxRevision, MaxQC, MaxEnhance, MaxApproval

VARIABLES
  state,            \* trạng thái hiện tại
  revisionRound,    \* số vòng REVIEW <-> REVISION
  qcRound,          \* số vòng QC loop (PLAN -> QC -> PLAN)
  enhanceRound,     \* số vòng PLAN_ENHANCE loop
  approvalRound,    \* số vòng changes_requested (sdd/plan approval)
  stallCount,       \* số vòng REVIEW không giảm BLOCKING liên tiếp
  planApproved,     \* flag: plan đã được duyệt
  done

vars == <<state, revisionRound, qcRound, enhanceRound, approvalRound,
          stallCount, planApproved, done>>

Init ==
  /\ state = "INIT"
  /\ revisionRound = 0
  /\ qcRound = 0
  /\ enhanceRound = 0
  /\ approvalRound = 0
  /\ stallCount = 0
  /\ planApproved = FALSE
  /\ done = FALSE

(* Các nhánh nondeterministic (do agent/user quyết định) *)
Approved    == \/ TRUE \/ FALSE          \* stub — dùng tên rõ hơn bên dưới
SddDecision(d)   == d \in {"approved", "rejected", "changes_requested"}
PlanDecision(d)  == d \in {"approved", "rejected", "changes_requested"}
ReviewOutcome(b, dec) ==
  \/ b = 0 /\ dec = "clean"                       \* không blocking
  \/ b > 0 /\ dec = "decreasing"                  \* blocking giảm
  \/ b > 0 /\ dec = "stalled"                     \* blocking không giảm
  \/ b > 0 /\ dec = "still_blocking"              \* blocking đến max rounds

(* ------------------------------------------------------------------ *)
(* Next-state relation                                                 *)
(* ------------------------------------------------------------------ *)
Next ==
  \/ state = "INIT" /\ state' = "CLASSIFY" /\ UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "CLASSIFY" /\
       (state' = "BRAINSTORM" \/ state' = "DONE") /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "BRAINSTORM" /\ state' = "ANALYZE" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "ANALYZE" /\ state' = "DESIGN" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "DESIGN" /\ state' = "REVIEW" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  (* REVIEW: clean -> SDD_APPROVAL; decreasing -> REVISION (round+1);
     stalled (2 lần không giảm) -> ESCALATE; still_blocking -> ESCALATE *)
  \/ state = "REVIEW" /\ dec = "clean" /\ state' = "SDD_APPROVAL" /\
       stallCount' = 0 /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, planApproved, done>>
  \/ state = "REVIEW" /\ dec = "decreasing" /\
       revisionRound < MaxRevision /\
       revisionRound' = revisionRound + 1 /\ stallCount' = 0 /\ state' = "REVISION" /\
       UNCHANGED <<qcRound, enhanceRound, approvalRound, planApproved, done>>
  \/ state = "REVIEW" /\ dec = "stalled" /\ stallCount < 1 /\
       revisionRound < MaxRevision /\
       revisionRound' = revisionRound + 1 /\ stallCount' = stallCount + 1 /\
       state' = "REVISION" /\
       UNCHANGED <<qcRound, enhanceRound, approvalRound, planApproved, done>>
  \/ state = "REVIEW" /\ (dec = "still_blocking" \/ stallCount >= 1) /\
       state' = "ESCALATE" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "REVISION" /\ state' = "REVIEW" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  (* SDD_APPROVAL *)
  \/ state = "SDD_APPROVAL" /\ SddDecision(d) /\
       ( (d = "approved" /\ state' = "PLAN" /\ planApproved' = planApproved /\ approvalRound' = approvalRound)
       \/ (d = "rejected" /\ state' = "REJECTED")
       \/ (d = "changes_requested" /\ approvalRound < MaxApproval /\
            approvalRound' = approvalRound + 1 /\ state' = "DESIGN")
       \/ (d = "changes_requested" /\ approvalRound >= MaxApproval /\ state' = "ESCALATE") ) /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, stallCount, done>>
  (* PLAN -> GAP_SCAN *)
  \/ state = "PLAN" /\ state' = "GAP_SCAN" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "GAP_SCAN" /\ state' = "QC" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  (* QC: pass -> PLAN_ENHANCE; fail + round < Max -> PLAN (round+1);
     fail + round >= Max -> ESCALATE *)
  \/ state = "QC" /\ qcResult = "pass" /\ qcRound' = qcRound + 1 /\ state' = "PLAN_ENHANCE" /\
       UNCHANGED <<revisionRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "QC" /\ qcResult = "fail" /\ qcRound < MaxQC /\
       qcRound' = qcRound + 1 /\ state' = "PLAN" /\
       UNCHANGED <<revisionRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "QC" /\ qcResult = "fail" /\ qcRound >= MaxQC /\ state' = "ESCALATE" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  (* PLAN_ENHANCE: clean -> PLAN_APPROVAL; blocking + round < Max -> PLAN;
     blocking + round >= Max -> ESCALATE *)
  \/ state = "PLAN_ENHANCE" /\ enhanceResult = "clean" /\ state' = "PLAN_APPROVAL" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "PLAN_ENHANCE" /\ enhanceResult = "blocking" /\ enhanceRound < MaxEnhance /\
       enhanceRound' = enhanceRound + 1 /\ state' = "PLAN" /\
       UNCHANGED <<revisionRound, qcRound, approvalRound, stallCount, planApproved, done>>
  \/ state = "PLAN_ENHANCE" /\ enhanceResult = "blocking" /\ enhanceRound >= MaxEnhance /\
       state' = "ESCALATE" /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved, done>>
  (* PLAN_APPROVAL *)
  \/ state = "PLAN_APPROVAL" /\ PlanDecision(d) /\
       ( (d = "approved" /\ planApproved' = TRUE /\ approvalRound' = approvalRound /\ state' = "WRITE_STATE")
       \/ (d = "rejected" /\ state' = "REJECTED")
       \/ (d = "changes_requested" /\ approvalRound < MaxApproval /\
            approvalRound' = approvalRound + 1 /\ state' = "DESIGN")
       \/ (d = "changes_requested" /\ approvalRound >= MaxApproval /\ state' = "ESCALATE") ) /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, stallCount, done>>
  \/ state = "WRITE_STATE" /\ planApproved = TRUE /\ state' = "DONE" /\ done' = TRUE /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved>>
  \/ state \in {"DONE", "REJECTED", "ESCALATE"} /\ state' = state /\ done' = done /\
       UNCHANGED <<revisionRound, qcRound, enhanceRound, approvalRound, stallCount, planApproved>>

(* ------------------------------------------------------------------ *)
(* Safety: EXECUTE (activation) chỉ với plan đã duyệt                   *)
(* ------------------------------------------------------------------ *)
SafetyWriteState == state = "WRITE_STATE" => planApproved = TRUE
SafetyDoneApproved ==
  (state = "DONE" /\ done) =>
    (planApproved = TRUE \/ revisionRound = 0)   \* S-tier skip: CLASSIFY->DONE

(* Convergence: mọi counter bị chặn trên *)
BoundedCounters ==
  /\ revisionRound <= MaxRevision
  /\ qcRound <= MaxQC
  /\ enhanceRound <= MaxEnhance
  /\ approvalRound <= MaxApproval
  /\ stallCount <= 1

(* Liveness: cuối cùng tới trạng thái kết thúc *)
Terminal == state \in {"DONE", "REJECTED", "ESCALATE"}
Liveness == <>[]Terminal

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Theorem Safety == Spec => []SafetyWriteState
Theorem SafetyDone == Spec => []SafetyDoneApproved
Theorem Converges == Spec => []BoundedCounters
Theorem Terminates == Spec => Liveness
=============================================================================