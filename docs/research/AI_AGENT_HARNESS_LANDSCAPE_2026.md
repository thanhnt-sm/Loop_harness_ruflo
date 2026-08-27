# AI Agent Harness Landscape 2026

> Nghiên cứu competitive landscape các AI agent harness frameworks và orchestration systems.
> Ngày: 2026-08-27 | Nguồn: 17+ sources, 10 web searches, 3 deep fetches

---

## Executive Summary

Năm 2025-2026, **Harness Engineering** trở thành discipline mới (Martin Fowler formalized Apr 2026). AGENTS.md trở thành open standard (60,000+ repos, Linux Foundation AAIF). Plan-Then-Execute là pattern phổ biến nhất — tăng task completion 40-70%, giảm hallucination ~60%.

AHD có **competitive advantages độc nhất**: 3-Phase mandatory workflow, 49 deterministic hooks, 6+ adversarial personas, multi-provider orchestration (6+ tools), runtime governance enforcement.

---

## Industry Overview

### Xu hướng chính

1. **"Harness Engineering"** — Agent = Model + Harness (Martin Fowler, Apr 2026)
2. **AGENTS.md standard** — 60,000+ repos adopting, Linux Foundation AAIF govern (Dec 2025)
3. **MCP ecosystem** — ~9,400 published servers, ~1,300 production-ready, AAIF governed
4. **Plan-Then-Execute dominant** — planning trước → approve → execute (agentic-patterns.com, Mar 2026)
5. **Spec-Driven Development (SDD)** — countermeasure chính cho "spec drift"
6. **Gartner forecast**: 40% enterprise apps có AI agents vào 2026, nhưng 40% agentic projects sẽ fail by 2027 nếu thiếu governance

### Market Statistics

| Metric | Value | Source |
|--------|-------|--------|
| Dev dùng AI (2026) | 84% | Uvik/SD Times |
| Trust trong AI (2024→2026) | 40% → 29% | DX research |
| PR AI-authored review wait | 4-6× longer | Industry data |
| Security vulnerabilities AI code | +15-24% | CSA/Wiz |
| Agents in production | 57% | LangChain/Fordel |
| Quality as barrier #1 | 32% | LangChain survey |

---

## Framework Comparison

### 1. Claude Code (Anthropic)

- **URL**: https://code.claude.com
- **Architecture**: Terminal-native, deep MCP support, subagents
- **5 Harness Layers**: Memory → Tools → Permissions → Hooks → Observability
- **Key Features**:
  - Plugin marketplace (spring 2026): Skills + Plugins
  - Subagents (Plan/Explore/Task) cho parallel work
  - PreToolUse hooks intercepting tool calls
  - `--resume` flag cho session continuity
- **Guardrails**: Interactive permission prompts, .claudeignore, hook-based enforcement
- **Insight**: "Constraints beat raw horsepower" — reasoning budget max scored 53.9% vs high scored 63.6%
- **Strengths**: Frontier model integration, deep MCP ecosystem, biggest harness community
- **Weaknesses**: Proprietary, vendor lock-in, rate limits

### 2. Devin (Cognition Labs)

- **URL**: https://devin.ai
- **Architecture**: Cloud-based "brain" + containerized "DevBox" (Linux)
- **Devin 2.0** (Apr 2025): $20/month, 83% productivity improvement
- **Key Features**:
  - Interactive Planning trước khi code
  - Devin Search and Wiki (persistent knowledge base)
  - Parallel agent capabilities
  - Devin Fusion: hybrid-model routing
- **Guardrails**: Sandboxed environment, transparent observation
- **Strengths**: Fully autonomous, real-world deployment (Goldman Sachs, Nubank — 12x efficiency)
- **Weaknesses**: Task completion 15-30% independently, loss of architectural control

### 3. Claude Code Harness (Chachamaru127)

- **URL**: https://github.com/Chachamaru127/claude-code-harness
- **Stars**: 3,100+ | License: MIT | Language: Go
- **Architecture**: Plan→Work→Review→Ship cycle với Go-native guardrail engine
- **Key Features**:
  - 5 verb skills: plan, work, review, sync, release
  - Runtime floor (5 categories): billing, network, secrets, production, destruction — **không override được**
  - Guardrails R01-R15: configurable per-project
  - Go engine chạy **trước** mỗi tool call
  - Multi-session: roster + cross-worktree visibility
  - HTML decision surfaces cho non-engineers
