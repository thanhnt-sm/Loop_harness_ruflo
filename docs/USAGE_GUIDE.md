# Usage Guide — Tất cả Skills, Agents, Flows

> Hướng dẫn đầy đủ cách sử dụng hệ thống Agent Harness Deploy (AHD) với Devin CLI.

## Mục lục

1. [Bắt đầu nhanh](#1-bắt-đầu-nhanh)
2. [3 Executor skills](#2-3-executor-skills)
3. [23 AHD skills](#3-23-ahd-skills)
4. [Agents (Commander + Workers + Personas + Executors)](#4-agents)
5. [Canon protocols (10 files)](#5-canon-protocols)
6. [Hooks (8 events)](#6-hooks)
7. [MCP servers (4)](#7-mcp-servers)
8. [Scripts (8)](#8-scripts)
9. [Tools (14 PowerShell)](#9-tools)
10. [Flows chính](#10-flows-chính)

---

## 1. Bắt đầu nhanh

```bash
# Cài đặt (chỉ lần đầu)
cd D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo
devin

# Kiểm tra sức khỏe hệ thống
.\tools\health-check.ps1

# Verify workspace integrity
.\tools\verify-workspace.ps1
```

### Gọi skill nhanh

```bash
/lightning <task>    # Executor SWE-1.7 Lightning (trả phí, nhanh)
/glm <task>          # Executor GLM-5.2 (free, reasoning cao)
/kimi <task>         # Executor Kimi K2.7 (free đến 2026-07-05)
/auditor             # Audit code đối kháng
/tdd                 # Test-driven development
/gap-scan            # Quét thiếu sót
```

---

## 2. 3 Executor skills

Cả 3 cùng pattern: **orchestrator plan/review → executor implement/test/report**.

| Skill | Lệnh | Executor | Model | Cost | Context | Khi nào dùng |
|-------|------|----------|-------|------|---------|-------------|
| `/lightning` | `/lightning <task>` | lightning-executor | SWE-1.7 Lightning | $2.5/$12.5 MTok | 202K | Cần tốc độ (1000 tok/s) |
| `/glm` | `/glm <task>` | glm-executor | GLM-5.2 High | **Free** | 200K | Free tier, reasoning cao |
| `/kimi` | `/kimi <task>` | kimi-executor | Kimi K2.7 | **Free** (đến 07/2026) | 200K | Free tier, open-source |

### Workflow chung (6 bước)

1. **Frame task** — trích objective, acceptance criteria, constraints
2. **Preflight** — parallel reads: git status, repo instructions, build scripts
3. **Dispatch** — `run_subagent(profile: <executor>, is_background: false)`
4. **Review** — inspect diff độc lập, treat report as evidence not proof
5. **Correct** — trivial fix trực tiếp; lớn hơn thì `resume` cùng executor
6. **Report** — what changed, key files, verification, residual risks

### Ví dụ

```text
/lightning add pagination to the users endpoint and update its tests
/lightning reproduce and fix the checkout total rounding bug

/glm add input validation to the checkout form and update its tests
/glm review the auth module for security issues
/glm write tests for src/utils.js, coverage > 80%

/kimi refactor the cache adapter without changing its public API
/kimi write tests for src/utils.js, coverage > 80%
```

### Khi nào dùng cái nào?

- **Cần tốc độ** → `/lightning` (SWE-1.7 Lightning, 1000 tok/s)
- **Cần free + reasoning cao** → `/glm` (GLM-5.2, frontier capability)
- **Cần free + open-source** → `/kimi` (Kimi K2.7, free đến July 2026)
- **Trivial edit (vài dòng)** → sửa thẳng, skip delegation
- **Pure explanation** → trả lời trực tiếp, skip executor

---

## 3. 23 AHD skills

Tất cả trong `.devin/skills/`. Trigger: `[user]` (gọi bằng lệnh) hoặc `[model]` (tự invoke khi relevant).

### Executor skills (3)

| Skill | Lệnh | Mục đích |
|-------|------|----------|
| lightning | `/lightning <task>` | Dispatch cho SWE-1.7 Lightning |
| glm | `/glm <task>` | Dispatch cho GLM-5.2 (free) |
| kimi | `/kimi <task>` | Dispatch cho Kimi K2.7 (free) |

### Verification skills (5)

| Skill | Lệnh | Mục đích |
|-------|------|----------|
| auditor | `/auditor` | Adversarial code review — tìm security holes, false assumptions |
| fable-judge | `/fable-judge` | Judge fables (narrative verification) |
| claim-grader | `/claim-grader` | Grade claims: [fact] / [inference] / [unverified] |
| slop-detector | `/slop-detector` | Detect AI slop trong code/prose |
| comment_checker | `/comment_checker` | Check comment discipline (comments are debt) |

### Development skills (3)

| Skill | Lệnh | Mục đích |
|-------|------|----------|
| tdd | `/tdd` | Test-Driven Development (Red-Green-Refactor) |
| systematic_debugging | `/systematic_debugging` | Debug có phương pháp (reproduce→isolate→fix) |
| gap-scan | `/gap-scan` | Quét thiếu sót giữa current state và goal |

### Context/init skills (2)

| Skill | Lệnh | Mục đích |
|-------|------|----------|
| context-compactor | `/context-compactor` | Nén context khi quá lớn (4 levels, 65% reduction) |
| init_deep | `/init_deep` | Deep init cho repo lớn (scan, index, conventions) |

### Memory skills (3)

| Skill | Lệnh | Mục đích |
|-------|------|----------|
| loop-memory | `/loop-memory` | Sync loop state giữa các session |
| memory-audit | `/memory-audit` | Audit memory quality (stale, duplicates, contradictions) |
| graph-verify | `/graph-verify` | Verify knowledge graph integrity |

### Meta skills (3)

| Skill | Lệnh | Mục đích |
|-------|------|----------|
| user-preference | `/user-preference` | Học + apply preference của user |
| harness-sensor | `/harness-sensor` | Detect harness state |
| using-skills | `/using-skills` | Meta-skill: cách dùng skills |

### Specialized skills (4)

| Skill | Lệnh | Mục đích |
|-------|------|----------|
| nuwa-skill | `/nuwa-skill <person>` | Cognitive diversity verification (Munger/Feynman/Taleb) |
| aide-memory | `/aide-memory` | Persistent memory (recall/remember) |
| hlk-git-tools | `/hlk-git-tools` | Commit/push an toàn qua HLK layer |
| hlk-integrity-check | `/hlk-integrity-check` | Kiểm tra HLK layer sau upstream merge |

---

## 4. Agents

Tất cả trong `.devin/agents/`.

### Executors (3 — pinned model)

| Profile | Model | Vai trò |
|---------|-------|---------|
| lightning-executor | swe-1.7-lightning | Implementation cho `/lightning` |
| glm-executor | glm-5-2 | Implementation cho `/glm` (free) |
| kimi-executor | kimi-k2-7 | Implementation cho `/kimi` (free) |

### Commander (1 — orchestrator)

`COMMANDER.md` — main thread, dispatches workers, integrates results, never works directly.

### Workers (5)

| Worker | Vai trò |
|--------|---------|
| SCOUT | Scan/discover — tìm code, patterns, structure |
| BUILDER | Implement — viết code, sửa bug |
| AUDITOR | Verify — audit code quality, security |
| VERIFIER | Independent check — fresh context verification |
| MEMORY_KEEPER | Persist state — save to memory, update registry |

### Personas (3 — domain expertise)

| Persona | Vai trò |
|---------|---------|
| architect | System + backend architecture |
| code_reviewer | Code review |
| git_workflow_master | Git operations |

### Dispatch templates

`DISPATCH_TEMPLATES.md` — templates cho worker dispatch.

### Cách dispatch

```bash
# Qua skill (khuyến nghị)
/lightning <task>    # Tự dispatch lightning-executor

# Qua subagent trực tiếp
run_subagent(profile: lightning-executor, task: "<work order>")
run_subagent(profile: glm-executor, task: "<work order>")
run_subagent(profile: kimi-executor, task: "<work order>")
run_subagent(profile: subagent_explore, task: "<research task>")  # read-only
```

---

## 5. Canon protocols (10 files)

Tất cả trong `.devin/canon/`. **Chỉ 3 file load at BOOT**, còn lại on-demand.

| File | Load khi | Mục đích |
|------|----------|----------|
| CORE_CANON.md | **BOOT** | Identity, operating principles |
| BOOT_PROTOCOL.md | **BOOT** | 17-step startup (3-tier lazy-load) |
| REDLINES.md | **BOOT** (top 5) | 18 hard stops |
| LOOP_PROTOCOL.md | Chạy loop | Loop primitives, stop conditions |
| VERIFICATION_PROTOCOL.md | Verify output | Maker≠checker, read-back, CLI gates |
| MEMORY_PROTOCOL.md | Manage memory | 3-layer memory + deep-memory |
| CAVEMAN_PROTOCOL.md | Compress context | Token compression (~65% reduction) |
| HARNESS_ENGINEERING.md | Design harness | Design principles for agent systems |
| JUDGMENT_RUBRICS.md | Score/decide | Externalized decision criteria |
| HANDOFF_LETTER.md | Session end | Letter to future sessions |

### Sub-protocols (load on-demand)

| File | Mục đích |
|------|----------|
| LOOP_TURN_BASED.md | Turn-based loop (human-in-loop) |
| LOOP_GOAL_BASED.md | Goal-based loop (autonomous) |
| LOOP_TIME_BASED.md | DEPRECATED (merged into LOOP_PROTOCOL) |
| LOOP_PROACTIVE.md | DEPRECATED (merged into LOOP_PROTOCOL) |
| DAEMON_PROTOCOL.md | Daemonize MCP servers |

---

## 6. Hooks (8 events)

Tất cả trong `.devin/hooks/`. Cấu hình trong `.devin/config.json`.

| Event | Hook file | Mục đích |
|-------|-----------|----------|
| SessionStart | session_start.py | BOOT enforcement, verify boot_complete |
| SessionEnd | session_end.py | Cleanup, trigger memory save |
| UserPromptSubmit | user_prompt_submit.py | Inject harness state context |
| PostCompaction | (aide-memory hook) | Save context before compaction |
| Stop | stop.py | Session cleanup, memory write |
| PreToolUse | pre_tool_use.py | Security guard (encoding bypass, fail-closed) |
| PostToolUse | post_tool_use.py | State tracking, quality checks, done-detection |
| AgentStop | (aide-memory hook) | Agent stop cleanup |

### Hook features (U56-U62)

- **U56**: BOOT enforcement — `boot_complete=false` cho đến verify
- **U57**: Auto slop + comment checker trên Write/Edit
- **U58**: Done-detection — phát hiện "done/complete" → yêu cầu fable-judge
- **U59**: Skill auto-router — Write/Edit → suggest relevant skills
- **U60**: Loop enforcement — budget cap, time limit, staleness
- **U61**: State write verification — read-back, failure counter
- **U62**: Memory confidence — score 0-100, threshold 70%

---

## 7. MCP servers (4)

Cấu hình trong `.devin/mcp_config.json`.

| Server | Type | Mục đích | Tools chính |
|--------|------|----------|-------------|
| aide-memory | Local stdio | Persistent memory | aide_recall, aide_remember, aide_search |
| spark-memory | Remote HTTP | Shared memory cross-agent | mcp__spark-memory__* |
| deepwiki | Remote HTTP (free) | Query GitHub repo docs | read_wiki, ask_question |
| devin | Remote HTTP | Devin V3 API | session management, playbooks |

### Cách dùng aide-memory

```bash
# Recall (tìm memory)
aide_recall("user-preference")  # qua MCP tool

# Remember (lưu memory)
aide_remember("user prefers compact code", tags=["user-preference"])
```

---

## 8. Scripts (8)

Tất cả trong `.devin/scripts/`.

| Script | Mục đích | Cách gọi |
|--------|----------|----------|
| plan_dispatch.py | Plan + dispatch workers | `python .devin/scripts/plan_dispatch.py` |
| worktree.py | Git worktree management | `python .devin/scripts/worktree.py` |
| session_manager.py | Session state management | `python .devin/scripts/session_manager.py` |
| loop_memory_sync.py | Sync loop state cross-session | `python .devin/scripts/loop_memory_sync.py` |
| memory_audit.py | Audit memory quality | `python .devin/scripts/memory_audit.py` |
| pre_task_audit.py | Pre-task crash audit | `python .devin/scripts/pre_task_audit.py` |
| hook_integrity.py | Verify hook integrity | `python .devin/scripts/hook_integrity.py` |
| log_rotation.py | Rotate logs | `python .devin/scripts/log_rotation.py` |

---

## 9. Tools (14 PowerShell)

Tất cả trong `tools/`.

| Tool | Mục đích |
|------|----------|
| verify-workspace.ps1 | Verify integrity — 60 checks |
| health-check.ps1 | Health score (target ≥90) |
| merge-config.ps1 | Merge config files |
| aide-memory-daemon.ps1 | Start aide-memory daemon |
| backup-workspace.ps1 | Backup workspace |
| restore-workspace.ps1 | Restore từ backup |
| deploy-template.ps1 | Deploy template sang project mới |
| rollback-deploy.ps1 | Rollback deployment |
| init-new-project.ps1 | One-shot: package + deploy + git init + verify |
| package-template.ps1 | Đóng gói workspace → zip |
| clean-runtime.ps1 | Wipe runtime state |
| cleanup-orphan-sessions.ps1 | Cleanup orphan sessions |
| risk-contract-check.ps1 | Check risk contract |
| cross_platform.py | Cross-platform utilities |

---

## 10. Flows chính

### Flow 1: Code implementation (qua executor)

```text
User: /lightning add input validation to checkout form
  → Orchestrator frames task
  → Preflight: git status, repo instructions
  → Dispatch: run_subagent(lightning-executor, work_order)
  → Executor: inspect → implement → test → report
  → Orchestrator: review diff, verify, correct if needed
  → Report to user
```

### Flow 2: BOOT sequence

```text
Session start
  → session_start.py hook fires
  → Read AGENTS.md (3KB) + CORE_CANON + REDLINES (top 5)
  → Read loop_state.md registry
  → Read user_profile.md
  → Determine session_id
  → Check crashed sessions
  → (Tier M+) Pre-task audit + GoalSpec
  → (Tier L/XL) Deep-memory + init_deep + gap-scan
  → boot_complete = true
  → Ready for work
```

### Flow 3: Verification (auditor + fable-judge)

```text
Task declared "done"
  → post_tool_use.py detects "done/complete"
  → fable_judge_required = true
  → /auditor runs adversarial review
  → /claim-grader checks claims
  → /fable-judge verifies narrative
  → If PASS → done = true
  → If FAIL → resume executor with corrections
```

### Flow 4: Memory sync

```text
Session end
  → session_end.py hook fires
  → /loop-memory syncs loop state
  → /memory-audit cleans stale/duplicates
  → aide_remember saves key outcomes
  → knowledge_distill.md updated
  → handoff_letter.md written
```

### Flow 5: Continuous loop (xem CONTINUOUS_LOOP_GUIDE.md)

```text
GoalSpec → Loop iteration → State write → Stop check → (not met) → Next iteration
  → (met) → Verify → Done
  → (budget exhausted) → Stop, report
```

### Flow 6: Full power (one-shot)

```bash
# Paste tools/FULL_POWER_PROMPT.md vào Devin CLI
# Trigger 13-step chain:
# BOOT → INVENTORY → COMMANDER → TASK FRAMING → GAP SCAN
# → DECOMPOSE + DISPATCH (parallel) → INTEGRATE → VERIFY
# → NUWA COGNITIVE → CLAIM GRADING → SLOP CHECK
# → MEMORY WRITE-BACK → REPORT
```

---

## Tham khảo

- `docs/AGENTS_full_reference.md` — full AGENTS.md (27KB, reference)
- `docs/REDLINES_full.md` — full REDLINES (25KB, all 18 red lines + detail)
- `docs/BOOT_PROTOCOL_full.md` — full BOOT protocol (8.6KB)
- `docs/CONTINUOUS_LOOP_GUIDE.md` — hướng dẫn chạy loop liên tục
- `REPOS.md` — tất cả GitHub repos tham khảo
- `HLK/docs/REDTEAM_REPORT.md` — red team report
- `HLK/docs/UPGRADE_PLAN.md` — upgrade plan
