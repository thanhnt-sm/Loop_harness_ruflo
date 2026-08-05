# Devin CLI — Agent Harness Deploy + Lightning/GLM Orchestrators

## Kiến trúc chính: Agent Harness Deploy (AHD)

Workspace sử dụng **Agent Harness Deploy** (masteryee-labs/Tool.Agent-Harness-Deploy) làm **động cơ chính, kiến trúc chính, giải pháp chính**. AHD là self-deploying cross-tool AI harness — deploy canonical rules + skills + orchestrator + memory protocol + hooks vào `.devin/`.

### AHD cung cấp

| Layer | Location | Mục đích |
|-------|----------|----------|
| Canon (universal rules) | `.devin/canon/` | 10 protocol files: BOOT, MEMORY, LOOP, VERIFICATION, CAVEMAN, REDLINES, HARNESS_ENGINEERING, JUDGMENT_RUBRICS, HANDOFF_LETTER, CORE_CANON |
| Orchestrator | `.devin/agents/COMMANDER.md` + personas/ + workers/ | Commander + Worker persona system (architect, code_reviewer, database_optimizer, devops_automator, frontend_developer, git_workflow_master) |
| Skills (AHD) | `.devin/skills/*.md` + `nuwa-skill/` + `chroma-hybrid-search/` + `domain-adapters/` | 16 harness skills: auditor, claim-grader, comment_checker, context-compactor, fable-judge, gap-scan, graph-verify, harness-sensor, init_deep, loop-memory, memory-audit, slop-detector, systematic_debugging, tdd, user-preference, using-skills |
| Runtime hooks | `.devin/hooks/` | Python hooks: pre_tool_use.py, post_tool_use.py, stop.py, ahd_session.py |
| Runtime scripts | `.devin/scripts/` | 7 scripts: worktree.py, plan_dispatch.py, session_manager.py, loop_memory_sync.py, memory_audit.py, pre_task_audit.py, ahd_session.py |
| Session state | `.devin/session_state/`, `.devin/loop_state/`, `.devin/context_flags/` | Per-session machine state + human state |
| Shared state | `.agents/` | loop_state.md (registry), knowledge_distill.md (anti-patterns), user_profile.md (preferences) |
| Project rules | `.devin/rules/` | Project-owned, AHD không overwrite |
| Entry file | `.devin/AGENTS.md` | Auto-generated từ canon — 186KB canonical harness body |
| Vault | `.devin/skills/assets/vault/` | Anti-link-rot templates: caveman_template.json, strix_security_rules.json, memory_mcp_schema.json |

### AHD canonical protocols (10 files trong `.devin/canon/`)

| Protocol | Mục đích |
|----------|----------|
| `CORE_CANON.md` | Tool-agnostic source of truth — identity, operating principles, deploy contract |
| `BOOT_PROTOCOL.md` | 17-step startup sequence — registry, knowledge, profile, GoalSpec |
| `MEMORY_PROTOCOL.md` | 3-layer memory: hot registry, hot session, knowledge + cold archive |
| `LOOP_PROTOCOL.md` | Loop/goal primitives, stop conditions, idle-yank |
| `VERIFICATION_PROTOCOL.md` | Maker ≠ checker, read-back verification, CLI gates |
| `CAVEMAN_PROTOCOL.md` | Token compression style (~65% reduction) |
| `HARNESS_ENGINEERING.md` | Design principles for agent-facing systems |
| `JUDGMENT_RUBRICS.md` | Externalized decision criteria |
| `HANDOFF_LETTER.md` | Letter to future sessions |
| `REDLINES.md` | Hard stops — violating → stop, ask human |

### AHD orchestrator: Commander + Workers

```
Commander (main thread)
├── SCOUT (worker) — scan/discover
├── BUILDER (worker) — implement
├── AUDITOR (worker) — verify
├── VERIFIER (worker) — independent check
├── MEMORY_KEEPER (worker) — persist state
└── Nuwa cognitive angles — Munger/Feynman/Taleb verification
```

Personas: `architect`, `code_reviewer`, `database_optimizer`, `devops_automator`, `frontend_developer`, `git_workflow_master`

## Tích hợp với existing stack

AHD là **main engine**. Existing components được bảo vệ và tích hợp:

