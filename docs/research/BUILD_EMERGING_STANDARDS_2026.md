# BUILD: Emerging Agent Standards 2026 — A2A, AAIF, MCP Evolution (T12)

> **RESEARCH BỔ SUNG** (Iteration 5) — Build trên nền **trends chuẩn hóa** 2026 cho multi-agent harness.
> Định hướng user: đa AI provider + multi-agent interoperable + không vendor lock-in.
> Ngày: 2026-08-27. English + Vietnamese. KHÔNG duplicate T3/T4/T8.

---

## 1. Three-layer agentic stack (reference architecture 2026) ⭐

Với A2A join AAIF (Aug 20, 2026), stack chính thức: [fact]

```
Layer 1: WebMCP       — structured web access cho agents
Layer 2: MCP          — agent-to-tool (DB, APIs, services)  [vertical]
Layer 3: A2A          — agent-to-agent (task delegation, coordination) [horizontal]
```

- **MCP ≠ A2A — chúng bổ sung, không cạnh tranh.** MCP = agent-to-tool (stateless, transactional, fast). A2A = agent-to-agent (delegation, discovery, identity, long-running state across orgs). [fact]
- Workflow mẫu: orchestrator dùng **A2A** delegate data-validation task cho specialist; specialist dùng **MCP** pull records từ Snowflake; result về qua A2A. [fact]
- **Đừng build custom protocol; đừng ép MCP cover A2A hay ngược lại.** Pin protocol versions, test trên cùng release channel như CI. [fact]

---

## 2. A2A Protocol v1.0 (March 2026) ⭐

- Open standard cho inter-agent communication, donate từ Google → Linux Foundation. Steering gồm AWS, Cisco, Google, IBM Research, Microsoft, Salesforce, SAP, ServiceNow. 150+ orgs. [fact]
- **v1.0 (March 2026)**: multi-protocol bindings (JSON-RPC, gRPC, HTTP/REST), version negotiation, multi-tenancy, **signed Agent Cards** (cryptographic identity verification). [fact]
- Agent Card (JSON): advertise capabilities; client discover + delegate không cần human broker. [fact]
- Async-first: task object có lifecycle, artifacts làm output; polling/streaming/push notifications; long-running + HITL. [fact]
- **Opaque execution**: agents collaborate qua declared capabilities, KHÔNG share internal thoughts/plans/tools → bảo mật + IP. [fact]
- Spec dùng **Protocol Buffers** làm normative source (proto → SDK bindings, không manual edit). Extensions qua URI versioned. [fact]
- IBM Agent Communication Protocol merge vào A2A (Aug 2025) → field hướng single shared standard. [fact]

---

## 3. AAIF (Agentic AI Foundation) — governance neutral ⭐

- Linux Foundation (Dec 9, 2025): founding contributions **Anthropic's MCP, Block's goose, OpenAI's AGENTS.md**. [fact]
- Aug 2026: **A2A join AAIF** → 3-layer stack dưới một roof. 250+ orgs co-governing. [fact]
- **Tại sao quan trọng**: trước Aug 2026 cả 2 protocol có "single-vendor problem". Giờ changes cần RFC + Steering Committee review + public comment (như OpenAPI/GraphQL). Projects không biến mất khi backer pivot. [fact]
- AAIF working groups: Accuracy & Reliability, Agentic Commerce, Governance/Risk/Regulatory, Identity & Trust, Observability & Traceability, Security & Privacy, Workflows & Process Integration, Taxonomy & Landscape. [fact]

---

## 4. AGENTS.md — open standard (already in AHD!) ⭐

- OpenAI released Aug 2025; adopted bởi 60,000+ repos + frameworks (Amp, Codex, Cursor, Devin, Factory, Gemini CLI, GitHub Copilot, Jules, VS Code). [fact]
- **AHD ĐÃ CÓ AGENTS.md chuẩn** — alignment với standard. Cần giữ AGENTS.md làm single source of project guidance. [fact/inference]
- AAIF: AGENTS.md = layer "Instructions and context" — standardize cách projects communicate expectations cho agents. [fact]

---

## 5. Adoption numbers (2026) ⭐

- MCP: **110M monthly SDK downloads**, 9,652 servers registry, 15,000+ GitHub MCP repos, **78% enterprise AI teams báo MCP in production**. Integration time: 18h custom → 4.2h qua MCP. [fact]
- Gartner: **40% enterprise apps sẽ có task-specific AI agents by end 2026** (từ <5% 2025). [fact]
- Salesforce Agentforce, ServiceNow Now Assist, Google ADK implement A2A v1.0. [fact]

---

## 6. Recommendations cho AHD ⭐

| # | Standard | Áp dụng vào AHD | Ưu tiên |
|---|----------|-----------------|---------|
| S1 | **3-layer stack** | AHD = MCP (tool access) + A2A (cross-agent delegation) + WebMCP; đừng tự build protocol | 🔴 HIGH |
| S2 | **Signed Agent Cards** | Nếu AHD delegate cho external agents → verify identity qua signed cards | 🟠 MED |
| S3 | **AGENTS.md standard** | Giữ AGENTS.md làm open standard (already done) | 🟠 MED |
| S4 | **AAIF governance** | Theo RFC/version-negotiation discipline cho internal protocols | 🟡 LOW |
| S5 | **Multi-tenancy + multi-binding** | Nếu AHD expose agents → support multi-protocol bindings | 🟡 LOW |

> **Cạnh tranh với harness Claude/Codex/GPT**: AHD dùng open standards (MCP/A2A/AGENTS.md) → portable across providers, không lock-in vào 1 vendor model. Đây là lợi thế cốt lõi của AHD để chạy multi-provider.

---

## Sources (MỚI)

- a2a-protocol.org/latest, aaif.io/blog/a2a-joins-aaif, aaif.io, a2a-protocol.org/announcing-1.0, github.com/google/A2A
- linuxfoundation.org/press (AAIF formation), byteiota.com (A2A+MCP one roof), developers.googleblog.com (A2A launch)

---

*Iteration 5 output | 2026-08-27 | Emerging standards build (MỚI) | Confidence: High*
