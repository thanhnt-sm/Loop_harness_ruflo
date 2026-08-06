---
name: full-power
triggers:
  - user
description: "Full Power Mode — 3-Phase đầy đủ (Plan→Approve→Execute) với max parallel, adversarial review, QC gates, enforcement. FORCE Plan phase bắt buộc. Gọi: /full-power <task>"
---

# Full Power Mode — 3-Phase Architecture (Plan → Approve → Execute)

> **Đây là skill mạnh nhất của hệ thống.** Trigger toàn bộ chain 3-Phase với max parallel subagents,
> adversarial review, QC gates, enforcement đầy đủ.
>
> **Plan phase BẮT BUỘC** — không skip, không rút gọn. Mọi task M-tier+ phải đi qua Plan phase
> trước khi execute. Chỉ S-tier (<5 lines, 1 file, no verification) được skip.

## Cách gọi

```
/full-power <task description>
/full-power add authentication to the API with JWT tokens
/full-power refactor the checkout module to support multiple payment providers
/full-power fix all failing tests in src/checkout/ and increase coverage to 80%
```

## Flow tổng quan

```
TASK → BOOT → INVENTORY → COMMANDER MODE → TIER CLASSIFICATION
  → S-tier? → làm trực tiếp → REPORT
  → M-tier+? → PHASE 1: PLAN (FORCE) → PHASE 2: APPROVE → PHASE 3: EXECUTE → REPORT
```

---

## Bước 1: BOOT

Đọc và thực hiện `.devin/canon/BOOT_PROTOCOL.md` — 3-tier lazy-load:
- **Tier S** (task <30 min): Steps 1-8 only
- **Tier M** (task 30min-2h): Steps 1-12
- **Tier L/XL** (task 2h+): All steps 1-17
- Unclear → default M. Upgrade nếu scope grows.

Đọc (lazy-load, KHÔNG load all):
- `.devin/AGENTS.md` (~3KB entry file)
- `.devin/loop_state.md` (registry, <3KB)
- `.agents/user_profile.md` (<2KB)
- `.devin/canon/CORE_CANON.md` (~2KB)
- `.devin/canon/REDLINES.md` (top 5, ~2KB)

## Bước 2: INVENTORY

Kiểm tra khả dụng (chạy 1 lần, ghi nhận):
- Skills: `ls .devin/skills/` — 16 top-level skill files + packages (`/plan`, `/adversarial-consensus`, `/full-power`, `/nuwa-skill`, v.v.)
- Agents: `ls .devin/agents/` — COMMANDER + personas + workers + executors
- Hooks: `ls .devin/hooks/` — 13 hooks (pre_tool_use, post_tool_use, schema_gate, coverage_enforce, drift_detect, self_heal, otel_instrument, v.v.)
- Scripts: `ls .devin/scripts/` — 22 scripts (plan_orchestrator, plan_quality_check, coverage_matrix, approval_gate, dag_compile, dag_executor, state_router, event_bus, blackboard, spc_monitor, checkpoint, v.v.)
- Canon: `ls .devin/canon/` — 15 protocol files
- MCP: aide-memory, spark-memory, deepwiki, devin

## Bước 3: COMMANDER MODE

Vào vai **Commander** (xem `.devin/agents/COMMANDER.md`):
- Main thread — quyết định, dispatch, integrate, verify
- KHÔNG tự grep toàn repo, KHÔNG đọc 10+ files, KHÔNG batch-edit, KHÔNG tự verify
- Decompose → dispatch workers → đọc reports → integrate

## Bước 4: TIER CLASSIFICATION (bắt buộc)

Phân tích task, xác định tier:

| Tier | Tiêu chí | Flow |
|------|----------|------|
| **S** | <5 lines, 1 file, no verification, no destructive op | Sửa trực tiếp → REPORT |
| **M** | 1-3 files, simple logic, 30min-2h | 3-Phase đầy đủ |
| **L** | Multiple files, needs research, 2h+ | 3-Phase đầy đủ + deep research |
| **XL** | Architecture change, security-critical, multi-system | 3-Phase đầy đủ + Nuwa cognitive |

