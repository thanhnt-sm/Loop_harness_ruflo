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
5. **Correct** — trivial fix trực tiếp; lớn hơn thì `resume` cùng executor (giữ cache ấm). Sau 2 resume không tiến triển → stop, hỏi user
6. **Report** — what changed, key files, verification outcome, residual risks

## Guardrails (luôn áp dụng)

- Smallest coherent diff — không scope creep
- Preserve pre-existing user changes — không revert/overwrite
- No destructive ops, push, publish, external side effects without explicit approval
- No unrelated refactors, dependencies, generated files, documentation
- No weakening tests/security/typing/lint để pass check
- Trivial edits (vài dòng rõ ràng) sửa thẳng, skip delegation
- Fan-out chỉ khi write sets disjoint + user yêu cầu
- Background executor không thể prompt approval → resume foreground nếu denied
- Nếu `lightning-executor` unavailable → stop, report missing profile (không substitute model khác)

## MCP servers (qua plugins + Ruflo)

| MCP server | Nguồn | Mục đích |
|------------|-------|----------|
| `claude-flow` | Ruflo MCP (local) | memory_search, memory_store, swarm tools |
| `spark-memory` | spark-mcp plugin | Shared memory cộng đồng cross-agent |
| `deepwiki` | yellow-devin plugin | Query documentation GitHub repos (free) |
| `devin` | yellow-devin plugin | Devin V3 API: session management, playbooks |

## Plugins đã cài

| Plugin | Version | Cung cấp |
|--------|---------|----------|
| `yellow-devin` | v2.3.7 | 9 commands `/devin:*`, devin-orchestrator agent, DeepWiki + Devin MCP |
| `spark-mcp` | v0.4.0 | Spark shared memory MCP |

## Skills có sẵn trong `.devin/skills/`

| Skill | Mục đích |
|-------|----------|
| `lightning` | Execution chính — planner + executor (dabit3/lightning-orchestrator) |
| `hlk-git-tools` | Commit/push an toàn qua HLK layer |
| `hlk-integrity-check` | Kiểm tra HLK layer sau upstream merge |
| `hlk-upstream-pull` | Pull upstream ruflo + reinstall HLK |
| `ruflo-autopilot` | [DEPRECATED] Legacy Ruflo MCP-only orchestration |

## Custom subagents trong `.devin/agents/`

| Profile | Model | Vai trò |
|---------|-------|---------|
| `lightning-executor` | swe-1.7-lightning | Implementation executor cho `/lightning` |

## Phạm vi an toàn cho code changes

- `v3/` — source code Ruflo
- `src/` — source code dự án
- `.devin/skills/`, `.devin/agents/` — định nghĩa skill/agent
- `scripts/` — utility scripts
- **KHÔNG đụng**: `HLK/` (security layer), `.claude/` (Claude Code config), security policies, `.env`
