# Loop Protocol — Goal-Based Loop Detail

> Sub-protocol of `LOOP_PROTOCOL.md`. Load when task has a measurable endpoint.
> Goal-based = human sets success condition + budget, independent evaluator model decides done.
>
> **Required context**: This sub-protocol references `§State contract`, `§Mandatory stop conditions`,
> and `§Maker/checker` from `LOOP_PROTOCOL.md`. Load core first if not already loaded.

## Kickoff template (goal-based)

```
Start the "[LOOP NAME]" goal-loop.
Goal/Purpose: [verifiable end state]
Max iterations: [N]  Budget cap: [tokens]  Time limit: [wall-clock]
Between iterations run: [check command, e.g. ".venv/bin/python -m pytest tests/ --tb=short"]
Exit when: [exit condition, e.g. "check returns 0 AND no new failures for 2 consecutive runs"]

Step 1: [first action]  Step 2: [second action]  Step 3: [third action]
Convergence: if 3 consecutive iterations produce no new fix, STOP and report.
State: §State contract
Maker/checker: the agent that fixes does not judge exit condition. Re-run check command cold.
```

### Rules for all kickoffs

1. Every bracket must be filled. `[TBD]` = wish, not kickoff. 2. Check command must be deterministic. "Does it look good?" ≠ check command. 3. Exit condition must be testable by check command. 4. Max iterations mandatory even for `/goal`. 5. State write is non-negotiable.

## Concrete loop library (goal-based loops)

> Source: loops.elorm.xyz pre-built loop collection.

| # | Name | Mode | Goal/Purpose | Max iter | Check command | Convergence | Unique |
|---|------|------|--------------|----------|---------------|-------------|--------|
| 1 | Ship PR Until Green | `/goal` | PR open with all CI passing | 10 | `gh pr checks --watch` | 3 no new fix → STOP | Budget: 100K, 60 min |
| 4 | Independent Verifier Pass | `/goal` | Build, lint, tests pass independently | 8 | `npm run build && npm run lint && npm test` | 3 no new fix → STOP + escalate | Verifier never fixes — dispatches to Builder |

### Standard loop body (applies to all)

Steps: (1) check status/read state/run check command. (2) If problem found → read logs, fix, verify. (3) Re-check, write state, call `.venv/bin/python .devin/scripts/loop_memory_sync.py`. State: §State contract. Maker/checker: CI/verifier checks; agent fixes. No self-approval.

### Loop-specific notes

| # | Unique steps | Variants |
|---|-------------|----------|
| 1 | Branch → push → PR → wait CI → fix → re-check | No CI → `npm test`/`pytest`. Multi-CI → `gh pr checks --watch` |
| 4 | Run build/lint/tests cold → if fail: dispatch to Builder → re-run | Python → `pytest && ruff . && mypy .`. Go → `go test && go vet`. Multi-agent → 2 agents |

### Adding new loops

1. Identify repeated scenario (same structure 3+ times → belongs in library). 2. Pick mode (endpoint → `/goal`). 3. Write concrete kickoff (fill all brackets, no `[TBD]`). 4. Add variants. 5. Test it.

## Karpathy Loop (named pattern)

> Source: Karpathy's experiment design, via Wisely Chen's guide. Named pattern for autonomous research/optimization loops.

### The 3 elements

| # | Element | What it means |
|---|---------|---------------|
| 1 | **Agent with file modification access** | Read + write code/files, not just observe |
| 2 | **Auto-measurable metric** | Script/command objectively scores each iteration |
| 3 | **Fixed time limit per iteration** | Wall-clock cap. No open-ended runs. |

### The pattern

```
Start the "[NAME]" Karpathy-loop.
Agent: has read+write access to [files/dirs]
Metric: [command that outputs a number]  Time limit per iteration: [N min]
Max iterations: [N]  Budget cap: [N tokens]
Steps: (1) Read prior experiment log. (2) Generate hypothesis + code modification.
(3) Run experiment, capture metric score. (4) Write result to log.
(5) Metric improved → keep change; not → revert. (6) Check stop condition.
Convergence: 5 consecutive iterations, no metric improvement → STOP.
State: §State contract (with hypothesis + score + outcome)
Maker/checker: the metric script is the checker. Agent does not self-judge.
```

### When to use / NOT to use

- **Use:** Optimization with clear metric. Research with hypothesis generation. Parameter tuning.
- **NOT:** No auto-metric → Edge loop. Subjective output → human steers. Catastrophic failure → human in loop.
- **Agent swarm variant:** Karpathy's full vision = many loops in parallel. **Start with one loop.** Scale to swarm only after single loop reliably converges.

## Harness Gap Loop (regression → test case → SLA)

> Source: Ryan Carson's Control-Plane Pattern, via Wisely Chen's guide. Every production regression is a harness gap to close.

### The principle

`production regression → harness gap issue → test case added → SLA tracked`. 1. Regression occurs. 2. Open harness gap issue. 3. Add test case from reproduction conditions. 4. Add to harness (CI/benchmark). 5. Track SLA.

### The loop

```
Start the "Harness Gap Closure" goal-loop (triggered by production regression).
Goal: regression fixed AND test case exists that would have caught it
Max iterations: [5]  Budget cap: [30K tokens]  Time limit: [2 hours]
Steps: (1) Reproduce regression, confirm. (2) Fix regression. (3) Write test case
that fails on pre-fix, passes on post-fix. (4) Add to security benchmark.
(5) Open harness gap issue: what happened, why harness missed it, test added.
(6) Track SLA: time from regression → test added.
Exit when: fix merged AND test case in CI AND harness gap issue closed.
State: §State contract
```

### SLA tracking

| Metric | Target |
|--------|--------|
| Regression → issue opened | < 1 hour |
| Issue → test case added | < 24 hours |
| Test added → running in CI | < 1 hour |
| Recurring regressions (same root cause) | 0 |

### Rules

- **Every regression opens a harness gap issue.** No exceptions.
- **Fix not complete until test case in CI.** Fix without test = patch, not fix.
- **Track SLA over time.** Growing SLA = gap loop degrading.
- **Recurring regressions = red line.** Same root cause recurs → gap loop failed. Escalate.

## PRD iteration principle (spec is never done on first pass)

> Source: Wisely Chen's ATPM QA articles. First-pass requirement accuracy is 60-80%.

Traditional: PRD (fixed) → Code (expensive) → QA (expensive). AI-era: PRD (iterable) → Code (regenerated) → QA (regenerated from PRD).

### The iteration loop

```
Start the "PRD Iteration" goal-loop.
Goal: PRD accurately reflects what user actually wants (verified by working code)
Max iterations: [5]  Budget cap: [40K tokens]  Time limit: [4 hours]
Steps: (1) Write initial PRD from user request (accept 60-80% accuracy).
(2) Generate code from PRD, run it. (3) Compare output vs user intent — diverge?
(4) Divergence = PRD gap, not code bug. Update PRD. (5) Regenerate code + QA.
(6) Repeat until user confirms "yes, this is what I want."
Exit when: user confirms PRD matches intent AND code passes QA derived from PRD.
State: §State contract
```

### Rules

- **GoalSpec is a draft, not a contract.** Expect change.
- **Code generation is spec validation.** Generate early, run early, find PRD gaps early.
- **When code is wrong, check PRD first.** If PRD wrong, "correct" code is still wrong.
- **QA regenerated from PRD, not manually maintained.**
- **User confirmation is exit condition, not "all tests pass."**