**DEFAULT: M-tier.** Nếu unclear → M. Upgrade nếu scope grows.

**ENFORCEMENT**: Nếu task là M-tier+ và agent cố skip Plan phase → RED LINE violation.
Plan phase KHÔNG TÙY CHỌN. Nó là BẮT BUỘC.

TASK:
<task sẽ được inject khi gọi skill>

Nếu S-tier → làm trực tiếp, skip đến Bước 14 (REPORT).
Nếu M-tier+ → tiếp tục Bước 5 (PLAN phase — BẮT BUỘC).

---

## Bước 4.5: PREFLIGHT — Auto-activate tất cả scripts

Tạo `session_id` = `s-YYYYMMDD-<task_slug>` (slugify từ `<task>`).

Chạy tuần tự, không skip:

```bash
# 1. Log rotation
python .devin/scripts/log_rotation.py --rotate

# 2. Hook integrity
python .devin/scripts/hook_integrity.py --verify

# 3. Khởi tạo session với tier từ Bước 4
python .devin/scripts/session_manager.py init <session_id> --goal "<task>" --complexity <S|M|L|XL>

# 4. Cost cap theo tier (S=1, M=5, L=10, XL=20)
python .devin/scripts/cost_tracker.py --session <session_id> --set-cap <cap>

# 5. Pre-task audit
python .devin/scripts/pre_task_audit.py --tags "<task_slug>" --session <session_id> --json
```

- Nếu `pre_task_audit` trả `ok: false` → stop, hỏi user.
- Sau mỗi bước tiếp theo, gọi `python .devin/scripts/session_manager.py heartbeat <session_id>` để giữ session active.

**Cost guardrail**: Sau **mỗi step**, chạy `python .devin/scripts/cost_tracker.py --session <session_id> --check`. Nếu exit code 1 → stop, báo user.

**Script auto-activation map**:

| Script | Khi chạy | Lệnh |
|---|---|---|
| `log_rotation.py` | Preflight | `--rotate` |
| `hook_integrity.py` | Preflight | `--verify` |
| `session_manager.py` | Preflight/heartbeat/status/sync | `init`, `heartbeat`, `status`, `sync` |
| `cost_tracker.py` | Preflight + sau mỗi step | `--set-cap`, `--check` |
| `pre_task_audit.py` | Preflight + pre-execute | `--tags`, `--files` |
| `plan_orchestrator.py` | Phase 1 | `--init`, `--step` |
| `plan_quality_check.py` | Phase 1 QC | `<plan.md>` |
| `approval_gate.py` | Phase 2 | `--interactive` |
| `plan_dispatch.py` | Phase 3 pre-dispatch | `--plan` |
| `dag_compile.py` / `dag_executor.py` | Phase 3 | compile + execute |
| `worktree.py` | Phase 3 | `create` |
| `spc_monitor.py` | Phase 3/7d | `--check` |
| `checkpoint.py` | Trước DAG execute | `--save` |
| `state_router.py` | Phase 3 per worker | `--route <state.json>` |
| `event_bus.py` | Phase 3 per task result | `--publish execute.results <result.json>` |
| `blackboard.py` | Phase 3 evidence sharing | `--write evidence <task_id> <value.json>` |
| `coverage_matrix.py` | Phase 3 Layer 3 | `<plan.md> --verify` |
| `nuwa_roi.py` | Bước 10 | `--record-nuwa`, `--report` |
| `memory_audit.py` / `loop_memory_sync.py` | Bước 11 | merge + sync |

---

## Bước 5: PHASE 1 — PLAN (BẮT BUỘC, KHÔNG SKIP)

