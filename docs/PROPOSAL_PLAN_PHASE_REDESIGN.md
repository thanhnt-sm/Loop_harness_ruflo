# PROPOSAL: Tái kiến trúc Phase Plan — Max Power + Max Quality

> **Status**: DRAFT — Chờ human approval
> **Date**: 2026-07-17
> **Author**: Devin (GLM-5.2 High) + 4 parallel research subagents
> **Risk Tier**: R3 (Critical path — thay đổi kiến trúc cốt lõi)
> **Research basis**: 4 subagent nghiên cứu song song (dynamic flow, PAE architecture, current system analysis, parallel execution patterns)

---

## §1. Vấn đề hiện tại (Phân tích sâu)

### 1.1. Chẩn đoán: "Thiết kế đẹp trên giấy, không có cơ chế thực thi"

Hệ thống hiện tại có **thiết kế xuất sắc** trong tài liệu (3-Phase, 5 SCOUT song song, adversarial review, 10-dimension QC, approval gate), nhưng **KHÔNG có orchestration layer** để tự động hóa quy trình.

**Bằng chứng thực tế:**
- Chưa bao giờ có file `SOLUTION_DESIGN_*.md` được tạo
- Chưa bao giờ có file `IMPLEMENTATION_PLAN_*.md` được tạo
- Chưa bao giờ có file `QUALITY_REPORT_*.md` được tạo
- `.devin/plan_state/` chỉ có 1 file test, không phải plan state thực
- Tất cả scripts (plan_quality_check.py, approval_gate.py, dag_compile.py, dag_executor.py, state_router.py) **tồn tại nhưng chưa bao giờ được auto-run**

### 1.2. 7 điểm yếu nghiêm trọng (ranked by severity)

| # | Severity | Vấn đề | Tác động |
|---|----------|--------|----------|
| 1 | 🔴 CRITICAL | **Không có orchestration script** — skill docs chỉ mô tả, không có code tự động chạy | Agent có thể bỏ qua Plan phase hoàn toàn |
| 2 | 🔴 CRITICAL | **Plan enforcement bypassable** — `plan_enforce.py` chỉ block nếu CÓ plan state. Không có plan state = không block | Agent viết code trực tiếp, không bị chặn |
| 3 | 🔴 CRITICAL | **Không có plan files được tạo** — không có evidence, không có audit trail | User không thể review plan |
| 4 | 🔴 CRITICAL | **Không có human approval UI** — `approval_gate.py` chỉ CLI, không interactive | Human không thể approve/reject dễ dàng |
| 5 | 🟡 HIGH | **Quality check không auto-run** — agent phải tự nhớ chạy | QC có thể bị bỏ qua |
| 6 | 🟡 HIGH | **DAG compile/execute không integrated** — scripts isolated | Parallel execution không được sử dụng |
| 7 | 🟡 HIGH | **Không có progress visibility** — user không thấy Plan phase đang chạy bước nào | User không biết agent đang làm gì |

### 1.3. Gap so với best practices (từ research)

| Best practice (2024-2026) | Hệ thống hiện tại | Gap |
|---------------------------|-------------------|-----|
| Plan as first-class artifact (structured, versioned, inspectable) | Plan chỉ là mô tả văn bản trong skill docs | 🔴 CRITICAL |
| Deterministic plan compilation (JSON DAG → immutable workflow) | dag_compile.py tồn tại nhưng không auto-run | 🔴 CRITICAL |
| D-P-D flow engineering (deterministic gate giữa mỗi probabilistic step) | Không có gate giữa các bước | 🟡 HIGH |
| Single-response batch spawning (parallel subagents trong 1 response) | Mô tả trong docs nhưng agent phải tự làm | 🔴 CRITICAL |
| Deterministic gates (model-free QC) | schema_gate.py tồn tại nhưng không integrated | 🟡 HIGH |
| Drift detection with SPC | drift_detect.py tồn tại nhưng không integrated | 🟡 HIGH |
| Adversarial review with cross-examination | 3 personas tồn tại nhưng không auto-dispatch | 🟡 HIGH |
| Named aggregator with conflict resolution | Không có | 🔴 CRITICAL |
| Plan-execution traceability (link mỗi execution step → plan step) | Không có | 🟡 HIGH |

