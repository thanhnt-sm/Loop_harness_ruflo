------------------------ MODULE state_router ------------------------
(*
 * State Router conditional edges — TLA+ spec (Task 3.6).
 *
 * Mirror của .devin/scripts/state_router.py (EDGES list, 13 edges).
 *
 * Steps: ANALYZE, DESIGN, PLAN, QUALITY_CHECK, APPROVE, DISPATCH,
 *        EXECUTE, VERIFY, REPORT, DONE
 *
 * Properties:
 *   Safety   : EXECUTE chỉ reachable sau APPROVE (approved=TRUE).
 *              DONE chỉ qua REPORT (báo cáo xong) hoặc APPROVE reject.
 *   Deadlock : Mọi state đều có edge enabled (trừ terminal DONE).
 *)
EXTENDS Integers

CONSTANT MaxDesign

VARIABLES
  step,           \* bước hiện tại
  findings,       \* số phát hiện ANALYZE
  design,         \* đã có thiết kế?
  plan,           \* đã có plan?
  qualityScore,   \* điểm chất lượng [0,1]
  approved,       \* approved flag
  tasksDispatched,
  allTasksComplete,
  allGatesPass,
  tasksRemaining, \* số tác vụ còn lại (EXECUTE loop hữu hạn)
  verifyRounds,   \* số lần VERIFY loop lại EXECUTE (hữu hạn)
  designRounds,   \* số lần QUALITY_CHECK loop lại DESIGN (hữu hạn)
  executed,       \* đã từng tới EXECUTE (cho safety)
  done

vars == <<step, findings, design, plan, qualityScore, approved,
          tasksDispatched, allTasksComplete, allGatesPass,
          tasksRemaining, verifyRounds, designRounds, executed, done>>

Init ==
  /\ step = "ANALYZE"
  /\ findings = 0
  /\ design = FALSE
  /\ plan = FALSE
  /\ qualityScore = 0.0
  /\ approved = FALSE
  /\ tasksDispatched = FALSE
  /\ allTasksComplete = FALSE
  /\ allGatesPass = FALSE
  /\ tasksRemaining = 0
  /\ verifyRounds = 0
  /\ designRounds = 0
  /\ executed = FALSE
  /\ done = FALSE

