# CMDC_MAX_POWER_RESEARCH — Cài MAX POWER + Tính năng độc đáo của Command Code

> Định kỳ: 2026-08-27
> Nguồn tham chiếu: `commandcode.ai/docs/*` (qua bundled `command-code-knowledge` skill, 15 reference file, ~7000 dòng) + `commandcode.ai/blog/*` + bundled skills (`mod-builder`, `skill-builder`, `design`)
> Trạng thái: **APPLIED** (full MAX POWER)

---

## Phần 1 — Features chưa được tận dụng (research 2026-08-27)

Web search rate-limited tại thời điểm research; dùng toàn bộ bundled reference (`reference/*.md`, 15 file) + skill bundled (`skill-builder`, `mod-builder`, `design`).

### 1.1 Custom agents — chưa pin model / maxTurns / permissionMode / background / showOutput

**Trước**: 11 agent đều `model: inherit`, không cap turn, default permission, không background.

**Sau (MAX POWER)**: 12 agent pin đủ:

| Agent | model | maxTurns | permissionMode | background | disallowedTools |
|-------|-------|----------|----------------|------------|-----------------|
| `commander` | `claude-opus-4-8` | 60 | default | false | — |
| `executor-glm` | `zai-org/glm-5.2` | 40 | default | true | — |
| `executor-kimi` | `moonshotai/kimi-k2.6` | 50 | default | true | — |
| `executor-lightning` | `claude-sonnet-5` | 50 | default | true | — |
| `verifier` | `claude-haiku-4-5` | 20 | plan | false | shell, write, edit |
| `persona-architect` | `claude-sonnet-5` | 25 | plan | true | shell, write, edit |
| `persona-code-reviewer` | `claude-sonnet-5` | 25 | plan | true | shell, write, edit |
| `persona-saboteur` | `claude-sonnet-5` | 30 | plan | true | write, edit |
| `persona-security-auditor` | `claude-sonnet-5` | 30 | plan | true | write, edit |
| `persona-new-hire` | `claude-sonnet-5` | 20 | plan | true | shell, write, edit |
| `hlk-engineer` | `claude-sonnet-5` | 30 | default | false | — |
| `scheduler` (mới) | `claude-haiku-4-5` | 10 | default | false | — |

Lợi ích:
- **Prompt cache riêng** mỗi agent (per docs: "Pinning a model gives the agent its own prompt cache, so a slow planner and a fast implementer don't thrash each other's").
- **Cost optimization**: persona dùng sonnet (review lens), executor dùng free tier, verifier dùng haiku (cheap, read-only).
- **Safety**: persona `permissionMode: plan` + `disallowedTools` = read-only thật sự, không thể shell inject.
- **Parallel dispatch**: `background: true` trên 3 executor + 5 persona = chạy song song 8 task trong 1 turn.
- **Cap turn**: persona không loop vô hạn (20-30 turns max).

### 1.2 Mods (ModApi) — chưa khai thác

**MAX POWER** đã tạo `.commandcode/mods/hlk-guardian.ts` (TypeScript ESM):

- 1 slash command `/hlk-quick` — chạy song song `hlk-status --self-test` + `hlk-verify-integrity.js`, in 1 dòng verdict.
- 1 inline tool `hlk_status` — read `HLK/config/hlk.config.json` trả về version + features + redact pattern count (optional).
- 1 lifecycle observer `session.start` — auto-verify HLK mỗi session start (fail-open).
- 1 README.md giải thích cách load (`cmd --mod ./.commandcode/mods/hlk-guardian.ts` hoặc `--mod-dir`).

Đây là tính năng **độc đáo nhất của cmdc**: viết custom plugin bằng TS, không cần patch runtime. Skill `mod-builder` bundled hỗ trợ scaffold.

### 1.3 Memory — chưa có project memory tier 2

**MAX POWER** đã tạo `.commandcode/AGENTS.md` (project memory):

- Workspace overview 3 layer.
- cmdc surface (skill/MCP/hook/agent/command/mod).
- Quick commands.
- Hard guards (binding).
- Tier classification.
- Import root `AGENTS.md` + canon + 3 docs (CMDC_QUICKREF, FULL_GUIDE, SECURITY_AUDIT).

