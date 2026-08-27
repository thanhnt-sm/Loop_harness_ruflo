# AHD BUILD-STRATEGY BACKLOG — Recommendations → Next-Session Plan

> Backlog tổng hợp **tất cả recommendations** từ 7 BUILD research files (T4, T7-T13).
> Mục đích: tạo plan sơ bộ để session sau **phân tích sâu + triển khai** code vào AHD.
> Ngày: 2026-08-27 | Song ngữ EN + VI | Chưa implement (blueprint).

---

## 0. Tổng quan (Overview)

7 BUILD research files sinh **48 recommendations** (R1-R10, M1-M5, W1-W7, L1-L6, V1-V8, S1-S5, P1-P8) chia 7 theme. Mỗi recommendation là issue AHD có thể implement. Dưới đây grouped + prioritized + gán file source + code để track.

**Triển khai nguyên tắc**: AHD đã có 49 hooks + governance enforcement → nhiều recommendation là **enhancement** lên primitives có sẵn (budget, kill-switch, approval gate), không rebuild từ zero.

---

## 1. BACKLOG CHI TIẾT (grouped by theme)

### Theme A — Orchestration (source: BUILD_ORCHESTRATION_2026.md)
| Code | Recommendation | Priority | Hiện trạng AHD |
|------|----------------|----------|----------------|
| R1 | Decompose by **context boundary**, not role type | HIGH | partial (role-centric có) |
| R2 | **Approve intent, not args** (planner trả args:null) | HIGH | approval_gate.py approve args hiện tại |
| R3 | **Cheap classifier/router + premium planner** | HIGH | có router multi-provider nhưng chưa split theo cost role |
| R4 | **Planner-Generator-Evaluator isolation** (evaluator không thấy trace) | MED | adversarial có nhưng chưa strict isolation |
| R5 | **Variable slim** (propagate chỉ IDs giữa tasks) | MED | — |
| R6 | **Z3/formal verify plan** trước execute (acyclicity+budget) | MED | plan_enforce có nhưng chưa formal verify |
| R7 | **Durable approvals + checkpoint resume** | MED | — |
| R8 | **Fresh WorkingMemory per sub-agent** | MED | subagents có nhưng chưa explicit fresh WM |
| R9 | **Fan-out cap + token/total budget** | LOW | có budget hooks |
| R10 | **Open runtime** (Claude Code/Gemini CLI/Codex cùng DAG) | LOW | orchestrator Devin-specific |

### Theme B — Multi-Provider (source: BUILD_MULTI_PROVIDER_2026.md)
| Code | Recommendation | Priority |
|------|----------------|----------|
| M1 | **Per-call-site budget attribution** (classify/router/planner/synthesizer buckets) | HIGH |
| M2 | **Fallback chain** (executor model fail → fallback provider) | HIGH |
| M3 | **Context-window aware selection** (auto chọn provider đủ window) | MED |
| M4 | **Cost tracking + budget alert** | MED |
| M5 | **Semantic cache layer** (cho research/prompts lặp) | LOW |

### Theme C — Small-Context / Weak Model (source: BUILD_SMALL_CONTEXT_2026.md)
| Code | Recommendation | Priority |
|------|----------------|----------|
| W1 | **State-externalizing harness** (model giữ semantic, harness giữ bookkeeping) | HIGH |
| W2 | **Derived-state rendering** (evidence graph + BM25 top-K) | HIGH |
| W3 | **Auto WM budget từ context window** (adaptive 8K↔200K) | HIGH |
| W4 | **Prefix-cache aware compaction** (static system prompt, pinned memory) | HIGH |
| W5 | **4 chiến lược Context (Write/Select/Compress/Isolate)** | MED |
| W6 | **Decision tree** (Skill/Subagent/Multi-Agent/Dynamic Workflows) | MED |
| W7 | **Dynamic Workflow generation** (gen harness runtime) | LOW |

### Theme D — Durable Long-Session (source: BUILD_LONG_SESSION_2026.md)
| Code | Recommendation | Priority |
|------|----------------|----------|
| L1 | **Durable step boundaries** (phases → workflow/activity, checkpoint) | HIGH |
| L2 | **Resume from checkpoint** (không redo paid LLM calls) | HIGH |
| L3 | **Idempotency + receipts** (tool layer trả receipt, not just NL) | MED |
| L4 | **Saga cho irreversible** (human gate trước khi ship) | MED |
| L5 | **Durable waiting** (approve gate + webhook resume) | MED |
| L6 | **Compacted durable state** (goal+receipts, not full history) | MED |

### Theme E — Verification / Compete (source: BUILD_VERIFY_COMPETE_2026.md)
| Code | Recommendation | Priority |
|------|----------------|----------|
| V1 | **Private versioned golden set** (mine từ merged PRs + failures) | HIGH |
| V2 | **SWE-bench Pro** cho public claim + private suite release | HIGH |
| V3 | **Trajectory eval** (ghi + so path agent) | HIGH |
| V4 | **CI gates đa chiều** (step/tool/latency/cost/safety) | MED |
| V5 | **Judge bias guardrails** (position-swap, kappa≥0.7) | MED |
| V6 | **Per-line prompt ablation** (auto-chạy mỗi prompt change) | MED |
| V7 | **Replay infra + trace join** (stable eval + prod) | MED |
| V8 | **Canary + auto-rollback** | LOW |