> **RED LINE**: Skip Plan phase cho M-tier+ = violation. Hook `plan_enforce.py` sẽ block.
> Plan phase chạy qua `plan_orchestrator.py` — FSM state machine tự động orchestrate toàn bộ flow.

### 5a. AUTO-ACTIVATE Orchestrator

> **ĐIỀU ĐẦU TIÊN PHẢI LÀM khi xác định M-tier+.**
> Không hỏi user. Không chờ xác nhận. Chỉ chạy orchestrator.

**NGAY LẬP TỨC** chạy:

```bash
python .devin/scripts/plan_orchestrator.py --init --task "<task description>"
```

Đọc `next_action` từ JSON output. Thực hiện action:
- `skip` → S-tier, skip Plan phase
- `dispatch_scouts` → Dispatch 5 SCOUTs (xem 5b)
- `dispatch_architect` → Dispatch ARCHITECT (xem 5c)
- `dispatch_reviewers` → Dispatch reviewers (xem 5c)
- `decompose_plan` → Decompose SDD (xem 5d)
- `run_qc` → Run quality check (xem 5e)
- `present_approval` → Run approval gate (xem Bước 6)
- `write_plan_state` → Write plan state (xem Bước 6)
- `done` → Plan phase hoàn thành
- `escalate` → Present issues to user

Sau mỗi action, viết results vào temp JSON, rồi gọi:

```bash
python .devin/scripts/plan_orchestrator.py --step --state <state_file> --results <results_file>
```

Lặp lại cho đến khi `state` = `DONE` hoặc `REJECTED` hoặc `ESCALATE`.

### 5b. ANALYZE — 5 SCOUT subagents song song (max parallel)

Orchestrator trả `action: dispatch_scouts` với 5 scout missions. Dispatch ALL 5 trong 1 response (background, subagent_explore). Collect results → write results JSON → call `--step`.

### 5c. DESIGN — 1 ARCHITECT + 3 adversarial reviewers (C3 pattern)

Orchestrator trả `action: dispatch_architect`. Dispatch ARCHITECT (foreground, glm-executor). Sau architect xong → call `--step` → orchestrator trả `action: dispatch_reviewers`.

Dispatch 3 reviewers ĐỒNG THỜI (background, subagent_explore):
- **SABOTEUR** (`.devin/agents/personas/saboteur.md`): "How do I break this in production?"
- **NEW_HIRE** (`.devin/agents/personas/new_hire.md`): "Can I understand this with zero context?"
- **SECURITY_AUDITOR** (`.devin/agents/personas/security_auditor.md`): OWASP-informed vulnerability scan

Collect reviews → aggregate (deduplicate, promote 2+ found, classify BLOCKING/ADVISORY/INFO) → call `--step`.

**Nếu BLOCKING + revision rounds < 3** → orchestrator trả `action: dispatch_revision` → resume architect → re-review.
**Nếu BLOCKING + revision rounds >= 3** → orchestrator escalate to human.
**Nếu không BLOCKING** → orchestrator tiếp tục PLAN.

### 5d. PLAN — Decompose thành atomic tasks

Orchestrator trả `action: decompose_plan`. Decompose SDD thành atomic tasks:
- Mỗi task: Task ID, description, file path(s), function(s), acceptance criteria, REQ ID, risk tier (R0-R4)
- Build dependency DAG (Mermaid graph)
- Generate coverage matrix: REQ ID → Task ID → File Path → Function → Status
- Risk assessment (R0-R4) + mitigation + rollback plan
- Test strategy: unit, integration, E2E per requirement
- Output: `docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md` (theo `docs/templates/PLAN_TEMPLATE.md`)

Call `--step` → orchestrator transitions to QC.

### 5e. QUALITY CHECK (BẮT BUỘC, KHÔNG SKIP)

Orchestrator trả `action: run_qc`:

```bash
python .devin/scripts/plan_quality_check.py docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md
```

