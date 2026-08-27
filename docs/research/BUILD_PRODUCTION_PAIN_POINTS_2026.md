# BUILD: Production Pain Points & Real-World Failures (T13)

> **RESEARCH BỔ SUNG** (Iteration 5) — Build chống **production failures** của agent/MCP/RAG.
> Định hướng user: chạy phiên dài/phức tạp, production-grade, cạnh tranh harness Claude/Codex/GPT.
> Ngày: 2026-08-27. English + Vietnamese. KHÔNG duplicate T2/T3 (pain points baseline).

---

## 1. Con số nghiệt ngã (MỚI, chưa có ở T2)

- **88% AI agent pilots NEVER reach production** (Forrester + Anaconda 2026). [fact]
- **Gartner**: 40% agentic AI projects CANCELLED by 2027 do escalating costs / unclear business value / inadequate risk controls. [fact]
- **12% succeed** — share 4 attributes: pre-deployment infra investment, governance docs trước deploy, baseline metrics trước pilots, dedicated business ownership. 3/4 là **product design decisions**. [fact]
- MCP: 110M downloads, 78% enterprises có MCP in prod — nhưng **52% MCP servers abandoned**, median completes chỉ **71% tasks** (top 10% = 95%). Gap = vague tool descriptions + missing observability. [fact]
- Stress test 100 servers/12,000 trials: failures = schema mismatch 38%, timeouts 24%, auth/quota 19%, upstream API 12%, MCP bugs 7%. [fact]

> **Insight cốt lõi**: "The protocol works. The stack is nearly complete. Yet 88% never reach production. **Đó là product design problem, không phải model/orchestration/protocol problem.**" (The Gradient) [fact]

---

## 2. MCP production gaps (3 missing primitives) ⭐

Paper arxiv 2603.13417 — MCP thiếu 3 protocol-level primitives cho production scale: [fact]
1. **Identity propagation** — user/tenant data leakage do thiếu identity; 10 agents share 1 credential → không thể link tool call tới user (compliance fail HIPAA/SOC2/GDPR). [fact]
2. **Adaptive timeout budgeting (ATBA)** — sequential tool chains exhaust turn budgets. [fact]
3. **Structured error semantics (SERF)** — unrecoverable turns do unstructured tool errors. [fact]
→ Proposals: CABP (Context-Aware Broker Protocol, 6-stage broker pipeline), ATBA, SERF. Production readiness checklist 5 dims: server contracts, user context, timeouts, errors, observability. [fact]

---

## 3. Post-mortems thực tế (MỚI)

### 3.1 Miami fintech MCP rollout (2:47 AM incident) ⭐
- Risk-scoring upstream timeout → MCP server return **stale cached context** (optimistic error handling) thay vì propagate clear error. LLM flag 214 transactions incorrectly, 94 min silent operation. [fact]
- Root causes: no circuit breaker trên client; no completeness/confidence field trong MCP tool responses; timeout copied từ staging; no canary; cache TTL 15min catastrophic at scale. [fact]
- Fixes: explicit health checks; **add completeness/confidence field**; client-side circuit breaker checks context completeness before calling LLM; canary 5% 48h; environment-specific timeout. [fact]
- Lesson: "Treat MCP as **distributed systems problem**, not AI problem." [fact]

### 3.2 RAG + MCP agent (80 DAU, 5 things broke) ⭐
- **Vector-only trap**: "Tier-1 SLA streaming" vs "Tier-2 SLA batch" semantically close → wrong chunk. Fix: **hybrid (BM25+vector) + cross-encoder rerank top-20**. [fact]
- **null→success**: MCP tool timeout return `null`, model interpret as "no issues" → told user everything fine while job dead 90min. Fix: **structured `{ok, error, detail}` responses, never raw null**. [fact]
- **Keyword router brittle**: 12-line `if/elif` died on real users ("hey is prod borked lol" + 600-word Slack). Fix: **small LLM router** (~90% accuracy, 20× cheaper, 3.6× lower latency than frontier routing). [fact]
- **No caching/parallelism**: $300-400/day for 80 users, P50 6s/P95 14s. Fix: embedding cache, tool-result TTL cache, async independent calls, cheap model cho boring hops. [fact]
- **No evals**: embedding upgrade degraded retrieval, noticed 3 days later. Fix: **golden dataset in VCS, deterministic + judge checks, run mọi PR**. [fact]
- Lesson: "Build **eval harness on day zero**, agent on day two." [fact]

