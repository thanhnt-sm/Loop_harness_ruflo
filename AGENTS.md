# Devin CLI — Agent Harness Deploy (AHD)

> **Full reference**: `docs/AGENTS_full_reference.md` (load on-demand only)
> **Usage guide**: `docs/USAGE_GUIDE.md` — tất cả skills/agents/flows
> **Loop guide**: `docs/CONTINUOUS_LOOP_GUIDE.md` — chạy loop liên tục

## Language Policy (BẮT BUỘC cho mọi agent)

> **TẤT CẢ AI agent trong workspace này PHẢI phản hồi bằng tiếng Việt có dấu.**
> - Response language: **tiếng Việt** (có dấu đầy đủ: à, á, ả, ã, ạ, ă, â, đ, ê, ô, ơ, ư...)
> - Code comments: **tiếng Việt**, tự nhiên, dễ hiểu
> - Technical terms giữ nguyên tiếng Anh: API, token, commit, branch, merge, deploy, hook, skill, agent...
> - Lần đầu dùng technical term: ghi chú ngắn trong ngoặc đơn, ví dụ: "commit (đánh dấu một phiên bản code)"
> - Commit messages: giữ nguyên tiếng Anh (theo git convention)
> - File names, variable names: giữ nguyên tiếng Anh (không dấu)
> - **KHÔNG BAO GIỜ** trả lời bằng tiếng Anh với user trừ khi user yêu cầu rõ ràng

## Workspace Governance (BẮT BUỘC — mọi agent, mọi provider)

> **File gốc**: `.devin/rules/WORKSPACE_GOVERNANCE.md` (đọc khi cần chi tiết).
> **Lint nhanh**: `python3 tools/check_governance.py` — chạy trước khi kết thúc task.

- **Không sinh file rác**: không tạo scratch/`*.bak`/`*.tmp`/file vô danh ở root/docs; file tạm → `tmp/` (gitignored), xóa khi xong.
- **File vào đúng nơi**: script → `.devin/scripts/` (+ test `tests/test_*.py`); hook → `.devin/hooks/`; plan → `docs/plans/<slug>/IMPLEMENTATION_PLAN.md`; report → `docs/plans/<slug>/EXECUTION_REPORT.md` hoặc `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md`; utility → `tools/`. Markdown mới ở root = vi phạm.
- **Runtime enforcement**: `pre_tool_use.py` + `plan_enforce.py` chặn ngay `write`/`edit`/`notebook_edit` và lệnh Bash tạo `.md`/junk ở root không nằm trong allowlist. Nếu bị chặn, dùng đúng thư mục theo bảng trên.
- **Khớp plan ↔ act**: Act chỉ sửa file có trong `File Path` của plan (đã duyệt) + test file của task; sau act viết execution report; self-check bằng `tools/check_governance.py --plan-act`.
- **Đa provider**: không ghi state của provider này vào thư mục provider khác (`.devin/` ↔ Devin, `.khuym/` ↔ Khuym, `.opencode/` ↔ opencode, `.aide/` ↔ Aide); runtime state gitignored không commit; `.devin/canon/` + `HLK/` cấm sửa trực tiếp.

## Orchestrator skills (3 executors)

| Skill | Executor | Model | Cost | Khi nào |
|-------|----------|-------|------|---------|
| `/lightning` | lightning-executor | SWE-1.7 Lightning | $2.5/$12.5 MTok | Cần tốc độ (1000 tok/s) |
| `/glm` | glm-executor | GLM-5.2 High | **Free** | Free tier, reasoning cao |
| `/kimi` | kimi-executor | Kimi K2.7 | **Free tier** | Open-source |

Pattern chung: orchestrator (active model) plan/review → executor implement/test/report.

## Cách dùng nhanh