---

## §2. Giải pháp đề xuất — Kiến trúc mới

### 2.1. Nguyên tắc thiết kế

1. **Plan là first-class artifact** — structured JSON + Markdown, version-controlled, inspectable, verifiable
2. **Orchestration layer tự động** — script chạy flow, không phụ thuộc agent tự làm theo docs
3. **D-P-D flow engineering** — deterministic gate giữa mỗi probabilistic step (LLM step)
4. **Max parallel + deterministic gates** — agent chạy max power, nhưng gate model-free kiểm soát kết quả
5. **Phase separation cứng** — Plan phase KHÔNG viết code, Execute phase KHÔNG sửa plan
6. **Human approval là red line** — không skip, không auto-bypass (trừ R0 trivial)

### 2.2. Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLAN ORCHESTRATOR (new)                       │
│  .devin/scripts/plan_orchestrator.py                             │
│  Tự động chạy toàn bộ Plan phase, không phụ thuộc agent tự làm   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: TIER CLASSIFICATION (D)                                 │
│  ├── Auto-classify S/M/L/XL từ task description                  │
│  ├── S-tier → skip Plan, return immediately                      │
│  └── M-tier+ → tiếp tục                                          │
│                                                                  │
│  Step 2: ANALYZE — 5 SCOUT song song (P → D)                     │
│  ├── Batch spawn 5 subagent_explore (background)                 │
│  │   SCOUT-1: Codebase structure                                 │
│  │   SCOUT-2: Relevant files + dependencies                      │
│  │   SCOUT-3: Cutting-edge solutions (web_search)                │
│  │   SCOUT-4: Test coverage gaps                                 │
│  │   SCOUT-5: Constraints (security, performance, compatibility) │
│  ├── D-gate: Validate mỗi SCOUT result (non-empty, relevant)     │
│  └── Aggregate findings → analysis_context.json                  │
│                                                                  │
│  Step 3: DESIGN — 1 ARCHITECT + 3 adversarial reviewers (P→D→P→D)│
│  ├── 3a: ARCHITECT (glm-executor, foreground)                    │
│  │   Input: analysis_context + SDD template                      │
│  │   Output: SOLUTION_DESIGN_draft.md                            │
│  ├── D-gate: Validate SDD (12 sections, non-empty)               │
│  ├── 3b: 3 adversarial reviewers song song (background)          │
│  │   SABOTEUR + NEW_HIRE + SECURITY_AUDITOR                      │
│  ├── D-gate: Validate reviews (findings structured)              │
│  ├── 3c: Aggregate reviews → promote issues 2+ found             │
│  ├── 3d: Revision loop (max 3 rounds)                            │
│  └── Output: SOLUTION_DESIGN_<task>.md (final)                   │
│                                                                  │
│  Step 4: PLAN — Decompose + DAG + Coverage (P → D)               │
│  ├── Decompose SDD → atomic tasks (Task ID, files, REQ_ID, risk) │
│  ├── Build dependency DAG (Mermaid + JSON)                       │
│  ├── D-gate: Validate DAG (acyclic, no orphan tasks)             │
│  ├── Generate coverage matrix (REQ → Task → File → Function)     │
│  ├── D-gate: Validate coverage (100% REQ covered)                │
│  ├── Test strategy + Rollback plan                               │
│  └── Output: IMPLEMENTATION_PLAN_<task>.md                       │
│                                                                  │
│  Step 5: QUALITY CHECK (D — deterministic, 10 dimensions)        │
│  ├── Auto-run plan_quality_check.py                              │
│  ├── D1-D10 scorecard                                            │
│  ├── FAIL bất kỳ dimension → loop lại Step 3 (max 3 rounds)      │
│  └── Output: QUALITY_REPORT_<task>.md                            │
│                                                                  │
│  Step 6: APPROVAL GATE (D — human-in-the-loop)                   │
│  ├── Present plan summary (feature, complexity, risk, coverage)  │
│  ├── Present adversarial findings (blocking, advisory)           │
│  ├── Present quality scorecard (D1-D10)                          │
│  ├── Wait for human decision:                                    │
│  │   Approve → write plan_state (approved) → return              │
│  │   Approve with modifications → loop lại Step 3/4              │
│  │   Reject → stop, log reason                                   │
│  │   Request more info → answer, re-present                      │
│  └── R0 auto-approve exception (all tasks R0)                    │
│                                                                  │
│  Step 7: WRITE PLAN STATE (D)                                    │
│  ├── Write .devin/plan_state/<task>.json (status=approved)       │
│  ├── This activates plan_enforce.py hook                         │
│  └── Return: {sdd_path, plan_path, quality_report_path}          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼ (sau approval)
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTE PHASE (separate)                      │
│  /lightning, /glm, /kimi — đọc plan as contract                  │
│  DAG-based parallel execution + deterministic gates              │
│  Coverage enforcement + drift detection + self-heal              │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3. Dynamic Flow — State Machine + DAG Hybrid

