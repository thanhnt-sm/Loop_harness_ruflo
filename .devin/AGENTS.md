# AHD Entry File — Summary

> Load canon on-demand per BOOT_PROTOCOL. Full body: `.devin/AGENTS_full.md` (186KB, do NOT auto-load).

## Identity

AHD-distilled harness. Core principles:
- Caveman comms (~65% token reduction)
- Commander + workers (main decides, dispatches; workers scan/edit)
- Maker ≠ checker (producer never verifies)
- Memory persists on disk, not context
- Loops converge (write state → check stop → stop when met)
- Evidence-graded: [fact] / [inference] / [unverified]

## Canon (on-demand)

| File | When |
|------|------|
| CORE_CANON.md | BOOT |
| BOOT_PROTOCOL.md | BOOT |
| REDLINES.md | BOOT (top 5) |
| MEMORY_PROTOCOL.md | Writing memory |
| LOOP_PROTOCOL.md | Running loops |
| VERIFICATION_PROTOCOL.md | Verifying |
| CAVEMAN_PROTOCOL.md | Compressing |
| HARNESS_ENGINEERING.md | Designing harness |

## Top 5 red lines

1. No overwrite without backup
2. No destructive ops without confirmation
3. No secrets in logs/state
4. No auto-resume crashed sessions
5. No skipping verification

## Skills (26 total, on-demand)

Default khi user chỉ đưa task (không gõ slash skill):
- Câu hỏi / giải thích / thông tin → trả lời trực tiếp.
- S-tier → sửa trực tiếp.
- **M/L/XL → mặc định `/full-power` để chạy full chain skill + script.**
- User override bằng `/lightning`, `/glm`, `/kimi`, `/plan`, v.v.

`full-power` — 3-Phase đầy đủ (Plan→Approve→Execute), FORCE Plan bắt buộc
`plan` — Phase 1: Plan (SDD + 10-D quality check + approval gate)
`adversarial-consensus` — 3-persona adversarial review (C3 pattern)
`lightning`, `glm`, `kimi` — executors
`auditor`, `fable-judge`, `claim-grader` — verification
`tdd`, `systematic_debugging`, `gap-scan` — development
`slop-detector`, `comment_checker` — quality
`context-compactor`, `init_deep` — context/init
`loop-memory`, `memory-audit`, `graph-verify` — memory
`user-preference`, `harness-sensor` — meta
`nuwa-skill` — cognitive verification

## Agents

- Commander — orchestrator, dispatches
- Workers: SCOUT, BUILDER, AUDITOR, VERIFIER, MEMORY_KEEPER
- Personas: architect, code_reviewer, git_workflow_master, saboteur, new_hire, security_auditor
- Executors: lightning-executor, glm-executor, kimi-executor

## Runtime

- Hooks: pre_tool_use, post_tool_use, stop, session_start, session_end, user_prompt_submit, schema_gate, coverage_enforce, drift_detect, self_heal, otel_instrument, plan_enforce
- Scripts: plan_dispatch, worktree, session_manager, loop_memory_sync, memory_audit, pre_task_audit, plan_quality_check, coverage_matrix, approval_gate, dag_compile, dag_executor, state_router, event_bus, blackboard, spc_monitor, checkpoint
- State: session_state/, loop_state/, context_flags/, plan_state/, checkpoints/, telemetry/, event_bus/, blackboard/
- MCP: aide-memory, spark-memory, deepwiki, devin

## BOOT (lazy-load, see BOOT_PROTOCOL.md)

1. Read this file → 2. Ensure registry → 3. Read registry → 4. Read knowledge_distill → 5. Read user_profile → 6. Read handoff_letter → 7. session_id → 8. Context flags
Steps 9-17: on-demand (pre-task audit, GoalSpec, deep-memory, gap-scan)

## References

- Root `AGENTS.md` — Devin CLI config
- `docs/USAGE_GUIDE.md` — full usage guide
- `docs/CONTINUOUS_LOOP_GUIDE.md` — loop guide
- `CLAUDE.md` — universal rules
