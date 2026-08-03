# Devin CLI — Lightning Orchestrator

## Kiến trúc

Workspace dùng **lightning-orchestrator** (dabit3/lightning-orchestrator) — skill tách 2 role:

| Role | Model | Trách nhiệm |
|------|-------|-------------|
| **Orchestrator** | Active Devin model | Hiểu request, ra quyết định, tạo work order, review diff |
| **lightning-executor** | SWE-1.7 Lightning (1000 tok/s) | Inspect code, implement, chạy checks, báo cáo evidence |

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
```

## Luồng công việc `/lightning`

1. **Frame task** — trích objective, acceptance criteria, constraints, validation needs
2. **Preflight** — parallel reads: working-tree status, repo instructions, build scripts
3. **Dispatch** — `run_subagent(profile: lightning-executor, is_background: false)` với work order tự chứa
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
- Nếu `lightning-executor` unavailable → stop, report missing profile

## MCP servers

| MCP server | Nguồn | Mục đích | Tools |
|------------|-------|----------|-------|
| `claude-flow` | `.devin/mcp_config.json` (local stdio) | Ruflo MCP — memory, swarm, agent tracking | `mcp__claude-flow__memory_search`, `mcp__claude-flow__memory_store`, `mcp__claude-flow__swarm_init`, v.v. |
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
| `lightning` | `[user]` | Execution chính — planner + executor |
| `hlk-git-tools` | `[user]` | Commit/push an toàn qua HLK layer |
| `hlk-integrity-check` | `[user]` | Kiểm tra HLK layer sau upstream merge |
| `hlk-upstream-pull` | `[user]` | Pull upstream ruflo + reinstall HLK |
| `ruflo-autopilot` | `[]` (disabled) | Legacy Ruflo MCP-only orchestration |

## Custom subagents trong `.devin/agents/`

| Profile | Model | Vai trò |
|---------|-------|---------|
| `lightning-executor` | swe-1.7-lightning | Implementation executor cho `/lightning` |

## Đã loại bỏ (redteam cleanup)

| Thành phần | Lý do | Hành động |
|------------|-------|-----------|
| `.agents/skills/` (137 skills) | Claude Code specific (`$agent-<name>` pattern) | Moved → `.agents/skills-disabled/` |
| `.claude/skills/` (42 skills) | Claude Flow/Ruflo specific (agentdb, flow-nexus, dual-mode) | Moved → `.claude/skills-disabled/` |
| Root `CLAUDE.md` (68KB) | Claude-specific swarm/dual-mode/Task tool content | Replaced → 1.2KB universal rules |
| `Read(.claude/**)` in config | Claude-specific path | Removed from allow list |
| `Exec(devin)` broad permission | Too permissive | Narrowed → specific subcommands |
| 2 separate PreToolUse hook entries | Duplicate matcher | Merged → 1 entry with 2 hooks |
| HLK skills missing `triggers` | Could auto-invoke, conflict with lightning | Added `triggers: [user]` |

## Phạm vi an toàn cho code changes

- `v3/` — source code Ruflo
- `src/` — source code dự án
- `.devin/skills/`, `.devin/agents/` — định nghĩa skill/agent
- `scripts/` — utility scripts
- **KHÔNG đụng**: `HLK/` (security layer), `.claude/` (Claude Code config), security policies, `.env`