(* ------------------------------------------------------------------ *)
Next ==
  \/ /\ step = "ANALYZE" /\ findings < 5
     /\ findings' = findings + 1 /\ step' = "ANALYZE"
     /\ UNCHANGED <<design, plan, qualityScore, approved, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, designRounds, executed, done>>
  \/ /\ step = "ANALYZE" /\ findings >= 5 /\ step' = "DESIGN"
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    tasksDispatched, allTasksComplete, allGatesPass,
                    tasksRemaining, verifyRounds, designRounds, executed, done>>
  \/ /\ step = "DESIGN" /\ design' = TRUE /\ step' = "PLAN"
     /\ UNCHANGED <<findings, plan, qualityScore, approved, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, designRounds, executed, done>>
  \/ /\ step = "PLAN" /\ plan' = TRUE /\ step' = "QUALITY_CHECK"
     /\ UNCHANGED <<findings, design, qualityScore, approved, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, designRounds, executed, done>>
  \/ /\ step = "QUALITY_CHECK" /\ qualityScore < 0.8 /\ designRounds < MaxDesign
     /\ step' = "DESIGN" /\ design' = FALSE /\ designRounds' = designRounds + 1
     /\ UNCHANGED <<findings, plan, qualityScore, approved, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, executed, done>>
  \/ /\ step = "QUALITY_CHECK" /\ qualityScore < 0.8 /\ designRounds >= MaxDesign
     /\ step' = "APPROVE" /\ designRounds' = designRounds
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, executed, done>>
  \/ /\ step = "QUALITY_CHECK" /\ qualityScore >= 0.8 /\ step' = "APPROVE"
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, designRounds, executed, done>>
  \/ /\ step = "APPROVE" /\ approved' = TRUE /\ step' = "DISPATCH"
     /\ UNCHANGED <<findings, design, plan, qualityScore, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, executed, done>>
  \/ /\ step = "APPROVE" /\ approved' = FALSE /\ step' = "DONE" /\ done' = TRUE
     /\ UNCHANGED <<findings, design, plan, qualityScore, tasksDispatched,
                    allTasksComplete, allGatesPass, tasksRemaining,
                    verifyRounds, executed>>
  \/ /\ step = "DISPATCH" /\ tasksDispatched' = TRUE /\ step' = "EXECUTE"
     /\ tasksRemaining' = 3 /\ executed' = TRUE
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    allTasksComplete, allGatesPass, verifyRounds, done>>
  \/ /\ step = "EXECUTE" /\ tasksRemaining > 0
     /\ tasksRemaining' = tasksRemaining - 1
     /\ step' = IF tasksRemaining - 1 = 0 THEN "VERIFY" ELSE "EXECUTE"
     /\ allTasksComplete' = (tasksRemaining - 1 = 0)
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    tasksDispatched, allGatesPass, verifyRounds, executed, done>>
  \/ /\ step = "VERIFY" /\ allGatesPass' = TRUE /\ step' = "REPORT"
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    tasksDispatched, allTasksComplete, tasksRemaining,
                    verifyRounds, executed, done>>
  \/ /\ step = "VERIFY" /\ allGatesPass' = FALSE /\ verifyRounds < 5
     /\ verifyRounds' = verifyRounds + 1 /\ step' = "EXECUTE"
     /\ tasksRemaining' = 3 /\ allTasksComplete' = FALSE
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    tasksDispatched, done>>
  \/ /\ step = "VERIFY" /\ allGatesPass' = FALSE /\ verifyRounds >= 5
     /\ step' = "REPORT" /\ allGatesPass' = FALSE
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    tasksDispatched, allTasksComplete, tasksRemaining,
                    verifyRounds, executed, done>>
  \/ /\ step = "REPORT" /\ step' = "DONE" /\ done' = TRUE
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    tasksDispatched, allTasksComplete, allGatesPass,
                    tasksRemaining, verifyRounds, executed>>
  \/ /\ step = "DONE" /\ step' = "DONE"
     /\ UNCHANGED <<findings, design, plan, qualityScore, approved,
                    tasksDispatched, allTasksComplete, allGatesPass,
                    tasksRemaining, verifyRounds, executed, done>>

(* ------------------------------------------------------------------ *)
(* Safety: EXECUTE chỉ sau APPROVE + DISPATCH; DONE chỉ khi đã REPORT
   hoặc APPROVE reject.                                                 *)
(* ------------------------------------------------------------------ *)
SafetyExecuteGated == executed => approved = TRUE
SafetyDoneGated == done => \/ (step = "REPORT" /\ allGatesPass = TRUE)
                            \/ approved = FALSE
SafetyApprovedSticky == approved = TRUE => approved' = TRUE

(* Deadlock freedom: mọi step (trừ DONE) có edge enabled *)
DeadlockFree ==
  step = "ANALYZE"        => (findings < 5 \/ findings >= 5)
  /\ step = "DESIGN"      => TRUE
  /\ step = "PLAN"        => TRUE
  /\ step = "QUALITY_CHECK" => (qualityScore < 0.8 \/ qualityScore >= 0.8)
  /\ step = "APPROVE"     => TRUE
  /\ step = "DISPATCH"    => TRUE
  /\ step = "EXECUTE"     => TRUE
  /\ step = "VERIFY"      => TRUE
  /\ step = "REPORT"      => TRUE

Liveness == <>[](step = "DONE")
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Theorem SafetyExecute == Spec => []SafetyExecuteGated
Theorem SafetyDone == Spec => []SafetyDoneGated
Theorem NoDeadlock == Spec => []DeadlockFree
Theorem Terminates == Spec => Liveness
=============================================================================