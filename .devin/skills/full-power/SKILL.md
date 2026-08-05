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
- Skills: `ls .devin/skills/` — 25 skills (gồm /plan, /adversarial-consensus, /full-power)
- Agents: `ls .devin/agents/` — COMMANDER + 6 personas + 5 workers + 3 executors
- Hooks: `ls .devin/hooks/` — 11 hooks (pre_tool_use, post_tool_use, schema_gate, coverage_enforce, drift_detect, self_heal, otel_instrument, v.v.)
- Scripts: `ls .devin/scripts/` — 16 scripts (plan_quality_check, coverage_matrix, approval_gate, dag_compile, dag_executor, state_router, event_bus, blackboard, spc_monitor, checkpoint, v.v.)
- Canon: `ls .devin/canon/` — 10 protocol files
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

## Bước 5: PHASE 1 — PLAN (BẮT BUỘC, KHÔNG SKIP)

> **RED LINE**: Skip Plan phase cho M-tier+ = violation. Hook `pre_tool_use.py` sẽ block.
> Plan phase tạo SDD + Implementation Plan + Quality Report TRƯỚC KHI viết bất kỳ code nào.

### 5a. ANALYZE — 5 SCOUT subagents song song (max parallel)

Dispatch 5 subagents (profile: `subagent_explore`, is_background: true) ĐỒNG THỜI:

| SCOUT | Nhiệm vụ | Tools |
|-------|----------|-------|
| SCOUT-1 | Scan codebase structure, patterns, conventions | grep, glob, read |
| SCOUT-2 | Find relevant files, dependencies, blast radius | grep, glob, read |
| SCOUT-3 | Research cutting-edge solutions | web_search, webfetch |
| SCOUT-4 | Analyze test coverage gaps | grep, glob, read, exec |
| SCOUT-5 | Check constraints (security, performance, compatibility) | grep, read, exec |

**Đợi TẤT CẢ 5 xong** → aggregate findings vào context.

### 5b. DESIGN — 1 ARCHITECT + 3 adversarial reviewers (C3 pattern)

**Round 1:**
1. Dispatch ARCHITECT (profile: `glm-executor`, foreground) — thiết kế giải pháp theo `docs/templates/SDD_TEMPLATE.md`
   - Input: aggregated findings từ 5 SCOUTs
   - Output: `docs/plans/SOLUTION_DESIGN_<task>.md`

2. Dispatch 3 reviewers ĐỒNG THỜI (profile: `subagent_explore`, is_background: true):
   - **SABOTEUR** (`.devin/agents/personas/saboteur.md`): "How do I break this in production?"
   - **NEW_HIRE** (`.devin/agents/personas/new_hire.md`): "Can I understand this with zero context?"
   - **SECURITY_AUDITOR** (`.devin/agents/personas/security_auditor.md`): OWASP-informed vulnerability scan

3. Aggregate findings:
   - Deduplicate (cùng root cause)
   - Promote: issue do 2+ reviewers tìm thấy → +1 severity
   - Classify: BLOCKING / ADVISORY / INFO

4. Nếu BLOCKING issues → ARCHITECT revise → quay lại review (max 3 rounds)
   Nếu không BLOCKING → tiếp tục

**Max 3 rounds.** Hết 3 rounds vẫn BLOCKING → escalate to human.

### 5c. PLAN — Decompose thành atomic tasks

1. Decompose solution thành atomic tasks:
   - Mỗi task: Task ID, description, file path(s), function(s), acceptance criteria, REQ ID, risk tier (R0-R4)
2. Build dependency DAG (Mermaid graph)
3. Generate coverage matrix: REQ ID → Task ID → File Path → Function → Status
4. Risk assessment (R0-R4) + mitigation + rollback plan
5. Test strategy: unit, integration, E2E per requirement
6. Output: `docs/plans/IMPLEMENTATION_PLAN_<task>.md` (theo `docs/templates/PLAN_TEMPLATE.md`)

### 5d. QUALITY CHECK (BẮT BUỘC, KHÔNG SKIP)

```bash
python .devin/scripts/plan_quality_check.py docs/plans/IMPLEMENTATION_PLAN_<task>.md
```

10 dimensions (D1-D10):
- D1: Requirement Coverage — all requirements có task?
- D2: Task Completeness — tasks atomic + actionable?
- D3: Dependency Correctness — DAG acyclic?
- D4: Key Links Planned — all integrations planned?
- D5: Scope Sanity — no scope creep?
- D6: Must-Haves Derivation — criteria falsifiable?
- D7: Context Compliance — follows AGENTS.md/CLAUDE.md?
- D8: Risk Assessment — all R3+ have mitigation?
- D9: Test Coverage — all requirements have test?
- D10: Rollback Plan — all R2+ have rollback?