| Component | Vai trò | Bảo vệ |
|-----------|---------|--------|
| `/lightning` + `/glm` skills | Devin-native subagent orchestrators | `.devin/skills/lightning/`, `.devin/skills/glm/` — không overwrite |
| `lightning-executor` + `glm-executor` agents | Pinned model executors | `.devin/agents/lightning-executor/`, `.devin/agents/glm-executor/` — không overwrite |
| HLK security layer | PreToolUse hook (sanitizer + vault-bridge) | `HLK/` — config.json hooks preserved |
| aide-memory MCP | Persistent cross-session memory | `.devin/mcp_config.json` — không đụng |
| aide-memory hooks | SessionStart/Stop/PreToolUse/PostToolUse | config.json hooks preserved + merged với AHD hooks |

### Config merge strategy

AHD deployer **không phải deep merge** — nó ghi đè permissions + hooks. Đã manually merge:
- HLK hook launcher (exec matcher) — **giữ nguyên**
- AHD pre_tool_use.py (exec matcher) — **thêm vào** cùng matcher
- aide-memory hooks (read/edit/write/grep/glob/mcp matchers) — **giữ nguyên**
- AHD post_tool_use.py (empty matcher) + AgentStop — **thêm vào**
- Permissions: AHD `Bash()` format + Devin `Exec()` format — **hợp nhất cả hai**

## Orchestrator skills: /lightning + /glm

Workspace có **2 orchestrator skills** — cùng pattern (planner + executor), khác model executor:

| Skill | Orchestrator | Executor | Model | Cost | Context |
|-------|-------------|----------|-------|------|---------|
| `/lightning` | Active Devin model | `lightning-executor` | SWE-1.7 Lightning | $2.5/$12.5 MTok | 202K |
| `/glm` | Active Devin model | `glm-executor` | GLM-5.2 High | **Free** (capable tier) | 200K |

**Khi nào dùng cái nào?**
- `/lightning` — khi cần tốc độ (SWE-1.7 Lightning tối ưu cho code, 1000 tok/s)
- `/glm` — khi cần free tier hoặc GLM-5.2 reasoning chất lượng cao
- Cả 2 cùng pattern: orchestrator plan/review, executor implement/test/report

> **Note**: GLM-5.2 là **"capable tier"** (frontier capability tại budget price, ~Opus-4.8 class) — không phải "cheap and dumb". Phù hợp cho high-stakes reasoning, security review, deep judgment, dù cost thấp. (Nguồn: outsourcerer repo)

## Cách dùng

```bash
# Mở Devin CLI tại workspace
cd .
devin

# Non-interactive
devin -p -- "mô tả công việc"

# Gọi skill lightning trực tiếp
/lightning <software-engineering task>

# Gọi skill glm trực tiếp
/glm <software-engineering task>

# AHD skills (tự invoke khi relevant)
/nuwa-skill <tên người/subject> — cognitive diversity verification
/tdd — test-driven development
/auditor — audit code
/gap-scan — differential gap scan
/slop-detector — detect AI slop
```

## Ví dụ

```text
/lightning add pagination to the users endpoint and update its tests
/lightning reproduce and fix the checkout total rounding bug
/lightning refactor the cache adapter without changing its public API

/glm add input validation to the checkout form and update its tests
/glm review the auth module for security issues
/glm write tests for src/utils.js, coverage > 80%

/nuwa-skill Munger — verify investment logic from Munger's perspective
/tdd write tests for src/utils.js, coverage > 80%
```

## Luồng công việc `/lightning` và `/glm`

Cả 2 skill cùng pattern:

1. **Frame task** — trích objective, acceptance criteria, constraints, validation needs
2. **Preflight** — parallel reads: working-tree status, repo instructions, build scripts
3. **Dispatch** — `run_subagent(profile: lightning-executor|glm-executor, is_background: false)` với work order tự chứa
4. **Review** — inspect diff độc lập, treat report as evidence not proof
5. **Correct** — trivial fix trực tiếp; lớn hơn thì `resume` cùng executor. Sau 2 resume không tiến triển → stop, hỏi user
6. **Report** — what changed, key files, verification outcome, residual risks

## Guardrails (luôn áp dụng)