10 dimensions (D1-D10): D1-D10 như mô tả trong `/plan` skill.

Call `--step` với QC result:
- **PASS tất cả** → orchestrator transitions to APPROVAL
- **FAIL + QC rounds < 3** → orchestrator loops back to DESIGN
- **FAIL + QC rounds >= 3** → orchestrator escalate to human

**ENFORCEMENT**: Nếu agent cố skip quality check → RED LINE violation.

---

## Bước 6: PHASE 2 — HUMAN APPROVE (BẮT BUỘC cho R1+)

Orchestrator trả `action: present_approval`. Chạy interactive approval gate:

```bash
python .devin/scripts/approval_gate.py docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md --interactive --quality-report docs/plans/<task_slug>/QUALITY_REPORT.md
```

Gate tự động present:
- Plan summary (feature, risk tier, tasks, requirements, files)
- Quality scorecard (D1-D10 pass/fail)
- Options: [y] Approve, [n] Reject, [m] Modify, [i] Info

**KHÔNG TIẾP TỤC CHO ĐẾN KHI USER APPROVE.**

Sau khi user decide → write results JSON → call `--step`:
- **Approved** → orchestrator transitions to WRITE_STATE
- **Rejected** → orchestrator transitions to REJECTED → stop
- **Changes requested** → orchestrator loops back to DESIGN

**ENFORCEMENT**: Nếu agent cố execute trước approval → RED LINE violation.
`python .devin/scripts/approval_gate.py <plan.md> --status` phải trả về `approved`.

---

## Bước 7: PHASE 3 — EXECUTE (max parallel, QC gates, enforcement)

### 7a. DISPATCH — Conflict detection + DAG-based parallel

Trước khi dispatch, phân tích plan để phát hiện conflict và xác định worktree / parallel groups:

```bash
python .devin/scripts/plan_dispatch.py --plan docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md --json
```

- Nếu có conflict → serialize hoặc hỏi user.
- Nếu `deadlock_detected` → stop và escalate.
- Dùng `parallel_groups` và `worktrees` từ output để dispatch.

Re-run `pre_task_audit` với file list thực tế từ plan output:

```bash
# Flatten owned_files + shared_files từ plan_dispatch JSON, join bằng dấu phẩy
python .devin/scripts/pre_task_audit.py --files "<owned+shared files>" --session <session_id> --json
```

Nếu conflict với active sessions → stop hoặc serialize.

Sau đó biên dịch và chạy DAG:

```bash
python .devin/scripts/dag_compile.py docs/plans/<task_slug>/IMPLEMENTATION_PLAN.md
python .devin/scripts/dag_executor.py .devin/plan_state/<task_slug>_workflow.json --execute
```

- Bounded batch (N=5 parallel, configurable)
- Worktree isolation (mỗi worker 1 worktree — `python .devin/scripts/worktree.py create <worker_id>`)
- Topological sort: independent tasks chạy song song, dependent tasks đợi

### 7b. EXECUTE — Workers tự trị trong boundary

Dispatch workers theo DAG batch:

| Task type | Profile | Model |
|-----------|---------|-------|
| Code changes fast | `lightning-executor` | SWE-1.7 Lightning |
| Code changes free | `glm-executor` | GLM-5.2 (free) |
| Code changes free (alt) | `kimi-executor` | Kimi K2.7 (free) |
| Research | `subagent_explore` | SWE-1.6 (cheap) |
| Verification | `subagent_explore` | SWE-1.6 (fresh context) |

Workers tự trị (max power trong boundary):
- Mỗi worker ghi state `.devin/state/<task_id>.json`, rồi gọi `python .devin/scripts/state_router.py --route .devin/state/<task_id>.json` để xác định bước tiếp.
- Tự retry, tự sửa within task scope.
- Reflexion: học từ mistake, retry smarter.
- Sau mỗi task: `python .devin/scripts/event_bus.py --publish execute.results .devin/state/<task_id>_result.json`
- Ghi evidence chia sẻ: `python .devin/scripts/blackboard.py --write evidence <task_id> .devin/state/<task_id>_evidence.json`

