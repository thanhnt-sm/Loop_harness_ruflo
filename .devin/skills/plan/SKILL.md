---
name: plan
triggers:
  - user
  - model
description: "Plan Phase — Tự động orchestrate qua plan_orchestrator.py. Phân tích → Thiết kế → Plan → Quality Check → Approval. Human approval gate bắt buộc."
---

# AUTO-ACTIVATION — Kích hoạt ngay lập tức

> **ĐÂY LÀ ĐIỀU ĐẦU TIÊN PHẢI LÀM khi skill này được invoke.**
> Không hỏi user. Không chờ xác nhận. Không giải thích dài dòng.
> Chỉ chạy orchestrator và follow instructions.

**KHI SKILL NÀY ĐƯỢC INVOKE với task `<task>`:**

1. **NGAY LẬP TỨC** chạy lệnh sau (thay `<task>` bằng task description thực tế):

```bash
python .devin/scripts/plan_orchestrator.py --init --task "<task>"
```

2. Đọc `next_action` từ JSON output. Thực hiện action đó:
   - `skip` → S-tier, Plan phase không cần. Báo user và kết thúc.
   - `dispatch_scouts` → Dispatch 5 SCOUT subagents (xem Step 2 bên dưới)
   - `dispatch_architect` → Dispatch 1 ARCHITECT (xem Step 3)
   - `dispatch_reviewers` → Dispatch 3 reviewers (xem Step 4)
   - `decompose_plan` → Decompose SDD thành tasks (xem Step 5)
   - `run_qc` → Run quality check (xem Step 6)
   - `present_approval` → Run approval gate (xem Step 7)
   - `write_plan_state` → Write plan state (xem Step 8)
   - `done` → Plan phase hoàn thành
   - `escalate` → Present unresolved issues to user

3. Sau mỗi action, viết results vào temp JSON file, rồi gọi:

```bash
python .devin/scripts/plan_orchestrator.py --step --state <state_file> --results <results_file>
```

4. Lặp lại bước 2-3 cho đến khi `state` = `DONE` hoặc `REJECTED` hoặc `ESCALATE`.

**State file path** nằm trong JSON output của `--init` (field `state_file`).

---

# PREFLIGHT — Auto-activate scripts trước khi bắt đầu

Tạo `session_id` bằng cách slugify task: `s-YYYYMMDD-<task_slug>` (ví dụ `s-20260806-integrate-scripts`).

Chạy tuần tự:

```bash
# 1. Rotate log nếu quá lớn
python .devin/scripts/log_rotation.py --rotate

# 2. Verify hooks chưa bị tamper
python .devin/scripts/hook_integrity.py --verify

# 3. Khởi tạo session
python .devin/scripts/session_manager.py init <session_id> --goal "<task>" --complexity <S|M|L|XL>

# 4. Pre-task audit — kiểm tra active sessions
python .devin/scripts/pre_task_audit.py --tags "<task_slug>" --session <session_id> --json
```

- Nếu `pre_task_audit` trả `ok: false` → stop, đọc conflicts, hỏi user.
- Nếu `session_manager init` fail do quá 3 active sessions → dùng `--force` để queue hoặc hỏi user.

Sau đó tiếp tục `plan_orchestrator.py --init`.

---

# COST GUARDRAIL

Sau **mỗi lần gọi `--step`**, chạy:

```bash
python .devin/scripts/cost_tracker.py --session <session_id> --check
```

Nếu exit code 1 (cost cap exceeded) → stop và báo user.

---

# Mission

This skill implements **Phase 1 (PLAN)** of the AHD 3-Phase architecture using the **plan_orchestrator.py** FSM state machine:

```
Phase 1: PLAN     →  Phase 2: APPROVE  →  Phase 3: EXECUTE
(this skill)         (human gate)         (/lightning, /glm, /kimi)
```

The orchestrator (`plan_orchestrator.py`) drives the entire flow as a state machine. The agent interacts with it via CLI: init → step → step → ... → done. This ensures the Plan phase runs reliably and produces visible, high-quality output.

Optimize in this order:

1. Correctness and completeness of the design
2. Coverage of every stated requirement
3. Adversarial robustness (break-resistance, readability, security)
4. Traceability (every task links to a REQ ID)
5. Minimal scope (no speculative features)

Do not trade thoroughness for speed. A bad plan costs more in rework than a slow plan costs in latency.

# Overview

The orchestrator runs a state machine with these states:

```
INIT → CLASSIFY → ANALYZE → DESIGN → REVIEW → SDD_APPROVAL → PLAN → QC → PLAN_APPROVAL → WRITE_STATE → DONE
                              ↑          |              |
                              |--- REVISION (max 3)     |
                              |                         |
                              ←--- QC FAIL (max 3) ←----|
```

Each state transition produces a **next_action** that tells the agent exactly what to do. The agent performs the action, then calls `--step` with results to advance the state machine.

# Workflow

## Step 1 — INIT: Khởi tạo orchestrator

```bash
python .devin/scripts/plan_orchestrator.py --init --task "<task description>"
```

The orchestrator:
- Creates a state file at `.devin/plan_state/<task_slug>_orchestrator.json`
- Classifies task tier (S/M/L/XL)
- Returns first `next_action`

**If S-tier** → orchestrator returns `action: skip` → Plan phase not needed, proceed to execution.
**If M-tier+** → orchestrator returns `action: dispatch_scouts` → continue to Step 2.

## Step 2 — ANALYZE: Dispatch 5 SCOUT subagents song song

The orchestrator returns `action: dispatch_scouts` with 5 scout missions. Dispatch ALL 5 in a SINGLE response for max parallelism:

```
run_subagent(profile: subagent_explore, is_background: true, task: SCOUT-1 mission)
run_subagent(profile: subagent_explore, is_background: true, task: SCOUT-2 mission)
run_subagent(profile: subagent_explore, is_background: true, task: SCOUT-3 mission)
run_subagent(profile: subagent_explore, is_background: true, task: SCOUT-4 mission)
run_subagent(profile: subagent_explore, is_background: true, task: SCOUT-5 mission)
```

Collect all 5 results with `read_subagent`. Then write results to a temp JSON file and call `--step`:

```bash
# Write results JSON
# Format: {"action": "wait_scouts", "scout_results": [...]}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

The orchestrator transitions to DESIGN and returns `action: dispatch_architect`.

## Step 3 — DESIGN: Dispatch ARCHITECT

The orchestrator returns `action: dispatch_architect` with SDD template path and output file path.

Dispatch 1 ARCHITECT subagent (foreground, profile: glm-executor):

```
run_subagent(profile: glm-executor, is_background: false, task: "Design solution using SDD template at docs/templates/SDD_TEMPLATE.md. Analysis context: <aggregated findings>. Output: docs/plans/<task_slug>/SOLUTION_DESIGN.md")
```

After architect completes, write results JSON and call `--step`:

```bash
# Format: {"action": "dispatch_architect", "sdd_path": "docs/plans/<task_slug>/SOLUTION_DESIGN.md"}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

The orchestrator transitions to REVIEW.

## Step 4 — REVIEW: Dispatch 3 adversarial reviewers song song

The orchestrator returns `action: dispatch_reviewers` with 3 reviewer personas.

Dispatch ALL 3 in a SINGLE response:

```
run_subagent(profile: subagent_explore, is_background: true, task: SABOTEUR review of SDD)
run_subagent(profile: subagent_explore, is_background: true, task: NEW_HIRE review of SDD)
run_subagent(profile: subagent_explore, is_background: true, task: SECURITY_AUDITOR review of SDD)
```

Collect all 3 reviews. Aggregate findings:
- Deduplicate (cùng root cause)
- Promote: issue found by 2+ reviewers → +1 severity
- Classify: BLOCKING / ADVISORY / INFO

Write results JSON and call `--step`:

```bash
# Format: {"action": "dispatch_reviewers", "findings": [{"severity": "BLOCKING", ...}, ...]}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

**If BLOCKING issues + revision rounds < 3** → orchestrator transitions to REVISION → dispatch architect with issues to fix → re-review.
**If BLOCKING issues + revision rounds >= 3** → orchestrator transitions to ESCALATE → present unresolved issues to human.
**If no BLOCKING issues** → orchestrator transitions to SDD_APPROVAL.

## Step 5 — SDD_APPROVAL: Human approve the Solution Design

The orchestrator returns `action: present_sdd_approval` with the SDD path.

Run the interactive approval gate for the Solution Design:

```bash
python .devin/scripts/approval_gate.py docs/plans/<task_slug>/SOLUTION_DESIGN.md --interactive --artifact sd
```

The gate presents:
- SDD summary (feature, risk tier, options, trade-offs, recommendation)
- Key design decisions
- Options: [y] Approve, [n] Reject, [m] Modify, [i] Info

Wait for user decision, then write results JSON and call `--step`:

```bash
# Format: {"action": "present_sdd_approval", "decision": "approved"/"rejected"/"changes_requested", "reason": "...", "modifications": "..."}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

**If approved** → orchestrator transitions to PLAN (Step 6).
**If rejected** → orchestrator transitions to REJECTED → stop.
**If changes_requested** → orchestrator loops back to DESIGN.

## Step 6 — PLAN: Decompose thành atomic tasks

The orchestrator returns `action: decompose_plan` with plan template path.

As the main agent, decompose the SDD into atomic tasks:
- Each task: Task ID, description, file path(s), function(s), acceptance criteria, REQ ID, risk tier (R0-R4)
- Build dependency DAG (Mermaid graph)
- Generate coverage matrix: REQ ID → Task ID → File Path → Function
- Define test strategy + rollback plan
- Write to `docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md` using `docs/templates/PLAN_TEMPLATE.md`

Write results JSON and call `--step`:

```bash
# Format: {"action": "decompose_plan", "plan_path": "docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md"}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

The orchestrator transitions to QC.

## Step 7 — QC: Run quality check (10 dimensions)

The orchestrator returns `action: run_qc` with the command to run.

```bash
python .devin/scripts/plan_quality_check.py docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md
```

The script evaluates the plan across 10 dimensions (D1–D10):

| Dim | Name | What it checks |
|-----|------|----------------|
| D1 | Requirement coverage | Every REQ ID has at least one task |
| D2 | Task completeness | Each task has file path + function + acceptance criteria |
| D3 | Dependency correctness | DAG in Mermaid is acyclic |
| D4 | Key links planned | All integration points from SDD have tasks |
| D5 | Scope sanity | No orphan tasks outside requirements |
| D6 | Must-haves derivation | Acceptance criteria falsifiable, not vague |
| D7 | Context compliance | Plan follows AGENTS.md/CLAUDE.md |
| D8 | Risk assessment | All R3+ tasks have mitigation |
| D9 | Test coverage | All requirements have test cases |
| D10 | Rollback plan | All R2+ tasks have rollback |

Write results JSON and call `--step`:

```bash
# Format: {"action": "run_qc", "qc_result": {"all_pass": true/false, "report_path": "..."}}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

**If all PASS** → orchestrator transitions to PLAN_APPROVAL.
**If FAIL + QC rounds < 3** → orchestrator loops back to PLAN.
**If FAIL + QC rounds >= 3** → orchestrator transitions to ESCALATE.

## Step 8 — PLAN_APPROVAL: Human approve the Implementation Plan

The orchestrator returns `action: present_plan_approval` with the plan and quality report paths.

Run the interactive approval gate for the Implementation Plan:

```bash
python .devin/scripts/approval_gate.py docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md --interactive --quality-report docs/plans/<task_slug>/QUALITY_REPORT.md --artifact plan
```

The gate presents:
- Plan summary (feature, risk tier, tasks, requirements, files)
- Quality scorecard (D1-D10 pass/fail)
- Options: [y] Approve, [n] Reject, [m] Modify, [i] Info

Wait for user decision, then write results JSON and call `--step`:

```bash
# Format: {"action": "present_plan_approval", "decision": "approved"/"rejected"/"changes_requested", "reason": "...", "modifications": "...", "target": "plan"/"sdd"}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

**If approved** → orchestrator transitions to WRITE_STATE.
**If rejected** → orchestrator transitions to REJECTED → stop.
**If changes_requested** →
- `target: "plan"` → loop back to PLAN.
- `target: "sdd"` → loop back to DESIGN.

## Step 9 — WRITE_STATE: Activate enforcement hook

The orchestrator returns `action: write_plan_state` with the command to run.

```bash
python .devin/scripts/approval_gate.py docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md --approve --artifact plan
```

This writes the plan state file that activates `plan_enforce.py` hook — allowing execution to proceed.

Write results JSON and call `--step`:

```bash
# Format: {"action": "write_plan_state"}
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

The orchestrator transitions to DONE. Plan phase complete.

# Output Files

| File | Purpose | Step |
|------|---------|------|
| `docs/plans/<task_slug>/SOLUTION_DESIGN.md` | Solution Design Document — architecture, components, data flow | Step 3 |
| `docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md` | Implementation Plan — atomic tasks, DAG, coverage matrix, test + rollback | Step 6 |
| `docs/plans/<task_slug>/QUALITY_REPORT.md` | Quality Report — D1–D10 scorecard, pass/fail per dimension | Step 7 |
| `.devin/plan_state/<task_slug>_orchestrator.json` | Orchestrator state — FSM state, history, all paths | All steps |
| `.devin/plan_state/<task_slug>_approved.json` | Approval state — activates enforcement hook (for plans under `docs/plans/<task_slug>/`) | Step 9 |
| `.devin/plan_state/<task_slug>_sd_approved.json` | SDD approval state | Step 5 |

# Guardrails

- **DO NOT write any code during the Plan phase.** This skill produces documents only. Code is written in Phase 3 (EXECUTE) by an executor skill.
- **DO NOT skip the orchestrator.** Always use `plan_orchestrator.py` to drive the flow. Do not manually skip steps.
- **DO NOT skip the quality check.** The 10-dimension check is mandatory for every plan, regardless of complexity.
- **DO NOT proceed without human approval** — except the S-tier auto-skip exception.
- **DO NOT skip adversarial review.** Minimum 3 personas (SABOTEUR, NEW_HIRE, SECURITY_AUDITOR). Fewer is a quality check failure.
- **Maximum 3 revision rounds.** After 3 rounds with unresolved issues, escalate to the human.
- **Maximum 3 QC rounds.** After 3 rounds with failing dimensions, escalate to the human.
- **DO NOT edit files outside `docs/plans/`.** This skill's write scope is limited to plan documents.
- **Preserve pre-existing user changes.** Before writing any plan file, check the working tree for uncommitted changes and note them.

# Integration

After approval, the user triggers execution with one of the executor skills:

| Command | Executor | When |
|---------|----------|------|
| `/lightning <task>` | SWE-1.7 Lightning | Speed-critical (1000 tok/s) |
| `/glm <task>` | GLM-5.2 | Free tier, high reasoning |
| `/kimi <task>` | Kimi K2.7 | Free tier, open-source |

The executor reads `docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md` as its **contract** — the plan is the source of truth for what to build, in what order, and how to verify. The executor should not redesign; it implements the approved plan.

If the executor discovers a plan defect during implementation, it must stop and report back. The user then re-triggers `/plan` to revise the design rather than allowing the executor to improvise.

> *Plan là contract (hợp đồng). Executor chỉ thực thi, không tự ý thay đổi thiết kế. Nếu phát hiện lỗi trong plan → dừng, báo lại, chạy lại /plan.*

---

# WRAP-UP — Auto-activate scripts khi Plan hoàn thành

Khi orchestrator đạt `DONE` hoặc `REJECTED`:

```bash
# 1. Final cost check
python .devin/scripts/cost_tracker.py --session <session_id> --check

# 2. Cập nhật session status
python .devin/scripts/session_manager.py status <session_id> completed
# hoặc `crashed` nếu plan bị reject / escalate

# 3. Merge memory
python .devin/scripts/memory_audit.py
python .devin/scripts/loop_memory_sync.py
```