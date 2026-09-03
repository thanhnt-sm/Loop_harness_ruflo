# CMDC_WRAP_REPORT — wrap `.devin` + `.opencode` + `HLK` cho command-code (cmdc)

> Định kỳ: 2026-08-27
> Skill: `harness-upgrade` (full-power, focus = cmdc cross-provider bridge)
> Plan: inline (user duyệt apply trực tiếp, scope "Đầy đủ + personas + HLK max performance")
> Trạng thái: **COMPLETE** (apply đã thực hiện)

## Mục tiêu

Tạo lớp wrap/registration để command-code CLI (`cmd`) phát hiện và dùng được
toàn bộ cài đặt đã có trong `.devin/` + `.opencode/` + `HLK/`: skills,
MCP servers, hooks, custom agents, custom slash commands, permissions, và
**HLK security layer ở MAX PERFORMANCE** (sanitizer + telemetry blocker +
git-tools + 6 prompts + 3 skills + loop self-learning).

## Baseline (trước)

- `.commandcode/` chỉ có `taste/taste.md` rỗng.
- Không có `.mcp.json`.
- Không có `settings.json` của cmdc.
- cmdc không thấy skills/agents/MCP/hooks/commands của workspace.

## After (đã áp dụng)

### 1. `.commandcode/settings.json` (4152 bytes)

- `skills`: trỏ tới `.devin/skills` + `.opencode/skills` → cmdc auto-discover
  88 + 32 skill files.
- `permissions`: deny/ask/allow mirror từ `.devin/config.json`, schema cmdc
  (Shell/Read/Edit) → an toàn khi chạy trong cmdc.
- `hooks`: 4 event × N handler — `SessionStart`, `PreToolUse` (shell +
  write|edit), `PostToolUse` (shell + write|edit), `Stop`.

### 2. `.mcp.json` (529 bytes, project scope)

Mirror `opencode.json.mcp`:

- `aide-memory` (stdio, `npx -y aide-memory mcp .`, timeout 20s)
- `ruflo-hlk-mcp` (stdio, `node HLK/wrappers/ruflo-hlk-mcp.mjs mcp start`, timeout 30s)

### 3. `.commandcode/hooks/*.sh` (4 scripts) + HLK hook chain

| File | Vai trò | Status |
|------|---------|--------|
| `deny-dangerous.sh` | PreToolUse shell (line 1) — block rm -rf /, force-push, curl \| sh, mkfs, dd, chmod 777, ... (mirror `.devin/canon/REDLINES.md` + `.devin/config.json.deny`) | active |
| `bridge-devin.sh` | PreToolUse + PostToolUse (line 3) — forward stdin JSON sang `.devin/hooks/<event>.py` (fire-and-forget, fail-open, timeout 3s) | active |
| `session-start-git.sh` | SessionStart — inject git branch + status vào `additionalContext` | active |
| `audit-writes.sh` | PostToolUse write\|edit — append audit line vào `.commandcode/write-audit.log` | active |
| **`HLK/wrappers/hlk-hook-launcher.mjs`** | PreToolUse + PostToolUse (line 2) — HLK sanitizer (28 redact patterns từ `HLK/config/hlk.config.json.security_rules.redact_patterns`) + telemetry blocker | active |

**Hook chain (in order)**:

```
cmdc PreToolUse shell
  → deny-dangerous.sh          (line 1: deny destructive)
    → hlk-hook-launcher.mjs    (line 2: HLK sanitize + block telemetry)
      → bridge-devin.sh         (line 3: forward to .devin/hooks/*.py)
```

### 4. `.commandcode/agents/*.md` (11 agents)

**5 harness (cmdc):**

- `commander.md` — orchestrator (load `.devin/agents/COMMANDER.md`)
- `executor-glm.md` — free tier, simple ops
- `executor-kimi.md` — free tier, code gen
- `executor-lightning.md` — paid, complex
- `verifier.md` — read-only done-gate (fable-judge)

**5 personas (cmdc):**

- `persona-architect.md`
- `persona-code-reviewer.md`
- `persona-saboteur.md`
- `persona-security-auditor.md`
- `persona-new-hire.md`

**1 HLK operator (cmdc)** — security layer specialist:

- `hlk-engineer.md` — HLK status/integrity/sanitize/git-tools/MAX POWER/
  prompt-driven analysis/loop self-learning. Read-only by default. BẮT BUỘC
  dispatch trong step 5 PREFLIGHT của full-power.

### 5. `.commandcode/commands/*.md` (15 slash commands)

