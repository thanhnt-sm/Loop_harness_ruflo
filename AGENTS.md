# Devin CLI — Lightning + GLM Orchestrators

## Kiến trúc

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
```

## Ví dụ

```text
/lightning add pagination to the users endpoint and update its tests
/lightning reproduce and fix the checkout total rounding bug
/lightning refactor the cache adapter without changing its public API

/glm add input validation to the checkout form and update its tests
/glm review the auth module for security issues
/glm write tests for src/utils.js, coverage > 80%
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
- No destructive ops — chặn bởi `.devin/hooks.v1.json` (rm -rf, git push --force, git reset --hard, drop table, v.v.)
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

| Skill | Triggers | Mục đích |
|-------|----------|----------|
| `lightning` | `[user]` | Execution — planner + SWE-1.7 Lightning executor |
| `glm` | `[user]` | Execution — planner + GLM-5.2 executor (free tier) |
| `aide-memory` | `[user, model]` | Persistent memory — recall/remember theo file scope |
| `hlk-git-tools` | `[user]` | Commit/push an toàn qua HLK layer |
| `hlk-integrity-check` | `[user]` | Kiểm tra HLK layer sau upstream merge |

## Custom subagents trong `.devin/agents/`

| Profile | Model | Vai trò |
|---------|-------|---------|
| `lightning-executor` | swe-1.7-lightning | Implementation executor cho `/lightning` |
| `glm-executor` | glm-5-2 | Implementation executor cho `/glm` (free tier) |

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

## Phạm vi an toàn cho code changes

- `src/` — source code dự án
- `.devin/skills/`, `.devin/agents/` — định nghĩa skill/agent
- `scripts/` — utility scripts
- **KHÔNG đụng**: `HLK/` (security layer), security policies, `.env`