**Pattern**: FSM (Finite State Machine) cho control flow + DAG cho parallel execution

```
State Machine:
  IDLE → CLASSIFYING → ANALYZING → DESIGNING → PLANNING → QC → APPROVAL → APPROVED
                                  ↑                    │          │
                                  └─── QC FAIL ────────┘          │
                                  ↑                               │
                                  └─── APPROVE WITH MODS ─────────┘
                                                                   │
                                                          REJECTED → STOP
```

**Dynamic routing** (từ state_router.py, upgraded):
- `ANALYZING` → nếu tất cả SCOUT return empty → `DESIGNING` với minimal context
- `DESIGNING` → nếu SABOTEUR tìm thấy CRITICAL → `REVISION` (loop)
- `QC` → nếu D8 (file path specificity) FAIL → `PLANNING` (re-decompose)
- `QC` → nếu D1 (requirement coverage) FAIL → `DESIGNING` (re-design)
- `APPROVAL` → nếu R0 all tasks → `APPROVED` (auto)

### 2.4. Data Flow — Hybrid Event Bus + Context Isolation

**Pattern**: Event bus cho coordination + context isolation cho execution

```
┌──────────────────────────────────────────────────┐
│              EVENT BUS (.devin/plan_state/)       │
│  Typed events: scout.complete, design.draft,      │
│  review.finding, qc.result, approval.decision     │
│  Mỗi event: {id, run_id, type, payload, timestamp}│
└──────────────────────────────────────────────────┘
         ↑                    ↓                    ↑
    Publish              Subscribe            Subscribe
         │                    │                    │
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  SCOUT-1     │    │  SCOUT-2     │    │  SCOUT-3     │
│  (isolated   │    │  (isolated   │    │  (isolated   │
│   context)   │    │   context)   │    │   context)   │
└──────────────┘    └──────────────┘    └──────────────┘
```

**Context isolation**: Mỗi subagent nhận MINIMAL context (chỉ gì cần cho task của nó), không nhận full conversation history. Giảm token cost, tránh context rot.

**Shared blackboard** (optional): `.devin/plan_state/blackboard.json` — partition thành:
- `facts` — findings từ SCOUTs
- `artifacts` — SDD draft, plan draft
- `decisions` — ADRs, design decisions
- `reviews` — adversarial findings

### 2.5. Max Parallel Execution

**Pattern**: Single-response batch spawning + DAG scheduling

**Step 2 (ANALYZE)**: 5 SCOUT subagents batch spawn trong 1 response:
```
run_subagent(SCOUT-1, background=true)  # Tất cả 5 spawn
run_subagent(SCOUT-2, background=true)  # trong 1 response
run_subagent(SCOUT-3, background=true)  # → chạy song song
run_subagent(SCOUT-4, background=true)  # → wall-clock = max(slowest)
run_subagent(SCOUT-5, background=true)  # → không phải sum(all)
```

**Step 3b (ADVERSARIAL REVIEW)**: 3 reviewers batch spawn:
```
run_subagent(SABOTEUR, background=true)      # 3 reviewers
run_subagent(NEW_HIRE, background=true)      # song song
run_subagent(SECURITY_AUDITOR, background=true)  # → 3 kết quả cùng lúc
```

