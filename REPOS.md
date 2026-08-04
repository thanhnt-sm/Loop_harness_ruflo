# REPOS.md — Master Reference List

> Toàn bộ GitHub repos, documentation sources, papers, và tools được **tham khảo, sử dụng, hoặc học hỏi** trong quá trình xây dựng workspace này.
>
> Workspace hiện tại = kết quả của 3 giai đoạn: (1) Ruflo cleanup, (2) best practices research, (3) Agent Harness Deploy.

---

## 1. Main Engine — Repo chính thức deployed

| Repo | Vai trò | License | Trạng thái |
|------|---------|---------|------------|
| [masteryee-labs/Tool.Agent-Harness-Deploy](https://github.com/masteryee-labs/Tool.Agent-Harness-Deploy) | **Agent Harness Deploy (AHD)** — self-deploying cross-tool AI harness. Deploy canonical rules + skills + orchestrator + memory protocol + hooks vào `.devin/`. Là **động cơ chính** của workspace. | — | Deployed (commit `c327869`) |

---

## 2. Vendored Skills (anti-link-rot copies trong workspace)

| Repo | Vai trò | License | Vendored tại |
|------|---------|---------|--------------|
| [alchaincyf/nuwa-skill](https://github.com/alchaincyf/nuwa-skill) | **Nuwa** — cognitive-diversity skill distillation factory. Distill mental models của public figures (Munger, Feynman, Taleb, v.v.) thành runnable perspective skills. | MIT | `.devin/skills/nuwa-skill/` (commit `72857dc`, 2026-07-07) |

---

## 3. AHD Canon — Sources extracted vào canonical protocols

Các repo/concept sau được AHD distill thành 10 protocol files trong `.devin/canon/`:

| Source | Concept được distill | Canon file |
|--------|---------------------|------------|
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Caveman token-compression prompt syntax (~65% reduction) | `CAVEMAN_PROTOCOL.md` |
| [cheeseonamonkey/Lean-Caveman](https://github.com/cheeseonamonkey/Lean-Caveman) | Lean Caveman variant | `CAVEMAN_PROTOCOL.md` |
| [JuliusBrussee/caveman-code](https://github.com/JuliusBrussee/caveman-code) | Caveman for code | vault/README.md |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | Multi-persona Commander/Worker operational architecture | `COMMANDER.md`, `PERSONA_TEMPLATE.md` |
| [obra/superpowers](https://github.com/obra/superpowers) | Subagent-driven development, systematic debugging, TDD | `COMMANDER.md`, `systematic_debugging.md`, `tdd.md` |
| [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering) | Loop-audit, Loop Readiness Score | `LOOP_PROTOCOL.md` |
| [Sahir619/fable-method](https://github.com/Sahir619/fable-method) | Fable judge adversarial done-gate, domain adapters template | `fable-judge.md`, `domain-adapters/TEMPLATE.md` |
| [kangarooking/cangjie-skill](https://github.com/kangarooking/cangjie-skill) | RIA++ six-section structure | `HARNESS_ENGINEERING.md` |
| oh-my-openagent (Sisyphus Labs, SUL-1.0) | Comment-checker, init-deep, Todo Enforcer, Prometheus planner | `comment_checker.md`, `init_deep.md`, `CORE_CANON.md`, `LOOP_PROTOCOL.md` |
| romanticamaj (2026 retrospective) | Context moat concept | `MEMORY_PROTOCOL.md` |
| deusyu/harness-engineering (Fowler) | Context rot, Guides × Sensors taxonomy, behavior harness gap | `MEMORY_PROTOCOL.md`, `VERIFICATION_PROTOCOL.md` |
| Carlos E. Perez ("From Loop Engineering to Graph Engineering?", 2026-07-18) | Verification anchor tiers | `VERIFICATION_PROTOCOL.md` |
| kpab/claude-fable-5-skills | No gold-plating | `VERIFICATION_PROTOCOL.md` |
| Wisely Chen (AI Coding reflection + ATPM QA articles) | Bottleneck shift, three QA strategies, two code types, start small > null | `VERIFICATION_PROTOCOL.md` |
| Riven (HE article + comprehensive HE guide) | Sensor output = fix instructions | `VERIFICATION_PROTOCOL.md` |
| OpenAI Harness Engineering blog | Harness engineering principles | `HARNESS_ENGINEERING.md` |
| Anthropic Harness Design | Harness engineering principles | `HARNESS_ENGINEERING.md` |
| Mitchell Hashimoto | Harness engineering principles | `HARNESS_ENGINEERING.md` |
| 温煜鈞 / 李宏毅 | Harness engineering principles (ZH community) | `HARNESS_ENGINEERING.md` |

---

## 4. AHD Vault — Structural templates (anti-link-rot)

| Repo | Template file | Mục đích |
|------|---------------|----------|
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | `caveman_template.json` | Caveman compression template |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | `agency_framework.toml` | Commander/Worker structural source |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | `memory_mcp_schema.json` | Three-layer memory schema |
| [usestrix/strix](https://github.com/usestrix/strix) | `strix_security_rules.json` | Penetration-testing detection rules, auto-remediation |
| [safishamsi/graphify](https://github.com/safishamsi/graphify) | `graphify_knowledge_spec.json` | Code-to-knowledge-graph parsing |
| [kevintsai1202/deep-memory](https://github.com/kevintsai1202/deep-memory) | (referenced in vault README) | Deep-memory retrieval, SHA discipline |
| [p-e-w/heretic](https://github.com/p-e-w/heretic) | (referenced in vault README) | Sandbox boundary re-alignment |

Vault location: `.devin/skills/assets/vault/`

---

## 5. Nuwa Skill Ecosystem — Perspective skills (cùng tác giả alchaincyf)

| Repo | Subject |
|------|---------|
| [alchaincyf/paul-graham-skill](https://github.com/alchaincyf/paul-graham-skill) | Paul Graham |
| [alchaincyf/zhang-yiming-skill](https://github.com/alchaincyf/zhang-yiming-skill) | Zhang Yiming (ByteDance) |
| [alchaincyf/karpathy-skill](https://github.com/alchaincyf/karpathy-skill) | Andrej Karpathy |
| [alchaincyf/ilya-sutskever-skill](https://github.com/alchaincyf/ilya-sutskever-skill) | Ilya Sutskever |
| [alchaincyf/mrbeast-skill](https://github.com/alchaincyf/mrbeast-skill) | MrBeast |
| [alchaincyf/trump-skill](https://github.com/alchaincyf/trump-skill) | Donald Trump |
| [alchaincyf/steve-jobs-skill](https://github.com/alchaincyf/steve-jobs-skill) | Steve Jobs |
| [alchaincyf/elon-musk-skill](https://github.com/alchaincyf/elon-musk-skill) | Elon Musk |
| [alchaincyf/munger-skill](https://github.com/alchaincyf/munger-skill) | Charlie Munger |
| [alchaincyf/feynman-skill](https://github.com/alchaincyf/feynman-skill) | Richard Feynman |
| [alchaincyf/naval-skill](https://github.com/alchaincyf/naval-skill) | Naval Ravikant |
| [alchaincyf/taleb-skill](https://github.com/alchaincyf/taleb-skill) | Nassim Taleb |
| [alchaincyf/zhangxuefeng-skill](https://github.com/alchaincyf/zhangxuefeng-skill) | Zhang Xuefeng |
| [alchaincyf/x-mentor-skill](https://github.com/alchaincyf/x-mentor-skill) | X Mentor (topic skill) |
| [alchaincyf/darwin-skill](https://github.com/alchaincyf/darwin-skill) | Darwin — skill evolution optimizer |
| [alchaincyf/fanbox](https://github.com/alchaincyf/fanbox) | FanBox — Coding Agent cockpit |
| [alchaincyf/huashu-design](https://github.com/alchaincyf/huashu-design) | Huashu design skill (animation) |
| [titanwings/colleague-skill](https://github.com/titanwings/colleague-skill) | Colleague skill — distilling departing colleagues (Nuwa inspiration) |
| [vercel-labs/skills](https://github.com/vercel-labs/skills) | Universal CLI installer (55+ runtimes) — Nuwa install method |

---

## 6. Devin CLI Ecosystem — Repos tham khảo cho best practices

| Repo | Mục đích |
|------|----------|
| [jsklan/devin-api-mcp](https://github.com/jsklan/devin-api-mcp) | MCP server wrap full Devin API (v1+v3+deepwiki proxy) |
| [mjinno09/devin-mcp](https://github.com/mjinno09/devin-mcp) | Rust MCP cho Devin session management |
| [ldastey-dev/devin-mcp](https://github.com/ldastey-dev/devin-mcp) | Python MCP wrap v1+v2+v3beta1 multi-org |
| [desertaxle/devin-mcp](https://github.com/desertaxle/devin-mcp) | Python MCP delegate tasks to Devin |
| [adw0rd/awesome-mcp-tools-mcp](https://github.com/adw0rd/awesome-mcp-tools-mcp) | CLI + MCP bridge cho 2000+ MCP servers catalog |
| [adrianmikula/AgentSkills](https://github.com/adrianmikula/AgentSkills) | Claude plugins/skills (security, outreach) — compatible `.agents` standard |
| [everyinc/compound-engineering-plugin](https://github.com/everyinc/compound-engineering-plugin) | Devin plugin mẫu (compound engineering methodology) |

---

## 7. Tools & Libraries referenced

| Tool | Mục đích | Referenced in |
|------|----------|---------------|
| ChromaDB | Vector database cho hybrid search | `chroma-hybrid-search/SKILL.md` |
| BGE-Reranker | Reranker cho hybrid search | `chroma-hybrid-search/SKILL.md` |
| BM25 | Keyword search cho hybrid search | `chroma-hybrid-search/SKILL.md` |
| tree-sitter | AST-precise comment inventory | `harness-sensor.md` |
| uncomment | AST-precise comment checker (optional external) | `harness-sensor.md` |
| aide-memory | Persistent cross-session memory (Devin-native MCP) | `.devin/mcp_config.json` |
| spark-memory | Shared community memory (MCP plugin) | spark-mcp plugin |
| DeepWiki | AI-powered GitHub repo documentation (MCP) | yellow-devin plugin |

---

## 8. arXiv Papers referenced trong canon

| arXiv ID | Title (short) | Referenced in |
|----------|---------------|---------------|
| 2605.02741 | Volume-Quality Inverse Law (comment bloat predicts structural decay) | `CORE_CANON.md`, `REDLINES.md`, `harness-sensor.md` |
| 2512.20334 | Comment Traps (commented-out/defective comments propagate defects up to 58%) | `REDLINES.md` |
| 2606.09090 | Context Rot (in-file version stacking causes recursive-depth debt) | `REDLINES.md` |
| 2306.05685 | LLM-as-judge self-preference (models score own writing higher) | `VERIFICATION_PROTOCOL.md` |
| 2404.13076 | Familiarity bias in LLM judges | `VERIFICATION_PROTOCOL.md` |

---

## 9. Documentation Sources (Devin CLI + GLM + community)

### Devin CLI docs chính thức

| Doc | URL |
|-----|-----|
| Config reference | https://docs.devin.ai/cli/reference/configuration/config-file |
| Models | https://docs.devin.ai/cli/models |
| Rules & AGENTS.md | https://docs.devin.ai/cli/extensibility/rules |
| Skills overview | https://docs.devin.ai/cli/extensibility/skills/overview |
| Subagents | https://docs.devin.ai/cli/subagents |
| Plugins | https://docs.devin.ai/cli/extensibility/plugins |
| MCP configuration | https://docs.devin.ai/cli/extensibility/mcp/configuration |
| Hooks | https://docs.devin.ai/cli/extensibility/hooks |
| Global vs local | https://docs.devin.ai/cli/reference/configuration/global-vs-local |
| Changelog | https://docs.devin.ai/cli/changelog/stable |

### GLM best practices

| Nguồn | Takeaway |
|-------|----------|
| [GLM-5 system prompt research (gist)](https://gist.github.com/apnea/e9dd7a650bdc3300375fffc54592f48d) | Stable system prompts cho cache hits, concise > verbose |
| [Cline GLM-4.6 tuning](https://cline.bot/blog/cline-our-commitment-to-open-source-zai-glm-4-6) | Short explicit mechanically-precise instructions, explore→summarize→implement |
| [Booststash GLM-5.2 coding guide](https://www.booststash.com/how-to-use-glm-5-2-for-coding/) | Start with planning prompt (40% fewer correction cycles), self-review after implement |
| [Sider GLM-4.6 explained](https://sider.ai/blog/ai-tools/glm-4_6-explained-without-the-hype-what-s-actually-new-and-how-to-use-it) | Constraints > cleverness, decomposition, externalized memory, verification hooks |

### Community articles (AHD canon attributions)

| Nguồn | Topic |
|-------|-------|
| https://vocus.cc/article/6a10254ffd897800017eaac1 | Caveman token compression |
| https://www.reddit.com/r/ClaudeAI/comments/1sble09/ | Caveman Reddit discussion |
| https://www.threads.com/@krumjahn/post/DaZuvrPm6Fw | Agency-agents discussion |
| https://substack.com/@rumjahn | Rumjahn Substack (agency-agents author) |
| https://loops.elorm.xyz/ | Loop engineering |
| https://kevintsai1202.github.io/deep-memory/ | Deep-memory docs |
| https://agentskills.io | Agent Skills protocol standard |
| https://skills.sh | skills.sh compatibility |

---

## 10. Removed — Repos đã loại bỏ (Ruflo cleanup journey)

| Repo | Lý do removed |
|------|---------------|
| ruvnet/claude-flow (Ruflo upstream) | Không tương thích Devin CLI — toàn bộ v3/ source (8942 files, 371 MB) đã `git rm` |
| ruvnet/ruflo (Ruflo core) | Không tương thích — 556 files đã `git rm` |
| 35 ruflo Claude Code plugins | Không tương thích — 599 files đã `git rm` |

> Chi tiết cleanup: xem section "Đã loại bỏ (redteam cleanup)" trong `AGENTS.md`.

---

## Cập nhật

| Ngày | Thay đổi |
|------|----------|
| 2026-08-04 | Tạo REPOS.md — master reference list từ inventory toàn workspace |
