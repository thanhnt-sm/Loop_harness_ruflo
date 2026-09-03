# SESSION HANDOFF — 2026-08-27

> Context đầy đủ cho session mới tiếp tục AHD Build-Strategy implementation.
> Nguồn: `docs/reports/AHD_BUILD_STRATEGY_BACKLOG_2026-08-27.md` (48 recs, 7 themes, 19 tickets) + `docs/plans/ahd-build-strategy-implementation/IMPLEMENTATION_PLAN.md` (Phase 1: 7 tickets P1-01...P1-07).

---

## 1. OBJECTIVE (Mục tiêu)

Implement AHD Build-Strategy backlog để AHD **cạnh tranh giá trị** với harness Claude/Codex/GPT:
- Multi-provider, agent yếu + context nhỏ, phiên dài/phức tạp
- Không rebuild từ zero: AHD đã có 49 hooks + governance enforcement
- Hầu hết recommendation = **enhancement** lên primitives có sẵn

---

## 2. RESEARCH ĐÃ LÀM (Done)

| Artifact | Mô tả | Lines |
|----------|-------|-------|
| `docs/reports/BUILD_ORCHESTRATION_2026.md` | Orchestration patterns (R1-R10) | ~400 |
| `docs/reports/BUILD_MULTI_PROVIDER_2026.md` | Multi-provider routing/budget (M1-M5) | ~350 |
| `docs/reports/BUILD_SMALL_CONTEXT_2026.md` | Weak-model harness (W1-W7) | ~380 |
| `docs/reports/BUILD_LONG_SESSION_2026.md` | Durable long-session (L1-L6) | ~320 |
| `docs/reports/BUILD_VERIFY_COMPETE_2026.md` | Verification/benchmark (V1-V8) | ~420 |
| `docs/reports/BUILD_EMERGING_STANDARDS_2026.md` | MCP/A2A/WebMCP standards (S1-S5) | ~280 |
| `docs/reports/BUILD_PRODUCTION_PAIN_POINTS_2026.md` | Production guards (P1-P8) | ~360 |
| **BACKLOG** | 48 recs grouped 7 themes → 19 tickets | 139 |

**Không cần re-research** — mỗi ticket reference BUILD file gốc (anti-duplicate).

---

## 3. BACKLOG SUMMARY

### 7 Themes → 48 Recommendations → 19 Tickets (3 Phases)

| Phase | Tickets | Priority | Key Codes | Status |
|-------|---------|----------|-----------|--------|
| **Phase 1** | P1-01 → P1-07 | HIGH (cạnh tranh) | R3,M1,M4,P1,P2,P3,W3,W4,L1,L2,V1,V3,S1 | 6/7 DONE |
| **Phase 2** | P2-01 → P2-07 | MED (hardening) | R2,R4,W1,W2,L3,L4,V4,V5,V6,P4,P5,R6 | 0/7 |
| **Phase 3** | P3-01 → P3-05 | LOW (nice-to-have) | R7-R10,W5-W7,V7,V8,S2,S4,S5,P6-P8 | 0/5 |

---

## 4. PHASE 1 — 7 TICKETS CHI TIẾT (Ready to Implement)