- Smallest coherent diff — không scope creep
- Preserve pre-existing user changes — không revert/overwrite
- No destructive ops — chặn bởi `.devin/hooks/pre_tool_use.py` + config.json deny list (rm -rf, git push --force, git reset --hard, drop table, v.v.)
- No unrelated refactors, dependencies, generated files, documentation
- No weakening tests/security/typing/lint để pass check
- Trivial edits (vài dòng rõ ràng) sửa thẳng, skip delegation
- Fan-out chỉ khi write sets disjoint + user yêu cầu
- Background executor không thể prompt approval → resume foreground nếu denied
- Nếu `lightning-executor` hoặc `glm-executor` unavailable → stop, report missing profile

## MCP servers

| MCP server | Nguồn | Mục đích | Tools |
|------------|-------|----------|-------|
| `aide-memory` | `.devin/mcp_config.json` (local stdio) | Persistent memory — recall/remember/search theo file scope | `mcp__aide-memory__aide_recall`, `mcp__aide-memory__aide_remember`, `mcp__aide-memory__aide_search`, v.v. |
| `spark-memory` | spark-mcp plugin (remote HTTP) | Shared memory cộng đồng cross-agent | `mcp__spark-memory__*` |
| `deepwiki` | yellow-devin plugin (remote HTTP, free) | Query documentation GitHub repos | `mcp__deepwiki__*` |
| `devin` | yellow-devin plugin (remote HTTP) | Devin V3 API: session management, playbooks | `mcp__devin__*` (cần `DEVIN_SERVICE_USER_TOKEN` + `DEVIN_ORG_ID`) |

## Plugins đã cài

| Plugin | Version | Cung cấp |
|--------|---------|----------|
| `yellow-devin` | v2.3.7 | 9 commands `/devin:*`, devin-orchestrator agent, DeepWiki + Devin MCP |
| `spark-mcp` | v0.4.0 | Spark shared memory MCP (cần `devin mcp login spark-memory`) |

## Skills trong `.devin/skills/`

### Devin-native skills (existing)

| Skill | Triggers | Mục đích |
|-------|----------|----------|
| `lightning` | `[user]` | Execution — planner + SWE-1.7 Lightning executor |
| `glm` | `[user]` | Execution — planner + GLM-5.2 executor (free tier) |
| `aide-memory` | `[user, model]` | Persistent memory — recall/remember theo file scope |
| `hlk-git-tools` | `[user]` | Commit/push an toàn qua HLK layer |
| `hlk-integrity-check` | `[user]` | Kiểm tra HLK layer sau upstream merge |

### AHD harness skills (deployed)

| Skill | Mục đích |
|-------|----------|
| `nuwa-skill` | Cognitive diversity verification — Munger/Feynman/Taleb perspectives |
| `chroma-hybrid-search` | Deep-memory hybrid search (BM25 + vector + reranker) |
| `auditor` | Audit code quality |
| `claim-grader` | Grade claims: [fact] / [inference] / [unverified-guess] |
| `comment_checker` | Check comment discipline (comments are debt) |
| `context-compactor` | Compress context (caveman mode) |
| `fable-judge` | Judge fables (narrative verification) |
| `gap-scan` | Differential gap scan (scope angles) |
| `graph-verify` | Verify knowledge graph |
| `harness-sensor` | Detect harness state |
| `init_deep` | Large-repo init (build code graph) |
| `loop-memory` | Loop memory sync |
| `memory-audit` | Audit memory (candidate → knowledge) |
| `slop-detector` | Detect AI slop |
| `systematic_debugging` | Systematic debugging protocol |
| `tdd` | Test-driven development |
| `user-preference` | User preference learning |
| `using-skills` | How to use skills |
| `domain-adapters/*` | Domain-specific adapters: coding, data, devops, design, finance, legal, marketing, research, business-ops |

## Custom subagents trong `.devin/agents/`

### Devin-native executors (existing)

| Profile | Model | Vai trò |
|---------|-------|---------|
| `lightning-executor` | swe-1.7-lightning | Implementation executor cho `/lightning` |
| `glm-executor` | glm-5-2 | Implementation executor cho `/glm` (free tier) |

### AHD orchestrator (deployed)