**Step 7 (EXECUTE)**: DAG-based parallel:
```
python .devin/scripts/dag_compile.py plan.md → workflow.json
python .devin/scripts/dag_executor.py workflow.json --execute --max-parallel 5
```
- Tasks không phụ thuộc nhau → chạy song song (batch 5)
- Tasks phụ thuộc → đợi prerequisite hoàn thành
- Worktree isolation cho write-heavy tasks

### 2.6. Quality Control — 3-Layer Deterministic Gates

**Layer 1: Deterministic Gates (model-free, cheap, fast)**
- Schema validation (JSON/Markdown format)
- Required fields check (SDD 12 sections, Plan 10 fields)
- DAG acyclic check
- Coverage matrix 100% check
- Secret scan (8 regex patterns)
- File path validation (safe zones vs blocked zones)
- Build/lint/typecheck pass

**Layer 2: Adversarial Consensus (medium cost)**
- 3-persona review (Saboteur + New Hire + Security Auditor)
- Issues 2+ found → promoted severity
- Cross-examination: dev agent tries to kill each finding
- Max 3 rounds → escalate if still BLOCKING

**Layer 3: Acceptance Tests (definitive)**
- Coverage matrix verification (all plan items executed?)
- Symbol verification (all expected functions exist?)
- Traceability (REQ → Task → Code → Test)
- Plan adherence (drift < 50%)

**D-P-D principle**: Không bao giờ để 2 probabilistic steps (LLM) chạy back-to-back mà không có deterministic gate ở giữa.

---

## §3. Chi tiết implementation

### 3.1. File mới: `.devin/scripts/plan_orchestrator.py`

**Đây là component CỐT LÕI** — script tự động chạy toàn bộ Plan phase.

**Flow**:
```python
def run_plan_phase(task_description, session_id):
    # Step 1: Classify tier (D)
    tier = classify_tier(task_description)
    if tier == "S":
        return {"skip": True}

    # Step 2: ANALYZE — 5 SCOUT song song (P → D)
    scout_results = dispatch_5_scouts_parallel(task_description)
    analysis_context = aggregate_scout_findings(scout_results)

    # Step 3: DESIGN — ARCHITECT + 3 reviewers (P → D → P → D)
    sdd_draft = dispatch_architect(analysis_context)
    for round in range(3):
        reviews = dispatch_3_reviewers_parallel(sdd_draft)
        promoted = promote_issues(reviews)
        if not promoted["blocking"]:
            break
        sdd_draft = revise_architect(sdd_draft, promoted)

    # Step 4: PLAN — Decompose + DAG (P → D)
    plan = decompose_to_tasks(sdd_draft)
    dag = build_dag(plan)
    coverage = generate_coverage_matrix(plan, dag)

    # Step 5: QC — 10 dimensions (D)
    qc_result = run_quality_check(plan)
    if not qc_result["all_pass"]:
        # Loop back to design (max 3 rounds)
        return run_plan_phase(task_description, session_id, round=round+1)

    # Step 6: APPROVAL (D — human)
    approval = present_approval_gate(sdd_draft, plan, qc_result)
    if approval != "approved":
        return {"status": "rejected"}

    # Step 7: Write plan state (D)
    write_plan_state(plan, status="approved")
    return {"status": "approved", "sdd": sdd_path, "plan": plan_path}
```

**Progress reporting** (stderr, visible cho user):
```
[Plan Phase] Step 1/7: Classifying tier... → M-tier
[Plan Phase] Step 2/7: Dispatching 5 SCOUTs... → IDs: scout-1..5
[Plan Phase] Step 2/7: Waiting for SCOUTs... → 3/5 complete
[Plan Phase] Step 2/7: All SCOUTs complete → aggregating findings
[Plan Phase] Step 3/7: Dispatching ARCHITECT... → designing solution
[Plan Phase] Step 3/7: SDD draft complete → validating (D-gate)
[Plan Phase] Step 3/7: Dispatching 3 reviewers... → SABOTEUR, NEW_HIRE, SECURITY_AUDITOR
[Plan Phase] Step 3/7: Reviews complete → 2 blocking, 3 advisory
[Plan Phase] Step 3/7: Revision round 1/3 → sending to ARCHITECT
...
[Plan Phase] Step 5/7: Quality check → D1-D10 scorecard
[Plan Phase] Step 6/7: Approval gate → waiting for human...
```

