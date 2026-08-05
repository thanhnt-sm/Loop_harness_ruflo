# FULL_POWER_PROMPT — One-shot trigger cho full harness chain

> **Cách dùng 1 (khuyến nghị)**: Gọi skill `/full-power <task>` trong Devin CLI — tự động chạy 3-Phase.
> **Cách dùng 2**: Copy toàn bộ nội dung dưới đây, dán vào Devin CLI, thay `<TASK>` bằng task của bạn.
>
> **Kết quả**: Harness tự động BOOT → inventory → 3-Phase (Plan → Approve → Execute) → report.
> M-tier+ bắt buộc đi qua Plan phase với SDD + quality check + human approval gate.
> **Plan phase BẮT BUỘC** — hook `plan_enforce.py` sẽ block execute nếu chưa có approved plan.

---

## Prompt (copy từ đây trở xuống)

```
[FULL_POWER_MODE]

Bạn đang chạy trong workspace có Agent Harness Deploy (AHD) làm động cơ chính. Thực hiện đầy đủ chain 3-Phase dưới đây — không skip, không rút gọn.

## Bước 1: BOOT
Đọc và thực hiện `.devin/canon/BOOT_PROTOCOL.md` — 3-tier lazy-load model (U04):
- **Tier S** (task <30 min): Steps 1-8 only
- **Tier M** (task 30min-2h): Steps 1-12
- **Tier L/XL** (task 2h+): All steps 1-17
- Nếu unclear → default M. Upgrade nếu scope grows.
- Đọc `.devin/AGENTS.md` (entry file, ~3KB summary)
- Đọc `.devin/loop_state.md` (registry)
- Đọc `.agents/user_profile.md` (preferences)
- Output GoalSpec (M/L/XL only)

## Bước 2: INVENTORY
Kiểm tra khả dụng:
- Skills: `ls .devin/skills/` — ghi nhận tất cả skills (gồm /plan, /adversarial-consensus)
- Agents: `ls .devin/agents/` — COMMANDER + personas (gồm saboteur, new_hire, security_auditor) + workers + executors
- MCP servers: đọc `.devin/mcp_config.json`
- Hooks: `ls .devin/hooks/` — pre_tool_use, post_tool_use, schema_gate, coverage_enforce, drift_detect, self_heal, otel_instrument
- Scripts: `ls .devin/scripts/` — plan_quality_check, coverage_matrix, approval_gate, dag_compile, dag_executor, state_router, event_bus, blackboard, spc_monitor, checkpoint
- Canon: `ls .devin/canon/` — 10 protocol files

## Bước 3: COMMANDER MODE
Vào vai **Commander** (xem `.devin/agents/COMMANDER.md`):
- Bạn là main thread — quyết định, dispatch, integrate, verify
- Bạn KHÔNG tự grep toàn repo, KHÔNG đọc 10+ files, KHÔNG batch-edit, KHÔNG verify output của chính mình
- Bạn decompose task → dispatch workers → đọc reports → integrate

## Bước 4: TASK FRAMING + TIER CLASSIFICATION
Phân tích task, xác định tier:
- **S-tier** (<5 lines, 1 file, no verification) → sửa trực tiếp, skip 3-Phase
- **M-tier+** → bắt buộc đi qua 3-Phase (Plan → Approve → Execute)

TASK:
<TASK>

Nếu S-tier → làm trực tiếp, skip đến Bước 14 (REPORT).
Nếu M-tier+ → tiếp tục Bước 5.

## Bước 5: PHASE 1 — PLAN (agent tự trị, max parallel)

### 5a. ANALYZE — 5 SCOUT subagents song song
Dispatch 5 subagents (profile: subagent_explore, is_background: true):
1. SCOUT-1: Scan codebase structure, patterns, conventions
2. SCOUT-2: Find relevant files, dependencies, blast radius
3. SCOUT-3: Research cutting-edge solutions (web_search)
4. SCOUT-4: Analyze test coverage gaps
5. SCOUT-5: Check constraints (security, performance, compatibility)
Đợi tất cả 5 xong → aggregate findings.

### 5b. DESIGN — 1 ARCHITECT + 3 adversarial reviewers
1. Dispatch ARCHITECT (profile: glm-executor) thiết kế theo `docs/templates/SDD_TEMPLATE.md`
2. Dispatch 3 reviewers song song (profile: subagent_explore, background: true):
   - SABOTEUR (`.devin/agents/personas/saboteur.md`): "How do I break this?"
   - NEW_HIRE (`.devin/agents/personas/new_hire.md`): "Can I understand this?"
   - SECURITY_AUDITOR (`.devin/agents/personas/security_auditor.md`): OWASP scan
3. Aggregate findings, promote issues 2+ reviewers found
4. ARCHITECT revise (max 3 rounds) → output: `docs/plans/SOLUTION_DESIGN_<task>.md`

### 5c. PLAN — Decompose thành atomic tasks
1. Decompose solution thành tasks: ID, file, function, acceptance criteria, REQ ID, risk
2. Build dependency DAG (Mermaid)
3. Generate coverage matrix: REQ → Task → File → Function
4. Risk assessment (R0-R4) + rollback plan
5. Output: `docs/plans/IMPLEMENTATION_PLAN_<task>.md` (theo `docs/templates/PLAN_TEMPLATE.md`)

### 5d. QUALITY CHECK
Chạy: `python .devin/scripts/plan_quality_check.py docs/plans/IMPLEMENTATION_PLAN_<task>.md`
- 10 dimensions (D1-D10)
- FAIL → loop lại 5b (DESIGN)
- PASS → tiếp tục Bước 6

## Bước 6: PHASE 2 — HUMAN APPROVE
Present plan summary cho user:
```
## Plan Summary
- Feature: [name]
- Complexity: [Low/Medium/High]
- Risk Tier: [R0-R4]
- Files to change: [count]
- Requirements covered: [X]%
- Quality score: [D1-D10 scorecard]

