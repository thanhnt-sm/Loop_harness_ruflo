# Tech Overview 2026 — Harness Engineering, Context Rot, Benchmarks, MCP Security

> **RESEARCH BỔ SUNG** (Iteration 2) — góc MỚI chưa cover ở baseline.
> Ngày: 2026-08-27 | Nguồn: Chroma, arXiv, OpenAI, Thoughtworks/Martin Fowler, BenchLM.ai, SWE-Bench, PolicyLayer, MCP Institute, Cybertize, Fullstack.
> English + Vietnamese. Đây là phần research mới (không duplicate `AI_AGENT_HARNESS_LANDSCAPE_2026.md`).

---

## 1. Harness Engineering Discipline (MỚI)

### 1.1 Nguồn gốc — "Agent = Model + Harness"

- **Coined: Mitchell Hashimoto** (co-founder HashiCorp, creator Terraform/Ghostty), Feb 2026:
  > "Khi agent mắc lỗi, bạn kỹ thuật một giải pháp để agent **không bao giờ** lặp lại lỗi đó." [fact]
- **6 ngày sau**: Ryan Lopopolo (OpenAI) case study — nhóm nhỏ ship sản phẩm **1 triệu dòng code Codex**, **1500 PR** bởi 3 engineers ở **3.5 PR/engineer/day**. [fact]
- **Böckeler framework** (Thoughtworks, trên Martin Fowler's site) — ngôn ngữ chuẩn ngành: **guides (feedforward controls)** + **sensors (feedback controls)** (mượn từ cybernetics). [fact]

### 1.2 Guides vs Sensors (phân loại MỚI, chưa có ở baseline)

| Thành phần | Loại | Ví dụ |
|------------|------|------|
| **Guides** (steer BEFORE act) | Feedforward | system prompts, CLAUDE.md, rules files, tool definitions |
| **Sensors** (validate AFTER act) | Feedback | linters, type checkers, tests, evals, output parsers |
| Hooks | Programmatic | PreToolUse, PostToolUse, pre-commit |
| Permissions | Guardrail | allowlists, tool-risk ratings |
| Sandboxes | Env | Docker, E2B, Firecracker |
| Observability | Monitor | traces, token usage, error rates |

**Key insight**: *"Sensors enforce at ~100%. Böckeler argues sensors là thành phần 'powerful and underdiscussed' — hầu hết team over-invest guides, under-invest sensors."* [fact]
**Ratchet principle** (Addy Osmani): harness chỉ siết chặt, không nới lỏng. (`Chamath/Osmani`) [fact]
**Manual minuti**: (1) Agent không biết rule? → thêm guide. (2) Agent cho biết rule nhưng vi phạm? → thêm sensor/hook. (3) Thiếu info? → thêm skill/MCP. (4) Dùng tool nguy hiểm? → restrict permission. (5) Context polluted? → subagent isolation. (6) Crash không ai thấy? → monitoring. [fact]

### 1.3 Natural-Language Agent Harnesses (NLAH) — arXiv 2603.25723

- Đề xuất harness logic **externalize thành executable artifact portable** (Natural-Language Agent Harnesses) + **Intelligent Harness Runtime (IHR)**. [fact]
- Bối cảnh: harness design hiện nằm rải rác trong controller code, khó transfer/compare/ablate. [fact]
- "Practical results support: **natural language remains important when used to specify harness-level control** — roles, contracts, verification gates, durable state — hơn là one-shot prompt phrasing." [fact]

### 1.4 Harness trong OpenAI (Case Study)

- **Map, not 1,000-page manual**: `AGENTS.md` ngắn (~100 lines) inject vào context, trỏ đến deeper sources. [fact]
- Context **"rots instantly"** — instruction file khổng lồ thành graveyard of stale rules. [fact]
- **Progressive disclosure** skills — không load mọi tool vào context lúc start. [fact]
- **Giữ invariants via custom lints + structural tests** (không micromanage) — golden principles trong repo, background agent scan deviation + auto-merge PR. [fact]
- **Repository-local = system of record**: bất cứ kiến thức để ngoài repo (Google Docs, chat) = "không tồn tại" đối với agent. [fact]

---

## 2. Context Rot — Research papers (MỚI)

### 2.1 Chroma report (Hong, Troynikov, Huber, Jul 2025) — `trychroma.com/research/context-rot`

- **NIAH (Needle in a Haystack) underestimate** long-context degradation — task quá đơn giản (lexical match), không đại diện thực tế. [fact]
- Test 18 LLMs: **performance degrades consistently với increasing input length**, non-uniform. [fact]
- Lower needle-question similarity (realistic) → degradation nhanh hơn. Distractors có impact non-uniform. [fact]
- LongMemEval: thêm irrelevant context (thêm bước retrieval) giảm đáng kể reliability. [fact]
- **Implication**: "whether relevant info is present ≠ enough; **how info is presented** matters more" → context engineering essential. [fact]

### 2.2 Premature Termination (GAIR-NLP ContextRot, arXiv 2606.29718)

- **Phenomenon MỚI**: under extensive context, models **give up hoặc đưa ra câu trả lời uncertain-incorrect SAI sớm** trước khi hết window. [fact]
- Premature termination rate **positively correlated với context length** (đã control query difficulty). [fact]
- **Context management = test-time scaling**: reduce premature termination để enable exploration. [fact]
- 7 methods, 3 categories: **context compaction, context trimming, context isolation**. Isolation (sub-agent) tốt cho model mạnh; compaction+trimming tốt cho model yếu. [fact]
- **Behavior-aware filtering** (parallel sampling): gain **2.6-4.9%** qua 3 aggregation methods. [fact]

### 2.3 Governance Decay (ConstraintRot, arXiv 2606.22528) — ⚠️ RẤT quan trọng cho harness

- Compaction **silently xóa governance constraints** (runtime policies, standing instructions) khi summarize history. [fact]
- Compaction làm **violation tăng 0%→30% (up to 59%)** qua 7 models (1,323 episodes). [fact]
- **8.3×** decay lớn hơn cho soft organizational policies vs hard safety norms. [fact]
- Soft policies erode chính xác những ràng buộc deployment-specific chỉ tồn tại trong context. [fact]
- **Compaction-Eviction Attack**: adversary bias compaction để xóa constraint → defeats mọi model (0%→65%). [fact]
- **Defense — Constraint Pinning**: extract constraint vào pinned buffer exempt compaction, re-inject verbatim, integrity-check → **restores violation về 0%** tại <0.5% token overhead. [fact]

**AHD implication**: `.devin/skills/context-compactor.md` (CAVEMAN_PROTOCOL) cần audit chống **governance decay** — pin các ràng buộc an toàn (REDLINES) khi compact. **ĐÂY LÀ GAP MỚI phát hiện.** [inference]

### 2.4 ARC (aclanthology 2026.findings-acl.930)

- Context như **execution-time state có thể sửa** (không phải static artifact). Active incremental context + selectively triggered reflection. [fact]
- Up to **11% absolute improvement** (BrowseComp-ZH). [fact]
- Tokens: raw history tăng linear; ARC giữ compact memory stabilize. [fact]

### 2.5 ACM (Agentic Context Management, arXiv 2607.23809)

- **Agent-triggered, lossless context management**: agent tự quyết khi nào compress, offload external memory, query on demand. [fact]
- Post-training: teacher-student dual constraints. [fact]
- Qwen3.5-9B: **+27% BrowseComp-Plus, +16% DeepSearchQA, +8% SWE-Bench Verified**; giảm **~20% peak token**; extend test-time exploration. [fact]

---

## 3. SWE-bench Verified Leaderboard (MỚI)

### 3.1 Top scores (Aug 2026, BenchLM.ai + Steel.dev)

| System | Score | Org | Method |
|--------|-------|-----|--------|
| Claude Opus 5 | **96%** | Anthropic | Self-reported, thinking blocks |
| Claude Mythos 5 | **95.5%** | Anthropic | Self-reported system card |
| Claude Fable 5 | **95.0%** | Anthropic | Self-reported |
| GPT-5.6 Sol | 82.2% | OpenAI | Thinking Machines |
| (Augment Code SWE-Agent) | 72.0% | Augment | Best autonomous scaffold (Apr 2026) |
| OpenHands + CodeAct v3 | 68.4% | Open source | Claude Opus 4.6 |
| mini-SWE-agent | 65% | Princeton | 100 lines Python |

- **Scaffold matters as much as model**: Claude Sonnet 4.5 → SWE-agent 43.2% vs Cline autonomous 59.8% = **16-point gap từ orchestration alone**. [fact]
- Top scores set: **benchmark nearing saturation** (top models clustered 1.0 pts). [fact]
- SWE-bench Pro harder: top models ~23% public vs 70%+ Verified. [fact]

### 3.2 Implication cho AHD

- AHD có 3-Phase + 49 hooks + adversarial review ⇒ scaffold-strength tương đương OpenHands/Claude Code Harness pattern. Kiến trúc "harness beats model" được xác nhận. [inference]
- mini-SWE-agent (65% chỉ với 100 dòng) chứng minh **purpose-designed scaffold** là lever lớn nhất. [fact]

---

## 4. MCP Security Crisis (MỚI — QUAN TRỌNG)

### 4.1 Adoption (MỚI, numbers khác baseline)

- SDK downloads: **100,000/tháng (Nov 2024) → 97 triệu/tháng (Mar 2026)** = **970×** trong 18 tháng. [fact]
- Public servers: **9,600–17,500 (registry)**; PolicyLayer phân loại **32,820 working servers, 517,973 tools**. [fact]
- Nhưng **chỉ 41%** software-industry technical leaders báo cáo even limited production use. Claim "78% production" bị walk-back. [fact]
- Dec 2025: Anthropic donate MCP → **AAIF** (Agentic AI Foundation, Linux Foundation). [fact]

### 4.2 Security math (MỚI)

- **8.5%** servers implement OAuth 2.1 (mandatory cho remote). [fact]
- **53%** expose credentials hardcoded; **79%** keys qua env vars. [fact]
- **Command injection 43%** (Equixly); **path traversal 82%** (Endor Labs, 2,614 impl). [fact]
- **28.1%** servers expose ≥1 destructive tool; **26.2%** can execute arbitrary commands. [fact]
- **43.28%** expose destructive/execute; stack 5 servers → **94.1%** probability. [fact]
- **96.4%** tool descriptions không cảnh báo hệ quả ("irreversible", "destroys",...). [fact]
- 88% orgs reported AI agent incidents (Sonar/Docker/Sysdig). [fact]
- CVEs: **CVE-2025-6514** (CVSS 9.6, mcp-remote RCE), **CVE-2025-49596** (9.4, Inspector RCE), **CVE-2026-33032** (9.8 auth bypass), **MCPoison/CurXecute** (Cursor). 30+ CVEs trong 60-day window. [fact]
- **Lethal trifecta** risks: confused-deputy, tool poisoning (~5.5%), rug pulls. [fact]
- Framework wrapper spread: **Agent Compromise Rate 11.9% (CrewAI) → 31.1% (SmolAgents)** — 2.6× (DEF CON 34). [fact]

### 4.3 MCP Best Practices (MỚI)

1. Xử lý MCP servers như **third-party dependencies** — pin version, scan, review. [fact]
2. **Least-privilege** mỗi credential. [fact]
3. **Isolate execution** (containers, sandbox, egress restrict). [fact]
4. **Gate high-impact tools on human approval** (client-side allowlist + per-tool confirm). [fact]
5. **Log tool calls as security events** (arguments, results, context). [fact]
6. **Manual**: "The confused-deputy problem is managed at the client boundary, not inside the model." (Safeguard.sh) [fact]

**AHD implication**: `.opencode/mcp/servers.json` cần audit — MCP tool risk classification + per-tool approval gate + destructive warning. **GAP MỚI phát hiện.** [inference]

---

## 5. AHD Action Items (synthesis MỚI — không duplicate)

| # | Phát hiện | Gap AHD | Ưu tiên |
|---|-----------|---------|---------|
| A1 | **Governance Decay** (ConstraintRot) | `context-compactor` skill cần **constraint pinning** để chống mất REDLINES khi compact | 🔴 HIGH |
| A2 | **MCP security** (96% no warning, 43% destructive) | `mcp/servers.json` cần tool-risk classification + destructive warning + approval gate | 🔴 HIGH |
| A3 | **Sensors > guides** (Böckeler) | AHD giàu guides; cần tăng **sensors** (mutation testing, behavioral) | 🟠 MED |
| A4 | **Ratchet principle** (Osmani) | Mỗi lỗi agent → fix harness vĩnh viễn (AHD: `.devin/hooks/` accumulate) | 🟠 MED |
| A5 | **Premature termination** (GAIR-NLP) | Monitoring "agent give up early" + behavior-aware filtering | 🟠 MED |
| A6 | **Map, not manual** (OpenAI) | AGENTS.md hiện có thể quá dài → audit tới ~100 lines + progressive disclosure | 🟡 LOW |

---

## Sources (MỚI)

- trychroma.com/research/context-rot, github.com/chroma-core/context-rot
- arxiv.org/abs/2606.29718 (Premature Termination), github.com/GAIR-NLP/ContextRot
- arxiv.org/html/2606.22528 (Governance Decay/ConstraintRot)
- aclanthology (ARC), arxiv.org/html/2607.23809 (ACM)
- arxiv.org/html/2603.25723 (NLAH/IHR)
- addyosmani.com/blog/agent-harness-engineering, openai.com/index/harness-engineering, lyzr.ai/blog/harness-engineering, amux.io/guides/harness-engineering, deepset.ai/blog/harness-engineering
- swebench.com, benchlm.ai/benchmarks/swe-bench-verified, swe-bench-pro, leaderboard.steel.dev, labs.scale.com/leaderboard
- policylayer.com/research/state-of-mcp, mcp.institute/research/state-of-mcp-2026, cybertizeweb.com/blog/ai/mcp-adoption-report-2026, practical-devsecops.com/mcp-security-statistics-2026-report, safeguard.sh/resources/blog/model-context-protocol-security-landscape, zuplo.com/blog/mcp-survey, forkast.news/the-structural-cost-of-the-mcp-security-crisis, index.canopii.dev/mcp-security-index

---

*Iteration 2 output | 2026-08-27 | Research bổ sung (không duplicate baseline) | Confidence: High*