```bash
cd . && devin                          # Mở CLI
devin -p -- "mô tả công việc"          # Non-interactive

/full-power <task>    # 3-Phase đầy đủ (Plan→Approve→Execute) — FORCE Plan bắt buộc
/plan <task>          # Chỉ Phase 1: Plan (SDD + SDD approval + quality check + plan approval gate)
/lightning <task>     # Executor SWE-1.7 Lightning (sau khi plan approved)
/glm <task>           # Executor GLM-5.2 (free, sau khi plan approved)
/kimi <task>          # Executor Kimi K2.7 (free, sau khi plan approved)
/adversarial-consensus <artifact>  # 3-persona adversarial review
/aide-memory          # Persistent memory recall/remember
/nuwa-skill <task>    # Research-heavy content tasks
/hlk-git-tools      # Git commit/push/doctor tools
/hlk-integrity-check  # Verify HLK layer integrity
/hlk-loop            # HLK pipeline tự học (status/dry-run/reset/iterate)
/assets               # Slop patterns and vault assets
/auditor              # Audit code
/tdd                 # Test-driven development
/gap-scan            # Scan thiếu sót
/harness-upgrade     # Rà soát + nâng cấp workspace thành best harness (token-efficient, small-context)
```

## 3-Phase Architecture (Plan → Approve → Execute) — BẮT BUỘC

**M-tier+ tasks BẮT BUỘC đi qua 3 phase. KHÔNG SKIP. Hook `plan_enforce.py` sẽ block Write/Edit nếu chưa có approved plan cho task hiện tại.**

### Auto-activation mechanism

#### Khi user gõ slash skill (`/plan <task>` hoặc `/full-power <task>`)

1. Skill được inject vào agent context
2. Agent đọc **AUTO-ACTIVATION directive** (section đầu tiên của skill)
3. Agent **NGAY LẬP TỨC** chạy `.venv/bin/python .devin/scripts/plan_orchestrator.py --init --task "<task>"`
4. Orchestrator trả `next_action` → agent thực hiện → báo results qua `--step` → lặp lại cho đến DONE

#### Khi user chỉ đưa ra task (không gõ slash skill)

1. Phân tích ý định trước:
   - Nếu là câu hỏi, giải thích, yêu cầu thông tin → **trả lời trực tiếp**, KHÔNG kích hoạt skill.
   - Nếu là task cần thực hiện → tiếp tục classify tier.
2. Classify tier:
   - **S-tier** (<5 dòng, 1 file, không verification, không destructive) → sửa trực tiếp, sau đó report.
   - **M/L/XL** → **mặc định gọi `/full-power <task>`** để chạy full chain: PREFLIGHT → Plan → Approve → Execute → Nuwa (L/XL) → Memory → Report.
3. User có thể override bằng cách gõ slash skill rõ ràng: `/lightning`, `/glm`, `/kimi`, `/plan`, `/adversarial-consensus`, v.v.

**Không cần manually chạy CLI. Skill tự động kích hoạt orchestrator.**

### 3 Phase flow

1. **PLAN** (`/plan` hoặc `/full-power`): Orchestrator FSM tự động:
   - **BRAINSTORM** (MỚI) — 6+ góc nhìn đa chiều (fastest, safest, simplest, scale, cheapest, robust) + Nuwa cognitive
   - Dispatch **8 SCOUTs** song song (tất cả search online) → collect findings
   - Dispatch 1 ARCHITECT → write SDD
   - Dispatch **6+ adversarial reviewers** + dynamic attack scenarios → aggregate findings
   - **SDD approval gate** — duyệt `SOLUTION_DESIGN.md` trước
   - Decompose SDD thành atomic tasks → write `IMPLEMENTATION_PLAN.md`
   - **GAP_SCAN** (MỚI) — quét thiếu sót trước khi QC
   - Run 10-D quality check → `QUALITY_REPORT.md`
   - **PLAN_ENHANCE** (MỚI) — nâng cấp plan tối đa: gap-scan + adversarial-consensus + nuwa + claim-grader + slop-detector
   - **Plan approval gate** — duyệt `IMPLEMENTATION_PLAN.md`
2. **APPROVE**: 2 interactive approval gates (`approval_gate.py --interactive --artifact sd|plan`)
3. **EXECUTE**: DAG-based parallel dispatch + TDD + systematic_debugging + 3-layer verify (schema_gate + adversarial-consensus + coverage_matrix) + fable-judge + graph-verify → coverage + audit

