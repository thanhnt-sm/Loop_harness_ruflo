# IMPLEMENTATION PLAN — AHD Build-Strategy Backlog Processing

> **PLAN** xử lý backlog 48 recommendations → 19 tickets từ `docs/reports/AHD_BUILD_STRATEGY_BACKLOG_2026-08-27.md`.
> Mục tiêu: implement để AHD cạnh tranh giá trị với harness Claude/Codex/GPT, đa provider, agent yếu + context nhỏ, phiên dài/phức tạp.
> Ngày: 2026-08-27 | Status: DRAFT (chờ approval) | Song ngữ EN+VI.
> Template: `docs/templates/PLAN_TEMPLATE.md`

---

## Phương pháp xử lý backlog (Giải pháp)

Mỗi ticket xử lý theo quy trình 5 bước (không skip):
1. **Deep-read**: đọc BUILD source file tương ứng (tra cứu recommendation code).
2. **Sub-plan**: viết plan chi tiết vào `docs/plans/ahd-build-strategy-implementation/<ticket-id>.md` (File Path + Function + Acceptance + REQ ID).
3. **Implement**: sửa đúng file (theo governance: `.devin/scripts/`, `.devin/hooks/`, `tools/`, `tests/`).
4. **Test**: viết/run test trong `tests/`.
5. **Report**: viết `EXECUTION_REPORT.md` + chạy `python tools/check_governance.py` (0 errors).

**Anti-duplicate**: mỗi ticket reference BUILD file gốc. Không re-research.

---

## PHASE 1 — HIGH (cạnh tranh trực tiếp)

### TICKET P1-01: Model tiering + per-call budget  `[R3+M1+M4]` ✅ DONE
- **File Path**: `.devin/scripts/router_config.py` (mới), `.devin/scripts/cost_tracker.py` (extend), `.devin/scripts/auto_model_router.py` (extend), `.devin/hooks/post_tool_config.py` (extend), `tests/test_model_tiering.py` (mới)
- **Function**: split classifier/router → cheap model; planner/synthesizer → premium; per-call-site budget attribution + alert
- **Acceptance**: (a) router chọn cheap model cho classify/route calls, (b) budget bucketed theo slot, (c) alert khi vượt budget
- **REQ ID**: REQ-P1-01

### TICKET P1-02: Structured-error MCP layer + circuit breaker  `[P1]` ✅ DONE
- **File Path**: `.devin/mcp_config.json` (audit), `.devin/hooks/post_tool_mcp_guard.py` (mới), `tests/test_mcp_guard.py` (mới)
- **Function**: wrap MCP tool calls; enforce `{ok,error,detail}` + completeness field; client-side circuit breaker (trip khi fail > threshold)
- **Acceptance**: (a) mọi MCP tool trả structured result, (b) circuit breaker trip + fallback khi upstream timeout, (c) no silent `null`
- **REQ ID**: REQ-P1-02 | **URGENT (security)**

### TICKET P1-03: Loop + context guards  `[P2+P3]` ✅ DONE
- **File Path**: `.devin/hooks/post_tool_bounded.py` (extend), `.devin/scripts/context_budget.py` (mới), `.devin/hooks/post_tool_config.py` (extend), `.devin/hooks/post_tool_engine.py` (integrate), `tests/test_loop_context_guards.py` (mới)
- **Function**: step limit (max 15 tool calls), token budget, repetition detection (same tool+params>2x→terminate); progressive tool discovery (3-4 tools/task); external WM; 80% context monitor
- **Acceptance**: (a) runaway loop bị kill, (b) chỉ load 3-4 tools/task (giảm token), (c) alert tại 80% context
- **REQ ID**: REQ-P1-03

### TICKET P1-04: Adaptive WM + prefix-cache compaction  `[W3+W4]` ✅ DONE
- **File Path**: `.devin/hooks/context_compaction.py` (extend), `.devin/scripts/adaptive_compress.py` (extend), `.devin/hooks/post_tool_config.py` (extend), `.devin/hooks/__init__.py` (mới), `.devin/scripts/__init__.py` (mới), `tests/test_adaptive_wm_compaction.py` (mới)
- **Function**: auto WM budget từ context window (8K→~6K, 200K→~128K); static system prompt + pinned memory; compact theo context-size pressure
- **Acceptance**: (a) WM auto-adaptive khi swap model, (b) prefix-cache stable (warm hits), (c) compact trigger theo budget không turn count
- **REQ ID**: REQ-P1-04

