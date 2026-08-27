# RESEARCH COVERAGE LOG — Log theo dõi nghiên cứu (chống duplicate)

> Log này theo dõi **chủ đề nào đã nghiên cứu, khi nào, nguồn nào** để mỗi iteration
> chi nghiên cứu **phần MỚI** — không duplicate nội dung đã có.
>
> Dùng chung cho cả bản EN và VI. Mỗi iteration phải đọc log này TRƯỚC khi research.

---

## Cách dùng (rules)

1. **Trước mỗi research**: đọc log này + grep chủ đề để biết gì đã cover.
2. **Chỉ research chủ đề mới** chưa có trong `Covered Topics` bên dưới.
3. **Sau mỗi research**: cập nhật log — thêm topic + file + ngày + nguồn.
4. **Anti-duplicate**: nếu topic đã `[covered]` → không research lại; nghiên cứu góc MỚI.

---

## Covered Topics

### Iteration 0 (2026-08-27) — Baseline research (đã xong trong session trước)

| # | Chủ đề (Topic) | Góc đã cover | File chứa | Nguồn | Status |
|---|----------------|--------------|-----------|-------|--------|
| T1 | Harness frameworks comparison | Claude Code, Devin, CC Harness, OpenCode, Cline, Cursor, OpenHands, Aider | `AI_AGENT_HARNESS_LANDSCAPE_2026.md` | 17+ sources | `[covered]` |
| T2 | Pain points AI coding | Verification load, over-editing, hallucination, testing bottleneck, security, judge bias, context rot, trust | `AI_CODING_PAIN_POINTS_2026.md` | 45+ sources | `[covered]` |
| T3 | AI agent solutions | Self-healing, adversarial review, CAT, TDD, memory, MCP, governance, DAG, best-of-N, routing, prompt-opt, SolidCoder | `AI_AGENT_SOLUTIONS_2026.md` | 19+ sources | `[covered]` |

### Iteration 2 (2026-08-27) — Harness Engineering + Context Rot + Benchmarks + MCP Security (ĐÃ XONG)

| # | Chủ đề (Topic) | Góc MỚI đã cover | File chứa | Nguồn | Status |
|---|----------------|------------------|-----------|-------|--------|
| T4 | Harness engineering discipline | Guides vs Sensors (Böckeler), OpenAI/Anthropic harness patterns, NLAH/IHR, Context Rot papers (Chroma, GAIR premature termination, ConstraintRot governance decay, ARC, ACM), SWE-bench 2026 leaderboard, MCP security crisis (97M downloads, 53% hardcoded creds, 43% destructive, CVEs) | `TECH_OVERVIEW_2026.md` (+ `en/`) | Chroma, arXiv, OpenAI, SwanBrock, Thoughtworks, BenchLM, SWE-Bench, MCP Institute | `[covered]` |

### Iteration 3 (upcoming) — ⚡ CHIẾN LƯỢC CỐT LÕI

> User định hướng: build harness/framework cạnh tranh giá trị với Claude (Fable/Opus/Sonnet), Codex, GPT-5.6 (Sol) — dùng được với NHIỀU AI provider + nhiều model (kể cả agent kém thông minh, context nhỏ), chạy phiên dài/phức tạp, logic nghiệp vụ phức tạp, phối hợp đồng thời, theo quy trình. Mỗi topic tập trung build-system/solution (không duplicate 3 file baseline).

