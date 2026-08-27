# BUILD: Multi-Agent Orchestration Framework (T7)

> **RESEARCH BỔ SUNG** (Iteration 3) — Build solution cho multi-agent orchestration.
> Định hướng user: build harness/framework cạnh tranh Claude/Codex/GPT, đa provider.
> Ngày: 2026-08-27. English + Vietnamese. **KHÔNG duplicate** `AI_AGENT_SOLUTIONS_2026.md` (T3) — file này tập trung *cách build*, không list-general giải pháp.

---

## 1. Hai structural primitives (điểm khởi đầu)

Anthropic guidance (HLD Handbook): **orchestrator-worker** + **handoff** là 2 primitive gốc.
Mọi pattern khác (debate, evaluator-optimizer, supervisor, hierarchical) = composition của 2 cái này. [fact]

- **Orchestrator-worker**: central LLM decompose → dispatch workers (thường parallel) → synthesize. Dominant pattern cho research, analysis, code-gen.
- **Handoff (peer-to-peer)**: transfer control kèm payload. OpenAI Agents SDK biên dịch handoff thành **synthetic tools** — model chọn giữa tool call và handoff trên cùng bề mặt quyết định. [fact]

**Nguyên tắc engineering cốt lõi (⚠️ MỚI, quan trọng):**
> **Decompose by CONTEXT BOUNDARY, not by ROLE TYPE.** [fact]
> Splitting theo role (planner/implementer/tester/reviewer) = "telephone game" — handoff mất fidelity từng hop.
> Splitting theo context boundary (independent research paths, clean API contracts, blackbox verifiers) = mỗi agent làm việc autonomously, minimal coordination.

**Chi phí (⚠️ đáng chú ý):** Anthropic đo standalone agent ≈ **4× tokens** của chat; multi-agent ≈ **15×**. Single agent → multi-agent ≈ thêm **~4×**. [fact]
=> **Rule: bắt đầu single richer agent; chỉ thêm multi-agent khi đặt tên được constraint cụ thể nó giảm.** [fact]

---

## 2. Bản đồ framework 2026 (so sánh build)

| Framework | Core abstraction | State model | HITL | Điểm mạnh |
|-----------|------------------|-------------|------|-----------|
| **LangGraph** (1.x, Oct 2025) | DAG + typed state | TypedDict + reducers | `interrupt()` + checkpointer | Durable, observable, long-running, crash recovery. Production: Klarna, Elastic |
| **OpenAI Agents SDK** (0.17.x, mid-2026) | Agent + handoff tools | Sessions (SQLite/Postgres/Redis/Mongo) | thêm thủ công | Min ceremony, provider-agnostic 100+ LLM |
| **MAF** (supersedes AutoGen) | Actor + GroupChat | Shared transcript | Termination conditions | Debate, code-interpreter |
| **CrewAI** | Role + process | Shared memory | callbacks | Rapid prototype |

**State models chia 3 loại:**
1. **Shared state / blackboard** (LangGraph `TypedDict` + reduce) — pro: đơn giản; con: context pressure tăng theo agent, race condition parallel writes cần **associative reducers**.
2. **Message passing (actor)** (AutoGen/MAF) — pro: scale cross-process; con: khó suy luận ordering/delivery.
3. **Handoff with payload** (Agents SDK `input_filter`) — pro: isolation sạch; con: mất info nếu filter aggressive. [fact]

---

## 3. Các kiến trúc build MỚI (2026) — học được

### 3.1 open-multi-agent (TypeScript) — "Describe goal, not graph"

- **Dynamic orchestrator**: coordinator **build task DAG at runtime** từ goal, deterministic scheduler execute, full data replayable. Không hand-wired graph. [fact]
- **Durable approvals**: preview/approve/suspend plans, tool calls; freeze approved plan để replay. [fact]
- **Reliability**: resume từ checkpoints, append-only plan repair ở task outcome barriers, retries/timeouts/loop-detection, **token & cost budgets**. [fact]
- **Eval**: cùng records feed versioned EvalSets, offline reports, CI gates, production sampling. [fact]
- **Open runtime**: Process + ACP backends đặt **Claude Code, Gemini CLI, Codex trên cùng task DAG** với LLM agents (hỗn hợp cloud + local). Fallback parser cho local models phát tool calls dạng text. [fact] ⭐
- **3 modes**: `runTeam()` (goal→DAG), `runAgent()` (single), `runTasks()` (explicit pipeline). [fact]

### 3.2 Lattice (Python) — "Formal safety proofs"

- **Contextual bandit router** (epsilon-greedy, UCB, Thompson) học optimal agent assignment từ execution feedback + MLP reward predictor. [fact]
- **Hybrid ReAct + Plan-and-Solve** planner. [fact]
- **Z3 verifier** chứng minh plan an toàn TRƯỚC khi execute: DAG acyclicity, budget feasibility, capability matching, custom policies. [fact] ⭐
- DAG executor topological, parallel, retry, checkpointing; **Scoped Memory** (namespace inheritance, TTL, semantic search, LRU, Redis); cost attribution per-agent/model qua LiteLLM. [fact]

### 3.3 agent-harness (BYO-LLM) — "Streaming-first, budgets"

