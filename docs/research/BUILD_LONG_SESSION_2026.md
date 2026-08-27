# BUILD: Durable Execution — Phiên dài & Business Logic (T11)

> **RESEARCH BỔ SUNG** (Iteration 4) — Build giải pháp **phiên dài/phức tạp + logic nghiệp vụ phức tạp**.
> Định hướng user: chạy phiên dài, phiên phức tạp, logic business phức tạp — cạnh tranh Claude/Codex/GPT.
> Ngày: 2026-08-27. English + Vietnamese. KHÔNG duplicate T3/T4/T7.

---

## 1. Tại sao cần durable execution

Khác request-response: agent dài ngày tiêu token đắt, gọi tool external, chờ human, delegate, chạy giờ/ngày. Nếu process restart ở step 8/10 mà retry từ đầu → **duplicate side effects, phí token, mất state hữu ích**. [fact]

> **"Nếu câu trả lời là 'nó cần bắt đầu lại', bạn không có agent, bạn có slot machine."** [fact]
> Durable execution: workflow **resume từ step cuối đã hoàn thành**, không từ đầu — LLM call đã trả không phải trả 2 lần, thẻ không bị charge 2 lần.

**Market validation 2026**: Temporal raise **$300M @ $5B valuation** (Feb 2026), **9.1 trillion lifetime actions** (1.86T từ AI-native). OpenAI dùng Temporal cho **Codex**. Stripe/Netflix/Snap dùng. LangGraph/Pydantic AI/OpenAI Agents SDK đưa durable execution thành first-class. [fact]

---

## 2. Bản đồ engines 2026

| Engine | Model | Kiến trúc | Footprint | Best for |
|--------|-------|-----------|-----------|----------|
| **Temporal** | Deterministic workflow replay từ event history | Multi-service cluster (Cassandra/Postgres) + workers | High | Scale, multi-service, chronic |
| **Restate** | Journal-based (mỗi step journaled trước khi proceed) | Single binary, laptop→multi-region | Mid | Edge/serverless |
| **DBOS Transact** | Library, checkpoint vào Postgres | @DBOS.workflow / @DBOS.step | Low (zero new infra) | Team đã dùng Postgres |
| **Inngest** | Step-based retries (step.run/invoke/sendEvent) | Managed | Minimal | Serverless/event-driven |
| **Cloudflare Workflows** | step.do() LLM/tool checkpoint | Edge | Minimal | Edge, I/O-bound |
| **Azure Durable Task** | Checkpoint state transitions | Managed | — | Azure stack |
| **LangGraph 1.0** | Checkpointer PostgresSaver per super-step | Library | Low | Graph-shaped agents |

**Cả 3 core mechanism**: **journal/replay**, **db checkpointing**, **step-based retries**. [fact]

**Bagian quan trọng (DBOS vs Temporal)** — không hỏi "cái nào production-ready" (cả 2 đều), mà hỏi **"bạn đang provision chống failure nào"**:
- Sợ *repay step đắt/không đảo ngược vì reboot* → DBOS (không thêm operational dep).
- Cần *isolation + scale 1 DB không cho* → Temporal. [fact]
- Determinism constraint là giá của replay: workflow code phải deterministic (no direct I/O, no wall-clock, no unseeded randomness) — non-determinism → activity/step. **Footgun phổ biến nhất.** [fact]

---

## 3. Các pattern durable cho agent ⭐

### 3.1 Workflow/Activity split (cốt lõi)
- **Workflow** = coordination logic thuần: conditionals, loops, parallel fan-out, error handling. Phải deterministic.
- **Activity/Step** = mọi side effect: LLM inference, tool call, API, DB. Có retry policy riêng, at-least-once.
- **Non-determinism rule là universal**: LLM calls inherent non-deterministic → phải wrap trong activity, journaled lần đầu, KHÔNG re-run khi replay. Footgun #1. [fact]

### 3.2 Replay scoped đúng — "replay orchestration, resume from recorded cognition"
Durable history phải store đủ **non-deterministic decisions** của agent để recovery không bắt model tái tạo lại: model request metadata, model response, selected tool call, tool args, tool result, human approval decision. [fact] ⭐