| Ticket | Code | File Path (Target) | Function | Acceptance (Key) | REQ ID | Status |
|--------|------|-------------------|----------|------------------|--------|--------|
| **P1-01** | R3+M1+M4 | `.devin/scripts/router_config.py` (new), `.devin/scripts/cost_tracker.py` (extend), `.devin/scripts/auto_model_router.py` (extend), `.devin/hooks/post_tool_config.py` (extend), `tests/test_model_tiering.py` (new) | Model tiering: classifier/router → cheap; planner/synthesizer → premium; per-call-site budget bucket + alert | (a) Router chọn cheap model cho classify/route, (b) Budget bucketed per slot, (c) Alert vượt budget | REQ-P1-01 | ✅ DONE |
| **P1-02** | P1 | `.devin/mcp_config.json` (audit), `.devin/hooks/post_tool_mcp_guard.py` (new), `tests/test_mcp_guard.py` (new) | Structured-error MCP: `{ok,error,detail}` + completeness; client circuit breaker | (a) MCP tools trả structured result, (b) Circuit breaker trip + fallback, (c) No silent `null` | REQ-P1-02 **URGENT** | ✅ DONE |
| **P1-03** | P2+P3 | `.devin/hooks/post_tool_bounded.py` (extend), `.devin/scripts/context_budget.py` (new), `.devin/hooks/post_tool_config.py` (extend), `.devin/hooks/post_tool_engine.py` (integrate), `tests/test_loop_context_guards.py` (new) | Loop/context guards: step limit 15, token budget, repetition detection (>2x same tool+params→terminate); progressive tool discovery 3-4/task; 80% context monitor | (a) Runaway loop killed, (b) Load 3-4 tools/task, (c) Alert 80% context | REQ-P1-03 | ✅ DONE |
| **P1-04** | W3+W4 | `.devin/hooks/context_compaction.py` (extend), `.devin/scripts/adaptive_compress.py` (extend), `.devin/hooks/post_tool_config.py` (extend), `.devin/hooks/__init__.py` (new), `.devin/scripts/__init__.py` (new), `tests/test_adaptive_wm_compaction.py` (new) | Adaptive WM budget từ context window (8K→~6K, 200K→~128K); static system prompt + pinned memory; compact theo budget pressure | (a) WM auto-adaptive swap model, (b) Prefix-cache stable, (c) Compact trigger theo budget | REQ-P1-04 | ✅ DONE |
| **P1-05** | L1+L2 | `.devin/hooks/ahd_session.py` (extend), `.devin/hooks/ahd_session_durable.py` (new), `.devin/hooks/post_tool_engine.py` (integrate), `.devin/hooks/post_tool_config.py` (extend), `tests/test_durable_execution.py` (new) | Durable step boundaries: checkpoint sau mỗi phase; resume từ checkpoint (no redo paid LLM); LLM call deduplication; tool receipts with idempotency keys; saga for irreversible actions | (a) Crash→resume phase cuối, (b) LLM calls không re-execute, (c) Idempotency keys, (d) Tool receipts emitted, (e) Saga human-gate for irreversible | REQ-P1-05 | ✅ DONE |
| **P1-06** | V1+V3 | `tools/golden_set_miner.py` (new), `tools/trajectory_eval.py` (new), `tools/eval_harness.py` (new), `tests/test_golden_set.py` (new), `tests/test_trajectory_eval.py` (new), `tests/test_eval_harness.py` (new) | Private golden set (mine merged PRs) + trajectory eval (strict path match + LLM-as-judge) | (a) Golden set ≥50 tasks versioned, (b) Trajectory eval bắt path divergence, (c) Run mọi PR | REQ-P1-06 | ✅ DONE |
| **P1-07** | S1 | `docs/ARCHITECTURE.md` (extend), `.opencode/mcp/servers.json` (MCP), A2A stub (new) | 3-layer stack: MCP (tool) + A2A (agent delegation) + WebMCP; không tự build protocol | (a) Architecture doc 3-layer, (b) A2A delegation PoC 2 agents, (c) Pin protocol versions | REQ-P1-07 | ⏳ PENDING |

---

## 5. GOVERNANCE RULES (Bắt buộc tuân thủ)

### 5.1 File Placement (WORKSPACE_GOVERNANCE.md)
| Type | Allowed Path | Forbidden |
|------|--------------|-----------|
| Script harness | `.devin/scripts/*.py` + `tests/test_*.py` | Root, docs/, scratch |
| Hook | `.devin/hooks/*.py` + `tests/test_*.py` | Nơi khác |
| Test | `tests/test_*.py` | Ngoài tests/ |
| Utility | `tools/*.py/.ps1/.sh` | Root |
| Plan artifact | `docs/plans/<slug>/IMPLEMENTATION_PLAN.md` | Root markdown |
| Report | `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md` | Plan dir |
| Scratch | `tmp/` (gitignored, clean up) | Tracked areas |

### 5.2 Plan ↔ Act Contract
1. **Plan phase**: Viết `IMPLEMENTATION_PLAN.md` với `File Path`, `Function`, `Acceptance Criteria`, `REQ ID`
2. **Approval gate**: Human duyệt SDD → Plan (2 gates)
3. **Act phase**: CHỈ sửa file trong plan + test file
4. **Post-act**: Viết `EXECUTION_REPORT.md`, self-check `git diff` ⊆ plan files
5. **Lint**: `python tools/check_governance.py` (0 errors trước commit)

