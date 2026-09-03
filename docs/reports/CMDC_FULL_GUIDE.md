# CMDC_FULL_GUIDE — Tài liệu toàn diện về command-code (cmdc) trong workspace này

> Định kỳ: 2026-08-27
> Phiên bản: 1.0
> Phạm vi: 3 lớp (`.devin` AHD + `.opencode` + `HLK`) → cmdc
> Mục đích: Tài liệu tham chiếu + quy trình FULL FLOW / FULL CHAIN / MAX POWER / LOOP
> Restart: cần restart cmdc session sau khi apply để wire mới có hiệu lực

---

## Phần 0 — Quick reference 1 phút

| Câu hỏi | Lệnh |
|----------|------|
| Muốn chạy 1 task M-tier trở lên? | `/full-power <task>` |
| Chỉ plan, không execute? | `/plan <task>` |
| Free tier cho code đơn giản? | `/glm <task>` hoặc `/kimi <task>` |
| Paid, nhanh cho task khó? | `/lightning <task>` (chỉ khi cần) |
| Red-team 1 artifact? | `/adversarial-consensus <artifact>` |
| Nâng cấp chính workspace? | `/harness-upgrade` |
| Kiểm tra HLK nhanh? | `/hlk-status` |
| Kiểm tra HLK sâu? | `/hlk-integrity-check` |
| Git workflow có HLK guard? | `/hlk-git-tools <action>` hoặc `/hlk-git-doctor` |
| Tự học HLK? | `/hlk-loop <status\|dry-run\|reset\|iterate>` |
| Redact secret? | `/hlk-sanitize <file\|text>` |
| MAX POWER HLK? | `/hlk-max-power` |
| Phân tích sâu (6 prompt)? | `/hlk-prompts <num\|keyword>` |

---

## Phần 1 — Tổng quan 3 lớp

Workspace này chạy **3 lớp song song**, command-code (cmdc) là CLI ở trên cùng.