| File | Vai trò |
|------|---------|
| `COMMANDER.md` | Commander persona — main thread decides, dispatches, integrates |
| `DISPATCH_TEMPLATES.md` | Dispatch templates cho worker personas |
| `model_tiers.md` | Model tier routing (Tier 1/2/3) |
| `PERSONA_TEMPLATE.md` | Template để tạo persona mới |
| `personas/architect.md` | System + backend architecture persona (merged from backend_architect + software_architect) |
| `personas/code_reviewer.md` | Code review persona |
| `personas/database_optimizer.md` | Database optimization persona |
| `personas/devops_automator.md` | DevOps automation persona |
| `personas/frontend_developer.md` | Frontend development persona |
| `personas/git_workflow_master.md` | Git workflow persona |
| `workers/AUDITOR.md` | Auditor worker — verify |
| `workers/BUILDER.md` | Builder worker — implement |
| `workers/MEMORY_KEEPER.md` | Memory keeper worker — persist state |
| `workers/SCOUT.md` | Scout worker — scan/discover |
| `workers/VERIFIER.md` | Verifier worker — independent check |

## Đã loại bỏ (redteam cleanup)

| Thành phần | Lý do | Hành động |
|------------|-------|-----------|
| `.agents/skills/` (137 skills) | Claude Code specific (`$agent-<name>` pattern) | Moved → `.agents/skills-disabled/` |
| `.claude/skills/` (42 skills) | Claude Flow/Ruflo specific (agentdb, flow-nexus, dual-mode) | Moved → `.claude/skills-disabled/` |
| Root `CLAUDE.md` (68KB) | Claude-specific swarm/dual-mode/Task tool content | Replaced → 1.9KB universal rules |
| `Read(.claude/**)` in config | Claude-specific path | Removed from allow list |
| `Exec(devin)` broad permission | Too permissive | Narrowed → specific subcommands |
| 2 separate PreToolUse hook entries | Duplicate matcher | Merged → 1 entry with 2 hooks |
| HLK skills missing `triggers` | Could auto-invoke, conflict with lightning | Added `triggers: [user]` |
| `v3/` source (8942 files, 371 MB) | Upstream ruflo source — không tương thích Devin | `git rm -r` + `.gitignore` |
| `plugins/` (599 files) | 35 ruflo Claude Code plugins — không tương thích Devin | `git rm -r` + `.gitignore` |
| `ruflo/` source (556 files) | Ruflo core source — không tương thích Devin | `git rm -r` + `.gitignore` |
| `scripts/` (~100 files) | Ruflo dev scripts (audit, smoke, benchmark) — reference removed source | `git rm -r` + `.gitignore` |
| `.claude-flow/`, `.claude-plugin/`, `docs/`, `verification/`, `services/`, `tests/`, `crates/` | Ruflo runtime artifacts + docs — không cần cho Devin | `git rm -r` + `.gitignore` |
| Root ruflo files (SKILL.md, Cargo.toml, README.md, CHANGELOG.md, v.v.) | Upstream ruflo project files | `git rm` + `.gitignore` |
| `package.json` workspaces + 7 broken scripts | Referenced removed v3/ source | Removed from scripts |
| Ruflo MCP server (`claude-flow`) + `node_modules/ruflo/` | Replaced by aide-memory (Devin-native) | Removed MCP config entry + node_modules |
| `hlk-upstream-pull` skill | Ruflo upstream đã remove — skill legacy | `git rm` |
| `ruflo-autopilot` skill | Legacy MCP orchestration — replaced by /lightning + /glm | `git rm` |
| `package-lock.json` (491 KB) | Stale ruflo dependency tree | `git rm` — will regenerate if needed |
| `package.json` ruflo manifest (212 lines) | All ruflo deps, workspaces, bin, files array | Replaced → 20-line minimal manifest |
| `.devin/hooks.v1.json` | Old hooks file — merged into `.devin/config.json` | Merged exec blocker + removed file |
| `.claude/` toàn bộ (374 files) | Toàn bộ Claude Code config ruflo-specific (settings.json, agents/, commands/, workflows/, helpers/, skills-disabled/, mcp.json, memory.db, statusline) | `git rm -r` + `Remove-Item` |
| HLK ruflo scripts (hlk-setup-max-power, hlk-update-max-power, hlk-devin-autopilot, hlk-agy-autopilot, hlk-lifecycle, ruflo-hlk wrappers) | Ruflo-specific install/autopilot scripts — không cần cho Devin | `git rm` |
| Launcher "Ruflo Autopilot" labels | Stale ruflo branding trong devin-run/devin-swe scripts | Cleaned → "Devin CLI" |
| HLK config `ruflo_version_tested` + "Ruflo Workspace" | Stale ruflo references trong hlk.config.json | Removed |