- **Support**: Claude Code, Codex CLI, Cursor, Grok
- **Strengths**: Strongest safety layer reviewed, machine-checked claims
- **Weaknesses**: Complex setup, Go dependency
- **vs AHD**: Rất tương đồng! Cả hai có Plan→Approve→Execute + guardrails trước tool calls + multi-provider

### 4. OpenCode (Anomaly)

- **URL**: https://opencode.ai | https://github.com/anomalyco/opencode
- **Stars**: 201,733 | License: MIT | Language: TypeScript
- **Architecture**: Terminal-first, provider-agnostic, Plan + Build dual modes
- **Key Features**:
  - Built-in agents: `build` (full-access) + `plan` (read-only) + `general` (subagent)
  - MCP integration (stdio + SSE)
  - LSP integration multi-language
  - Auto compact
  - Custom commands
- **Guardrails**: Permission model (allow/ask/deny)
- **Strengths**: Provider-agnostic, huge community, lightweight
- **Weaknesses**: Less sophisticated orchestration, no multi-phase workflow

### 5. Cline

- **URL**: https://cline.bot | https://github.com/cline/cline
- **Stars**: 46,000+ | License: Apache 2.0 | Language: TypeScript
- **Architecture**: Editor-embedded (VS Code), @cline/sdk
- **Key Features**:
  - Auto-approve toggles (read, edit, safe commands)
  - YOLO mode (experimental)
  - MCP server support
  - Plan/Act model patterns
- **Guardrails**: Permission toggles per-action
- **Strengths**: IDE-native, open source, BYOK
- **Weaknesses**: Editor-dependent, less autonomous

### 6. Cursor

- **URL**: https://cursor.com
- **Architecture**: VS Code fork with AI, cloud VMs, background agents
- **Key Features (2026)**:
  - Agent Mode (background agents on Pro+)
  - Composer 2.5 for parallel agents
  - Rules system: `.cursor/rules/` (MDC format)
  - Guardrail agents (@guardrail-agent)
- **Guardrails**: Rules + agent-level guardrails
- **Strengths**: Best day-to-day IDE experience, multi-model (GPT-5, Claude Sonnet 4)
- **Weaknesses**: $20/month, not terminal-native

### 7. OpenHands (formerly OpenDevin)

- **URL**: https://github.com/OpenHands/OpenHands
- **License**: MIT | Language: Python
- **Architecture**: Event-stream — every action/observation flows through central log
- **Strengths**: Fully open, self-hostable, autonomous multi-step
- **Weaknesses**: Complex setup, less interactive

### 8. Aider

- **URL**: https://github.com/Aider-AI/aider
- **License**: Apache 2.0 | Language: Python
- **Architecture**: Repo map + Architect/Editor split
- **Strengths**: Best for pair programming in existing repos, lightweight
- **Weaknesses**: Single-agent, no orchestration

---

## Comparison Matrix

| Framework | License | Stars | Multi-Provider | Hooks | Plan-Execute | Guardrails | Adversarial Review |
|-----------|---------|-------|---------------|-------|-------------|------------|-------------------|
| Claude Code | Proprietary | N/A | No | ✅ | Basic | ✅ | No |
| Devin | Proprietary | N/A | No | No | ✅ | Sandbox | No |
| Claude Code Harness | MIT | 3,100 | ✅ (4 tools) | ✅ (Go) | ✅ (5 verbs) | ✅✅ | No |
| OpenCode | MIT | 201,733 | ✅ (any) | No | Plan/Build | Basic | No |
| Cline | Apache 2.0 | 46,000+ | ✅ (BYOK) | No | Plan/Act | Toggles | No |
| Cursor | Proprietary | N/A | No | ✅ | ✅ | Rules | No |
| OpenHands | MIT | High | No | ✅ | ✅ | ✅ | No |
| Aider | Apache 2.0 | High | ✅ | No | Arch/Editor | No | No |
| **AHD** | **Custom** | **N/A** | **✅ (6+)** | **✅ (49 hooks)** | **✅ (3-Phase FSM)** | **✅✅ (enforced)** | **✅ (6+ personas)** |

---

