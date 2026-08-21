# Loop Protocol — Convergent Iteration (Caveman Compressed)

> Loops = autonomous agent work. Bad loops = burn money, produce noise. Every loop: goal + stop condition + budget.
> **U12**: This is CORE (<150 lines). Sub-protocols on-demand:
> - `LOOP_TURN_BASED.md` — turn-based detail (edge loop, Skills, idle-yank)
> - `LOOP_GOAL_BASED.md` — goal-based detail (Karpathy, harness gap, PRD iteration)
> - `LOOP_TIME_BASED.md` — time-based detail (entropy sweep, cadence loops)
> - `LOOP_PROACTIVE.md` — proactive detail (adversarial review, cognitive surrender)

---

## The Shift
Prompt Engineering = you talk to AI every turn.
Loop Engineering = design system where AI talks to itself, verifies, records state, runs next turn — until stop condition met.
Human moves from "driving every turn" to "designing loop, setting rules, handling exceptions."

---

## Two Loop Types (U46: 4→2)
> Time-based + proactive = special cases of goal-based + turn-based.

| Type | Trigger | Done-Decision | When |
|------|---------|---------------|------|
| **Turn-based** | Human prompt | Human reviews output | Exploratory; each output reshapes next Q. Includes periodic/cadence. |
| **Goal-based** | Human `/goal` w/ success condition + budget | Independent evaluator model | Result measurable; process not worth watching. Includes unattended/proactive. |

**Pick**: Exploratory → turn-based. Measurable → goal-based.
**Deeper handoff → higher bar for stop conditions + guardrails.**

---

## Three Loop Modes
| Mode | Semantics | When |
|------|-----------|------|
| `/loop` | Cadence, **local**: re-run N min/hr. Never self-stops. | Inspection, monitoring, periodic checks |
| `/schedule` | Cadence, **cloud**: server-side. Runs when laptop closed. | Periodic unattended across sleep |
| `/goal` | Condition-based: run until verifiable condition met. | Bug-fix-until-tests-pass, refactor-until-clean |

- Endpoint → `/goal`; no endpoint → `/loop` or `/schedule`.
- `/schedule` raises stakes: stop conditions + budget cap + adversarial review **mandatory**.

---

## 5+1 Components
| # | Component | Purpose |
|---|-----------|---------|
| 1 | Loop / Goal | How loop runs, when stops |
| 2 | Worktrees | Parallel agents don't clobber |
| 3 | Skills | Project knowledge written down |
| 4 | Connectors | Agents reach beyond fs (GitHub, Linear, Slack, DB) |
| 5 | Sub-agents | Maker ≠ checker |
| +1 | Memory | Cross-run persistent state |

---

## When NOT to Loop
3 conditions must hold:
1. **Measurable metric** — no metric → loop degrades to "runs but doesn't know if good."
2. **Failure cost controlled** — uncontrolled → human stays in loop.
3. **Harness hard enough** — weak harness → fix harness first, don't loop.

**Don't loop what script can do deterministically.** Fixed-format conversion, form filling, data cleaning → write script, don't burn tokens.

---

## Mandatory Stop Conditions (All 3 Required)
1. **Budget cap** — token/iter/cost limit. Hit → stop.
2. **Convergence** — N consecutive iters no new finding/improvement → stop.
3. **Time limit** — hard wall-clock cap. Hit → stop.

Missing any = broken loop. Don't run unattended.

---

## State Contract (Every Iter)
1. Read `.devin/loop_state.md` registry (active/completed sessions)
2. Read `.devin/loop_state/<sid>.md` for active session (where did I get to?)
3. Do one unit of work
4. Write `.devin/loop_state/<sid>.md` + `.devin/session_state/<sid>.json`
5. Call `loop_memory_sync.py` → regenerate registry
6. Check stop condition
7. Not met → next iter. Met → stop, archive result.

**Without step 4, next iter repeats work or skips ahead. State = spine.**

---

## Maker/Checker in Loops
Agent running loop body **must not** judge stop condition. Separate checker (fresh context or deterministic script) evaluates.
**Evaluator = smaller/faster/cheaper model than worker.** Worker = hard generative; evaluator = condition check (cheap — don't spend worker-tier tokens).

---

## Remediation Sub-Loop
Checker finds problem → fix = sub-task to worker (not checker fixing). Checker checks; worker fixes; checker re-checks. Cap retries: same problem 2 rounds → escalate human.

---

## Anti-Patterns
- No stop condition → don't run unattended. Ever.
- Same agent writes + checks → split them.
- Loop to avoid thinking → if can't define metric, can't loop. Hand to human.
- Ignoring state → next iter blind. Always read state first.

---

## Sub-Protocols (Load On-Demand)
| Sub-protocol | When | Key Content |
|--------------|------|-------------|
| `LOOP_TURN_BASED.md` | Exploratory, edge loop | Edge loop, Skills upgrade, idle-yank, kickoff template |
| `LOOP_GOAL_BASED.md` | Measurable endpoint | Karpathy loop, harness gap, PRD iteration, concrete library |
| `LOOP_TIME_BASED.md` | Periodic/cadence | Entropy management, cadence loops, `/loop` `/schedule` detail |
| `LOOP_PROACTIVE.md` | Unattended standing duty | Proactive pattern, adversarial review, cognitive surrender, phased rollout, warning signals, readiness score, comprehension debt, multi-session, loop-ifiability gate, throughput, cross-cutting relationships |