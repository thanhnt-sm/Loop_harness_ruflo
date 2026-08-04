# Tools — Workspace Packaging System

Hệ thống đóng gói + deploy workspace Agent Harness Deploy (AHD) sang dự án mới.

## Quick start

```powershell
# Cách 1: One-shot (khuyến nghị)
.\tools\init-new-project.ps1 -TargetPath D:\projects\my-new-app

# Cách 2: Từng bước
.\tools\package-template.ps1                              # → harness-template.zip
.\tools\deploy-template.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-new-app
.\tools\verify-workspace.ps1 -WorkspaceRoot D:\projects\my-new-app

# Clean runtime state (cho workspace hiện tại)
.\tools\clean-runtime.ps1
```

## Files

| File | Mục đích |
|------|----------|
| `init-new-project.ps1` | **One-shot orchestrator** — package + deploy + git init + verify + print hướng dẫn |
| `package-template.ps1` | Đóng gói workspace → `harness-template.zip` (clean, templated config) |
| `deploy-template.ps1` | Deploy template → dự án mới (resolve placeholders, git init) |
| `verify-workspace.ps1` | Verify integrity — kiểm tra đủ canon, skills, agents, hooks, scripts, vault, config |
| `clean-runtime.ps1` | Wipe runtime state (session, memories, loop_state, context_flags) |
| `FULL_POWER_PROMPT.md` | **One-shot prompt** — paste vào Devin CLI → tự động chạy full harness chain |

## Template bao gồm gì?

### Reusable (mang sang dự án mới)
- `.devin/canon/` — 10 protocol files (CORE_CANON, BOOT, MEMORY, LOOP, VERIFICATION, CAVEMAN, HARNESS_ENGINEERING, JUDGMENT_RUBRICS, HANDOFF_LETTER, REDLINES)
- `.devin/agents/` — COMMANDER + 7 personas + 5 workers + lightning-executor + glm-executor + dispatch templates + model tiers
- `.devin/skills/` — 21+ skills (16 AHD + 5 Devin-native + nuwa-skill + chroma-hybrid-search + 9 domain-adapters)
- `.devin/hooks/` — 4 Python hooks (pre_tool_use, post_tool_use, stop, ahd_session)
- `.devin/scripts/` — 7 runtime scripts (worktree, plan_dispatch, session_manager, loop_memory_sync, memory_audit, pre_task_audit)
- `.devin/skills/assets/vault/` — 5 anti-link-rot templates (caveman, agency_framework, memory_mcp, strix, graphify)
- `.devin/config.json` — merged config (templated placeholders, resolved on deploy)
- `.devin/mcp_config.json` — MCP servers (templated, resolved on deploy)
- `.devin/rules/` — Project rules placeholder (AHD không overwrite)
- `.devin/AGENTS.md` — Auto-generated canonical harness body (186KB)
- `.agents/` — Shared state (user_profile template, loop_state, knowledge_distill)
- `.aide/` — aide-memory config (memories wiped)
- `HLK/` — Security layer (sanitizer, vault-bridge, git-tools, wrappers, setup, upstream, config, loop, custom-hooks, skills)
- `AGENTS.md` — Root documentation (AHD main engine)
- `CLAUDE.md` — Universal rules
- `REPOS.md` — Master reference list
- `.gitignore` — Template
- `package.json` — Minimal manifest
- `.github/` — ISSUE_TEMPLATE, CODEOWNERS, dependabot, workflows
- `tools/` — This packaging system

### Loại bỏ (KHÔNG mang sang dự án mới)
- `.git/` — Git history (new project starts fresh)
- `.tools/` — Local tool binaries (machine-specific)
- `node_modules/` — Dependencies
- `.claude/`, `.cursor/` — Runtime (gitignored, recreated by hooks)
- `HLK/reports/` — Project-specific analysis reports
- `HLK/logs/` — Runtime logs
- `.github/issues/` — Project-specific issues
- `.github/supply-chain/` — Project-specific supply chain docs
- `.aide/memories/*` — Session memories (wiped by clean-runtime)
- `.devin/session_state/`, `.devin/loop_state/`, `.devin/context_flags/` — Runtime state (wiped)

## Placeholders (resolved bởi deploy-template.ps1)

| Placeholder | Thay bằng | Phát hiện bằng |
|-------------|-----------|----------------|
| `{{WORKSPACE_ROOT}}` | Absolute path to new project | User-provided TargetPath |
| `{{AIDE_MEMORY_GLOBAL}}` | Global `node_modules/aide-memory` path | `npm root -g` |
| `{{AIDE_MEMORY_CLI}}` | `aide-memory/dist/memory/cli.js` path | Derived from AIDE_MEMORY_GLOBAL |
| `{{NODE_EXE}}` | `node.exe` path | `Get-Command node` hoặc `.tools/node/node.exe` |

## FULL_POWER_PROMPT — Cách dùng

```bash
# 1. cd vào project mới
cd D:\projects\my-new-app

# 2. Mở Devin CLI
devin

# 3. Paste nội dung tools/FULL_POWER_PROMPT.md
#    Thay <TASK> bằng task của bạn
```

Prompt sẽ trigger:
1. **BOOT** — đọc canon, registry, profile, handoff → output GoalSpec
2. **INVENTORY** — kiểm tra skills, agents, MCP, hooks, canon
3. **COMMANDER MODE** — vào vai orchestrator
4. **TASK FRAMING** — phân tích task, output GoalSpec
5. **GAP SCAN** — scan blind spots
6. **DECOMPOSE + DISPATCH** — auto-spawn parallel subagents (Scout, Builder, Auditor, Verifier)
7. **INTEGRATE** — đọc reports, resolve conflicts
8. **VERIFY** — maker ≠ checker, CLI gates, SHA discipline
9. **NUWA COGNITIVE** — Munger/Feynman/Taleb adversarial review (L/XL tasks)
10. **CLAIM GRADING** — grade mọi claim [fact]/[inference]/[unverified-guess]
11. **SLOP CHECK** — detect + remove AI filler
12. **MEMORY WRITE-BACK** — store lessons, update registry
13. **REPORT** — final structured report

## Prerequisites

| Tool | Cài | Kiểm tra |
|------|-----|----------|
| Node.js 18+ | https://nodejs.org | `node -v` |
| aide-memory | `npm install -g aide-memory` | `npm list -g aide-memory` |
| Python 3.8+ | https://python.org | `python --version` |
| Git | https://git-scm.com | `git --version` |
| Devin CLI | https://devin.ai | `devin --version` |

## Troubleshooting

| Vấn đề | Fix |
|--------|-----|
| `aide-memory không tìm thấy` | `npm install -g aide-memory` rồi re-deploy |
| `config.json có unresolved placeholders` | Chạy `deploy-template.ps1` lại (resolve paths) |
| `hooks không chạy` | Kiểm tra `python` trong PATH, aide-memory global path đúng |
| `MCP servers không connect` | Kiểm tra `devin mcp list` + tokens cho spark-memory/deepwiki/devin |
| `verify-workspace fail` | Đọc errors, fix thủ công hoặc re-deploy |
