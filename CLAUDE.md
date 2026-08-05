# Workspace Rules — Devin CLI

> **Devin CLI**: See `AGENTS.md` for Devin-specific instructions (AHD main engine, `/lightning` + `/glm` orchestrators, plugins, MCP servers).
> **Full reference list**: See `REPOS.md` for all repos/sources referenced, used, and learned from.
> **Claude Code**: Full Claude Code instructions are in git history (commit c29eab8). Restore with `git show c29eab8:CLAUDE.md > CLAUDE.full.md`.

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

### Workflow
- For non-trivial tasks, briefly state a plan before editing
- Ask before running destructive commands (delete, force-push, drop, reset --hard)
- After edits, run the project's existing tests/linters when available
- Preserve pre-existing user changes — never revert/overwrite without explicit instruction

### Communication
- Be concise. Lead with the answer or the change, then brief rationale
- When uncertain, say so and verify with tools instead of guessing

### Vietnamese Conventions
- Comments in code: Vietnamese, natural language, easy to understand
- Responses to user: Vietnamese with diacritics
- Technical terms: keep English (API, token, commit, branch, merge, deploy)
- First use of technical term: add short definition in parentheses
