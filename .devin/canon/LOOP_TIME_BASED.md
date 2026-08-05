# Loop Protocol — Time-Based Loop Detail

> **U65: DEPRECATED** — Merged into LOOP_PROTOCOL.md (U46). This file retained for reference only.
> Do NOT load at BOOT. Load LOOP_PROTOCOL.md instead.
>
> Sub-protocol of `LOOP_PROTOCOL.md`. Load when task is periodic (content known, only timing repeats).
> Time-based = clock triggers, human/cap decides done. Modes: `/loop` (local) or `/schedule` (cloud).
>
> **Required context**: This sub-protocol references `§State contract`, `§Mandatory stop conditions`,
> and `§Maker/checker` from `LOOP_PROTOCOL.md`. Load core first if not already loaded.

## Cadence rules

- **Cadence matches data change rate, not your patience.** PR might change hourly → don't poll every minute. Over-polling burns tokens, API quota, and external-service budget for zero new information.
- `/loop` / `/schedule` for convergent tasks = infinite spend. Use `/goal` instead.
- `/schedule` raises the stakes: it runs while you're away, so stop conditions + budget cap + adversarial review are **mandatory**, not optional. A broken `/schedule` burns budget 24/7.

## Kickoff template (time-based)

```
Start the "[LOOP NAME]" cadence-loop.
Goal/Purpose: [what to monitor]
Max iterations: [N]  Budget cap: [tokens]  Time limit: [wall-clock]
Cadence: [interval, e.g. 5 min / 1 hour / 6 hours]
Between iterations run: [check command]
Exit when: max iterations OR time limit OR user stops

Step 1: [first action]  Step 2: [second action]  Step 3: [third action]
State: §State contract (with timestamp + result)
Maker/checker: the agent that fixes does not judge exit condition.
```

**Mode differences:** `/loop` has cadence interval, no convergence (monitors don't converge). `/loop` state includes timestamp + result.

### Hook-based variant (event-driven, no prompt needed)

For tools with hooks: configure `afterEdit` hook to run check command on `exit_code != 0` → `notify_agent_with_output`. Agent receives hook output, decides fix or escalate. `/goal` loop without explicit kickoff — edit event starts each iteration.

## Concrete loop library (time-based loops)

> Source: loops.elorm.xyz pre-built loop collection.

| # | Name | Mode | Goal/Purpose | Max iter | Check command | Convergence | Unique |
|---|------|------|--------------|----------|---------------|-------------|--------|
| 2 | CI Failure Watcher | `/loop` | Monitor CI, auto-fix failures | 12 (1hr) | `gh run list --branch $(git branch --show-current) --limit 1` | None (cadence) | Cadence: 5 min |
| 3 | Post-Edit Test Guard | hook | Regression protection during editing | — | `npm test -- --findRelatedTests $(git diff --name-only HEAD)` | — | Event-driven (afterEdit) |
| 5 | Daily Triage | `/loop` | Scan repo: issues, failing tests, stale branches | 7 (1wk) | `git fetch --all && gh issue list --state open && npm test -- --listTests` | None (cadence) | Report only, L1 |
| 6 | Dependency Sweeper | `/loop` | Check outdated + vulnerable deps; patch if safe | 4 (24hr) | `npm audit --json && npm outdated --json` | 2 same vuln → STOP | Cadence: 6h |
| 7 | Post-Merge Cleanup | `/loop` | Clean stale branches, rebuild indexes, archive | 4 (24hr) | `git branch --merged main \| grep -v main` | None (cadence) | Cadence: 6h |

### Loop-specific notes

| # | Unique steps | Variants |
|---|-------------|----------|
| 2 | Check CI → if failed: fix+push → if ok: wait | Multi-branch → `--branch`. Non-GitHub → `curl` API |
| 3 | Edit → hook runs tests → if fail: fix before more edits | Python → `pytest --testmon`. No testmon → `pytest -k "<file>"` |
| 5 | Fetch → list issues → list tests → stale branches >14d → report | No GitHub → tracker CLI. Python → `pytest --collect-only` |
| 6 | audit+outdated → if high/critical: `npm audit fix` + test → if breaking: report | Python → `pip-audit`. Go → `govulncheck`. L1 → report only |
| 7 | List merged → delete → archive >30d → rebuild deep-memory | Protected → `grep -v "main\|develop\|release"`. No deep-memory → skip |

## Entropy Management (background sweep)

> Source: OpenAI's Harness Engineering blog, via Wisely Chen's guide. Agents replicate existing patterns — including bad ones. Without a background sweep, entropy accumulates and hardens.

### The defense: background sweep loop

A dedicated `/loop` that periodically: (1) scans for pattern drift, (2) updates quality scores, (3) opens refactor PRs. Cadence: [e.g. every 24 hours]. Max iterations: [1 per run]. Time limit: [30 min per run]. Steps: scan repo for anti-patterns → score each module (clean/drift/degraded) → drift: open refactor PR (L2), degraded: flag in `knowledge_distill.md` + escalate → write sweep results to state, call `python .devin/scripts/loop_memory_sync.py`. Exit when: sweep complete. State: §State contract (with sweep results).

### Entropy accumulation chain

Without sweep: anti-pattern in A → replicated to B → C, D → becomes "the convention" → refactoring requires breaking 4+ modules. With sweep: anti-pattern in A → sweep detects within 24h → refactor PR for A only → fixed before it spreads.

### Rules

- **Every repo with daily agent output needs entropy sweep.** Weekly min, daily preferred.
- **Sweep is L2 (assisted).** Human reviews refactor PR before merge.
- **Degraded modules escalate to human.** Don't auto-fix deeply degraded — fix might add entropy.
- **Track quality scores.** Dropping score needs architectural attention, not just refactor.
