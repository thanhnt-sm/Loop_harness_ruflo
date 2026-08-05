# Loop Protocol — Proactive Loop Detail

> Sub-protocol of `LOOP_PROTOCOL.md`. Load when task is standing duty with unpredictable input.
> Proactive = event/schedule triggers, **no human present**, adversarial review agent decides done.
> **L3 (unattended) by definition** — requires Readiness Score ≥90 and prior L1→L2→L3 progression.
>
> **Required context**: This sub-protocol references `§State contract`, `§Mandatory stop conditions`,
> and `§Maker/checker` from `LOOP_PROTOCOL.md`. Load core first if not already loaded.

## Proactive loop pattern (no human present, workflow generated on the spot)

> Source: Inside article (2026-07-14) on Loop Engineering, fourth type. The most automated: trigger and done-decision both handed to the system, **and** the workflow itself is generated at trigger time.

### The pattern

A **routine** (long-running watcher) monitors a channel (GitHub issues, Slack, alert stream, PR queue). When something needs handling, the routine generates a fresh workflow on the spot:

```
[routine: watch channel]
   └─ event arrives (unpredictable content)
      └─ triage agent: classify + decide if action needed
         └─ fix agent: produce the change
            └─ adversarial review agent: attack the fix
               └─ passes → close task. Fails → back to fix (cap 2 rounds → escalate to human).
```

Three agents, three roles, **never the same agent across roles** (maker≠checker extended to triage≠fix≠review).

### Kickoff template

```
Start the "[NAME]" proactive-loop.
Routine: watch [channel: GitHub issues / Slack #channel / alert stream / PR queue]
Trigger: [observable condition that means "needs handling"]
Max concurrent tasks: [N]  Budget cap per task: [tokens]  Time limit per task: [wall-clock]
Max retries per task: 2  (3rd → escalate to human, do NOT keep retrying)

Per triggered task:
  Step 1 — Triage agent (fresh context): classify incoming event.
    Is action needed? What kind? What's the scope? Write triage result to state.
  Step 2 — Fix agent (fresh context, ≠ triage): produce change from triage result.
  Step 3 — Adversarial review agent (fresh context, ≠ fix): attack the fix.
    Try to break it. Find edge cases. Check it doesn't solve X by breaking Y.
    Pass → close task. Fail → back to Step 2 (count toward retry cap).
  Step 4 — Write outcome to state, call python .devin/scripts/loop_memory_sync.py.

Exit per task: adversarial review passes OR retry cap hit (escalate).
Exit routine: user stops OR channel decommissioned.
State: §State contract (per task: triage result, fix diff, review verdict, retries)
Maker/checker: triage ≠ fix ≠ review. Three separate agents. No agent plays two roles.
```

### When to use / NOT to use

- **Use:** You can't predict what comes in, only that something will. Standing duty: PR queue, alert stream, issue triage, on-call bot.
- **NOT:** Predictable content → use `/loop` or `/schedule` with a fixed prompt. Measurable endpoint → use `/goal`. Needs human judgment on each item → stay turn-based or L1.

### Why adversarial review is the gate (not optional)

Proactive runs **while no human is watching**. Without an adversarial reviewer, errors compound silently. The adversarial reviewer is the substitute for the human who would otherwise catch the mistake.

Adversarial ≠ lenient review. The reviewer's job is to **try to break the fix**, not to confirm it's fine. Concrete attacks:
- Does the fix solve the symptom by breaking something else? (grep for collateral damage)
- Does it pass the stated test but fail an adjacent one? (run the broader test suite)
- Does it hardcode what should be parameterized? (check for magic values)
- Does it match `knowledge_distill.md` anti-patterns? (grep state+knowledge)
- Does it touch files outside the triage scope? (diff vs triage result)

### Guardrails (mandatory — proactive without these is a red line)