## AHD Unique Strengths

1. **3-Phase Architecture** — FORCE Plan phase bắt buộc, approval gates interactive
2. **Multi-provider orchestration** — 6+ tools trong 1 harness, shared governance
3. **49 deterministic hooks** — enforcement trước tool call, không review sau
4. **6+ adversarial personas** — C3 protocol, unique trong industry
5. **Workspace file governance** — runtime enforcement (tools/check_governance.py)
6. **DAG-based executor** — parallel task dispatch với worktree isolation
7. **Self-healing** — Monitor→Detect→Diagnose→Recover, circuit breaker
8. **Token efficiency** — Caveman protocol (~65% reduction), lazy-load canon
9. **Evidence-graded claims** — [fact]/[inference]/[unverified] tagging

---

## AHD Improvement Areas

| Area | Industry Trend | AHD Status | Recommendation |
|------|---------------|------------|----------------|
| **Hook lifecycle standardization** | PreToolUse/PostToolUse/Stop events | 49 hooks nhưng contracts chưa standard | Document event contracts rõ ràng hơn |
| **AGENTS.md compatibility** | AAIF standard format | Dùng AGENTS.md nhưng format riêng | Ensure compatibility với AAIF standard |
| **MCP ecosystem** | 9,400+ servers | 4 MCP servers | Expand ecosystem ( evaluation) |
| **Observability dashboard** | HTML views cho non-engineers | Telemetry + event_bus | Expose dashboards |
| **Cross-session memory** | Anthropic initializer agent pattern | Memory system có sẵn | Benchmark với Anthropic pattern |
| **Multi-tool install** | Claude Code Harness hỗ trợ 4 tools | Support 6+ providers | Easy setup documentation |

---

## Key Industry Patterns

### PreToolUse Hooks (Most Important)

> "Instructions tell agents what to do. Hooks ensure they actually do it." — htek.dev

- Hooks intercept **trước** tool call, deterministic, auditable
- "The model layer alone cannot be the security control. Models are non-deterministic and persuadable."

### Layered Enforcement (5 layers)

1. **Permission Guardrails** — scope what agent can touch
2. **Behavioral Guardrails** — prevent unwanted actions
3. **Output Guardrails** — validate what agent produces
4. **Resource Guardrails** — limits with kill switch
5. **Ops Guardrails** — logging, audit, observability

### Plan-Then-Execute

- Planning improves task completion **40-70%**
- Reduces hallucinations **~60%**
- Planner commits to bounded action graph
- Executor enforces deterministically

---

## Sources

| # | Source | URL | Date |
|---|--------|-----|------|
| 1 | Anthropic: Effective harnesses | anthropic.com/engineering | Nov 2025 |
| 2 | ShipWithAI: Harness Engineering Guide | shipwithai.io | Apr 2026 |
| 3 | FutureAGI: Best Agent Harnesses 2026 | futureagi.com | Jul 2026 |
| 4 | Claude Code Harness (Chachamaru127) | github.com | 2025-2026 |
| 5 | Codersera: AI Coding Agents 2026 | codersera.com | Aug 2026 |
| 6 | htek.dev: Agent Hooks | htek.dev | Feb 2026 |
| 7 | Endor Labs: Agent Governance | endorlabs.com | Jul 2026 |
| 8 | Zylos Research: Agent-Orchestrated Dev | zylos.ai | Jun 2026 |
| 9 | CORE Agentic Workflow | codeongrass.com | Apr 2026 |
| 10 | TeamDay: Agentic Coding Guide 2026 | teamday.ai | Jul 2026 |
| 11 | Zylos: Multi-Agent Orchestration | zylos.ai | Jan 2026 |
| 12 | Agentic-patterns.com | agentic-patterns.com | Mar 2026 |
| 13 | Cline docs | docs.cline.bot | 2025 |
| 14 | OpenCode GitHub | github.com/anomalyco | 2025-2026 |
| 15 | Cursor docs | cursor.com/docs | 2026 |
| 16 | RUCAIBox awesome-agent-harness | github.com/RUCAIBox | 2025-2026 |
| 17 | ThomasLiu ai-coding-harness (320 repos) | github.com/ThomasLiu | 2025-2026 |

---

*Cập nhật: 2026-08-27 | Confidence: High | 17+ sources*
