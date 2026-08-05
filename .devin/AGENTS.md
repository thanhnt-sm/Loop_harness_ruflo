# Agent Harness Deploy — Entry File

> **Summary only.** Load canon on-demand per BOOT_PROTOCOL. Full canon body at `.devin/AGENTS_full.md` (186KB, reference only — do NOT auto-load).

## Identity

You are operating inside an **AHD-distilled harness**. Core principles:

- **Caveman comms**: strip filler, keep signal. ~65% token reduction.
- **Commander + workers**: main thread decides, dispatches, integrates. Workers scan/edit.
- **Maker ≠ checker**: producer never verifies. Fresh context or CLI verifies.
- **Memory persists**: state on disk, not context.
- **Loops converge**: every iteration writes state, checks stop, stops when met.
- **Evidence-graded**: tag claims [fact] / [inference] / [unverified-guess].

## Canon files (load on-demand per BOOT_PROTOCOL)

| File | When to load | Content |
|------|-------------|---------|
| `.devin/canon/CORE_CANON.md` | BOOT | Identity, operating principles, deploy contract |
| `.devin/canon/BOOT_PROTOCOL.md` | BOOT | 17-step startup sequence |
| `.devin/canon/REDLINES.md` | BOOT (top 5 below) | 18 hard stops — violating → stop, ask human |
| `.devin/canon/MEMORY_PROTOCOL.md` | When writing memory | 3-layer memory + deep-memory |
| `.devin/canon/LOOP_PROTOCOL.md` (+ sub-protocols) | When running loops | Core: primitives, stop conditions. Sub-protocols on-demand: TURN_BASED, GOAL_BASED, TIME_BASED, PROACTIVE |
| `.devin/canon/VERIFICATION_PROTOCOL.md` | When verifying | Maker/checker, read-back, CLI gates |
| `.devin/canon/CAVEMAN_PROTOCOL.md` | When compressing | Token compression style |
| `.devin/canon/HARNESS_ENGINEERING.md` | When designing harness | Design principles for agent-facing systems |
| `.devin/canon/JUDGMENT_RUBRICS.md` | When scoring | Externalized decision criteria |
| `.devin/canon/HANDOFF_LETTER.md` | Session end | Letter to future sessions |

## Top 5 red lines (full 18 in REDLINES.md)

1. **No overwrite without backup** — `.bak` before overwriting. No exceptions.
2. **No destructive ops without confirmation** — stop, describe, wait for approval.
3. **No secrets in tool log** — never write keys/tokens into session_state or journal.
4. **No auto-resume** — detect crashed sessions, ask human before continuing.
5. **No skipping verification** — every deploy ends with verify.py or fresh-context read-back.

## Skills (on-demand, triggered by task match)

| Skill | Trigger |
|-------|---------|
| `lightning`, `glm` | Code execution (Lightning=$, GLM=free) |
| `aide-memory` | Persistent memory recall/remember |
| `hlk-git-tools`, `hlk-integrity-check` | Safe git ops, HLK layer check |
| `auditor`, `fable-judge` | Verification, adversarial done-gate |
| `claim-grader` | Grade claims [fact]/[inference]/[unverified] |
| `comment_checker`, `slop-detector` | Detect code/prose slop |
| `context-compactor` | Context oversized |
| `gap-scan`, `graph-verify` | Scope scanning, graph verification |
| `harness-sensor`, `init_deep` | Sensor mode, large-repo init |
| `loop-memory`, `memory-audit` | Loop memory sync, memory audit |
| `systematic_debugging`, `tdd` | Debug, test-driven development |
| `user-preference`, `using-skills` | Preference learning, meta-skill |
| `nuwa-skill` | Cognitive verification (Munger/Feynman/Taleb) |

All skills in `.devin/skills/`. AHD skills (16) are `.md` files; named skills have `SKILL.md` in subdirs.

## Agents

| Role | Purpose |
|------|---------|
| Commander (`.devin/agents/COMMANDER.md`) | Orchestrator — dispatches, never works directly |
| Workers: SCOUT, BUILDER, AUDITOR, VERIFIER, MEMORY_KEEPER (`.devin/agents/workers/`) | Research, implement, audit, verify, memory write-back |
| Personas (6): architect, code_reviewer, database_optimizer, devops_automator, frontend_developer, git_workflow_master (`.devin/agents/personas/`) | Domain expertise for dispatch |

## Runtime

- **Hooks**: `.devin/hooks/` — pre_tool_use.py (guard), post_tool_use.py (state), stop.py (cleanup), ahd_session.py (shared)
- **Scripts**: `.devin/scripts/` — plan_dispatch, worktree, session_manager, loop_memory_sync, memory_audit, pre_task_audit, ahd_session
- **State**: `.devin/session_state/`, `.devin/loop_state/`, `.devin/context_flags/`, `.agents/` (shared)
- **MCP**: aide-memory (local), spark-memory, deepwiki, devin (remote)

## Red Team + Upgrade

| Document | Path |
|----------|------|
| Red Team Report | `HLK/docs/REDTEAM_REPORT.md` |
| Upgrade Plan (40 upgrades) | `HLK/docs/UPGRADE_PLAN.md` |
| Upgrade Tracker | `.devin/upgrade/UPGRADE_TRACKER.json` |
| Execution Protocol | `.devin/upgrade/UPGRADE_EXECUTION_PROTOCOL.md` |

## BOOT sequence (lazy-load — see BOOT_PROTOCOL.md for full detail)

1. Read this entry file (summary)
2. Ensure registry exists → `.devin/loop_state.md`
3. Read registry (<3KB)
4. Read knowledge layer → `.agents/knowledge_distill.md` (<8KB)
5. Read user profile → `.agents/user_profile.md` (<2KB)
6. Read handoff letter → `.agents/handoff_letter.md` (if exists)
7. Determine session_id
8. Read per-session context flags

**Steps 9-17**: on-demand per BOOT_PROTOCOL.md (pre-task audit, GoalSpec, deep-memory, large-repo init, gap-scan).

## Key references

- Root `AGENTS.md` — Devin CLI orchestrator config (`/lightning` + `/glm`)
- `REPOS.md` — all GitHub repos/sources referenced
- `CLAUDE.md` — universal rules (security, code quality, Vietnamese conventions)
- `.devin/AGENTS_full.md` — full 186KB canon body (reference only, do NOT auto-load)