1. **Retry cap = 2 per task.** 3rd failure → escalate. Never retry indefinitely.
2. **Budget cap per task.** Hit → escalate, don't silently continue.
3. **Time limit per task.** Wall-clock cap. Hit → escalate.
4. **Adversarial review is non-skippable.** No review = no close.
5. **Three distinct agents.** Triage = fix = review (same agent) = self-approval = red line.
6. **Max concurrent tasks.** Unbounded concurrency = resource contention + comprehension debt. Default 3.
7. **Escalation queue.** Failed/capped tasks land in a human-readable queue, not silently dropped.
8. **State write per task.** Every triggered task writes state.

### Cognitive surrender check (extra, proactive-specific)

Before deploying a proactive loop, the builder must answer:
1. For each plausible incoming event type, what does correct handling look like?
2. What's a failure mode the adversarial reviewer would miss?
3. What's the escalation criteria — when does the routine give up on a task?

Can't answer → cognitive surrender. You're building the loop to avoid understanding the work. Stop. Do the understanding first.

---

## Phased rollout (L1 → L2 → L3)

> Source: cobusgreyling/loop-engineering. Loops amplify judgment — good and bad. Unattended loops make unattended mistakes.

### The three levels

| Level | What the loop does | Human involvement | Readiness |
|-------|-------------------|-------------------|-----------|
| **L1 — Report-only** | Observe, analyze, report. No changes. | Human reads report, decides action. | ≥50 |
| **L2 — Assisted fixes** | Apply fixes, human approves before commit/push. | Human reviews each fix. | ≥70 |
| **L3 — Unattended** | Full autonomy: fix, commit, push, PR. | Human reviews after the fact. | ≥90 |

### Rollout rules

1. Start at L1. Always. No exceptions. Never ran L1 → cannot skip to L3. 2. L1→L2: ≥5 iterations, 0 harmful actions. 3. L2→L3: ≥10 iterations, 0 harmful actions reaching production. 4. Demotion: L3 harm → L2. L2 harm → L1. 5. Never skip levels. L1→L3 skip is a red line.

### What counts as "harmful"

Auto-fixing something not broken (false positive). Pushing code that fails CI. Deleting needed branch/file. Modifying protected file without approval. Spending >2x estimated token budget.

### Logging the level

Every kickoff must state: `Level: L1 (report-only) | L2 (assisted) | L3 (unattended)`. Log to state. Track promotion/demotion history.

---

## Warning signals (observable → meaning → action)

> Source: personal governance framework "預警表" concept. Signals must be observable (file state, command output, timestamps) — not feelings.
> U26: Reduced from 15 to 5 core signals (via negativa — keep only highest-impact).

### The signal table

| # | Observable signal | Meaning | Action |
|---|-------------------|---------|--------|
| 1 | State not updated 2+ iterations | Skipping state writes — loop blind | Force state write. 2nd round → red line, escalate. |
| 2 | GoalSpec empty | BOOT incomplete | Stop. Re-run BOOT. No work without GoalSpec for L/XL. |
| 3 | 3+ fixes, each reveals new problem elsewhere | Architectural problem | Stop fixing. Question architecture. Discuss with human. |
| 4 | Model claims "file written" but read-back shows missing/unchanged | False completion | Re-execute write. Verify read-back. 2nd fail → escalate. |
| 5 | Loop actions don't map to GoalSpec | Intent drift | STOP. Re-confirm intent with human. |

### How to use the table

1. **At BOOT:** Check 2. 2. **Between iterations:** Check 1, 5. 3. **Anytime:** 3, 4 are circuit breakers — STOP immediately.

### Rules

- **Observable, not interpretive.** "Agent seems confused" ≠ signal. "Agent's output contradicts GoalSpec §2" = signal.
- **One signal → one action.** Don't bundle. Circuit breakers first, then state, then knowledge, then memory.
- **Log signal fires to state.** Record: which signal, when, action taken.

## Failure reverse-engineering (proactive weak-model defense)

> Source: community Fable 5 harness-building prompt. Warning signals are reactive. F.R.E. is proactive (predict failure → pre-build defense).

### The method

1. Identify failure mode (exact cognitive/mechanical failure). 2. Find root cause (trigger). 3. Design defense (observable precursor + preventive action). 4. Add to signal table.