### 3.3 Enterprise failure patterns (openempower) ⭐
1. **Runaway loops**: agent error→retry→new error→loop; single runaway $50-500. Guard: step limit (max 15 tool calls), token budget, repetition detection (same tool+params >2x → terminate). [fact]
2. **Tool misuse / hallucinated actions**: financial agent "confirmed" match bằng hallucinate record. Guard: action verification vs source-of-truth trước exec; HITL cho irreversible; strict schema validation. [fact]
3. **Context window exhaust**: perf degrades after 5 steps. Guard: task decomposition có clean context boundaries; external working memory; context budget monitor 80%. [fact]
4. **Cost explosions**: 1 PR review $12 vs avg $0.40. Guard: per-task budget caps, model tiering, circuit breaker (hourly spend >3× rolling avg → pause), cost attribution. [fact]

---

## 4. Amazon Prime Video — progressive tool discovery ⭐

- Comprehensive tool access qua centralized MCP servers **degraded performance** (more tools = more confusion + hallucination). [fact]
- Solution: **progressive discovery** — 1 "find tools" capability at init, load only **3-4 context-appropriate tools per task**. [fact]
- Measured: **405,000 tokens (400 tools) → 1,600–2,500 tokens. 160× reduction.** [fact]
- Block's MCP (12,000 employees): 50-75% time savings — nhưng đến từ **structuring which contexts load by default**, not từ plugging servers. [fact]
> Insight: agent's context window = design surface như mobile screen: limited real estate, high cost of distraction, zero tolerance for irrelevance. [fact]

---

## 5. Recommendations cho AHD ⭐

| # | Pain point | Build vào AHD | Ưu tiên |
|---|------------|---------------|---------|
| P1 | **Silent partial failure** | MCP tools return structured `{ok,error,detail}` + completeness field; client-side circuit breaker | 🔴 HIGH |
| P2 | **Runaway loops** | Step limit + token budget + repetition detection (kill switch) | 🔴 HIGH |
| P3 | **Context exhaust** | Progressive tool discovery (3-4 tools/task), external working memory, context budget monitor | 🔴 HIGH |
| P4 | **Cost explosion** | Per-task budget caps, model tiering, circuit breaker on hourly spend, cost attribution | 🟠 MED |
| P5 | **Identity leakage** | Identity propagation (per-user/tenant credential, không share) | 🟠 MED |
| P6 | **Eval-less deploy** | Golden dataset in VCS, run mọi PR, day-zero eval harness | 🟠 MED |
| P7 | **Schema drift** | Pin MCP schemas, CI validate against live server | 🟡 LOW |
| P8 | **Vague tool descriptions** | Tool names + descriptive schemas (giảm arg hallucination) | 🟡 LOW |

> **AHD advantage**: đã có 49 hooks + governance enforcement → P1/P2/P3/P4 phần lớn đã có primitives (budget, kill-switch). Cần bổ sung **structured-error MCP layer + progressive discovery + identity propagation**.

---

## Sources (MỚI)

- commonplace.workforcefutures.net (arxiv 2603.13417 MCP production gaps), techmeetups.io (Miami MCP post-mortem), towardsai.net (RAG+MCP 5 failures)
- openempower.com (enterprise failure patterns), n1n.ai (MCP production playbook), thegradient.com (MCP design problem, 88% fail), idir-mellaz.fr (RAG+MCP), aiagentsfirst.com (MCP builder playbook)

---

*Iteration 5 output | 2026-08-27 | Production pain points build (MỚI) | Confidence: High*