### 3.2. File: `.devin/scripts/plan_dispatch.py` (đã triển khai)

**Helper script** — phân tích dependency graph, phân bổ file ownership, phát hiện conflict trước khi dispatch:

> **Implementation note**: Tên gốc trong proposal là `plan_dispatcher.py` (dispatch/collect subagents). Trong thực tế, việc dispatch subagents được thực hiện trực tiếp trong `/plan` và `/full-power` skills qua `run_subagent`. `plan_dispatch.py` đảm nhiệm phần conflict detection và allocation trước dispatch, output JSON dispatch plan để Commander paste vào worker prompts.

```python
def dispatch_parallel_scouts(task_description, num_scouts=5):
    """Batch spawn N SCOUT subagents trong 1 response"""
    # Tạo work orders tự chứa cho mỗi SCOUT
    work_orders = [
        create_scout_work_order(i, task_description)
        for i in range(num_scouts)
    ]
    # Dispatch tất cả (agent gọi run_subagent cho từng one)
    return work_orders

def collect_parallel_results(agent_ids, timeout=300):
    """Collect results từ tất cả background subagents"""
    results = []
    for agent_id in agent_ids:
        result = read_subagent(agent_id, block=True, timeout=timeout)
        results.append(result)
    return results

def aggregate_findings(results, strategy="deduplicate_and_merge"):
    """Named aggregator — merge findings, deduplicate, resolve conflicts"""
    # Deduplicate (cùng root cause)
    # Promote (2+ reviewers tìm thấy → +1 severity)
    # Classify (BLOCKING / ADVISORY / INFO)
    return aggregated
```

### 3.3. Upgrade: `plan_enforce.py` — Fix bypass vulnerability

**Vấn đề hiện tại**: Chỉ block nếu CÓ plan state. Không có plan state = không block.

**Fix**: Check task tier từ session_state. Nếu M-tier+ và chưa có plan state → block.

```python
def main():
    # ... existing code ...

    # NEW: Nếu không có plan state VÀ task là M-tier+ → BLOCK
    tier = _classify_tier(task_desc, session_state)
    if tier != "S":
        plan_state = _get_plan_state(root)
        if not plan_state or plan_state.get("status") != "approved":
            # Block — M-tier+ requires approved plan
            block_reason = (
                f"PLAN ENFORCEMENT: Task tier={tier} requires approved plan. "
                f"No approved plan found in .devin/plan_state/. "
                f"Run /plan or /full-power first to create plan. "
                f"Plan phase is MANDATORY for M-tier+ tasks."
            )
            print(json.dumps({"allow": False, "reason": block_reason}))
            sys.exit(1)
```

### 3.4. Upgrade: `approval_gate.py` — Interactive mode

```python
def interactive_approval(plan_path, quality_report_path):
    """Present plan summary + hỏi user approve/reject"""
    # Load plan + quality report
    plan = load_plan(plan_path)
    qc = load_quality_report(quality_report_path)

    # Present summary
    print("## Plan Summary")
    print(f"- Feature: {plan['feature']}")
    print(f"- Complexity: {plan['complexity']}")
    print(f"- Risk Tier: {plan['risk_tier']}")
    print(f"- Files to change: {len(plan['tasks'])}")
    print(f"- Requirements covered: {qc['coverage_percent']}%")
    print(f"- Quality score: {qc['scorecard']}")
    print()
    print("## Adversarial Review Findings")
    print(f"- Blocking: {qc['blocking_count']}")
    print(f"- Advisory: {qc['advisory_count']}")
    print()
    print("## Approval Decision")
    response = input("Approve? [y/n/modify]: ").strip().lower()

    if response == "y":
        write_approval_state(plan_path, "approved")
        return "approved"
    elif response == "modify":
        modifications = input("Specify modifications: ")
        write_approval_state(plan_path, "changes_requested", modifications)
        return "changes_requested"
    else:
        reason = input("Reason for rejection: ")
        write_approval_state(plan_path, "rejected", reason)
        return "rejected"
```