Cấu trúc 3-tier memory (per docs):
- Tier 1 (user): `~/.commandcode/AGENTS.md` (chưa tạo — để user tự quản).
- Tier 2 (project): `.commandcode/AGENTS.md` (MỚI).
- Tier 3 (subdir): `AGENTS.md` trong subdirectory nếu cần.

Compaction: memory là system prompt, không bị summary. Tier 2 load mỗi turn; cost ổn định.

### 1.4 Settings — thiếu các tinh chỉnh MAX

Đã thêm vào `.commandcode/settings.json`:

- `onDemandToolDescriptions: true` — shell prompt chỉ explain khi nhấn `ctrl+e`. Mặc định on; pin rõ để audit.
- `disableScratchpad: false` — bật session scratchpad. Mỗi session có `/tmp/commandcode-<uid>/<cwd>/<session-id>/scratchpad`, exported as `$COMMANDCODE_SCRATCHPAD` env. Silent access, shared với sub-agent, survive compaction, cleaned 30d.
- `autoCompact: true` — auto-compact khi context sắp đầy. Manual: `/compact`.

### 1.5 Skill flags — bổ sung

`cmdc-harness-bridge/SKILL.md` đã thêm:

- `disable-model-invocation: false` — model vẫn thấy (cần thiết cho delegation).
- `user-invocable: true` — user có thể gõ `/cmdc-harness-bridge`.
- `argument-hint: "[]"` — hiển thị trong `/` menu.
- `allowed-tools: Read` — chỉ đọc, không exec.

Đây là các extension field mà docs gọi là "mirror Agent Skills / Claude Code frontmatter" — portable giữa các agent.

### 1.6 Scheduler agent (mới)

`.commandcode/agents/scheduler.md` — dùng `cron_create` tool built-in. Ví dụ workflow:

```bash
# User: "lập lịch HLK self-test mỗi ngày 9h sáng"
/task scheduler "tạo cron job: 0 9 * * * → chạy node HLK/bin/hlk-status.mjs --self-test"
```

Scheduler agent (`claude-haiku-4-5`, maxTurns=10) sẽ tạo cron + verify bằng `cron_list`.

---

## Phần 2 — Tính năng độc đáo của Command Code (chưa thấy ở agent khác)

| # | Feature | Tại sao độc đáo | Cách dùng |
|---|---------|------------------|-----------|
| 1 | **Plan mode + Plan review** (GitHub-style review) | Plan mode read-only, agent viết plan, mở review panel. User comment từng dòng, `ctrl+a` approve, `ctrl+r` submit review. Modes bypass/auto-accept skip review tự động (theo docs). | `/plan <task>` |
| 2 | **Background sub-agent** (`background: true`) | Sub-agent detach, return `agent_id`, main thread tiếp tục. Collect sau qua `agent_output` với `wait`/`status`/`kill`. | Trong agent frontmatter |
| 3 | **One-level-deep delegation** | Sub-agent KHÔNG thể gọi sub-agent (tool bị remove). Tránh infinite recursion. | Per agent |
| 4 | **Session scratchpad** ($COMMANDCODE_SCRATCHPAD) | Shared working dir giữa main + sub-agent, silent access, survive compaction. 30d retention. | Env var + auto |
| 5 | **Checkpoint + rewind** (Esc Esc 500ms) | Snapshot mỗi prompt + backup file modified. Rewind về bất kỳ checkpoint, restore conversation+code. 200 backup / 30 days. 10MB cap per file. | `/rewind` |
| 6 | **Compaction append-only** | On-disk log KHÔNG bao giờ rewrite. Compaction append entry + pointer. `/tree` vẫn reach mọi branch. | `/compact` (manual) hoặc auto |
| 7 | **Session tree** (`/tree`) | Mỗi entry có parent → tree, không linear. Fork/clone/tree 3 cấp branch management. | `/tree`, `/fork`, `/clone` |
| 8 | **12-rung permission ladder** | deny > ask > allow, mọi rule match aggressive, allow match conservative. Bypass là rung 9 (sau deny/ask/circuit breaker). | `settings.json.permissions` |
| 9 | **MCP tool allowlist specific** (không `*`) | Mỗi tool phải named. `mcp__server__*` wildcard chỉ dành cho deny/ask, KHÔNG cho allow. | settings.json |
| 10 | **Memory 3-tier** (user / project / subdir) | Mỗi tier load khi relevant. `@path` import lồng 5 cấp, trong code fence thì skip. | `AGENTS.md` + `@README.md` |
| 11 | **Mods (ModApi)** | TypeScript plugin load qua `cmd --mod <path>`. Lifecycle observer + custom command + custom tool. | `.commandcode/mods/*.ts` |
| 12 | **`onDemandToolDescriptions`** | Shell prompt chỉ explain khi user nhấn `ctrl+e` (on-demand), tránh token cost upfront. | Setting |
| 13 | **Input repair** (model heal) | JSON-stringified → parsed, scalar → wrapped, alias rename (`path`→`file_path`, `cmd`→`command`). 540 token saved/request. | Built-in |
| 14 | **Disable bypass enforcement** | `disableBypass: "disable"` chặn `--yolo` ở engine + CLI entry + TUI cycle + decision store. | settings.json |
| 15 | **`disableSkillShellExecution`** | Chặn `!cmd` inline + fenced shell trong SKILL.md. Chống supply chain. | settings.json |

