# Devin CLI — Lightning Orchestrator + Ruflo MCP Hybrid

## Kiến trúc thực tế

Workspace này dùng **2 layer tách bạch** cho Devin CLI:

| Layer | Vai trò | Cơ chế |
|-------|---------|--------|
| **Execution** | Code, test, refactor nhanh | `/lightning` skill + `lightning-executor` subagent (SWE-1.7 Lightning, 1000 tok/s) |
| **Learning** | Nhớ pattern, lưu bài học | Ruflo MCP server (`claude-flow`) qua `.devin/mcp_config.json` |

**Không có swarm 15 agents tự động**. Mặc định dùng **1 executor** (nhanh, rẻ, đúng). Fan-out song song chỉ khi user yêu cầu rõ và write sets disjoint.

## Cách dùng

```bash
# Mở Devin CLI tại workspace
cd .
devin

# Non-interactive với task cụ thể
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

1. **Pattern recall** — `memory_search` (Ruflo MCP, namespace `patterns`). Nếu hit score > 0.7, fold vào work order.
2. **Frame task** — trích objective, acceptance criteria, constraints.
3. **Dispatch** — `run_subagent(profile: lightning-executor, is_background: false)` với work order tự chứa.
4. **Review** — inspect diff độc lập, treat report as evidence not proof.
5. **Correct** — trivial fix trực tiếp; lớn hơn thì `resume` cùng executor (giữ cache ấm). Sau 2 resume không tiến triển → stop, hỏi user.
6. **Verify** — `npm run build` + `npm test` + `npm run typecheck` trong package bị thay đổi.
7. **Persist pattern** — `memory_store` (chỉ khi verify pass). Không lưu pattern lỗi.
8. **Report** — what changed, key files, verification outcome, pattern stored?, residual risks.

## Guardrails (luôn áp dụng)

- Smallest coherent diff — không scope creep.
- Preserve pre-existing user changes — không revert/overwrite.
- No destructive ops (`rm -rf`, `git push --force`, `git reset --hard`) — chặn bởi `.devin/hooks.v1.json`.
- No weakening tests/security/typing/lint để pass check.
- Trivial edits (vài dòng rõ ràng) sửa thẳng, skip delegation.
- Fan-out chỉ khi write sets disjoint + user yêu cầu.
- Background executor không thể prompt approval → resume foreground nếu denied.

## MCP server

Ruflo MCP server (`claude-flow`) chạy qua HLK wrapper:

- `.devin/mcp_config.json` — cấu hình MCP
- Tools available: `memory_search`, `memory_store`, `swarm_init`, `agent_spawn`, `hooks_route`, `agent_execute`, `agent_status`, v.v.
- Lightning chỉ dùng `memory_search` (đầu) + `memory_store` (cuối, sau verify). Các MCP tool khác dùng cho orchestration thủ công khi cần.

## Skills có sẵn trong `.devin/skills/`

| Skill | Mục đích |
|-------|----------|
| `lightning` | Execution chính — planner + executor hybrid |
| `hlk-git-tools` | Commit/push an toàn qua HLK layer |
| `hlk-integrity-check` | Kiểm tra HLK layer sau upstream merge |
| `hlk-upstream-pull` | Pull upstream ruflo + reinstall HLK |

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
