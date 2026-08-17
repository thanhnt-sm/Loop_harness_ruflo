# Workspace Rules — Devin CLI

> **Devin CLI**: See `AGENTS.md` for Devin-specific instructions (AHD main engine, `/lightning` + `/glm` orchestrators, plugins, MCP servers).
> **Full reference list**: See `REPOS.md` for all repos/sources referenced, used, and learned from.
> **Claude Code**: Full Claude Code instructions are in git history (commit c29eab8). Restore with `git show c29eab8:CLAUDE.md > CLAUDE.full.md`.
> **Cline**: Cline auto-loads this file + `AGENTS.md` + `.clinerules/` at session start. The source map is `.clinerules/00-source-map.md` (regenerate after structural changes with `python3 tools/gen_source_map.py`).

## Universal Rules (apply to all agents)

### Security
- Never hardcode secrets, API keys, tokens, or passwords in source files
- Never print or log secret values; reference environment variables instead
- Do not commit files matching: `*.pem`, `*.key`, `*.env`, `secrets/`, `credentials/`

### Code Quality
- Prefer small, focused changes over large rewrites
- Match existing style and conventions of the file/project being edited
- Do not add comments or docs unless they already exist nearby or explicitly requested
- Add error handling for I/O, network, and external calls

### File Organization
- NEVER save working files or tests to the root folder
- Source code: `.devin/scripts/` (plan/execution scripts) and `.devin/hooks/` (hook guards); `tests/` for tests; `docs/` for documentation; `.devin/scripts/` or `tools/` for utilities
- Files under 500 lines
- Typed interfaces for all public APIs
- **Workspace Governance**: follow `.devin/rules/WORKSPACE_GOVERNANCE.md` — no junk files, files go to the designated directories only, plan↔act must match (`docs/plans/<slug>/IMPLEMENTATION_PLAN.md` → `EXECUTION_REPORT.md`). Run `python3 tools/check_governance.py` before finishing a task.

### Workflow
- For non-trivial tasks, briefly state a plan before editing
- Ask before running destructive commands (delete, force-push, drop, reset --hard)
- After edits, run the project's existing tests/linters when available
- Preserve pre-existing user changes — never revert/overwrite without explicit instruction

### Communication
- Be concise. Lead with the answer or the change, then brief rationale
- When uncertain, say so and verify with tools instead of guessing

### Language Policy (BẮT BUỘC)
- **TẤT CẢ responses PHẢI bằng tiếng Việt có dấu.** KHÔNG ngoại lệ.
- Comments in code: Vietnamese, tự nhiên, dễ hiểu
- Technical terms giữ nguyên tiếng Anh: API, token, commit, branch, merge, deploy, hook, skill, agent...
- Lần đầu dùng technical term: ghi chú ngắn trong ngoặc đơn
- Commit messages: giữ nguyên tiếng Anh (theo git convention)
- File names, variable names: giữ nguyên tiếng Anh (không dấu)
- KHÔNG trả lời bằng tiếng Anh với user trừ khi user yêu cầu rõ ràng