---

## Phần 3 — So sánh với OpenCode / Claude Code (research từ REPOS.md + docs)

| Feature | cmdc | opencode | claude-code | AHD |
|---------|-------|----------|-------------|-----|
| Plan mode review | ✅ GitHub-style | partial | ✅ similar | n/a |
| Background sub-agent | ✅ `background: true` | ✅ | ✅ | ✅ |
| Checkpoint rewind | ✅ Esc Esc 500ms | partial | ✅ | n/a |
| Session tree | ✅ `/tree` fork/clone | n/a | n/a | n/a |
| Scratchpad | ✅ `$COMMANDCODE_SCRATCHPAD` | n/a | partial | n/a |
| Mods (TS plugin) | ✅ `cmd --mod` | ✅ `@opencode-ai/plugin` | ✅ hooks | ✅ AHD |
| Memory 3-tier | ✅ AGENTS.md | ✅ | ✅ CLAUDE.md | ✅ `.devin/AGENTS.md` |
| MCP tool allowlist | ✅ specific (no `*`) | ✅ | ✅ | ✅ |
| Hardening `disableBypass` | ✅ | partial | partial | n/a |
| `disableSkillShellExecution` | ✅ | n/a | n/a | n/a |
| HLK security layer | n/a | n/a | n/a | ✅ custom |
| Plan orchestrator (3-Phase FSM) | n/a | n/a | n/a | ✅ 22 scripts |

cmdc có **Session tree + Scratchpad + Compaction append-only + Mods** là
4 tính năng OpenCode/Claude Code **không có tương đương** (chỉ có 1 phần).

---

## Phần 4 — Hardening tổng kết (sau MAX POWER)

Tổng rule hiện tại trong `.commandcode/settings.json`:

- **Top-level**: `skills` (2 path) + `disableSkillShellExecution: true` + `onDemandToolDescriptions: true` + `disableScratchpad: false` + `autoCompact: true`.
- **Permissions**:
  - `defaultMode: "default"` + `disableBypass: "disable"` + `additionalDirectories: ["HLK"]`.
  - 29 allow rule (git read-only, build/test, check_governance, 6 Read path, 5 MCP aide-memory tool cụ thể + 1 ruflo-hlk-mcp wildcard deferred).
  - 15 ask rule (git mutating, npm publish, pip install, npm install, node/npx/python -c, Edit .env, WebFetch, WebSearch).
  - 62 deny rule (filesystem root + home, git force ops, curl|sh, disk/partition, crypto, system control, chmod 777, secret reads, persistence vectors, control surfaces, HLK layers).