**Boundary (KHÔNG được vượt)**:
- KHÔNG sửa plan (plan = contract)
- KHÔNG out of scope (no scope creep)
- KHÔNG skip acceptance criteria
- KHÔNG skip verification
- KHÔNG modify hooks/canon/AGENTS.md

**ENFORCEMENT**: 
- `schema_gate.py` validate mọi output
- `coverage_enforce.py` track mọi plan item
- `drift_detect.py` phát hiện lệch plan
- `self_heal.py` tự sửa khi fail
- Sau mỗi batch: `python .devin/scripts/session_manager.py heartbeat <session_id>`
- Sau mỗi batch: `python .devin/scripts/cost_tracker.py --session <session_id> --check`
- Trước khi chạy DAG executor: `python .devin/scripts/checkpoint.py .devin/plan_state/<task_slug>_workflow.json --save pre-execute .devin/plan_state/<task_slug>_orchestrator.json`

### 7c. VERIFY — 3-layer (BẮT BUỘC)

**Layer 1: Deterministic Gates** (cheap, fast, không thể bypass)
```bash
python .devin/hooks/schema_gate.py    # Schema validation, secret scan, symbol verify
```
- JSON schema validation
- Required fields check
- Secret scan (8 regex patterns)
- Symbol verification (grep expected functions)
- File path validation (safe zones vs blocked zones)
- Build/lint/typecheck pass

**Layer 1 FAIL → BLOCK, không chạy Layer 2.**

**Layer 2: Adversarial Consensus** (medium cost)
```
/adversarial-consensus <artifact_path>
```
- 3-persona review (Saboteur + New Hire + Security Auditor)
- Issues 2+ found → promoted severity
- Max 3 rounds → escalate if still BLOCKING

**Layer 2 BLOCKING → revise, không chạy Layer 3.**

**Layer 3: Acceptance Tests** (definitive)
```bash
python .devin/scripts/coverage_matrix.py docs/plans/IMPLEMENTATION_PLAN_<task>.md --verify
```
- Run acceptance tests per requirement
- Coverage matrix: 100% plan items executed?
- Symbol verification: all expected functions exist?
- Traceability: REQ → Task → Code → Test

**Layer 3 FAIL → escalate to human.**

### 7d. REPORT — Coverage + audit trail

- Coverage matrix verification (all plan items executed?)
- Traceability matrix (REQ → Task → Code → Test)
- Drift detection report (PostToolUse hook `.devin/hooks/drift_detect.py`)
- SPC check (`python .devin/scripts/spc_monitor.py --check`)
- Self-heal log (if triggered)
- OTel audit trail

---

## Bước 8: CLAIM GRADING

Chạy `.devin/skills/claim-grader.md` — grade mọi claim trong final report:
- `[fact]` — có file:line evidence
- `[inference]` — logic deduction từ facts
- `[unverified-guess]` — cần verify thêm

## Bước 9: SLOP CHECK

Chạy `.devin/skills/slop-detector.md` + `.devin/skills/comment_checker.md`:
- Detect AI-generated filler (delve, leverage, seamless, robust)
- Detect slop comments (restating code, over-explaining)
- Remove nếu tìm thấy

## Bước 10: NUWA COGNITIVE VERIFICATION (L/XL only)

Chạy `.devin/skills/nuwa-skill/` cho adversarial cognitive review:
- **Munger perspective** — check cognitive biases trong design decisions
- **Feynman perspective** — check có explain được đơn giản không
- **Taleb perspective** — check robustness against black swans, tail risks

Record Nuwa metrics và xem ROI recommendation:

```bash
python .devin/scripts/nuwa_roi.py --session <session_id> --record-nuwa --bugs <n> --tokens <n>
python .devin/scripts/nuwa_roi.py --session <session_id> --report
```

Nếu recommendation = `reduce` → giảm tần suất Nuwa, chỉ dùng cho high-stakes tasks.

## Bước 11: MEMORY WRITE-BACK + SESSION CLOSE

- `python .devin/scripts/memory_audit.py` — merge candidate memories
- `python .devin/scripts/loop_memory_sync.py` — update registry
- `python .devin/scripts/session_manager.py sync --session <session_id>` — sync loop state
- `python .devin/scripts/session_manager.py status <session_id> completed` — close session
- Store lessons vào aide-memory: `mcp__aide-memory__aide_remember`
- Append handoff letter nếu có decisions worth recording

## Bước 12: REPORT

Output final report:

```markdown
## GoalSpec
- Objective: ...
- Acceptance criteria: [✓/✗] each item
- Risk level: S/M/L/XL

## Plan Reference
- SDD: docs/plans/SOLUTION_DESIGN_<task>.md
- Plan: docs/plans/IMPLEMENTATION_PLAN_<task>.md
- Quality report: docs/plans/QUALITY_REPORT_<task>.md
- Approval: [date + approver]

## What changed
- Files: (list with brief description)
- Diff stat: (insertions/deletions)

## Coverage Matrix
- Requirements: X/Y covered (Z%)
- Tasks: X/Y executed
- Symbols: X/Y verified

## Verification (3-layer)
- Layer 1 Deterministic gates: ✓/✗ (details)
- Layer 2 Adversarial review: ✓/✗ (N blocking, N advisory)
- Layer 3 Acceptance tests: ✓/✗ (N pass, N fail)
- Claim grades: N fact, N inference, N unverified

## Enforcement
- Drift detected: Yes/No (dimensions)
- SPC violations: N
- Self-heal triggered: Yes/No (N attempts)
- Plan adherence: X% (bigram Jaccard)

## Subagents dispatched
- SCOUT x5: (findings summary)
- ARCHITECT: (design summary)
- SABOTEUR: (findings)
- NEW_HIRE: (findings)
- SECURITY_AUDITOR: (findings)
- BUILDER xN: (changes summary)
- VERIFIER: (criteria confirmed)

## Residual risks
- (anything not fully verified)

## Next steps (optional)
- (follow-up tasks if any)
```

---

## Stop conditions (LUÔN áp dụng)

| Condition | Trigger | Action |
|-----------|---------|--------|
| Budget cap | >15 iterations | Stop, report progress |
| Convergence | 2 iterations no progress | Stop, hỏi user |
| Stuck | 2 resume same executor no progress | Stop, hỏi user |
| Red line | Violate REDLINES.md | Stop, hỏi user |
| Plan adherence | Drift > 50% | Stop, hỏi user |
| Self-heal budget | 3 recovery attempts exhausted | Escalate to human |
| Adversarial deadlock | 3 rounds still BLOCKING | Escalate to human |

---

## Guardrails (RED LINES — không vi phạm)

1. **KHÔNG skip Plan phase** cho M-tier+ → RED LINE
2. **KHÔNG skip quality check** (10-D) → RED LINE
3. **KHÔNG skip human approval** cho R1+ → RED LINE
4. **KHÔNG skip adversarial review** (min 3 personas) → RED LINE
5. **KHÔNG execute trước approval** → RED LINE
6. **KHÔNG sửa plan trong khi execute** → RED LINE
7. **KHÔNG scope creep** ngoài plan → RED LINE
8. **KHÔNG skip verification** (3-layer) → RED LINE
9. **KHÔNG skip coverage matrix verify** → RED LINE
10. **Max 3 adversarial rounds** → escalate if not converge
11. **Max 3 self-heal attempts** → escalate if exhausted
12. **Plan = contract** — lệch plan = drift, alert nếu > 50%

---