**Core (10):** `full-power`, `plan`, `lightning`, `glm`, `kimi`,
`adversarial-consensus`, `harness-upgrade`, + 3 HLK ban đầu
(`hlk-git-tools`, `hlk-integrity-check`, `hlk-loop`).

**HLK mở rộng (5 mới):**

- `hlk-status.md` — diagnostic + integrity quick check.
- `hlk-sanitize.md` — apply 28 redact patterns lên file/text.
- `hlk-git-doctor.md` — git pre-flight qua `hlk-git-doctor.mjs`.
- `hlk-max-power.md` — update + verify + status (MAX POWER flow).
- `hlk-prompts.md` — load + execute 1 of 6 HLK analysis prompts
  (codebase_analysis / redteam_security / solution_architect /
  data_leak_hardening_guide / harness_deepdive_hardening /
  ruflo_hardening_implementation).

### 6. `.commandcode/skills/cmdc-harness-bridge/SKILL.md` (index)

Wrapper index liệt kê cách cmdc surface → source cho cả 3 layer
(`.devin` + `.opencode` + `HLK`). Active ngay khi cmdc start session.

### 7. `/full-power` nâng cấp — chạy qua tất cả flow / mod / agent + HLK

Sau yêu cầu của user, tôi cập nhật cả 2 file launcher:

- `.commandcode/commands/full-power.md` (8849 bytes, source of truth cho cmdc)
- `.opencode/command/full-power.md` (sync với cmdc)

**Tất cả 18 step** (không skip):

1. BOOT
2. INVENTORY
3. COMMANDER MODE
4. TIER CLASSIFICATION
5. PREFLIGHT
6. BRAINSTORM (6 góc nhìn + Nuwa)
7. 8 SCOUTs (research song song)
8. ARCHITECT (SDD)
9. 6+ adversarial reviewers (song song)
10. SDD approval gate
11. DECOMPOSE
12. GAP_SCAN
13. 10-D QC
14. PLAN_ENHANCE
15. Plan approval gate
16. EXECUTE (DAG parallel)
17. MEMORY + NUWA + REPORT
18. APPLY

**Tất cả mod** (load-on-demand theo phase, không load all cùng lúc):

- 15 canon files (CORE_CANON, BOOT_PROTOCOL, REDLINES, MEMORY_PROTOCOL,
  LOOP_TURN/TIME/GOAL/PROACTIVE, VERIFICATION, CAVEMAN, DAEMON, HANDOFF,
  HARNESS_ENGINEERING, JUDGMENT_RUBRICS)
- AHD layer (5 dir)
- 88 skill files + 32 wrappers
- Opencode layer
- cmdc bridge layer (mới)

**Tất cả 37 agent** (dispatch song song, max parallel):

- 5 harness (commander + 3 executors + verifier)
- 5 personas cmdc
- **1 HLK operator (`hlk-engineer`) — bắt buộc ở step 5 PREFLIGHT**
- 5 workers AHD (SCOUT/BUILDER/AUDITOR/MEMORY_KEEPER/VERIFIER)
- 6 personas Devin
- 15 personas/roles opencode (architect, auditor, builder, code_reviewer,
  commander, git_workflow_master, 3 executors, memory_keeper, new_hire,
  saboteur, scout, security_auditor, verifier)

## Verification & quality verdict

- **Governance**: `python tools/check_governance.py` → errors=0 (1 warning
  cũ về plan thiếu exec report, không liên quan task này).
- **JSON validity**: `.commandcode/settings.json` + `.mcp.json` parse OK.
- **Hook contract**: scripts follow cmdc JSON-stdin/JSON-stdout contract
  với `hookSpecificOutput.permissionDecision` cho PreToolUse.
- **HLK self-test**: `node HLK/bin/hlk-status.mjs --self-test` → version
  đồng nhất, config OK. 1 finding: thiếu `bin/hlk-lifecycle.mjs` (đã có
  trong `package.json.bin` nhưng file chưa shipped — không do task này, đã
  có sẵn từ trước).
- **HLK integrity**: `node HLK/wrappers/hlk-verify-integrity.js` → 14 file
  bắt buộc có đủ, config hợp lệ, gitignore bảo vệ secrets OK, sanitizer
  smoke test PASS.