- **Hooks**: 4 event × 1-4 line:
  - SessionStart (3 hook): session-start-git + HLK + bridge-devin.
  - PreToolUse shell (3): deny-dangerous + HLK + bridge-devin.
  - PreToolUse write|edit (3): schema-validate + HLK + bridge-devin.
  - PostToolUse shell (2): HLK + bridge-devin.
  - PostToolUse write|edit (4): schema-validate + HLK + bridge-devin + audit-writes.
  - Stop (2): HLK + bridge-devin.

---

## Phần 5 — Tổng tài sản cmdc sau MAX POWER

```
38 cmdc files = 12 agents + 15 commands + 5 hooks + 1 mod + 1 AGENTS.md + 1 settings.json + 1 settings.local.json + 1 SKILL.md + 1 mods/README.md
+ 1 file .mcp.json
+ 1 file opencode.json (opencode side)
+ 1 settings.local.json (gitignored)
```

| Surface | Count | Notes |
|---------|-------|-------|
| Custom agents | **12** | 5 harness + 5 personas + 1 HLK + 1 scheduler. Tất cả pin model + maxTurns + permissionMode + background |
| Custom slash commands | **15** | 10 core + 5 HLK mở rộng |
| Mods (TS plugin) | **1** | `hlk-guardian.ts` (slash + tool + lifecycle) |
| Hooks (4 event × line) | **3+3+2+4+2 = 14** | deny-dangerous, schema-validate, bridge-devin, HLK, audit-writes |
| Skills (49 + 1 index) | **50** | 17 (.devin) + 32 (.opencode) + 1 (cmdc-harness-bridge) |
| MCP servers | **2** | aide-memory (5 tool allowlist) + ruflo-hlk-mcp (wildcard deferred) |
| Memory files | **2** | root `AGENTS.md` (AHD governance) + `.commandcode/AGENTS.md` (cmdc surface) |
| Permission rules | **106** | 29 allow + 15 ask + 62 deny |

---

## Phần 6 — Restart guide

Sau khi apply MAX POWER, **restart cmdc session**:

```bash
# Verify nhanh
python tools/check_governance.py
node HLK/wrappers/hlk-verify-integrity.js
node -e "JSON.parse(require('fs').readFileSync('.commandcode/settings.json'))"

# Restart cmdc
cmd --mod ./.commandcode/mods/hlk-guardian.ts
```

Trong session:

```
/skills                  # expect 50+ skills
/agents                  # expect 12 agents
/mcp                     # 2 server connected
/mods                    # hlk-guardian loaded
/hlk-quick               # via mod, nhanh hơn /hlk-status
/memory                  # mở .commandcode/AGENTS.md
```

Nếu model ID pin trong agent frontmatter không tồn tại trong account → fallback
theo session model (`/model <id>`).

---

## Phần 7 — Next candidates (chưa làm, có score)

1. **`/import` from opencode** — `.opencode/AGENTS.md` không tồn tại, nhưng `.opencode/skills/*` có thể mang vào `.commandcode/skills/`.
2. **BYOK provider** — khi cần model local/private, setup qua `/connect` rồi pin vào agent frontmatter.
3. **Worktree skill** — wrap `enter_worktree` / `exit_worktree` thành 1 command `/worktree-isolate` cho parallel task.
4. **Taste + memory write-back** — auto update `.commandcode/taste/` sau mỗi session pattern.
5. **Mod #2**: `aide-memory-sync.ts` — auto sync memory từ `aide-memory` MCP mỗi session start.
6. **Mod #3**: `governance-drift.ts` — periodic check `check_governance.py` + báo cáo drift.
7. **Per-agent `effort`** — pin reasoning effort (`low|medium|high|xhigh|max`) trong frontmatter (cmdc reference mới).
8. **`/plans <name>`** — browse saved plans từ session trước.
9. **Tạo `~/.commandcode/AGENTS.md`** — user-level memory tier 1.
10. **Per-skill `user-invocable: false`** cho skill nội bộ (nuwa, domain-adapters) — chỉ model thấy, user không thấy trong `/` menu.