### 5.3 Dependency Management
- `requirements-lock.txt` = hash-pinned (regen từ `pyproject.toml` via `uv pip compile`)
- `filelock < 3.13` (pin comment trong `pyproject.toml`)
- `pydantic-core ==` pinned by `pydantic`
- Pre-commit: `python tools/check_deps.py`

---

## 6. FIRST ACTIONS (Session mới bắt đầu từ đây)

### 6.1 BOOT (Lazy-load)
```bash
# 1. Read entry files
cat AGENTS.md
cat .devin/AGENTS.md
cat .devin/canon/CORE_CANON.md
cat .devin/canon/REDLINES.md  # top 5

# 2. Check registry
cat .devin/loop_state.md

# 3. Inventory
ls .devin/scripts/
ls .devin/hooks/
ls .devin/agents/
```

### 6.2 PREFLIGHT (Full-power protocol)
```bash
# Session ID
SESSION_ID="s-20260827-ahd-build-strategy"

# 1. Log rotation
.venv/bin/python .devin/scripts/log_rotation.py --rotate

# 2. Hook integrity
.venv/bin/python .devin/scripts/hook_integrity.py --verify

# 3. Init session (XL tier - architecture change, multi-system)
.venv/bin/python .devin/scripts/session_manager.py init "$SESSION_ID" \
  --goal "Implement AHD Build-Strategy Phase 1 (7 tickets)" \
  --complexity XL

# 4. Cost cap XL=20
.venv/bin/python .devin/scripts/cost_tracker.py --session "$SESSION_ID" --set-cap 20

# 5. Pre-task audit
.venv/bin/python .devin/scripts/pre_task_audit.py --tags "ahd-build-strategy" --session "$SESSION_ID" --json
```

### 6.3 START WITH P1-02 (URGENT - Security)
```bash
# Deep-read BUILD_PRODUCTION_PAIN_POINTS_2026.md (P1 section)
# Create sub-plan: docs/plans/ahd-build-strategy-implementation/P1-02.md
# Implement MCP structured-error + circuit breaker
```

**Lý do P1-02 first**: Security + governance decay (T4 A1) = 2 most urgent per backlog notes.

---

## 7. KEY FACTS (Decision Locks)

| Fact | Evidence | Implication |
|------|----------|-------------|
| AHD có 49 hooks + governance | `ls .devin/hooks/ | wc -l` | Enhance, không rebuild |
| `filelock < 3.13` pinned | `pyproject.toml` comment | Không bump độc lập |
| `pydantic-core ==` pinned by `pydantic` | `requirements-lock.txt` | Bump cùng lúc |
| Pre-commit 4 gates | `.githooks/pre-commit` | Redaction, junk, gitignore, governance |
| S-tier <5 lines auto-skip Plan | AGENTS.md tier table | Chỉ M/L/XL cần Plan phase |
| 2 approval gates bắt buộc | `approval_gate.py --interactive` | SDD + Plan approval |
| 3-layer verify bắt buộc | `schema_gate` + `adversarial-consensus` + `coverage_matrix` | Không skip layer |

---

## 8. RESIDUAL RISKS / OPEN QUESTIONS

| Risk | Mitigation |
|------|------------|
| Model tiering (P1-01) cần provider config (LiteLLM-style) | Verify `npx claude-flow` availability; fallback manual config |
| MCP servers.json audit có thể breaking change | Audit trước, test từng server |
| Golden set mining (P1-06) cần merged PR history | Start với recent 50 PRs, version v1 |
| A2A PoC (P1-07) external dependency | Stub trước, integrate sau |

---

## 9. CONTACT / ESCALATION

- **Blocker**: Stop, report progress, ask user
- **Red line violation**: Stop immediately, ask user
- **Budget cap >20 iterations**: Stop, report
- **Convergence stall 2 rounds**: Escalate

---

## 10. NEXT SESSION CHECKLIST

- [ ] Run BOOT + PREFLIGHT
- [ ] Verify `pre_task_audit` returns `ok: true`
- [ ] Start P1-07 (3-layer stack: MCP + A2A + WebMCP) → sub-plan → implement → test → report
- [ ] Run `python tools/check_governance.py` after each ticket
- [ ] Update `.devin/loop_state.md` registry
- [ ] Write handoff letter if paused mid-ticket

---

*Handoff generated 2026-08-27 | Full-power protocol | Ready for next session*