**FAIL bất kỳ dimension → loop lại 5b (DESIGN).**
**PASS tất cả → tiếp tục Bước 6.**

**ENFORCEMENT**: Nếu agent cố skip quality check → RED LINE violation.

---

## Bước 6: PHASE 2 — HUMAN APPROVE (BẮT BUỘC cho R1+)

Present plan summary cho user:

```markdown
## Plan Summary
- Feature: [name]
- Complexity: [Low/Medium/High]
- Risk Tier: [R0-R4]
- Files to change: [count]
- Requirements covered: [X]%
- Quality score: [D1-D10 scorecard]

## Adversarial Review Findings
- Saboteur: [N blocking, N advisory]
- New Hire: [N blocking, N advisory]
- Security Auditor: [N blocking, N advisory]
- Promoted (2+ found): [N issues]

## Risk Section
- Blockers: [list or "none"]
- Mitigation: [for each blocker]

## Approval Decision
- [ ] Approve — proceed to execute
- [ ] Approve with modifications — [specify]
- [ ] Reject — reason: [text]
- [ ] Request more information
```

**KHÔNG TIẾP TỤC CHO ĐẾN KHI USER APPROVE.**

| Risk tier | Approval |
|-----------|----------|
| R0 (routine) | Auto-approve, skip gate |
| R1 (moderate) | Plan review required |
| R2 (high complexity) | Plan + ADR review |
| R3 (critical path) | Plan + ADR + security review |
| R4 (regulatory) | Full architecture review |

**ENFORCEMENT**: Nếu agent cố execute trước approval → RED LINE violation.
`python .devin/scripts/approval_gate.py <plan.md> --status` phải trả về `approved`.

---

## Bước 7: PHASE 3 — EXECUTE (max parallel, QC gates, enforcement)

### 7a. DISPATCH — DAG-based parallel

```bash
python .devin/scripts/dag_compile.py docs/plans/IMPLEMENTATION_PLAN_<task>.md
python .devin/scripts/dag_executor.py .devin/plan_state/<task>_workflow.json --execute
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
- Dynamic flow: `python .devin/scripts/state_router.py --route state.json`
- Tự retry, tự sửa within task scope
- Reflexion: học từ mistake, retry smarter
- Event bus: `python .devin/scripts/event_bus.py --publish execute.results <result.json>`

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
- Drift detection report (`drift_detect.py`)
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

## Bước 11: MEMORY WRITE-BACK

- `python .devin/scripts/memory_audit.py` — merge candidate memories
- `python .devin/scripts/loop_memory_sync.py` — update registry
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

## Tích hợp với skills khác

| Skill | Khi nào trigger | Cách |
|-------|----------------|------|
| `/plan` | Bước 5 (PLAN phase) | Auto-trigger cho M-tier+ |
| `/adversarial-consensus` | Bước 5b (DESIGN) + 7c (VERIFY) | Auto-trigger |
| `/lightning` | Bước 7b (EXECUTE) | User chọn sau approval |
| `/glm` | Bước 7b (EXECUTE) | User chọn sau approval |
| `/kimi` | Bước 7b (EXECUTE) | User chọn sau approval |
| `/auditor` | Bước 7c (VERIFY) | Auto-trigger Layer 2 |
| `/gap-scan` | Bước 5a (ANALYZE) | Auto-trigger |
| `/claim-grader` | Bước 8 | Auto-trigger |
| `/slop-detector` | Bước 9 | Auto-trigger |
| `/nuwa-skill` | Bước 10 (L/XL only) | Auto-trigger |
| `/context-compactor` | Context > 70% | Auto-trigger |
| `/tdd` | Bước 7b nếu task liên quan test | User chọn |

---

## Tham khảo

- `tools/FULL_POWER_PROMPT.md` — prompt gốc (reference)
- `.devin/agents/COMMANDER.md` — Commander protocol
- `.devin/canon/BOOT_PROTOCOL.md` — BOOT sequence
- `.devin/canon/REDLINES.md` — 18 hard stops
- `.devin/canon/VERIFICATION_PROTOCOL.md` — Maker≠Checker
- `docs/USAGE_GUIDE.md` — hướng dẫn sử dụng
- `docs/CONTINUOUS_LOOP_GUIDE.md` — hướng dẫn loop
- `docs/PROPOSAL.md` — tài liệu đề xuất 3-Phase