```
┌───────────────────────────────────────────────────────────────┐
│  command-code (cmdc)  —  CLI bạn đang dùng                    │
│  /full-power, /plan, /hlk-status, ...                         │
└───────────────────────────────────────────────────────────────┘
        │                │                  │
        ▼                ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  .devin/     │  │  .opencode/  │  │  HLK/        │
│  AHD layer   │  │  opencode    │  │  Security    │
│              │  │  layer       │  │  layer       │
│  15 canon    │  │  6 agents    │  │  5 bin       │
│  17 SKILL    │  │  32 SKILL    │  │  9 wrappers  │
│  11 agents   │  │  15 personas │  │  8 git-tools │
│  88+ skill   │  │  10 commands │  │  2 security  │
│  13 hooks    │  │  L0-L4 tool  │  │  6 prompts   │
│  22 scripts  │  │  registry    │  │  3 skills    │
│  4 MCP       │  │  harness.ts  │  │  loop        │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Tổng tài sản cmdc có thể dùng**:

- 49 SKILL.md (17 trong `.devin/skills/` + 32 wrapper trong `.opencode/skills/`)
- 11 custom agent (5 harness + 5 personas + 1 HLK operator)
- 15 custom slash command
- 4 hook shim + 1 HLK hook (5 line tổng)
- 2 MCP server (aide-memory + ruflo-hlk-mcp)
- 36 deny / 8 ask / 25 allow permission rules
- 1 index skill (`cmdc-harness-bridge`)

---

## Phần 2 — Skills (49 files)

### 2.1 Top-level skills (17 trong `.devin/skills/`)

| Skill | Mô tả ngắn |
|-------|------------|
| `full-power` | MAX POWER 18-step chain (Plan→Approve→Execute + adversarial + QC) |
| `plan` | Plan phase only (SDD + decompose + quality check + approval gate) |
| `lightning` | SWE-1.7 Lightning executor wrapper (1000 tok/s, paid) |
| `glm` | GLM-5.2 executor wrapper (free) |
| `kimi` | Kimi K2.7 executor wrapper (free) |
| `adversarial-consensus` | 3-persona adversarial review |
| `harness-upgrade` | Tự rà soát + nâng cấp workspace |
| `hlk-loop` | HLK pipeline tự học |
| `hlk-integrity-check` | Verify HLK layer |
| `hlk-git-tools` | HLK git commit/push/doctor |
| `nuwa-skill` | Distill mental models (Feynman/Munger/Taleb perspective) |
| `update_from_repos` | Sync từ upstream repos |
| `aide-memory` | Persistent memory (recall/remember) |
| `assets` | Slop patterns + vault assets |
| + 3 detail skills | `harness-upgrade/detail/*`, `nuwa-skill/*` |

### 2.2 Wrapper skills (32 trong `.opencode/skills/`)

Mirror `.devin/skills/` cho opencode runtime, bao gồm:
- 10 skills chính (mirror từ `.devin`): adversarial-consensus, aide-memory, full-power, plan, glm, kimi, lightning, harness-upgrade, hlk-loop, hlk-upstream-pull, hlk-integrity-check
- 7 utility: assets, context-compactor, gap-scan, harness-sensor, init_deep, loop-memory, memory-audit, slop-detector, systematic_debugging, tdd, claim-grader, fable-judge, comment_checker, auditor, graph-verify
- 2 nuwa examples: taleb-perspective, munger-perspective, feynman-perspective
- 12 domain-adapters: business-ops, coding, data, design, devops, finance, generic, legal, marketing, research (10 main + template + readme = 12)

### 2.3 Skill index cho cmdc (1 file)

- `.commandcode/skills/cmdc-harness-bridge/SKILL.md` — chỉ mục liệt kê 3 lớp + cách cmdc surface resolve + delegation map.

---

## Phần 3 — Agents (11 files trong `.commandcode/agents/`)

### 3.1 5 harness

| Agent | Vai trò | Tools |
|-------|---------|-------|
| `commander` | Orchestrator (Plan + dispatch + review) | read, glob, grep, agent, run_command |
| `executor-glm` | Free tier, simple ops (GLM-5.2) | + edit, write, shell |
| `executor-kimi` | Free tier, code gen (Kimi K2.7) | + edit, write, shell |
| `executor-lightning` | Paid, complex_reasoning (SWE-1.7 Lightning 1000 tok/s) | + edit, write, shell |
| `verifier` | Read-only done-gate (fable-judge style) | read, glob, grep |

### 3.2 5 personas (cmdc)

| Agent | Vai trò |
|-------|---------|
| `persona-architect` | System design, trade-off matrix, ADRs |
| `persona-code-reviewer` | Bugs, security, test coverage, naming |
| `persona-saboteur` | Red-team attack 8 vector (A-H) |
| `persona-security-auditor` | OWASP, secrets, sandbox, egress |
| `persona-new-hire` | Onboarding gap, doc quality |

### 3.3 1 HLK operator

| Agent | Vai trò |
|-------|---------|
| `hlk-engineer` | HLK status/integrity/sanitize/git-tools/MAX POWER/prompts/loop. **BẮT BUỘC ở step 5 PREFLIGHT của full-power.** |

### 3.4 Agent liên quan (không wrap cmdc, có sẵn trong `.opencode/` + `.devin/`)

- 5 workers AHD: `SCOUT`, `BUILDER`, `AUDITOR`, `MEMORY_KEEPER`, `VERIFIER` (xem `.devin/agents/workers/`)
- 6 personas Devin: `architect`, `code_reviewer`, `git_workflow_master`, `new_hire`, `saboteur`, `security_auditor`
- 15 personas/roles opencode: architect, auditor, builder, code_reviewer, commander, git_workflow_master, 3 executors (glm/kimi/lightning), memory_keeper, new_hire, saboteur, scout, security_auditor, verifier
- 6 harness opencode: harness-orchestrator, harness-executor-glm/kimi/lightning, harness-verifier, harness-subagent

---

## Phần 4 — Slash commands (15 files)

### 4.1 Core (10)

| Command | Nguồn | Mục đích |
|---------|-------|----------|
| `/full-power` | `.devin/skills/full-power/` | MAX POWER 18-step |
| `/plan` | `.devin/skills/plan/` | Plan only |
| `/lightning` | `.devin/skills/lightning/` | SWE-1.7 paid |
| `/glm` | `.devin/skills/glm/` | GLM-5.2 free |
| `/kimi` | `.devin/skills/kimi/` | Kimi K2.7 free |
| `/adversarial-consensus` | `.devin/skills/adversarial-consensus/` | 3-persona review |
| `/harness-upgrade` | `.devin/skills/harness-upgrade/` | Self-improve |
| `/hlk-git-tools` | `HLK/skills/hlk-git-tools/` | Git workflow |
| `/hlk-integrity-check` | `HLK/skills/hlk-integrity-check/` | Verify HLK |
| `/hlk-loop` | `HLK/skills/hlk-loop/` | Self-learning |

### 4.2 HLK mở rộng (5 mới)

| Command | Wrap | Mục đích |
|---------|------|----------|
| `/hlk-status` | `node HLK/bin/hlk-status.mjs --self-test` + `hlk-verify-integrity.js` | Diagnostic nhanh |
| `/hlk-sanitize` | `HLK/security/sanitizer.js` (28 patterns) | Redact secret |
| `/hlk-git-doctor` | `node HLK/git-tools/hlk-git-doctor.mjs` | Git pre-flight |
| `/hlk-max-power` | `node HLK/bin/hlk-update.mjs --yes` + status | MAX POWER flow |
| `/hlk-prompts` | 6 prompts trong `HLK/prompts/` | Phân tích sâu |

---

## Phần 5 — Hooks (5 lines — chạy theo thứ tự)

### 5.1 SessionStart

```
1. .commandcode/hooks/session-start-git.sh    (inject git branch + status)
2. .commandcode/hooks/bridge-devin.sh          (forward tới .devin/hooks/session_start.py)
```

### 5.2 PreToolUse shell (3 line theo thứ tự)

```
1. .commandcode/hooks/deny-dangerous.sh              (block destructive: rm -rf /, force-push, curl|sh, mkfs, dd, chmod 777, ...)
2. node HLK/wrappers/hlk-hook-launcher.mjs          (HLK sanitizer 28 patterns + telemetry blocker)
3. .commandcode/hooks/bridge-devin.sh PreToolUse     (forward tới .devin/hooks/pre_tool_use.py)
```

### 5.3 PreToolUse write|edit

```
1. .commandcode/hooks/bridge-devin.sh PreToolUse write   (forward tới .devin/hooks/pre_tool_use.py)
```

### 5.4 PostToolUse shell

```
1. node HLK/wrappers/hlk-hook-launcher.mjs          (HLK post-process)
2. .commandcode/hooks/bridge-devin.sh PostToolUse     (forward tới .devin/hooks/post_tool_use.py)
```

### 5.5 PostToolUse write|edit

```
1. .commandcode/hooks/bridge-devin.sh PostToolUse write   (forward + audit)
2. .commandcode/hooks/audit-writes.sh                       (append audit log)
```

---

## Phần 6 — MCP servers (2 file trong `.mcp.json`)

| Server | Command | Timeout | Mục đích |
|--------|---------|---------|----------|
| `aide-memory` | `npx -y aide-memory mcp .` | 20s | Persistent memory (recall/remember/search/update/forget) |
| `ruflo-hlk-mcp` | `node HLK/wrappers/ruflo-hlk-mcp.mjs mcp start` | 30s | HLK qua MCP cho cross-tool access |

---

## Phần 7 — Quy trình (chain) — cách chạy

### 7.1 CHAIN A — Sửa nhanh 1 file (S-tier, 1 turn)

```
/glm "sửa typo trong src/auth.ts dòng 42, đổi 'autorization' thành 'authorization'"
# hoặc đơn giản gõ trực tiếp không cần slash command
```

**Áp dụng khi**: <5 dòng, 1 file, no destructive, no verification.
**KHÔNG chạy** 3-phase.

---

### 7.2 CHAIN B — Task đơn giản có verify (M-tier, vài phút)

```
/kimi "thêm field email vào User model + 1 unit test"
```

**Áp dụng khi**: 1-3 file, simple logic, 30min-2h.
**Có 3-phase rút gọn** (plan → execute → verify).

---

### 7.3 CHAIN C — Task phức tạp (M/L-tier, đầy đủ 3-phase)

```
/plan "refactor checkout module support multi payment provider"
# orchestrator chạy: BRAINSTORM → SCOUTs → ARCHITECT → adversarial → SDD approval → QC → plan approval
# → bạn duyệt plan → /full-power để execute
```

**Áp dụng khi**: multi-file, cần research, 2h+.
**3-phase đầy đủ**: Plan (auto) → Approve (bạn) → Execute (auto).

---

### 7.4 CHAIN D — MAX POWER toàn diện (XL-tier, full 18 step + HLK)

```
/full-power "nâng cấp auth subsystem: OAuth2 + RBAC + audit log + threat model + tests"
```

**Áp dụng khi**: architecture change, security-critical, multi-system.
**18 step đầy đủ** (xem Phần 8 chi tiết) + dispatch 37 agent + load 49 skill + 15 canon + 6 HLK prompt.

---

### 7.5 CHAIN E — Red-team 1 artifact

```
/adversarial-consensus "docs/plans/foo/IMPLEMENTATION_PLAN.md"
```

**Áp dụng khi**: cần verify 1 plan/code trước merge.
**3 persona song song**: architect + saboteur + security_auditor (hoặc code_reviewer).

---

### 7.6 CHAIN F — Self-improve workspace

```
/harness-upgrade
```

**Áp dụng khi**: định kỳ (1 tuần / 1 tháng) hoặc khi cảm thấy token/quality giảm.
**FULL CHAIN**: PREFLIGHT → REVIEW → LEARN → UPGRADE → VERIFY → RED-TEAM v2.0 + V5 → COMPENSATION → REPORT → APPLY.

---

### 7.7 CHAIN G — HLK MAX POWER + verify

```
/hlk-max-power
# hoặc:
/hlk-status
/hlk-integrity-check
/hlk-git-doctor
```

**Áp dụng khi**: trước commit lớn, sau khi merge, hoặc định kỳ.

---

### 7.8 CHAIN H — Loop tự học (continuous improvement)

```
/hlk-loop status
/hlk-loop dry-run
/hlk-loop iterate
/hlk-loop reset
```

**Áp dụng khi**: muốn HLK tự học pattern mới từ session.

---

### 7.9 CHAIN I — Phân tích sâu qua prompt

```
/hlk-prompts                          # list 6 prompts
/hk-prompts 02                        # run red-team security
/hlk-prompts architect                # run solution architect
/hlk-prompts data-leak                # run data leak hardening
```

**Áp dụng khi**: cần phân tích chuyên sâu 1 khía cạnh (codebase / red-team / architect / data-leak / harness-hardening / ruflo-hardening).

---

## Phần 8 — FULL FLOW của `/full-power` (18 step)

**Đây là chain MAX POWER. Mỗi step đều BẮT BUỘC, KHÔNG skip.**

| # | Step | Owner | Output |
|---|------|-------|--------|
| 1 | BOOT (lazy-load canon tier S/M/L) | `commander` | session state |
| 2 | INVENTORY (skills/agents/hooks/scripts/canon/MCP) | `commander` | inventory.json |
| 3 | COMMANDER MODE | `commander` | role-loaded |
| 4 | TIER CLASSIFICATION (S/M/L/XL) | `commander` | tier |
| 5 | PREFLIGHT (log_rotation → hook_integrity → session init → cost cap → pre_task_audit → **HLK self-test + integrity** qua `hlk-engineer`) | `commander` + `hlk-engineer` | session_id + cap + HLK status |
| 6 | BRAINSTORM (6 góc + Nuwa cognitive) | brainstorm×6 | BRAINSTORM_REPORT.md |
| 7 | 8 SCOUTs (research online song song) | SCOUT×8 | scout findings |
| 8 | ARCHITECT (viết SDD) | `persona-architect` | SOLUTION_DESIGN.md |
| 9 | 6+ ADVERSARIAL REVIEWERS + dynamic attack scenarios | saboteur + personas×6 | attack_report.md |
| 10 | SDD APPROVAL GATE (interactive) | user via `approval_gate.py` | approved SDD |
| 11 | DECOMPOSE SDD → atomic tasks | BUILDER worker | IMPLEMENTATION_PLAN.md |
| 12 | GAP_SCAN | gap-scan skill | gap report |
| 13 | 10-D QUALITY CHECK | `plan_quality_check.py` | QUALITY_REPORT.md |
| 14 | PLAN_ENHANCE (gap-scan + adversarial + nuwa + claim-grader + slop-detector) | composer | enhanced plan |
| 15 | PLAN APPROVAL GATE | user | approved plan |
| 16 | EXECUTE (DAG parallel + TDD + systematic_debugging + 3-layer verify) | BUILDER×N + EXECUTOR | code changes |
| 17 | MEMORY + NUWA (L/XL) + REPORT | memory_keeper + nuwa | report + memory |
| 18 | APPLY (M+ qua /full-power, S-tier sửa trực tiếp) | `commander` | applied |

### 8.1 Mod được load theo phase (KHÔNG load all cùng lúc)

```
Boot/Preflight:   CORE_CANON, BOOT_PROTOCOL, REDLINES (top 5)
BRAINSTORM:       nuwa-skill, user-preference
SCOUTs:           domain-adapters (12 adapters), update_from_repos
ARCHITECT:        harness-engineering, HARNESS_ENGINEERING.md
Adversarial:      adversarial-consensus, fable-judge, claim-grader
QC:               gap-scan, slop-detector, comment_checker
EXECUTE:          tdd, systematic_debugging, harness-sensor, graph-verify
Memory/Nuwa:      memory-audit, loop-memory, nuwa-skill
HLK (mọi phase):  HLK/prompts/* (load on-demand qua /hlk-prompts)
```

### 8.2 Agent được dispatch theo phase

- Step 1-4: `commander` (main thread)
- Step 5: `commander` + **`hlk-engineer`** (BẮT BUỘC)
- Step 6: 6 brainstorm subagents song song
- Step 7: 8 SCOUTs song song
- Step 8: `persona-architect` (load `.devin/agents/personas/architect.md`)
- Step 9: 6+ personas song song — `persona-architect`, `persona-saboteur`, `persona-security-auditor`, `persona-code-reviewer`, `persona-new-hire`, + persona Devin + persona opencode
- Step 11: BUILDER worker (AHD)
- Step 16: `executor-glm/kimi/lightning` (route theo task type) + BUILDER×N song song
- Step 17: `memory_keeper` + `verifier` (independent done-gate) + nuwa
- Tổng: **37 agent unique** (5 harness + 5 personas cmdc + 1 HLK + 5 workers + 6 personas Devin + 15 personas opencode)

---

## Phần 9 — LOOP MAX PERFORMANCE (tự học liên tục)

### 9.1 `/hlk-loop` — Self-learning pipeline

`HLK/loop/hlk-loop.mjs` chạy pipeline:

```
[observe] → [learn] → [validate] → [consolidate] → [regress check] → [apply]
```

Subcommands:

- `status` — xem state hiện tại (counters, last iteration, retention).
- `dry-run` — chạy 1 iteration không apply.
- `iterate` — chạy 1 iteration có apply.
- `reset` — clear state (DESTRUCTIVE, cần user confirm).

### 9.2 Vòng đời 1 task hoàn chỉnh (FULL LOOP)

```
1. /hlk-status                      # check baseline
2. /full-power "<task>"             # run chain
3. orchestrator auto-call:          # 18 step
   - PREFLIGHT (HLK self-test)
   - BRAINSTORM
   - SCOUTs
   - ARCHITECT
   - adversarial
   - SDD approval ←── bạn duyệt
   - DECOMPOSE
   - QC
   - PLAN_ENHANCE
   - PLAN approval ←── bạn duyệt
   - EXECUTE (TDD + verify)
   - MEMORY write-back
   - REPORT
4. /hlk-loop iterate                # HLK tự học từ task vừa xong
5. /hlk-status                      # verify still green
6. /hlk-git-tools commit "msg"      # commit (sau khi doctor pass)
7. /hlk-git-tools push              # push
```

### 9.3 Bật MAX LOOP

```bash
# Bật HLK tự học + auto-iterate
node HLK/loop/hlk-loop.mjs --auto-iterate --yes
# (xem HLK/loop/ cho flags chi tiết)
```

---

## Phần 10 — Bảng quyết định: dùng chain nào?

| Đặc điểm task | Chain | Lệnh |
|----------------|-------|------|
| <5 dòng, 1 file | A (Sửa nhanh) | gõ trực tiếp hoặc `/glm` |
| 1-3 file, simple logic | B (Kimi executor) | `/kimi <task>` |
| Multi-file, cần research | C (Plan → Execute) | `/plan` → `/full-power` |
| Architecture / security-critical | D (MAX POWER) | `/full-power <task>` |
| Verify 1 artifact | E (Adversarial) | `/adversarial-consensus <artifact>` |
| Định kỳ self-improve | F (Harness upgrade) | `/harness-upgrade` |
| HLK security check | G (HLK) | `/hlk-status` / `/hlk-max-power` |
| Continuous learning | H (Loop) | `/hlk-loop iterate` |
| Phân tích sâu | I (Prompts) | `/hlk-prompts <num>` |

---

## Phần 11 — Guardrails (BẮT BUỘC)

1. **M+ tier → phải qua Plan** (`/full-power` hoặc `/plan`).
2. **S-tier (1 file, <5 dòng) → sửa trực tiếp OK**, không cần Plan.
3. **Không đụng `HLK/`, `.env`** trừ khi user nói rõ file đó.
4. **Không force-push, không rm-rf / hoặc ~** — `deny-dangerous.sh` đã chặn.
5. **Trước commit/push** → `/hlk-git-doctor` bắt buộc.
6. **Sau merge** → `/hlk-integrity-check` bắt buộc.
7. **Mọi "done" claim** phải có deterministic gate:
   - `python tools/check_governance.py`
   - `node HLK/bin/hlk-status.mjs --self-test`
   - `node HLK/wrappers/hlk-verify-integrity.js`
   - `pytest -q` (relevant module)
8. **Report đúng nơi**:
   - `docs/plans/<slug>/EXECUTION_REPORT.md` (cho task theo plan)
   - `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md` (cho report ad-hoc)
9. **Tier 1 Critical** từ adversarial review → fix ngay trong session, không để deferred.
10. **Memory write-back** sau mỗi task: dispatch `memory_keeper` worker ở step 17.

---

## Phần 12 — Restart & first-run checklist

Sau khi apply wrap (hoặc sau khi pull code mới):

```bash
# 1. Verify governance
python tools/check_governance.py
# Expect: errors=0

# 2. Verify HLK
node HLK/bin/hlk-status.mjs --self-test
node HLK/wrappers/hlk-verify-integrity.js
# Expect: both pass (1 known issue: hlk-lifecycle.mjs missing — pre-existing)

# 3. Verify JSON
node -e "JSON.parse(require('fs').readFileSync('.commandcode/settings.json'))"
node -e "JSON.parse(require('fs').readFileSync('.mcp.json'))"
# Expect: silent (no error)

# 4. Restart cmdc
cmd
# Expect: SessionStart hook chạy, /full-power xuất hiện, /hlk-status xuất hiện
```

Trong session cmdc đầu tiên:

```
/skills                  # verify 49 skills listed
/agents                  # verify 11 custom agents
/mcp                     # verify 2 MCP servers connected
/hlk-status              # quick diagnostic
/full-power "test task nhỏ"   # smoke test full chain
```

---

## Phần 13 — Tài liệu liên quan

- `docs/reports/CMDC_WRAP_REPORT.md` — báo cáo apply wrap (cách áp dụng + verification).
- `docs/AGENTS_full_reference.md` — tham chiếu đầy đủ AHD.
- `docs/USAGE_GUIDE.md` — hướng dẫn tổng hợp.
- `docs/CONTINUOUS_LOOP_GUIDE.md` — hướng dẫn loop liên tục.
- `HLK/docs/15-full-setup-guide.md` — hướng dẫn HLK đầy đủ.
- `HLK/docs/10-setup-max-power.md` — MAX POWER setup.
- `HLK/docs/05-van-hanh-runbook-va-playbook.md` — runbook hàng ngày.
- `.commandcode/skills/cmdc-harness-bridge/SKILL.md` — index trong cmdc.