### 3.5. Upgrade: Skills `/plan` và `/full-power`

**Thay đổi**: Skill docs sẽ hướng dẫn agent gọi `plan_orchestrator.py` thay vì tự làm từng bước.

**`/plan` skill (simplified)**:
```markdown
# Mission
Run plan_orchestrator.py to execute Phase 1 (PLAN) automatically.

# Workflow
1. Classify task tier (S/M/L/XL)
2. If S-tier → return (skip plan)
3. If M-tier+ → run:
   python .devin/scripts/plan_orchestrator.py --task "<task>" --session <session_id>
4. Orchestrator tự động:
   - Dispatch 5 SCOUTs song song
   - Dispatch ARCHITECT + 3 reviewers
   - Run quality check (10 dimensions)
   - Present approval gate
5. Wait for human approval
6. After approval → plan state written → executor can proceed
```

### 3.6. Output files (visible, structured, version-controlled)

```
docs/plans/<task_name>/
├── SOLUTION_DESIGN.md       # SDD — 12 sections (architecture, components, data flow)
├── IMPLEMENTATION_PLAN.md   # Plan — atomic tasks, DAG, coverage matrix
├── QUALITY_REPORT.md        # QC — D1-D10 scorecard
├── analysis_context.json    # Aggregated findings từ 5 SCOUTs
├── review_findings.json     # Adversarial review results
├── plan_state.json          # Approval state (pending/approved/rejected)
└── execution_trace.json     # (sau execute) — link mỗi step → plan step
```

---

## §4. So sánh: Hiện tại vs Đề xuất

| Khía cạnh | Hiện tại | Đề xuất |
|-----------|----------|---------|
| **Orchestration** | Agent tự đọc docs và tự làm | `plan_orchestrator.py` tự động chạy |
| **Parallel subagents** | Mô tả trong docs, agent tự dispatch | Batch spawn trong 1 response, auto-collect |
| **Plan files** | Chưa bao giờ được tạo | Auto-tạo structured JSON + Markdown |
| **Quality check** | Script tồn tại nhưng không auto-run | Auto-run sau Step 4, gate trước approval |
| **Approval gate** | CLI-only, không interactive | Interactive mode, present summary + hỏi user |
| **Enforcement** | Bypassable (no plan state = no block) | Fix: check tier, block M-tier+ without plan |
| **Progress visibility** | Không có | stderr progress reporting từng bước |
| **Dynamic flow** | Static (agent tự quyết) | FSM + DAG hybrid, auto-routing |
| **Data flow** | N/A | Event bus + context isolation |
| **Plan-execution traceability** | Không có | execution_trace.json link mỗi step → plan step |
| **D-P-D gates** | Không có | Deterministic gate giữa mỗi LLM step |

---

## §5. Lợi ích mong đợi

1. **Plan phase VISIBLE** — user thấy rõ từng bước đang chạy, thấy file đầu ra
2. **Plan phase HIGH QUALITY** — 5 SCOUT song song, 3 adversarial reviewers, 10-dimension QC
3. **Plan phase ENFORCED** — không skip được, hook block M-tier+ without approved plan
4. **Max parallel** — 5 SCOUT + 3 reviewers chạy song song, wall-clock = max(slowest)
5. **Quality control** — deterministic gates + adversarial consensus + coverage matrix
6. **Human approval** — interactive, present full summary, user decide
7. **Audit trail** — mọi file version-controlled, execution trace link plan → code
8. **Dynamic flow** — FSM auto-route dựa trên kết quả từng bước

---

## §6. Risks + Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Orchestrator script quá phức tạp | Medium | High | Modular design, mỗi step là function riêng |
| Subagent timeout/fail | Medium | Medium | Retry 1 lần, nếu fail → skip + log warning |
| Quality check quá strict | Low | Medium | Configurable thresholds, R0 auto-approve |
| Approval gate block quá lâu | Low | Low | Timeout 24h, auto-reject if no response |
| Plan files conflict với existing | Low | Low | Check working tree trước khi write |
| Parallel subagent rate limit | Medium | Low | Max 5 concurrent, queue additional |