| # | Chủ đề (Topic) | Góc MỚI sẽ cover (build solutions) | File dự kiến | Nguồn | Status |
|---|----------------|--------------------------------------|--------------|-------|--------|
| T7 | Framework orchestration đa agent | DAG/task-graph scheduling, planner-executor split, subagent isolation, parallel fan-out, state machines, work-stealing pool, retry/backoff, kill-switch | `BUILD_ORCHESTRATION_2026.md` | open-multi-agent, Lattice, agent-harness, A.DOT, Hydra, LangGraph, HLD Handbook | `[covered]` |
| T8 | Đa AI provider + router | Provider abstraction, model router (cost/latency/quality), fallback chain, multi-model ensemble, per-task model selection, structured output normalization | `BUILD_MULTI_PROVIDER_2026.md` | LiteLLM, OpenRouter, Portkey, Vercel AI Gateway, Envoy AI Gateway | `[covered]` |
| T9 | Context nhỏ + agent kém thông minh | Prompt compression, chain-of-thought externalization, retrieval augmentation, chunking, external memory, subagent delegation, "shrink-wrap" state | `BUILD_SMALL_CONTEXT_2026.md` | Externalization arXiv, Harness-1 (20B), Eight Pillars, agent-harness, Anthropic context engineering | `[covered]` |
| T10 | Verification + compete | Eval harness, regression of agent tests, mutation testing, golden-recipe replay, score tracking vs Claude/Codex/GPT, benchmark gates | `BUILD_VERIFY_COMPETE_2026.md` | SWE-bench Pro, AgentEval, swe-agent, BenchLM, agenticarchitect/multi-eval-harness | `[covered]` |
| T11 | Phiên dài/phức tạp + business logic | Long-running session state, checkpoint/resume, durable execution, saga/compensation, business-rule engine, deterministic replay | `BUILD_LONG_SESSION_2026.md` | Temporal (durable workflow), DBOS, Restate, Inngest, Cloudflare Workflows | `[covered]` |

### Iteration 3b (2026-08-27) — ⚠️ REGISTER: 3 subagent reports (session trước, untracked)

> ⚠️ `docs/research/orchestration_patterns.md`, `planning_best_practices.md`, `qc_enforcement_mechanisms.md`
> là output subagent (session trước) chưa được log — nội dung tốt, KHÔNG tái research các chủ đề này (anti-duplicate).
> Lưu ý governance: các file này thiếu suffix ngày + chưa tách EN/VI — giữ nguyên, chỉ REGISTER trong log.

| Chủ đề đã cover (subagent) | File | Góc chính |
|----------------------------|------|-----------|
| Orchestration patterns 2026 | `orchestration_patterns.md` | DAG parallel (LLMCompiler 1.8–3.7×), event bus, blackboard scoped regions, event sourcing replay, MCP tool layer, bounded batch, sliding window work-stealing, reflexion, PIVOT, LATS (MCTS), adversarial consensus, subgoal eval, SPC quality drift, AEE verification, ABC behavioral contracts, hypervisor execution rings, plan adherence SLI |
| Planning best practices | `planning_best_practices.md` | Devin/Cursor/Copilot/OpenAI planning phase |
| QC & enforcement mechanisms | `qc_enforcement_mechanisms.md` | Advanced QC + execution enforcement 2025-2026 |

### Iteration 4 (upcoming)

| # | Chủ đề (Topic) | Góc MỚI sẽ cover | File dự kiến | Nguồn | Status |
|---|----------------|------------------|--------------|-------|--------|
| T12 | Emerging tech agents 2026 | A2A protocol, agent SDK mới, standards evolution, agent taxonomies | TBD | TBD | `[pending]` |
| T13 | Pain points - production góc mới | Production deployment failures, RAG limitations, MCP real-world adoption | TBD | TBD | `[pending]` |
| T14 | Multi-agent communication | Message schemas, protocol, handoff, shared blackboard, tool-call contracts | TBD | TBD | `[pending]` |

---

## Chống duplicate — checklist TRƯỚC mỗi iteration

- [ ] Đọc log này + grep `[covered]` cho chủ đề định research
- [ ] Nếu chủ đề `[covered]` → chọn góc MỚI hoặc bỏ
- [ ] Chỉ research khi topic/perspective CHƯA có
- [ ] Sau research → cập nhật log sang `[covered]` + đủ metadata

---

*Cập nhật: 2026-08-27 | Vòng (iteration): 2 — đang chạy T7-T11 (BUILD STRATEGY)*