### Three weak-model failure scenarios

> U26: Reduced to 2 core scenarios (via negativa). Signal refs updated to new 5-signal table.

| # | Failure mode | Root cause | Observable precursor | Defense | Signal |
|---|-------------|------------|---------------------|---------|--------|
| 1 | Semantic drift | GoalSpec + completed-work scroll out of context | Edits file marked "done" | Read state every iteration. Before editing: grep state+knowledge. | 5 |
| 2 | False completion | Completion narrative before tool call | Claims "written" but read-back shows missing | Every write → read-back. `verify.py` at session end. | 4 |

### When to run

At harness setup (predict top 2 failure modes). After a failure (reverse-engineer → add new signal). On model change. Every 50 iterations.

## Loop Readiness Check (U26: binary, replaces 0-100 rubric)

> U26: Replaced complex 0-100 rubric with simple binary check (via negativa).

### Binary check

A workspace is **loop-ready** if ALL of these pass:
1. State persistence: registry exists, state written every iteration
2. Knowledge layer: `knowledge_distill.md` exists (if applicable)
3. Stop conditions: every loop has budget + convergence + time limit
4. Maker ≠ checker: fresh-context or CLI verification, not self-approval
5. Memory safety: no secrets in any layer
6. Red lines: REDLINES.md exists, referenced in entry file
7. Skills loaded: ≥1 skill deployed

If ALL pass → **loop-ready** (can run L3 unattended).
If ANY fail → **not loop-ready** (fix before running loops).

## Comprehension debt + Intent debt

> Source: cobusgreyling/loop-engineering. Two silent failure modes in long-running loops.

### Comprehension debt

After a loop runs N iterations unattended, the human loses track of what the loop is actually doing. The loop runs, but understanding decays. **Defense:** periodic re-read of state + summary. L3 loops must include a "comprehension checkpoint" every N iterations: human reads summary, confirms understanding.

### Intent debt

The loop's goal drifts from the human's actual intent as context changes. The loop keeps running on the original goal, but the human's intent has shifted. **Defense:** intent confirmation checkpoint. Every N iterations, human confirms "yes, this is still what I want."

## Multi-session coordination

### Conflict types

| Type | Example | Resolution |
|------|---------|------------|
| **File conflict** | Two sessions edit same file | Worktree isolation. Merge before close. |
| **Intent conflict** | Two sessions with contradictory goals | Human arbitrates. One session defers. |
| **Resource conflict** | Two sessions compete for API quota | Queue. One at a time per resource. |

### Coordination protocol

1. Before starting: check `.devin/loop_state.md` for active sessions with overlapping `owned_files` or `tags`.
2. If overlap: ask human whether to continue or start fresh.
3. During: write `owned_files` to state. Other sessions check before editing.
4. On close: release `owned_files`. Call `loop_memory_sync.py`.

### When sessions collide

If two sessions edited the same file: diff both, merge manually, or ask human which to keep. **Never auto-merge across sessions.**

## Loop-ifiability gate (3 conditions)

### The 3 conditions (all must pass)

1. **Measurable metric** — can you define a number/command that tells you "this iteration improved"?
2. **Failure cost is controlled** — if this loop makes a mistake, is the damage bounded?
3. **Harness is hard enough** — does the verification infrastructure catch mistakes?

### Decision tree

All 3 pass → loop-ify. Any fail → don't loop. Fix the failing condition first.

### Examples

| Task | Metric? | Failure controlled? | Harness hard? | Verdict |
|------|---------|---------------------|---------------|---------|
| Fix failing tests | tests pass | yes (tests catch) | yes | Loop |
| Refactor for performance | benchmark score | yes (revert if slower) | yes | Loop |
| Write marketing copy | no auto-metric | no (bad copy ships) | no | Don't loop |
| Monitor CI | CI status | yes (report only) | yes | Loop (L1) |

### The gate is mandatory

Running a loop without passing the gate = loop for the sake of looping = burns money, produces noise.

## Cognitive surrender (human-side failure mode)