### 3.3 Idempotency (bắt buộc)
- **Workflow ID**: Temporal/DBOS return result cũ nếu cùng ID đã chạy (idempotent execution).
- **At-least-once chỉ an toàn cho operation idempotent** (read, cache); non-idempotent (charge card, one-shot SMS, POST) → disable blind retry hoặc idempotency token accepted bên ngoài. [fact]
- **Tool layer trả receipts** (request idempotency keys → same result cho duplicate). ⭐

### 3.4 Saga compensation
- Orchestration saga (central coordinator) vs Choreography saga (events). [fact]
- AI challenge: compensate AI-generated side effects rất khó — cancel flight được, nhưng **không unsend email / unpublish indexed article** được → **human review gate cho irreversible actions**, không auto rollback. [fact]
- Compensating transactions phải idempotent (sẽ bị retry). [fact]

### 3.5 Signals/Query (durable HITL waiting)
- Workflow chạy tới WaitForSignal → suspend; worker terminated được. Khi human approve / webhook / API respond webslow → gửi typed signal → resume từ suspend point. Dormant hàng ngày/hàng tuần, không giữ memory/thread. [fact] ⭐ (bài Codex/enterprise)

### 3.6 Continue-as-New (chống lịch sử phình vô hạn)
- Khi event history quá lớn → close segment, start mới với **compacted durable state**: current goal, pending waits, open tool receipts, user-visible status, links tới archived history. [fact] ⭐
- DBOS khuyên: store long-lived objects trong DB + interact qua shorter-lived workflows; dùng **partitioned durable queues** cho concurrency/ordering.

### 3.7 DBOS extra (đáng build vào AHD)
- **Durable queues**: global concurrency limits, per-worker, rate limiting, partitioned per-tenant, priority, dedup, debouncing. [fact]
- **Transactions**: DB ops co-commit với checkpoint (một transaction).
- **Fork workflow từ step cụ thể** để recovery 1 phần. [fact]

---

## 4. Best practices tổng hợp ⭐

| # | Principle | Detail |
|---|-----------|--------|
| D1 | **Wrap LLM call như durable step, không inline** | chống re-execution đắt + xử non-determinism |
| D2 | **Named steps + completion signals** | lifecycle records, resumable waits |
| D3 | **Idempotency keys + receipts** | tool layer trả receipt, not just NL |
| D4 | **Compensate design upfront** | cho mọi side effect; irreversible → human gate |
| D5 | **Continue-as-New + compact state** | chống history phình |
| D6 | **Explicit wait states** | suspend HITL/timer đúng primitive |
| D7 | **Adaptive durability (next frontier)** | auto quyết step nào full persist theo cost/reversibility/criticality |

**Outer control workflow + child sub-workflows** (DBOS): tăng observability, tăng tốc recovery/replay. [fact]

---

## 5. Recommendations cho AHD ⭐

AHD hiện chạy 3-phase trong session — thiếu durable layer. Gợi ý:

| # | Build | Approach |
|---|-------|----------|
| L1 | **Durable step boundaries** | Chuyển phases thành workflow/activity; checkpoint state sau mỗi phase | 🔴 HIGH |
| L2 | **Resume from checkpoint** | Nếu process chết → resume phase cuối, không redo paid LLM calls | 🔴 HIGH |
| L3 | **Idempotency + receipts** | Tool layer trả exit code/receipt; idempotency key | 🟠 MED |
| L4 | **Saga cho irreversible** | Define compensation/ human gate trước khi ship | 🟠 MED |
| L5 | **Durable waiting** | Approve gate + external webhook resume (analog Temporal signals) | 🟠 MED |
| L6 | **Compacted durable state** | current goal + pending waits + receipts, not full history | 🟠 MED |

> **Pick** DBOS-style (library, Postgres) nếu AHD đã có DB; Temporal-style nếu cần cluster scale. Với harness local, DBOS/checkpoint approach là đủ + nhẹ.

---

## Sources (MỚI)

- dreaming.press/posts/dbos-vs-temporal-durable-agents, docs.dbos.dev (migrating-from-temporal), zylos.ai/research (durable execution agent runtimes), alatirok.com (Temporal vs Restate vs DBOS)
- belsoftsolutions.com (reliable AI workflows), tiarebalbi.com (DBOS vs Temporal), docs.dbos.dev

---

*Iteration 4 output | 2026-08-27 | Durable execution build (MỚI) | Confidence: High*
