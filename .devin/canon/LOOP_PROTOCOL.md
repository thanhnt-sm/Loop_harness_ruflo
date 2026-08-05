# Loop Protocol — Convergent Iteration

> Loops let agents work autonomously. Bad loops burn money and produce noise.
> Every loop needs: a goal, a stop condition, and a budget.
>
> **U12: Split protocol** — this is the CORE file (<150 lines). Load sub-protocols on-demand:
> - `.devin/canon/LOOP_TURN_BASED.md` — turn-based loop detail (edge loop, Skills, idle-yank)
> - `.devin/canon/LOOP_GOAL_BASED.md` — goal-based loop detail (Karpathy, harness gap, PRD iteration)
> - `.devin/canon/LOOP_TIME_BASED.md` — time-based loop detail (entropy sweep, cadence loops)
> - `.devin/canon/LOOP_PROACTIVE.md` — proactive loop detail (adversarial review, cognitive surrender)

## The shift

Prompt Engineering: you talk to the AI every turn.
Loop Engineering: you design a system where the AI talks to itself, verifies, records state, and runs the next turn — until a stop condition is met.

The human moves from "driving every turn" to "designing the loop, setting rules, handling exceptions."

---

## Two loop types (U46: simplified from 4 to 2)

> U46: Via negativa — reduced 4 loop types to 2. Time-based and proactive
> were special cases of goal-based and turn-based respectively.

The two questions every loop answers: **what starts a run**, and **what decides it's finished**.

| Type | Trigger | Done-decision | When |
|------|---------|---------------|------|
| **Turn-based** | Human prompt | Human reviews output | Exploratory; each output reshapes next question. Includes periodic/cadence (time-based was a special case). |
| **Goal-based** | Human `/goal` w/ success condition + budget | Independent evaluator model | Result measurable; process not worth watching. Includes unattended/proactive (proactive was a special case with event trigger). |

**Pick by task nature:** Exploratory → turn-based. Measurable → goal-based.

**The deeper the handoff, the higher the bar for stop conditions + guardrails.**

→ Detail: `LOOP_TURN_BASED.md`, `LOOP_GOAL_BASED.md`
→ `LOOP_TIME_BASED.md` and `LOOP_PROACTIVE.md` retained for reference but
  their patterns are subsumed into the two primary types.

---

## Three loop modes

| Mode | Semantics | When to use |
|------|-----------|-------------|
| `/loop` | Cadence-based, **local**: re-run every N min/hours. Never self-stops. | Inspection, monitoring, periodic checks |
| `/schedule` | Cadence-based, **cloud**: runs server-side. Keeps running when laptop closed. | Periodic work unattended across sleep |
| `/goal` | Condition-based: run until a verifiable condition is met. | Bug-fix-until-tests-pass, refactor-until-clean |

- Has an endpoint → `/goal`; no endpoint → `/loop` or `/schedule`.
- `/schedule` raises the stakes: stop conditions + budget cap + adversarial review are **mandatory**.

## The 5+1 components

| # | Component | Purpose |
|---|-----------|---------|
| 1 | Loop / Goal | How the loop runs, when it stops |
| 2 | Worktrees | Parallel agents don't clobber each other's files |
| 3 | Skills | Project knowledge written down, so agents don't guess |
| 4 | Connectors | Agents reach beyond the filesystem (GitHub, Linear, Slack, DB) |
| 5 | Sub-agents | Maker and checker are different agents |
| +1 | Memory | Cross-run persistent state — agents forget, repos don't |

## When NOT to loop

Three conditions must hold to loop-ify a work segment:
1. **Measurable metric** — no metric → loop degrades to "runs but doesn't know if it's good."
2. **Failure cost is controlled** — uncontrolled → human stays in the loop.
3. **Harness is hard enough** — weak harness → fix the harness first, don't loop yet.

**Don't loop what a script can do deterministically.** Fixed-format conversion, form filling, data cleaning — write a script, don't burn model tokens.

→ Detail: `LOOP_PROACTIVE.md` §"Loop-ifiability gate"

---

## Mandatory stop conditions (all three required)

1. **Budget cap** — token/iteration/cost limit. Hit → stop.
2. **Convergence check** — N consecutive iterations with no new finding/improvement → stop.
3. **Time limit** — hard wall-clock cap. Hit → stop.

A loop missing any of the three is a broken loop. Do not run it unattended.

## State contract

Every iteration:
1. Read `.devin/loop_state.md` registry (which sessions are active/completed).
2. Read `.devin/loop_state/<session_id>.md` for the active session (where did I get to?).
3. Do one unit of work.
4. Write `.devin/loop_state/<session_id>.md` and `.devin/session_state/<session_id>.json`.
5. Call `python .devin/scripts/loop_memory_sync.py` to regenerate `.devin/loop_state.md` registry.
6. Check stop condition.
7. Not met → next iteration. Met → stop, archive result.

Without step 4, the next iteration repeats work or skips ahead. State is the spine.

## Maker/checker in loops

The agent that runs the loop body **must not** judge whether the stop condition is met. A separate checker (fresh context, or deterministic script) evaluates the condition.

**The evaluator should be a smaller / faster / cheaper model than the worker.** The worker does the hard generative work; the evaluator only checks a condition. That check is cheap — don't spend worker-tier tokens on it.

## Remediation sub-loop

When a checker finds a problem, the fix is a sub-task dispatched to a worker — not the checker fixing it. Checker checks; worker fixes; checker re-checks. Cap retries: same problem 2 rounds → escalate to human.

## Anti-patterns

- No stop condition → don't run unattended. Ever.
- Same agent writes + checks → split them.
- Loop to avoid thinking → if you can't define a metric, you can't loop. Hand to human.
- Ignoring state → next iteration is blind. Always read state first.

---

## Sub-protocols (load on-demand)

| Sub-protocol | When to load | Key content |
|--------------|-------------|-------------|
| `LOOP_TURN_BASED.md` | Exploratory tasks, edge loop pattern | Edge loop, Skills upgrade, idle-yank, kickoff template |
| `LOOP_GOAL_BASED.md` | Measurable endpoint tasks | Karpathy loop, harness gap loop, PRD iteration, concrete library |
| `LOOP_TIME_BASED.md` | Periodic/cadence tasks | Entropy management, cadence loops, `/loop` `/schedule` detail |
| `LOOP_PROACTIVE.md` | Unattended standing duty | Proactive pattern, adversarial review, cognitive surrender, phased rollout, warning signals, readiness score, comprehension debt, multi-session, loop-ifiability gate, throughput, cross-cutting relationships |