S-tier (<5 lines, 1 file, no destructive op) → orchestrator auto-skip, sửa trực tiếp.

**Tài liệu kỹ thuật đầy đủ**: `docs/PLAN_ORCHESTRATOR_GUIDE.md`

## Guardrails

- Smallest coherent diff — không scope creep
- Preserve pre-existing user changes
- No destructive ops (chặn bởi hooks: rm -rf, force-push, drop table)
- No unrelated refactors/dependencies/docs
- Trivial edits sửa thẳng, skip delegation
- Fan-out chỉ khi write sets disjoint + user yêu cầu
- Executor unavailable → stop, report missing profile

## Dependency Management (BẮT BUỘC — không phá CI)

`requirements-lock.txt` là **hash-pinned lock** (sinh bởi `uv pip compile`). Bump sai một package = phá `--require-hashes` + `supply-chain` + `CI`.

1. **KHÔNG sửa tay version/hash trong `requirements-lock.txt`**. Muốn đổi dep → sửa `pyproject.toml` rồi regenerate:
   ```bash
   uv pip compile pyproject.toml -o requirements-lock.txt --generate-hashes
   ```
2. **`filelock` PIN `<3.13`** (có comment giải thích trong `pyproject.toml`). filelock 3.13+ eager import asyncio (~6s) làm hook vượt timeout 2.5s. **Không bao giờ bump độc lập** — đã có `ignore` trong `.github/dependabot.yml`.
3. **`pydantic-core` pin `==` bởi `pydantic`**. Bump `pydantic-core` độc lập → `ResolutionImpossible` (pydantic 2.x yêu cầu đúng một version pydantic-core). Bump `pydantic` + `pydantic-core` cùng nhau.
4. **SBOM phải khớp lock**: `sbom/python.sbom.json` phản ánh deps trong lock. Đổi lock → cập nhật SBOM.
5. Trước khi commit thay đổi dependency: chạy `python tools/check_deps.py` (chặn filelock vi phạm pin, pydantic-core lệch, SBOM drift). Pre-commit hook đã auto-chạy khi stage file dep.
6. **Không commit debug noise** (print debug, file tạm, commit `debug:`/`fix:` lặp lại). Chạy test + `python tools/check_governance.py` trước khi push.

## MCP servers

| Server | Mục đích |
|--------|----------|
| aide-memory | Persistent memory (recall/remember) |
| spark-memory | Shared memory cross-agent |
| deepwiki | Query GitHub repo docs |
| devin | Devin V3 API (sessions, playbooks) |

## Canon (on-demand, KHÔNG load all at BOOT)

| File | Load khi nào |
|------|-------------|
| CORE_CANON.md | BOOT (always) |
| BOOT_PROTOCOL.md | BOOT (always) |
| REDLINES.md | BOOT (top 5 only) |
| LOOP_PROTOCOL.md | Chạy loop |
| VERIFICATION_PROTOCOL.md | Verify output |
| MEMORY_PROTOCOL.md | Manage memory |
| CAVEMAN_PROTOCOL.md | Compress context |
| HARNESS_ENGINEERING.md | Design harness |

## AHD components (on-demand)

- **Canon**: `.devin/canon/` — 15 protocol files
- **Skills**: `.devin/skills/` — 12 skills (plan, full-power, lightning, glm, kimi, adversarial-consensus, aide-memory, nuwa-skill, hlk-git-tools, hlk-integrity-check, hlk-loop, assets)
- **Agents**: `.devin/agents/` — 3 executors + COMMANDER + 6 personas + 5 workers
- **Hooks**: `.devin/hooks/` — 13 Python hooks
- **Scripts**: `.devin/scripts/` — 21 runtime scripts
- **HLK**: `HLK/` — security layer
- **Tools**: `tools/` — packaging, deploy, init-new-project, verify, health-check

## Safe zones cho code changes

- `src/`, `.devin/skills/`, `.devin/agents/`, `scripts/` — OK
- `HLK/`, security policies, `.env` — **KHÔNG đụng**