## Tham khảo đầy đủ

> **Master reference list**: xem [`REPOS.md`](./REPOS.md) — toàn bộ GitHub repos, documentation, papers, tools được tham khảo/sử dụng/học hỏi (AHD engine + vendored skills + canon sources + vault templates + Nuwa ecosystem + Devin CLI ecosystem + GLM best practices + removed repos).

## Đóng gói + Deploy sang dự án mới

Workspace có hệ thống đóng gói trong `tools/` — cho phép export workspace hiện tại thành template sạch, deploy sang dự án mới với 1 lệnh.

### Quick start

```powershell
# One-shot: package + deploy + git init + verify
.\tools\init-new-project.ps1 -TargetPath D:\projects\my-new-app

# Từng bước:
.\tools\package-template.ps1                              # → harness-template.zip (clean, templated)
.\tools\deploy-template.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-new-app
.\tools\verify-workspace.ps1 -WorkspaceRoot D:\projects\my-new-app

# Clean runtime state (wipe session/memories/loop_state)
.\tools\clean-runtime.ps1
```

### Files trong `tools/`

| File | Mục đích |
|------|----------|
| `init-new-project.ps1` | **One-shot orchestrator** — package + deploy + git init + verify + print hướng dẫn |
| `package-template.ps1` | Đóng gói workspace → `harness-template.zip` (clean runtime, templated config) |
| `deploy-template.ps1` | Deploy template → dự án mới (resolve placeholders, git init) |
| `verify-workspace.ps1` | Verify integrity — 73 checks (canon, skills, agents, hooks, scripts, vault, config, HLK) |
| `clean-runtime.ps1` | Wipe runtime state (session, memories, loop_state, context_flags) |
| `FULL_POWER_PROMPT.md` | **One-shot prompt** — paste vào Devin CLI → tự động chạy full harness chain (BOOT → inventory → Commander → decompose → dispatch parallel subagents → integrate → verify → Nuwa cognitive → claim grade → slop check → memory write-back → report) |
| `README.md` | Documentation đầy đủ cho packaging system |

### Template bao gồm gì (reusable)

- 10 canon protocols, COMMANDER + 7 personas + 5 workers + 2 executors
- 21+ skills (16 AHD + 5 Devin-native + nuwa-skill + chroma-hybrid-search + 9 domain-adapters)
- 4 Python hooks, 7 runtime scripts, 5 vault templates
- HLK security layer (sanitizer + vault-bridge + git-tools)
- config.json + mcp_config.json (templated placeholders, auto-resolved on deploy)
- AGENTS.md, CLAUDE.md, REPOS.md, .gitignore, package.json
- .github/ (ISSUE_TEMPLATE, CODEOWNERS, dependabot, workflows)

### Loại bỏ gì (KHÔNG mang sang dự án mới)

- `.git/` (new project starts fresh), `.tools/`, `node_modules/`
- `.claude/`, `.cursor/` (runtime, gitignored)
- `HLK/reports/`, `HLK/logs/` (project-specific)
- `.github/issues/`, `.github/supply-chain/` (project-specific)
- `.aide/memories/*`, `.devin/session_state/`, `.devin/loop_state/`, `.devin/context_flags/` (runtime state, wiped)

### Placeholders (auto-resolved bởi deploy-template.ps1)

| Placeholder | Thay bằng |
|-------------|-----------|
| `{{WORKSPACE_ROOT}}` | Absolute path to new project |
| `{{AIDE_MEMORY_GLOBAL}}` | Global `node_modules/aide-memory` path |
| `{{AIDE_MEMORY_CLI}}` | `aide-memory/dist/memory/cli.js` path |
| `{{NODE_EXE}}` | `node.exe` path |

