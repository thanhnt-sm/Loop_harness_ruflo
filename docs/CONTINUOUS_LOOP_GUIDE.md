# Continuous Loop Guide — Chạy Loop Liên Tục

> Hướng dẫn thiết lập và chạy loop liên tục với AHD + Devin CLI.
> Loop Engineering: thiết kế hệ thống nơi AI tự chạy, verify, ghi state, và lặp — cho đến khi đạt goal.

## Mục lục

1. [Khái niệm cốt lõi](#1-khái-niệm-cốt-lõi)
2. [3 chế độ loop](#2-3-chế-độ-loop)
3. [Thiết lập loop liên tục](#3-thiết-lập-loop-liên-tục)
4. [5+1 components](#4-51-components)
5. [Stop conditions (bắt buộc)](#5-stop-conditions-bắt-buộc)
6. [State contract](#6-state-contract)
7. [Maker ≠ Checker](#7-maker--checker)
8. [Continuous loop template](#8-continuous-loop-template)
9. [Loop với 3 executors](#9-loop-với-3-executors)
10. [Anti-patterns](#10-anti-patterns)
11. [Monitoring + troubleshooting](#11-monitoring--troubleshooting)

---

## 1. Khái niệm cốt lõi

**Prompt Engineering**: bạn nói với AI mỗi turn.
**Loop Engineering**: bạn thiết kế hệ thống nơi AI tự nói với chính nó, verify, ghi state, và chạy turn tiếp — cho đến khi stop condition được met.

Người dùng chuyển từ "lái mỗi turn" sang "thiết kế loop, đặt rules, xử lý exceptions."

### Khi nào NÊN loop

3 điều kiện phải đúng:
1. **Metric đo được** — không có metric → loop chạy nhưng không biết tốt/xấu
2. **Failure cost kiểm soát được** — không kiểm soát → human ở trong loop
3. **Harness đủ mạnh** — harness yếu → fix harness trước, chưa loop

### Khi nào KHÔNG loop

- Fixed-format conversion, form filling, data cleaning → viết script, không burn tokens
- Task không có metric đo lường → hand to human
- Task cần judgment sáng tạo → turn-based, không goal-based

---

## 2. 3 chế độ loop

| Mode | Lệnh | Semantics | Khi nào |
|------|------|-----------|---------|
| `/loop` | `/loop <task> every N min` | Cadence local, re-run mỗi N phút. Không self-stop. | Inspection, monitoring, periodic checks |
| `/schedule` | `/schedule <task> every N hours` | Cadence cloud, chạy server-side. Chạy khi laptop đóng. | Periodic work unattended across sleep |
| `/goal` | `/goal <task> until <condition>` | Condition-based, chạy đến khi condition met. | Bug-fix-until-tests-pass, refactor-until-clean |

### Quy tắc chọn

- **Có endpoint** → `/goal`
- **Không endpoint** → `/loop` hoặc `/schedule`
- **`/schedule` raises stakes**: stop conditions + budget cap + adversarial review **mandatory**

---

## 3. Thiết lập loop liên tục

### Bước 1: Define GoalSpec

```yaml
session_id: "s-loop-001"
goal: "Fix all failing tests in src/checkout/"
complexity: "L"
context_fill_pct: 0
scope:
  angles_required: ["test-coverage", "error-handling"]
  files_to_check: ["src/checkout/*.ts", "tests/checkout/*.test.ts"]
  sensor_mode: "code"
subtasks: []
acceptance_criteria:
  - "All tests in tests/checkout/ pass"
  - "No new test failures introduced"
  - "Coverage > 80% for src/checkout/"
human_in_loop_triggers:
  - "Test count drops below current"
  - "New error type discovered"
estimated_iterations: 10
cost_cap: 5.0  # USD max
cumulative_cost: 0.0
```

### Bước 2: Chọn executor

```bash
# Free tier (khuyến nghị cho loop dài)
/goal fix all failing tests using glm executor, budget $3

# Speed (khi cần nhanh)
/goal fix all failing tests using lightning executor, budget $3

# Free open-source
/goal fix all failing tests using kimi executor, budget $3
```

### Bước 3: Set stop conditions (mandatory)

```text
STOP CONDITIONS:
- Budget: $3.00 USD (tracked by post_tool_use hook)
- Convergence: 3 consecutive iterations with no new fix
- Time: 2 hours wall-clock
- Success: all tests pass + coverage > 80%
```

### Bước 4: Launch

```bash
# Goal-based loop
devin -p -- "/goal fix all failing tests in src/checkout/ until all tests pass, budget $3, max 10 iterations"

# Cadence loop (local)
devin -p -- "/loop run health-check every 30 min"

# Schedule loop (cloud, unattended)
devin -p -- "/schedule run entropy-sweep every 6 hours, budget $1/day"
```

---

## 4. 5+1 components

Mỗi loop cần 5+1 components:

| # | Component | Purpose | Trong hệ thống |
|---|-----------|---------|----------------|
| 1 | Loop/Goal | Cách loop chạy, khi nào stop | LOOP_PROTOCOL.md |
| 2 | Worktrees | Parallel agents không clobber files | `.devin/scripts/worktree.py` |
| 3 | Skills | Project knowledge ghi sẵn, agents không guess | `.devin/skills/` (23 skills) |
| 4 | Connectors | Agents reach beyond filesystem | MCP servers (4) |
| 5 | Sub-agents | Maker và checker là agents khác nhau | Executors + auditor + fable-judge |
| +1 | Memory | Cross-run persistent state | aide-memory + loop_state/ |

---

## 5. Stop conditions (bắt buộc)

**Thiếu bất kỳ điều kiện nào = broken loop. Không chạy unattended.**

| Condition | Mục đích | Default |
|-----------|----------|---------|
| **Budget cap** | Token/iteration/cost limit. Hit → stop. | $5 USD (U17) |
| **Convergence check** | N consecutive iterations không improvement → stop. | 3 iterations |
| **Time limit** | Hard wall-clock cap. Hit → stop. | 2 hours |

### Cách enforce

```python
# post_tool_use.py tự động track:
# - cumulative_cost (qua U17 cost tracking)
# - iteration_count
# - last_improvement_iteration
# - start_time

# Khi bất kỳ condition hit:
# → session_state.stop_reason = "budget_exhausted" | "converged" | "time_limit"
# → Loop dừng, report generated
```

---

## 6. State contract

**Mỗi iteration phải:**

1. Read `.devin/loop_state.md` registry (sessions active/completed)
2. Read `.devin/loop_state/<session_id>.md` (where did I get to?)
3. Do one unit of work
4. Write `.devin/loop_state/<session_id>.md` + `.devin/session_state/<session_id>.json`
5. Call `loop_memory_sync.py` to regenerate registry
6. Check stop condition
7. Not met → next iteration. Met → stop, archive.

**Không có step 4 → iteration tiếp blind. State là xương sống.**

### State file structure

```json
// .devin/session_state/<session_id>.json
{
  "session_id": "s-loop-001",
  "status": "in_progress",
  "goal": "Fix all failing tests",
  "iteration_count": 3,
  "cumulative_cost": 1.25,
  "cost_cap": 5.0,
  "last_improvement_iteration": 2,
  "convergence_threshold": 3,
  "start_time": "2026-08-05T10:00:00Z",
  "time_limit_hours": 2,
  "state_written": true,
  "last_state_write": "2026-08-05T10:30:00Z",
  "owned_files": ["src/checkout/total.ts"],
  "acceptance_criteria": ["all tests pass", "coverage > 80%"],
  "stop_reason": null
}
```

---

## 7. Maker ≠ Checker

**Agent chạy loop body KHÔNG được judge stop condition.** Separate checker (fresh context hoặc deterministic script) đánh giá.

### Pattern

```text
Worker (executor): làm work → report result
  ↓
Checker (auditor/fable-judge): evaluate result → check stop condition
  ↓
Not met → dispatch worker again
Met → stop, archive
```

### Checker nên là model nhỏ hơn/nhanh hơn

- Worker: GLM-5.2 / SWE-1.7 / Kimi K2.7 (generative work)
- Checker: auditor skill + fable-judge (evaluation only, cheap)

### Remediation sub-loop

```text
Checker finds problem → dispatch worker to fix → checker re-checks
  → Same problem 2 rounds → escalate to human
```

---

## 8. Continuous loop template

### Template: Goal-based loop (khuyến nghị)

```text
/goal <objective> until <success_condition>

EXECUTOR: glm-executor (free) | lightning-executor (fast) | kimi-executor (free)
BUDGET: $<amount> USD
MAX_ITERATIONS: <N>
TIME_LIMIT: <hours>h
CONVERGENCE: <N> iterations with no improvement

STOP CONDITIONS:
- Success: <condition>
- Budget: $<amount>
- Convergence: <N> iterations no improvement
- Time: <hours> hours

CHECKER: auditor + fable-judge (fresh context)
STATE: .devin/loop_state/<session_id>.md (write every iteration)
MEMORY: aide_remember after each iteration
```

### Template: Cadence loop (local)

```text
/loop <task> every <N> min

BUDGET: $<amount>/day
DURATION: indefinite (no success condition)
STOP: manual (Ctrl+C) or budget exhausted

STATE: .devin/loop_state/<session_id>.md
REPORT: after each run, write summary to .devin/loop_state/<session_id>.md
```

### Template: Schedule loop (cloud, unattended)

```text
/schedule <task> every <N> hours

BUDGET: $<amount>/day
DURATION: indefinite
STOP: manual or budget exhausted
ADVERSARIAL_REVIEW: mandatory (proactive pattern)
READINESS_SCORE: ≥90 required for unattended

STATE: .devin/loop_state/<session_id>.md
ALERT: if readiness < 90 → stop, notify human
```

---

## 9. Loop với 3 executors

### Free tier loop (khuyến nghị cho loop dài)

```bash
# GLM-5.2 (free, reasoning cao)
/goal fix all TypeScript errors using glm executor, budget $0, max 20 iterations

# Kimi K2.7 (free đến 2026-07-05)
/goal add test coverage for src/ using kimi executor, budget $0, max 15 iterations
```

### Speed loop (khi cần nhanh)

```bash
# SWE-1.7 Lightning (trả phí, 1000 tok/s)
/goal fix critical bug in checkout using lightning executor, budget $2, max 5 iterations
```

### Hybrid loop (worker + checker khác tier)

```text
Worker: kimi-executor (free, implement)
Checker: auditor skill (active model, review)
→ Cost tối ưu: worker free, checker dùng active model (ít tokens hơn)
```

---

## 10. Anti-patterns

| Anti-pattern | Tại sao sai | Fix |
|--------------|-------------|-----|
| No stop condition | Loop chạy mãi, burn tokens | 3 conditions mandatory |
| Same agent writes + checks | Self-confirmation bias | Split maker/checker |
| Loop to avoid thinking | Không define metric → không loop được | Hand to human |
| Ignoring state | Next iteration blind | Always read state first |
| No budget cap | Burn unlimited tokens | Set cost_cap trong GoalSpec |
| Worker = checker model | Waste expensive tokens on checking | Checker = cheaper model |
| No convergence check | Loop lặp lại same result | N iterations no improvement → stop |
| Loop what script can do | Burn tokens cho deterministic task | Write script instead |

---

## 11. Monitoring + troubleshooting

### Monitor loop state

```bash
# Check active loops
cat .devin/loop_state.md

# Check specific session
cat .devin/loop_state/<session_id>.md

# Check session state JSON
cat .devin/session_state/<session_id>.json

# Health check
.\tools\health-check.ps1
```

### Troubleshooting

| Vấn đề | Nguyên nhân | Fix |
|--------|-------------|-----|
| Loop không dừng | Stop condition không set | Check GoalSpec có budget + convergence + time |
| Loop lặp same work | State không write | Check post_tool_use.py chạy, session_state writable |
| Loop burn tokens | Budget cap không enforce | Check cost_cap trong GoalSpec, U17 tracking |
| Checker approves bad work | Same agent = checker | Split: worker ≠ checker (fresh context) |
| Loop crash | Session state corrupt | `.\tools\clean-runtime.ps1` → restart |
| Memory không persist | aide-memory MCP down | Check MCP config, restart daemon |

### Cleanup

```bash
# Wipe all runtime state (cẩn thận!)
.\tools\clean-runtime.ps1

# Cleanup orphan sessions only
.\tools\cleanup-orphan-sessions.ps1

# Backup before cleanup
.\tools\backup-workspace.ps1
```

---

## Quick start: 3 lệnh

```bash
# 1. Goal-based loop (phổ biến nhất)
devin -p -- "/goal fix all failing tests in src/ until all pass, budget $3, max 10 iterations, glm executor"

# 2. Cadence loop (monitoring)
devin -p -- "/loop run health-check every 30 min, budget $1/day"

# 3. Full power one-shot
# Paste tools/FULL_POWER_PROMPT.md vào Devin CLI
```

---

## Tham khảo

- `.devin/canon/LOOP_PROTOCOL.md` — core loop protocol
- `.devin/canon/LOOP_TURN_BASED.md` — turn-based loop detail
- `.devin/canon/LOOP_GOAL_BASED.md` — goal-based loop detail
- `.devin/canon/VERIFICATION_PROTOCOL.md` — maker/checker
- `docs/USAGE_GUIDE.md` — tất cả skills/agents/flows
- `tools/FULL_POWER_PROMPT.md` — one-shot full harness chain