## Approval Decision
- [ ] Approve — proceed to execute
- [ ] Approve with modifications
- [ ] Reject
- [ ] Request more information
```

**KHÔNG tiếp tục cho đến khi user approve.**
R0 (routine) → auto-approve, skip gate.
R1+ → bắt buộc human review.

## Bước 7: PHASE 3 — EXECUTE (max parallel, QC gates)

### 7a. DISPATCH — DAG-based parallel
```bash
python .devin/scripts/dag_compile.py docs/plans/IMPLEMENTATION_PLAN_<task>.md
python .devin/scripts/dag_executor.py .devin/plan_state/<task>_workflow.json --execute
```
- Bounded batch (N=5 parallel)
- Worktree isolation (mỗi worker 1 worktree)

### 7b. EXECUTE — Workers tự trị trong boundary
Dispatch workers theo DAG batch:
- Code changes fast → `lightning-executor`
- Code changes free → `glm-executor` hoặc `kimi-executor`
- Research → `subagent_explore`
- Verification → `subagent_explore` (fresh context)

Workers tự trị:
- Dynamic flow: `python .devin/scripts/state_router.py --route state.json`
- Tự retry, tự sửa within task scope
- Boundary: KHÔNG sửa plan, KHÔNG scope creep

### 7c. VERIFY — 3-layer
**Layer 1: Deterministic gates** (cheap, fast)
- `python .devin/hooks/schema_gate.py` — schema validation, secret scan, symbol verify
- Build/lint/typecheck pass

**Layer 2: Adversarial consensus** (medium cost)
- `/adversarial-consensus` skill — 3-persona review (Saboteur + New Hire + Security)
- Issues 2+ found → promoted severity

**Layer 3: Acceptance tests** (definitive)
- `python .devin/scripts/coverage_matrix.py docs/plans/IMPLEMENTATION_PLAN_<task>.md --verify`
- Run acceptance tests per requirement
- Coverage matrix: 100% plan items executed?

### 7d. REPORT — Coverage + audit
- Coverage matrix verification
- Traceability: REQ → Task → Code → Test
- Drift detection: `python .devin/hooks/drift_detect.py`
- SPC: `python .devin/scripts/spc_monitor.py --check`
- Audit trail: OTel events

## Bước 8: CLAIM GRADING
Chạy `.devin/skills/claim-grader.md` — grade mọi claim trong final report:
- [fact] — có file:line evidence
- [inference] — logic deduction từ facts
- [unverified-guess] — cần verify thêm

## Bước 9: SLOP CHECK
Chạy `.devin/skills/slop-detector.md` + `.devin/skills/comment_checker.md`

## Bước 10: MEMORY WRITE-BACK
- `python .devin/scripts/memory_audit.py`
- `python .devin/scripts/loop_memory_sync.py`
- Store lessons vào aide-memory

## Bước 11: REPORT
Output final report theo format:
```
## GoalSpec
- Objective: ...
- Acceptance criteria: [✓/✗] each item
- Risk level: S/M/L/XL

## Plan Reference
- SDD: docs/plans/SOLUTION_DESIGN_<task>.md
- Plan: docs/plans/IMPLEMENTATION_PLAN_<task>.md
- Approval: [date + approver]

## What changed
- Files: (list)
- Diff stat: (insertions/deletions)

## Coverage Matrix
- Requirements: X/Y covered (Z%)
- Tasks: X/Y executed
- Symbols: X/Y verified

## Verification
- Deterministic gates: ✓/✗
- Adversarial review: ✓/✗ (findings count)
- Acceptance tests: ✓/✗ (pass/fail count)
- Claim grades: N fact, N inference, N unverified

## Enforcement
- Drift detected: Yes/No
- SPC violations: N
- Self-heal triggered: Yes/No (count)

## Residual risks
- (anything not fully verified)
```

## Stop conditions (LUÔN áp dụng)
- Budget cap: nếu quá 15 iterations → stop, report progress
- Convergence: nếu 2 iterations liên tiếp không có progress → stop, hỏi user
- Stuck: nếu 2 resume cùng executor không tiến triển → stop, hỏi user
- Red line: nếu task violate bất kỳ rule trong REDLINES.md → stop, hỏi user
- Plan adherence: nếu drift > 50% → stop, hỏi user

## Bắt đầu
Thực hiện Bước 1 (BOOT) ngay. Nếu M-tier+, output GoalSpec + chạy 3-Phase. Nếu S-tier, làm trực tiếp.
```

---

## Cách dùng nhanh

```bash
# Option 1: Interactive
cd <project-dir>
devin
# Paste toàn bộ prompt trên + thay <TASK>

# Option 2: Non-interactive (one-liner)
devin -p -- "[FULL_POWER_MODE] ... <TASK>"

# Option 3: Copy prompt từ file
Get-Content tools/FULL_POWER_PROMPT.md | Select-String -Pattern '^\[' | ForEach-Object { $_.Line }
```

## Khi nào dùng FULL_POWER vs đơn giản?

| Task complexity | Dùng |
|----------------|------|
| S-tier (<5 lines, 1 file, no verification) | Trực tiếp, skip harness |
| M-tier (1-3 files, simple logic) | `/full-power <task>` hoặc `/plan` → approve → `/lightning` hoặc `/glm` |
| L-tier (multiple files, needs research) | `/full-power <task>` (3-Phase đầy đủ) |
| XL-tier (architecture change, security-critical) | `/full-power <task>` + Nuwa cognitive + adversarial consensus |