> "Two people can build the exact same loop and get opposite results. One uses it to run faster on work they deeply understand. The other uses it to avoid understanding the work."

When you design a loop with judgment, it's medicine. When you design it to save thinking, it's an accelerator — for the problem, not the solution. The loop can't tell the difference. You can.

Signs of cognitive surrender:
- Can't state what "done" looks like in concrete terms
- Can't list 3 ways the loop could go wrong
- Can't explain why each step in the loop body exists
- "Let the agent figure it out" as a design principle

## Throughput changes merge philosophy

> Source: deusyu/harness-engineering. When agent throughput far exceeds human attention, norms invert: **error correction becomes cheap; waiting becomes expensive.**

Traditional: human time expensive + low throughput → careful review → many gates. Harness: agent time cheap + high throughput → fast iteration fixes errors → few gates.

Prerequisite: **sufficient back-pressure** (tests, lint, structural checks) must exist. Without them, "fast iteration" = "fast rot."

### Rules

- **Don't apply low-throughput norms to high-throughput.** Gates at 5 PRs/week wrong at 50.
- **Back-pressure is prerequisite.** Fast merge without tests/lint = fast rot.
- **Flaky tests → retry, not block.** Track flakiness — rising rate = regression.
- **Agent-to-agent review valid.** Human reviews summary + escalated disagreements.
- **Optimize for iteration speed, not first-time success.**
- **Cheap models for subtasks, expensive for orchestration.**

## Cross-cutting relationships

| Principle | Relationship |
|-----------|-------------|
| Comprehension debt vs Cognitive surrender | Both silent, degrade quality. Debt = stop reading; Surrender = build loop to avoid understanding. |
| Entropy sweep vs Harness gap loop | Both needed. Sweep = proactive (find drift). Gap loop = reactive (close gap). |
| Warning signals vs F.R.E. | Reactive vs proactive. Same signal table. |
| Maker≠checker (VERIFICATION_PROTOCOL) | Agent-to-agent review valid if maker ≠ checker. |
| Entropy + Throughput | High throughput = more entropy. Sweep cadence must match throughput. |
| PRD iteration + Cognitive surrender | Not iterating PRD = accepting first guess = surrender. |
| Proactive loop + Cognitive surrender | Proactive runs unattended — cognitive surrender risk is highest. Extra pre-deploy check mandatory. |
| Proactive loop + Comprehension debt | No human per task → escalation queue is where comprehension debt hides. |
| Proactive loop + Maker≠checker | Extended to triage ≠ fix ≠ review. Three roles, three agents. |
| Four types + Loop-ifiability gate | The gate runs before any of the four types. Type choice is downstream of "should this loop at all?" |

## The deepest trap

> "Two people can build the exact same loop and get opposite results. One uses it to run
> faster on work they deeply understand. The other uses it to avoid understanding the work."

When you design a loop with judgment, it's medicine. When you design it to save thinking,
it's an accelerator — for the problem, not the solution. The loop can't tell the difference.
You can.

## Source references

- Addy Osmani / Boris Cherny / Karpathy autoresearch — Loop Engineering concept.
- Anthropic, "Getting started with loops" (2026-07-07) — official 4-type framework, evaluator-as-smaller-model, cadence-matches-change-rate, deterministic-work-to-script, turn-based+Skills.
- Inside article (2026-07-14), "Loop engineering 是什麼？四種迴圈決定你要盯 AI 代理多緊" — four-type handoff 2×2 framework, `/schedule` cloud vs `/loop` local, adversarial review as proactive gate.
- aiposthub.com (2026-07-13), "Claude Code 官方把 AI Agent 拆成 4 種循環" — operator-level details.
- loops.elorm.xyz — loop primitives + pre-built loop collection.
- cobusgreyling/loop-engineering — loop-audit, phased rollout (L1→L2→L3), comprehension/intent debt.
- govin999999 Threads (Loopkit Vault) — vault pattern.
- oh-my-openagent's Todo Enforcer (Sisyphus Labs) — idle-yank protocol.
- community Fable 5 harness-building prompt — failure reverse-engineering concept.