---

## §7. Implementation plan (nếu approved)

### Phase 1: Build orchestrator (core)
1. Tạo `plan_orchestrator.py` — main orchestration script
2. Tạo `plan_dispatch.py` — helper conflict detection / file ownership allocation trước khi dispatch (subagent dispatch/collect nằm trong skill)
3. Upgrade `plan_enforce.py` — fix bypass vulnerability
4. Upgrade `approval_gate.py` — interactive mode

### Phase 2: Integrate scripts
5. Integrate `plan_quality_check.py` vào orchestrator (auto-run)
6. Integrate `dag_compile.py` + `dag_executor.py` vào orchestrator
7. Integrate `state_router.py` cho dynamic routing
8. Integrate `event_bus.py` + `blackboard.py` cho data flow

### Phase 3: Update skills + docs
9. Update `/plan` skill — gọi orchestrator thay vì tự làm
10. Update `/full-power` skill — gọi orchestrator cho Phase 1
11. Update `COMMANDER.md` — reference orchestrator
12. Update `REDLINES.md` — add red line "no skip Plan phase"

### Phase 4: Test + verify
13. Test orchestrator với sample task
14. Verify plan files được tạo đúng format
15. Verify quality check auto-run
16. Verify approval gate interactive
17. Verify enforcement hook block correctly
18. Full system test: `/full-power <task>` → plan → approve → execute

---

## §8. Approval Decision

```markdown
## Proposal Summary
- Feature: Tái kiến trúc Phase Plan — orchestration layer tự động
- Complexity: High
- Risk Tier: R3 (critical path)
- Files to change: ~15 (4 new scripts, 4 upgraded scripts, 3 updated skills, 2 updated canon, 2 updated docs)
- Requirements covered: 100% (7 weaknesses addressed)
- Quality score: Pending (will run QC after implementation)

## Key Changes
1. NEW: plan_orchestrator.py — tự động chạy toàn bộ Plan phase
2. NEW: plan_dispatch.py — helper conflict detection / file ownership allocation trước khi dispatch (subagent dispatch/collect nằm trong skill)
3. FIX: plan_enforce.py — block M-tier+ without approved plan (không chỉ check plan state)
4. FIX: approval_gate.py — interactive mode, present summary + hỏi user
5. UPGRADE: /plan skill — gọi orchestrator thay vì tự làm
6. UPGRADE: /full-power skill — gọi orchestrator cho Phase 1
7. INTEGRATE: 6 scripts đã tồn tại nhưng chưa auto-run → integrate vào orchestrator

## Approval Decision
- [ ] Approve — proceed to implement
- [ ] Approve with modifications — [specify]
- [ ] Reject — reason: [text]
- [ ] Request more information
```

---

## §9. Research references

| # | Source | Key finding |
|---|--------|-------------|
| 1 | Agentspan/Conductor | Deterministic plan compilation — JSON DAG → immutable workflow |
| 2 | Devin architecture | Planner-Executor separation — plan as JSON state, not conversation text |
| 3 | Claude Code/Cursor | Plan Mode — file-based plans, user can edit before approval |
| 4 | D-P-D Flow Engineering | Never let 2 P steps run back-to-back without D gate |
| 5 | LangGraph | Conditional edge routing — state machine + DAG hybrid |
| 6 | CrewAI Flows | Event-driven routing with pub/sub |
| 7 | Fan-Out/Fan-In pattern | Named aggregator with conflict resolution |
| 8 | DynTaskMAS | DAG scheduling: 21-33% less execution time, 35.4% better utilization |
| 9 | Agent SPC | Drift detection 4-8 days before user impact |
| 10 | Adversarial review | Cross-examination: dev agent tries to kill each finding |
| 11 | DriftGuard | Causal state rollback + replanning |
| 12 | SELFGOAL | Adaptive subgoal trees for autonomous execution |
| 13 | GATE framework | 19 controls across 4 layers, +12.4pp success rate |
| 14 | Plan quality metrics | 8 dimensions: structure, citation, completeness, actionability, feasibility, correctness, integration, documentation |
| 15 | Current system analysis | 7 critical/high weaknesses, 0 plan files ever created |