### TICKET P1-05: Durable step boundaries + resume  `[L1+L2]` ✅ DONE
- **File Path**: `.devin/hooks/ahd_session.py` (extend), `.devin/hooks/ahd_session_durable.py` (mới), `.devin/hooks/post_tool_engine.py` (integrate), `.devin/hooks/post_tool_config.py` (extend), `tests/test_durable_execution.py` (mới)
- **Function**: checkpoint state sau mỗi phase; resume từ checkpoint (không redo paid LLM calls); LLM call deduplication; tool receipts with idempotency keys; saga for irreversible actions
- **Acceptance**: (a) process crash → resume phase cuối, (b) LLM calls không re-execute, (c) idempotency keys, (d) tool receipts emitted, (e) saga human-gate for irreversible
- **REQ ID**: REQ-P1-05

### TICKET P1-06: Private golden set + trajectory eval  `[V1+V3]` ✅ DONE
- **File Path**: `tools/golden_set_miner.py` (mới), `tools/trajectory_eval.py` (mới), `tools/eval_harness.py` (mới), `tests/test_golden_set.py` (mới), `tests/test_trajectory_eval.py` (mới), `tests/test_eval_harness.py` (mới)
- **Function**: mine merged PRs → versioned golden set; trajectory strict match + LLM-as-judge (so path agent)
- **Acceptance**: (a) golden set ≥50 tasks versioned, (b) trajectory eval bắt path divergence, (c) run mọi PR
- **REQ ID**: REQ-P1-06

### TICKET P1-07: 3-layer stack adoption  `[S1]`
- **File Path**: `docs/ARCHITECTURE.md` (extend), `.opencode/mcp/servers.json` (MCP), integration A2A stub (mới)
- **Function**: MCP (tool) + A2A (agent delegation) + WebMCP; không tự build protocol
- **Acceptance**: (a) architecture doc vẽ 3-layer, (b) A2A delegation PoC giữa 2 agents, (c) pin protocol versions
- **REQ ID**: REQ-P1-07

---

## PHASE 2 — MED (hardening)

| Ticket | Code | File Path (dự kiến) | Acceptance ngắn |
|--------|------|---------------------|-----------------|
| P2-01 | R2 | `.devin/scripts/approval_gate.py` | approve intent, args:null resolve runtime |
| P2-02 | R4 | `.devin/hooks/post_tool_quality.py` | evaluator không thấy generator trace |
| P2-03 | W1+W2 | `.devin/hooks/context_compaction.py` | state-externalizing + evidence graph/BM25 |
| P2-04 | L3+L4 | `.devin/scripts/state_store/` | idempotency+receipts; saga human-gate |
| P2-05 | V4+V5+V6 | `tools/eval_harness.py` | CI gates đa chiều; judge bias; per-line ablation |
| P2-06 | P4+P5 | `tools/cost_tracker.py`, `.devin/hooks/post_tool_mcp_guard.py` | cost circuit breaker; identity propagation |
| P2-07 | R6 | `.devin/hooks/plan_enforce.py` | formal plan verify (acyclicity+budget) |

## PHASE 3 — LOW (nice-to-have)

| Ticket | Code | Ghi chú |
|--------|------|---------|
| P3-01 | R7+R8+R9+R10 | durable approvals, fresh WM, fan-out cap, open runtime |
| P3-02 | W5+W6+W7 | context 4-strategies, decision tree, dynamic workflow gen |
| P3-03 | V7+V8 | replay infra, canary auto-rollback |
| P3-04 | S2+S4+S5 | signed agent cards, AAIF governance, multi-binding |
| P3-05 | P6+P7+P8 | eval-less guard, schema drift, tool description quality |

---
 
## Verification plan
 
- Mỗi ticket: unit/integration test trong `tests/` + `python tools/check_governance.py` (0 errors) trước commit.
- Phase 1 xong: chạy SWE-bench Pro + private golden set để chứng minh cạnh tranh.
- Governance: 2 approval gates (plan + SDD) cho M/L/XL tickets.
 
## Risks
 
- **P1-02 MCP security** + **A1 Governance Decay** (từ TECH_OVERVIEW) là 2 urgent nhất — làm đầu tiên.
- AHD đã có 49 hooks → nhiều ticket = enhance, không rebuild.
- Model tiering (P1-01) cần provider config (LiteLLM-style) — verify `npx claude-flow` availability.
 
---
 
*Plan DRAFT | 2026-08-27 | 7 Phase-1 tickets (5 DONE) + 7 Phase-2 + 5 Phase-3 | Confidence: High*