<!-- KHUYM:START -->
# Khuym Workflow

Use `khuym:using-khuym` first in this repo unless you are resuming an already approved Khuym handoff.

## Startup

1. Read this file at session start and again after any context compaction.
2. If `.khuym/onboarding.json` is missing or outdated, stop and run `khuym:using-khuym` before continuing.
3. If `.codex/khuym_status.mjs` exists, run `node .codex/khuym_status.mjs --json` as the first quick scout step.
4. If `.khuym/HANDOFF.json` exists, do not auto-resume. Surface the saved state and wait for user confirmation.
5. If `history/learnings/critical-patterns.md` exists, read it before planning or execution work.

## Chain

```
khuym:using-khuym
  → khuym:exploring
  → khuym:planning
  → khuym:validating
  → khuym:swarming
  → khuym:executing
  → khuym:reviewing
  → khuym:compounding
```

## Critical Rules

1. Never execute without validating.
2. `CONTEXT.md` is the source of truth for locked decisions.
3. If context usage passes roughly 65%, write `.khuym/HANDOFF.json` and pause cleanly.
4. Treat `.khuym/state.json` as the single runtime state file for routing, current focus, and operator notes.
5. After compaction, re-read `AGENTS.md`, run `node .codex/khuym_status.mjs --json` if present, then re-open `.khuym/HANDOFF.json`, `.khuym/state.json`, and the active feature context before more work.
6. P1 review findings block merge.

## Working Files

```
.khuym/
  onboarding.json     ← onboarding state for the Khuym plugin
  state.json          ← single runtime state file for agents, tools, and humans
  HANDOFF.json        ← pause/resume artifact
  reservations.json   ← local file reservations for same-session Codex swarms

history/<feature>/
  CONTEXT.md          ← locked decisions
  discovery.md        ← research findings
  approach.md         ← approach + risk map

history/learnings/
  critical-patterns.md

.beads/               ← bead/task files when beads are in use
.spikes/              ← spike outputs when validation requires them
```

.codex/
  khuym_status.mjs    ← read-only scout command for onboarding, state, and handoff
  khuym_state.mjs     ← shared state helpers used by the scout command
  khuym_reservations.mjs ← local reservation helper used by swarming, executing, and hooks

## Codex Guardrails

- Repo-local `.codex/` files installed by Khuym are workflow guardrails, not optional decoration.
- Use `node .codex/khuym_status.mjs --json` as the preferred quick scout step when it is available.
- Treat `compact_prompt` recovery instructions as mandatory.
- Use `bv` only with `--robot-*` flags. Bare `bv` launches the TUI and should be avoided in agent sessions.
- If the repo is only partially onboarded, stay in bootstrap/planning mode and surface what is missing before implementation.

## Session Finish

Before ending a substantial Khuym work chunk:

1. Update or close the active bead/task if one exists.
2. Leave `.khuym/state.json` and `.khuym/HANDOFF.json` consistent with the current pause/resume state.
3. Mention any remaining blockers, open questions, or next actions in the final response.
<!-- KHUYM:END -->


---

## HLK is Source of Truth (BẮT BUỘC — mọi agent, mọi provider)

> **Theo user directive**: từ giờ về sau, mọi phát triển hệ thống loop harness đặt vào **HLK**.
> Mọi AI agent (opencode, cmdc, Claude, GPT) phải **tham chiếu, đăng ký, dẫn chiếu** vào HLK.

### Quy tắc cứng

1. **HLK là source of truth duy nhất** cho verify-first chain.
   - Implementation: `HLK/chain/` (Python), `HLK/chain/loaders/` (Node), `HLK/chain/hlk_wrappers/` (Node wrapper)
   - Config: `HLK/config/hlk.config.json` (centralized, có section `verify_first`)
   - Skills: `HLK/skills/verify-first/SKILL.md` (canonical)
