# BUILD: Multi-Provider Gateway & Model Routing (T8)

> **RESEARCH BỔ SUNG** (Iteration 3-4) — Build solution cho đa AI provider + router.
> Định hướng user: dùng được với NHIỀU AI provider + nhiều model (kể cả agent kém thông minh).
> Ngày: 2026-08-27. English + Vietnamese. Tập trung *cách build*, không list-general.

---

## 1. Khái niệm phân biệt: AI Gateway vs LLM Router

- **LLM router** = 1 feature chọn model/provider theo price, latency, throughput, availability. [fact]
- **AI gateway** = thêm auth, observability, rate limits, caching, policy, billing quanh route. `LiteLLM`, `Portkey`, `OpenRouter`, `Vercel AI Gateway`, `Envoy AI Gateway 1.0` overlap vì production muốn cả 2. [fact]

**Kết luận kiến trúc**: build **gateway+router một lớp** — OpenAI-compatible endpoint duy nhất, đa provider.

---

## 2. Đề xuất kiến trúc: LiteLLM làm nền + nghiên cứu để quyết

### 2.1 LiteLLM (self-host) — nền tảng build đa provider

- **Proxy tự-host**: 1 OpenAI-compatible endpoint → 100+ providers, giữ API key trong mạng, không third-party, không margin. [fact]
- **6 routing strategies**: weighted pick, latency-based, rate-limit-aware, least-busy, lowest-cost, custom Python. `simple-shuffle` default recommended. [fact]
- **Failover chain**: `fallbacks: [{"gpt-5.5": ["claude-opus-4.8"]}, ...]`, `num_retries`, `request_timeout`, `cooldown_time`. [fact]
- **Context-window fallback** ⭐: nếu prompt vượt context model primary (256K) → tự route sang Gemini 1M. [fact]
- **Cost tracking**: log spend per request, aggregate theo model/user/team; virtual keys + team budgets. [fact]
- **Cooldown/retry**: Redis theo dõi cooldown server, tpm/rpm limits. [fact]
- Hiệu năng: ~2ms median overhead (4-instance), LiteLLM-Router handle ~2500 req/s @38ms p50 trên test config. [fact]

### 2.2 OpenRouter (hosted) — defense-in-depth layer

- **`models` array = prioritized fallback chain** (try current → next khi 429/503/refusal), app code không đổi. [fact]
- **`provider` block**: sort theo latency, order, data-policy, quantization, ZDR, price filters. "Ship routing policy change = edit request body". [fact]
- **Auto Router** (wisdom of market): classify prompt, rank candidates theo aggregate community spend trailing 7-day, deprioritize providers vừa outage 30s. [fact]
- Chi phí: pass-through provider price, +5.5% platform fee. SPOF ở OpenRouter. [fact]

### 2.3 Portkey (enterprise) — guardrails

- 1600+ models, **nested fallback strategies + weighted load balancing**, **semantic caching**, observability, guardrails. [fact]

### 2.4 Quyết định (decision framework — MỚI)

| Tình huống | Chọn |
|-----------|------|
| Data không rời mạng, compliance | LiteLLM self-host |
| Prototype, cần model breadth nhanh | OpenRouter |
| Defense-in-depth | **LiteLLM local + OpenRouter upstream** ⭐ |
| Value cao, đa team | Portkey |

**Quy luật kinh tế** ⭐: Divide infra cost / 5.5% fee. ~$200/tháng infra → LiteLLM rẻ hơn khi spend ≥ ~$3,600/tháng. **Caching + provider selection cắt inference cost 40–90%** — lý do mạnh nhất để có gateway. [fact]

> **Khuyến nghị AHD**: build architecture **"LiteLLM-type layer"** (thực chất tích hợp liteLLM Python SDK làm core router) với plugin interface để swap OpenRouter/Portkey. Cho phép đa provider: Claude, Gemini, DeepSeek, Kimi K2.7 (free), GLM, local vLLM — phù hợp user định hướng "nhiều AI provider".

---

## 3. Cost optimization patterns (MỚI)

| # | Pattern | Mechanism | Impact |
|---|---------|-----------|--------|
| C1 | **Model routing theo task** | cheap model cho classifier/router (≈300 tok), premium cho planner/synthesis | giảm token cost lớn trên hot path |
| C2 | **Semantic caching** | Portkey/OpenRouter — không trả tiền 2 lần cho cùng prompt | 40-90% high-volume |
| C3 | **Context-window fallback** | gemini 1M cho prompt vượt primary | tránh truncate |
| C4 | **Per-call-site budget attribution** | agent-harness bucket classifier/router/planner/synthesizer riêng | visibility + alert |
| C5 | **Cost-ladder routing** | LiteLLM auto router benchmark: complexity → cheapest tier đủ quality | 3-tier Gemini ladder |

---

## 4. Nhúng vào AHD (synthesis ⭐)

AHD hiện có M-tier+ routing mặc định (`/lightning`, `/glm`, `/kimi`, `/full-power`). Gợi ý nâng cấp:

| # | Feature MỚI | Build approach |
|---|-------------|----------------|
| M1 | **Per-call-site budget** | tag model theo task role (plan vs exec vs review) rote ep |
| M2 | **Fallback chain** | Nếu executor model fail (endpoint lỗi) → fallback model provider |
| M3 | **Context-window aware selection** | Tự chọn provider có window đủ cho prompt dài |
| M4 | **Cost tracking + budget alert** | Log spend mỗi slot → cảnh báo vượt budget |
| M5 | **Cache layer** | Semantic cache cho research/prompts lặp lại |

---

## Sources (MỚI)

- docs.litellm.ai/docs/routing-load-balancing, docs.litellm.ai/docs/routing, openrouter.ai/blog/insights/openrouter-vs-litellm
- open-techstack.com/blog/multi-provider-ai-gateways-fallback-routing, developersdigest.tech/blog/llm-router-comparison-2026
- merge.dev/blog/litellm-vs-openrouter, mudassirworks.hashnode.dev/litellm-vs-openrouter, markaicode.com/integrate/litellm-with-openrouter

---

*Iteration 3-4 output | 2026-08-27 | Multi-provider build (MỚI) | Confidence: High*