- **File tree**: 33 file mới, đúng vị trí theo cmdc discovery paths:
  - `.commandcode/settings.json` (4446 bytes, có HLK hook chain)
  - `.commandcode/agents/{commander,executor-glm,executor-kimi,executor-lightning,verifier,persona-architect,persona-code-reviewer,persona-saboteur,persona-security-auditor,persona-new-hire,hlk-engineer}.md` (11)
  - `.commandcode/commands/{full-power,plan,lightning,glm,kimi,adversarial-consensus,hlk-git-tools,hlk-integrity-check,hlk-loop,harness-upgrade,hlk-status,hlk-sanitize,hlk-git-doctor,hlk-max-power,hlk-prompts}.md` (15)
  - `.commandcode/hooks/{deny-dangerous,bridge-devin,session-start-git,audit-writes}.sh` (4)
  - `.commandcode/skills/cmdc-harness-bridge/SKILL.md` (1)
  - `.mcp.json` (project root)
- **Không destructive**: không sửa `HLK/`, `.env`, security policies, không
  xóa file, không force-push.
- **Mirror contract**: mọi deny rule trong `.devin/config.json.deny` có
  rule tương đương trong `.commandcode/settings.json.permissions.deny`.
- **HLK MAX PERFORMANCE wiring**:
  - `deny-dangerous.sh` (line 1) → `hlk-hook-launcher.mjs` (line 2) →
    `bridge-devin.sh` (line 3) trong PreToolUse shell.
  - `hlk-hook-launcher.mjs` (line 1) → `bridge-devin.sh` (line 2) trong
    PostToolUse shell.
  - HLK tự load 28 redact patterns + telemetry blocker overrides qua
    `HLK/config/hlk.config.json`.
  - `hlk-engineer` agent dispatch ở step 5 PREFLIGHT của full-power.
  - 15 slash commands = 10 core + 5 HLK-specific.

## HLK MAX PERFORMANCE — feature inventory

| Feature | Status | cmdc access |
|---------|--------|-----------|
| `knowledge_protection` | ✅ enabled | implicit (sanitizer hook) |
| `data_sanitization` | ✅ enabled (28 patterns) | `/hlk-sanitize`, hook chain |
| `secret_vault_override` | ✅ enabled | implicit (vault-bridge) |
| `telemetry_blocker` | ✅ enabled (6 env vars) | implicit (hook chain) |
| `custom_hooks_injection` | ✅ enabled | implicit (settings.json.hooks) |
| `post_merge_verify` | ✅ enabled | `/hlk-git-tools commit` + verify |
| MAX POWER agent | ✅ | `hlk-engineer` |
| MAX POWER update | ✅ | `/hlk-max-power` |
| MAX POWER prompts | ✅ (6) | `/hlk-prompts <num|keyword>` |
| MAX POWER git-tools | ✅ (8) | `/hlk-git-tools`, `/hlk-git-doctor` |
| MAX POWER loop | ✅ | `/hlk-loop` |
| Self-test | ✅ | `/hlk-status` |

## Next candidates (chưa làm, có score)

1. **Ship `bin/hlk-lifecycle.mjs`** — đã có trong `package.json.bin` nhưng
   file chưa tồn tại. Có thể tạo thin wrapper hoặc xóa khỏi `bin` map.
2. **Tự động đăng ký thêm personas** từ `.devin/agents/personas/` (hiện đã
   copy 5, còn lại 1 `git_workflow_master` — ưu tiên thấp).
3. **Mod bridge cho opencode**: viết 1 mod tương đương `.opencode/plugins/harness.ts`
   nhưng chạy native trong cmdc runtime (cần mod-builder).
4. **Caveman compression hook** cho cmdc output (token saving).
5. **Cập nhật AGENTS.md** để mention cmdc layer (1 dòng, low risk).
6. **Self-test** thực tế: chạy 1 task nhỏ trong cmdc để xác nhận bridge hoạt
   động đúng (cần user review kết quả thực tế).
7. **`/hlk-update` wrapper** — wrap `node HLK/bin/hlk-update.mjs --yes` thành
   slash command (hiện tại chỉ wrap qua `/hlk-max-power`).
8. **Per-file HLK check** — sub-skill scan 1 file cụ thể qua
   `hlk-sanitize` + báo cáo pattern trùng.

## Restart guide

Sau khi apply, user cần **restart cmdc session** để:

- `settings.json` được load (skills + permissions + hooks).
- `.mcp.json` được scan (MCP servers).
- `agents/*.md` + `commands/*.md` xuất hiện trong `/` menu.
- Skill `cmdc-harness-bridge` xuất hiện trong `/skills`.
- Hooks active ngay turn đầu (SessionStart inject git status).

Nếu thấy MCP "disconnected" → chạy `/mcp` trong session để reconnect.