2. **Mọi provider phải trỏ vào HLK**:
   - opencode: `opencode.json` tham chiếu `HLK` + `verify-first` skills
   - cmdc: `.commandcode/skills/`, `.commandcode/agents/`, `.commandcode/commands/` — chỉ là **POINTER** tới HLK
   - .opencode: tương tự — POINTER
3. **KHÔNG tạo implementation mới ngoài HLK** — nếu cần thêm feature, edit HLK trước, sau đó sync mirror.
4. **`.devin/` là NGOẠI LỆ** — KHÔNG xóa, giữ code cũ. Phần nào HLK có mà `.devin` không có → tạo **shim re-export** ở `.devin` trỏ về HLK.
5. **Mirror 1 chiều**: HLK → providers (KHÔNG BAO GIỜ sync ngược).

### Cách tham chiếu HLK

```bash
# Chạy verify-first chain
py HLK/chain/verify_first_cli.py <BRD.md>

# Node wrapper (thêm HLK loader + audit log)
node HLK/chain/hlk_wrappers/verify-first-wrapper.mjs <BRD.md>

# Python API
import sys; sys.path.insert(0, "HLK")
from chain import BRD, parse_brd_file, should_auto_merge
```

### Khi nào KHÔNG cần chain (S-tier)

- Bug fix <5 dòng, 1 file
- Documentation update nhỏ
- Typo/format

### Khi nào BẮT BUỘC chain (M-tier+)

- Multi-file changes (≥3 files)
- Functional requirement mới
- Có test code generation
- Mọi task > 30 phút

Xem `HLK/docs/migration-diff.md` cho diff .devin vs HLK, và `HLK/skills/verify-first/SKILL.md` cho chi tiết.


---

## HLK is Source of Truth (BẮT BUỘC — mọi agent, mọi provider)

> **Theo user directive**: từ giờ về sau, mọi phát triển hệ thống loop harness đặt vào **HLK**.
> Mọi AI agent (opencode, cmdc, Claude, GPT) phải **tham chiếu, đăng ký, dẫn chiếu** vào HLK.

### Quy tắc cứng

1. **HLK là source of truth duy nhất** cho verify-first chain.
   - Implementation: `HLK/chain/` (Python), `HLK/chain/loaders/` (Node), `HLK/chain/hlk_wrappers/` (Node wrapper)
   - Config: `HLK/config/hlk.config.json` (centralized, có section `verify_first`)
   - Skills: `HLK/skills/verify-first/SKILL.md` (canonical)
2. **Mọi provider phải trỏ vào HLK**:
   - opencode: `opencode.json` tham chiếu `HLK` + `verify-first` skills
   - cmdc: `.commandcode/skills/`, `.commandcode/agents/`, `.commandcode/commands/` — chỉ là **POINTER** tới HLK
   - .opencode: tương tự — POINTER
3. **KHÔNG tạo implementation mới ngoài HLK** — nếu cần thêm feature, edit HLK trước, sau đó sync mirror.
4. **`.devin/` là NGOẠI LỆ** — KHÔNG xóa, giữ code cũ. Phần nào HLK có mà `.devin` không có → tạo **shim re-export** ở `.devin` trỏ về HLK.
5. **Mirror 1 chiều**: HLK → providers (KHÔNG BAO GIỜ sync ngược).

### Cách tham chiếu HLK

```bash
# Chạy verify-first chain
py HLK/chain/verify_first_cli.py <BRD.md>

# Node wrapper (thêm HLK loader + audit log)
node HLK/chain/hlk_wrappers/verify-first-wrapper.mjs <BRD.md>

# Python API
import sys; sys.path.insert(0, "HLK")
from chain import BRD, parse_brd_file, should_auto_merge
```

### Khi nào KHÔNG cần chain (S-tier)

- Bug fix <5 dòng, 1 file
- Documentation update nhỏ
- Typo/format

### Khi nào BẮT BUỘC chain (M-tier+)

- Multi-file changes (≥3 files)
- Functional requirement mới
- Có test code generation
- Mọi task > 30 phút

Xem `HLK/docs/migration-diff.md` cho diff .devin vs HLK, và `HLK/skills/verify-first/SKILL.md` cho chi tiết.