### Theme F — Emerging Standards (source: BUILD_EMERGING_STANDARDS_2026.md)
| Code | Recommendation | Priority |
|------|----------------|----------|
| S1 | **3-layer stack** (MCP tool + A2A agent + WebMCP) — đừng tự build protocol | HIGH |
| S2 | **Signed Agent Cards** (verify identity external agents) | MED |
| S3 | **AGENTS.md standard** (already done — maintain) | MED |
| S4 | **AAIF governance** (RFC/version-negotiation discipline) | LOW |
| S5 | **Multi-tenancy + multi-binding** (nếu expose agents) | LOW |

### Theme G — Production Pain Points (source: BUILD_PRODUCTION_PAIN_POINTS_2026.md)
| Code | Recommendation | Priority |
|------|----------------|----------|
| P1 | **Structured-error MCP** (`{ok,error,detail}` + completeness field) + client circuit breaker | HIGH |
| P2 | **Runaway loops guard** (step limit + token budget + repetition detection) | HIGH |
| P3 | **Context exhaust guard** (progressive tool discovery 3-4/task, external WM, 80% monitor) | HIGH |
| P4 | **Cost explosion guard** (per-task caps, model tiering, hourly circuit breaker, attribution) | MED |
| P5 | **Identity leakage guard** (per-user/tenant credential, không share) | MED |
| P6 | **Eval-less deploy guard** (golden dataset VCS, run mọi PR, day-zero eval) | MED |
| P7 | **Schema drift guard** (pin MCP schemas, CI validate) | LOW |
| P8 | **Vague tool descriptions** (tên + schema rõ ràng giảm arg hallucination) | LOW |

---

## 2. PRELIMINARY PLAN (cho session sau)

> Mỗi item dưới = 1 ticket. Session sau nên: (1) deep-analysis file source, (2) viết plan chi tiết trong `docs/plans/<slug>/`, (3) implement + test + report.

### Phase 1 — HIGH priority (cạnh tranh trực tiếp với Claude/Codex/GPT harness)
1. **[R3+M1+M4] Model tiering + per-call budget** — split classifier/router (cheap) vs planner/synthesizer (premium); per-call-site budget attribution + alert. File: `.devin/scripts/` router + `tools/`.
2. **[P1] Structured-error MCP layer** — wrap MCP tool calls, enforce `{ok,error,detail}` + completeness; client-side circuit breaker. File: `.opencode/mcp/` + hook.
3. **[P2+P3] Loop + context guards** — step limit, token budget, repetition detection (kill switch); progressive tool discovery 3-4/task. File: `.devin/hooks/`.
4. **[W3+W4] Adaptive WM + prefix-cache compaction** — auto WM budget từ context window; static system prompt + pinned memory. File: harness context engine.
5. **[L1+L2] Durable step boundaries** — checkpoint sau mỗi phase; resume từ checkpoint. File: persistence layer.
6. **[V1+V3] Private golden set + trajectory eval** — mine merged PRs; trajectory strict match. File: `tests/` + eval harness.
7. **[S1] 3-layer stack adoption** — MCP (existing) + A2A (delegate) + WebMCP; không tự build protocol. File: architecture doc + integration.

### Phase 2 — MED priority (hardening)
8. [R2] Approve-intent-not-args trong approval_gate.py
9. [R4] Evaluator isolation (không thấy generator trace)
10. [W1+W2] State-externalizing + derived-state rendering (evidence graph, BM25)
11. [L3+L4] Idempotency+receipts + Saga human-gate
12. [V4+V5+V6] CI gates đa chiều + judge bias + per-line ablation
13. [P4+P5] Cost circuit breaker + identity propagation
14. [R6] Formal plan verify (Z3/acyclicity) — optional

### Phase 3 — LOW priority (nice-to-have)
15. [R7+R8+R9+R10] Durable approvals, fresh WM, fan-out cap, open runtime
16. [W5+W6+W7] Context 4-strategies, decision tree, dynamic workflow gen
17. [V7+V8] Replay infra + canary auto-rollback
18. [S2+S4+S5] Signed agent cards, AAIF governance, multi-binding
19. [P6+P7+P8] Eval-less guard, schema drift, tool description quality

---

## 3. Notes cho session sau

- **Không rebuild từ zero**: AHD đã có 49 hooks + governance. Hầu hết recommendation = enhance primitives.
- **Anti-duplicate**: mỗi implement ticket phải reference BUILD file tương ứng (đã có research).
- **Governance**: mỗi implement plan phải qua `docs/plans/<slug>/IMPLEMENTATION_PLAN.md` + exec report (theo WORKSPACE_GOVERNANCE.md).
- **MCP gap (P1)** + **Governance Decay (T4 A1)** là 2 HIGH-most urgent (security + correctness under compaction).
- **Benchmark cạnh tranh**: sau implement V1-V3, chạy SWE-bench Pro + private golden set để chứng minh AHD cạnh tranh được.

---

*End of BACKLOG | 2026-08-27 | 48 recommendations, 19 phased tickets | Confidence: High*