### FULL_POWER_PROMPT — Cách dùng

```bash
cd D:\projects\my-new-app
devin
# Paste nội dung tools/FULL_POWER_PROMPT.md + thay <TASK> bằng task của bạn
```

Prompt trigger 13-step chain: BOOT → INVENTORY → COMMANDER MODE → TASK FRAMING → GAP SCAN → DECOMPOSE + DISPATCH (parallel subagents) → INTEGRATE → VERIFY → NUWA COGNITIVE → CLAIM GRADING → SLOP CHECK → MEMORY WRITE-BACK → REPORT.

> Chi tiết: xem [`tools/README.md`](./tools/README.md)

## Phạm vi an toàn cho code changes

- `src/` — source code dự án
- `.devin/skills/`, `.devin/agents/` — định nghĩa skill/agent
- `scripts/` — utility scripts
- **KHÔNG đụng**: `HLK/` (security layer), security policies, `.env`

## Best practices (từ Devin docs + community research)

### Rules vs Skills

> **Devin docs khuyến nghị**: "Rules and AGENTS should be kept as small as possible. To improve coding ability, speed, and lower cost, use Skills instead whenever possible. Skills are only injected into context when relevant."

- `AGENTS.md` + `CLAUDE.md` = always-on context → giữ **minimal** (mỗi token đều được load mỗi session)
- Skills = on-demand context → chỉ inject khi relevant → **prefer skills cho domain knowledge**
- Pattern khuyến nghị: rule ngắn tham chiếu skill, skill chứa detail

### Subagent model pinning

| Profile | Model | Cost |
|---------|-------|------|
| `subagent_explore` | Default subagent model (SWE-1.6) | Cheap — billed at SWE rates |
| `subagent_general` | Same as parent (Opus, GPT-5, v.v.) | Same rate as parent — fans out = multiplies spend |
| Custom (`lightning-executor`, `glm-executor`) | `model:` trong AGENT.md | Dependent on pinned model |

- **Research/exploration** → dùng `subagent_explore` (cheap)
- **Code changes** → dùng custom executor với model pinned (lightning = SWE-1.7, glm = GLM-5.2 free)
- **Không** spawn `subagent_general` cho research — tốn premium tokens
- `model:` trong AGENT.md là **cách duy nhất** chạy write-capable subagent trên model khác parent

### GLM-5.2 prompting (từ Cline + Z.AI + community)

GLM-5.2 trained trên agentic trajectories — hiểu tool-use và code-editing workflows implicitly:

1. **Concise prompts > verbose** — GLM-5.2 tuned cho conciseness, verbose prompts "fight the training"
2. **Explore → Summarize → Implement** — structured workflow bắt buộc: đọc code trước, tóm tắt, rồi mới sửa
3. **Constraints over Cleverness** — spell out target format, acceptance tests, failure conditions
4. **Decomposition Over Monologues** — parse → plan → execute → verify
5. **Externalized Memory** — dùng aide-memory thay bắt model nhớ qua long context
6. **Verification Hooks** — second pass review catch dumb mistakes (orchestrator review executor's diff)
7. **Stable system prompts** — Z.AI prefix-based caching, system prompt identical across requests = cache hits
8. **Explicit invocation rules** — GLM có thể hallucinate tool params, cần tight prompting around invocation scope

### SWE-1.7 Lightning prompting

- Tối ưu cho code, 1000 tok/s — fast iteration
- Pattern planner + executor: orchestrator (premium model) plan/review, Lightning execute
- Work order tự chứa (self-contained) — executor không thấy conversation, cần full context
- `resume` cùng executor cho follow-up — giữ prompt cache warm, skip rediscovery

### Permissions (từ Devin docs)

```json
{
  "permissions": {
    "allow": ["Read(**)", "Exec(git status)", "Exec(git diff)", "Exec(git log)"],
    "deny": ["Exec(rm -rf)", "Exec(git push --force)", "Exec(git reset --hard)"],
    "ask": ["Exec(git commit)", "Exec(git push)", "Exec(npm publish)"]
  }
}
```

- `allow` — auto-approve safe operations (giảm approval fatigue)
- `deny` — hard-block destructive (rm -rf, force-push, drop table)
- `ask` — prompt before sensitive (commit, push, publish)
- Scope: project `.devin/config.json` (team) > `.devin/config.local.json` (personal) > user global

## Tham khảo (awesome-devin)

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

### GitHub repos hữu ích cho Devin CLI

| Repo | Mục đích |
|------|----------|
| [jsklan/devin-api-mcp](https://github.com/jsklan/devin-api-mcp) | MCP server wrap full Devin API (v1+v3+deepwiki proxy) |
| [mjinno09/devin-mcp](https://github.com/mjinno09/devin-mcp) | Rust MCP cho Devin session management |
| [ldastey-dev/devin-mcp](https://github.com/ldastey-dev/devin-mcp) | Python MCP wrap v1+v2+v3beta1 multi-org |
| [desertaxle/devin-mcp](https://github.com/desertaxle/devin-mcp) | Python MCP delegate tasks to Devin |
| [adw0rd/awesome-mcp-tools-mcp](https://github.com/adw0rd/awesome-mcp-tools-mcp) | CLI + MCP bridge cho 2000+ MCP servers catalog |
| [adrianmikula/AgentSkills](https://github.com/adrianmikula/AgentSkills) | Claude plugins/skills (security, outreach) — compatible `.agents` standard |
| [everyinc/compound-engineering-plugin](https://github.com/everyinc/compound-engineering-plugin) | Devin plugin mẫu (compound engineering methodology) |

### GLM best practices

| Nguồn | Takeaway |
|-------|----------|
| [GLM-5 system prompt research (gist)](https://gist.github.com/apnea/e9dd7a650bdc3300375fffc54592f48d) | Stable system prompts cho cache hits, concise > verbose |
| [Cline GLM-4.6 tuning](https://cline.bot/blog/cline-our-commitment-to-open-source-zai-glm-4-6) | Short explicit mechanically-precise instructions, explore→summarize→implement |
| [Booststash GLM-5.2 coding guide](https://www.booststash.com/how-to-use-glm-5-2-for-coding/) | Start with planning prompt (40% fewer correction cycles), self-review after implement |
| [Sider GLM-4.6 explained](https://sider.ai/blog/ai-tools/glm-4_6-explained-without-the-hype-what-s-actually-new-and-how-to-use-it) | Constraints > cleverness, decomposition, externalized memory, verification hooks |

## Red Team Report + Upgrade Plan

Workspace đã qua red team exercise (7-expert council). Kết quả và kế hoạch nâng cấp:

| Tài liệu | Đường dẫn | Mục đích |
|----------|-----------|----------|
| Red Team Report | `HLK/docs/REDTEAM_REPORT.md` | Báo cáo tấn công toàn diện từ 7 chuyên gia (Security, Token, Quality, Architecture, Performance, Flow, Cognitive) |
| Upgrade Plan | `HLK/docs/UPGRADE_PLAN.md` | 40 upgrades chi tiết với spec, acceptance criteria, verification steps, dependency graph |
| Upgrade Tracker | `.devin/upgrade/UPGRADE_TRACKER.json` | Progress tracking persist qua nhiều session — source of truth cho upgrade status |
| Execution Protocol | `.devin/upgrade/UPGRADE_EXECUTION_PROTOCOL.md` | Quy tắc thực thi nhiều vòng không drift — 13-step quick card, quality gates, rollback flow |

### Trạng thái hiện tại

| Phase | Tổng | Done | Pending | Target |
|-------|------|------|---------|--------|
| P0 (Critical) | 10 | 0 | 10 | 1-2 tuần |
| P1 (High) | 15 | 0 | 15 | 1 tháng |
| P2 (Medium) | 15 | 0 | 15 | 3 tháng |
| P3 (Low) | 10 | 0 | 10 | As time permits |

### Cách thực thi upgrade

1. Đọc `.devin/upgrade/UPGRADE_TRACKER.json` → tìm upgrade `status: "pending"` tiếp theo
2. Đọc spec trong `HLK/docs/UPGRADE_PLAN.md` (tìm `## UXX`)
3. Thực thi theo `UPGRADE_EXECUTION_PROTOCOL.md` (13-step quick card)
4. Update tracker sau khi done + commit