- **Hybrid DAG**: complexity classifier (1 cheap LLM call) → `complex` thì decompose DAG, `simple` thì routed. Unknown → default `simple`. [fact]
- **Per-call-site attribution**: classifier/router (≈300 tokens decision) dùng **cheap model**, planner/synthesizer (structured DAG + final answer) dùng **premium model** — budget bucketed tách riêng. [fact] ⭐ KEY для cost
- **Sub-agent-as-tool**: main ReAct loop quyết định delegate per-step (exploratory) với **fresh WorkingMemory** mỗi delegation; cross-delegation continuity qua long-term memory, không carry-over WM. [fact]
- **Sandboxed tool execution**: `ExecutorBridge` — allowlist, env scrubbing, Docker network/fs isolation, timeout. [fact]
- **Plan mode /plan on**: gate mỗi turn sau approval; **approve intent, not args** — planner trả `args: null` khi giá trị chỉ biết runtime (tránh fabricate placeholder JSON). [fact] ⭐
- **Both first-class**: orchestrator plan DAG cao-level, trong task dùng sub-agent tools cho dynamic decomposition mịn hơn. [fact]

### 3.4 A.DOT (hybrid data lakes) — "Evidence + provenance"

- Compile NL query → DAG plan 1 LLM pass, validated structural + semantic (DataOps). [fact]
- **Variable slim**: chỉ propagate necessary keys (IDs) giữa nodes — tránh vượt context/memory. [fact] ⭐
- **Paraphrase-aware plan caching** — reuse plan cho semantically-equivalent query. [fact]
- Explicit data provenance → lineage, verification, compliance audit. [fact]

### 3.5 Hydra — "Dynamic agent generation"

- **Brain** sinh **agent specifications on-the-fly** (role/tool/constraint/persona theo task) — khác CrewAI/AutoGen (pre-defined). [fact]
- Hybrid DAG, real-time streaming events (pipeline/agent/tool/quality events), retry exponential-backoff, **LLM quality gate** (score 1-10 + re-dispatch). [fact]
- **Context flow sanitize**: upstream output inject sanitized; token budgeting truncate long output với reference vào shared memory. [fact]
- HITL confirmation modal (risk badges, queue, auto-timeout, timeline log). [fact]

---

## 4. Pattern catalog — Orchestrator-Workers (AgentPatterns.Org)

- **Orchestrator-workers** (data-dependent decomposition): orchestrator decides sub-tasks at runtime. Distinct từ **supervisor** (routes work tới fixed specialist agents). [fact]
- Generalizes: Subagent Isolation, Lead Researcher, Hierarchical Agents, Agent-as-Tool Embedding, RL-Trained Conductor, **Planner-Generator-Evaluator Harness** (3 role-isolated agents, Evaluator grading WITHOUT seeing Generator trace). [fact]
- **Planner-Generator-Evaluator Harness** ⭐: decompose long job → Planner (feature list), Generator (1 chunk/fresh context), Evaluator (rubric, not seeing trace) — anti-memory-contamination.

### Patterns to combine (⭐ cho AHD):
- **Planner-Generator-Evaluator**: isolation để evaluator unbiased.
- **RL-Trained Conductor** (MỚI): train meta-model nhỏ dispatch work trên pool frontier LLM workers, recursive self-invoke, học topology end-to-end.

---

## 5. Recommendations cho harness AHD (synthesis ⭐)

| # | Pattern MỚI học | Áp dụng vào AHD | Ưu tiên |
|---|-----------------|-----------------|---------|
| R1 | **Decompose by context boundary** | AHD `plan_enforce` + DAG split theo clean contracts, không role-centric telephone game | 🔴 HIGH |
| R2 | **Approve intent, not args** | AHD `approval_gate.py` nên để `args: null` → resolve runtime | 🔴 HIGH |
| R3 | **cheap classifier/router + premium planner** | Router dùng model nhỏ (≈300 tok) — tiết kiệm token lớn | 🔴 HIGH |
| R4 | **Planner-Generator-Evaluator isolation** | Evaluator/adversarial review không thấy trace generator (chống bias) | 🟠 MED |
| R5 | **Variable slim (provenance)** | Chỉ propagate necessary IDs giữa tasks | 🟠 MED |
| R6 | **Z3/formal verify plan trước execute** | Verify DAG acyclicity + budget trước khi chạy | 🟠 MED |
| R7 | **Durable approvals + checkpoint resume** | Freeze approved plan, resume từ checkpoint | 🟠 MED |
| R8 | **Fresh WorkingMemory per sub-agent** | Isolate context từng subagent, continuity qua long-term memory | 🟠 MED |
| R9 | **Context-boundary fan-out cap + token/total budget** | Runtime cấp fan-out, enforce total token | 🟡 LOW |
| R10 | **Open runtime** (Claude Code/Gemini CLI/Codex) | AHD đặt nhiều CLI harness cùng DAG | 🟡 LOW |

**Chi phí phải chấp nhận**: multi-agent ≈ 15× tokens — build phải chọn đúng nơi thêm agent (chỉ khi constraint named).

---

## Sources (MỚI)

- github.com/JackChen-me/open-multi-agent, github.com/JiwaniZakir/lattice, github.com/ramannanda9/agent-harness, github.com/Metalheadache/Hydra
- arxiv.org/html/2603.14229 (A.DOT), hld.handbook.academy (Multi-Agent Orchestration HLD), agentpatternscatalog.org/patterns/orchestrator-workers/
- anthropic (build effective agents): context-boundary principle, ~4×/~15× token cost

---

*Iteration 3 output | 2026-08-27 | Build orchestration (MỚI) | Confidence: High*
