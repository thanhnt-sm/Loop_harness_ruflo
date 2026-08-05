# Plan Orchestrator — Tài liệu kỹ thuật đầy đủ

> Hệ thống tự động hóa Plan Phase (Giai đoạn Lập kế hoạch) theo kiến trúc AHD 3-Phase.
> Đây là tài liệu tham chiếu chính thức cho toàn bộ thành phần, cơ chế, và cách tích hợp.

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ thống)
2. [Kiến trúc thành phần](#2-kiến-trúc-thành-phần)
3. [FSM State Machine — Cơ chế hoạt động](#3-fsm-state-machine--cơ-chế-hoạt-động)
4. [Auto-activation từ Skill / CLI](#4-auto-activation-từ-skill--cli)
5. [Enforcement Hook — Cơ chế chặn](#5-enforcement-hook--cơ-chế-chặn)
6. [Approval Gate — Cơ chế phê duyệt](#6-approval-gate--cơ-chế-phê-duyệt)
7. [Quality Check — 10 chiều đánh giá](#7-quality-check--10-chiều-đánh-giá)
8. [Subagent Dispatch — Cơ chế song song](#8-subagent-dispatch--cơ-chế-song-song)
9. [Output Files — Cấu trúc artifact](#9-output-files--cấu-trúc-artifact)
10. [CLI Reference — Tham chiếu lệnh](#10-cli-reference--tham-chiếu-lệnh)
11. [Tích hợp với Hooks](#11-tích-hợp-với-hooks)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Tổng quan hệ thống

### Vấn đề giải quyết

Trước đây, Plan Phase được mô tả trong tài liệu nhưng **không có gì tự động hóa**:
- Agent có thể bỏ qua SCOUTs (không chạy subagents nghiên cứu)
- Agent có thể bỏ qua adversarial review (không chạy 3 reviewers)
- Agent có thể bỏ qua quality check (không chạy 10-dimension check)
- Agent có thể viết code ngay mà không có plan → enforcement hook không trigger vì không có state file

### Giải pháp

**Plan Orchestrator** — một FSM (Finite State Machine, bộ máy trạng thái hữu hạn) script Python điều phối toàn bộ Plan Phase:

```
User gọi /plan <task>
  → Skill plan được kích hoạt
  → Agent đọc skill instructions
  → Agent chạy plan_orchestrator.py --init --task "<task>"
  → Orchestrator phân loại tier, trả next_action
  → Agent thực hiện next_action (dispatch subagents, viết SDD, v.v.)
  → Agent báo kết quả qua --step
  → Orchestrator chuyển state, trả next_action tiếp theo
  → Lặp lại cho đến khi DONE hoặc REJECTED
```

### Nguyên tắc thiết kế

1. **Orchestrator là navigator, Agent là driver** — Orchestrator chỉ ra cần làm gì, Agent thực hiện bằng tools (run_subagent, write, exec). Orchestrator không tự dispatch subagents hay viết files.
2. **State file là source of truth** — Mọi trạng thái được persist vào JSON file. Agent có thể ngắt giữa chừng và resume.
3. **Fail-closed** — Khi không xác định được tier → default M (require plan). Khi không parse được input → block.
4. **Max rounds** — REVISION tối đa 3 vòng, QC tối đa 3 vòng. Vượt giới hạn → escalate to human.
5. **Human approval là bắt buộc** — Không có cách nào bypass approval gate cho M-tier+ tasks.

---

## 2. Kiến trúc thành phần

### Sơ đồ tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│                     USER (người dùng)                        │
│              Gọi: /plan <task> hoặc /full-power <task>       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    DEVIN CLI (agent)                         │
│  Đọc skill → chạy orchestrator → dispatch subagents →        │
│  viết files → báo results → lặp lại                          │
└──────┬───────────┬───────────┬───────────┬──────────────────┘
       │           │           │           │
       ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ plan_    │ │ approval │ │ plan_    │ │ plan_    │
│ orchest  │ │ _gate.py │ │ quality  │ │ enforce  │
│ rator.py │ │          │ │ _check.py│ │ .py      │
│ (FSM)    │ │ (human   │ │ (10 dim) │ │ (hook)   │
└──────────┘ │ gate)    │ └──────────┘ └──────────┘
     │       └──────────┘        │            │
     │          │                │            │
     ▼          ▼                ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│              .devin/plan_state/ (JSON state files)           │
│  <task_slug>_orchestrator.json  — FSM state + history        │
│  <task_slug>_approved.json      — approval state (nếu plan   │
│                                  nằm trong docs/plans/<slug>/)│
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              docs/plans/<task_slug>/ (output artifacts)      │
│  SOLUTION_DESIGN.md      — SDD (architecture document)       │
│  IMPLEMENTATION_PLAN.md  — atomic tasks + DAG + coverage     │
│  QUALITY_REPORT.md       — D1-D10 scorecard                  │
└─────────────────────────────────────────────────────────────┘
```

### Danh sách thành phần

| Thành phần | Đường dẫn | Vai trò | Loại |
|------------|-----------|---------|------|
| `plan_orchestrator.py` | `.devin/scripts/` | FSM state machine — điều phối toàn bộ Plan Phase | Python script (CLI) |
| `approval_gate.py` | `.devin/scripts/` | Human approval gate — quản lý phê duyệt plan | Python script (CLI + interactive) |
| `plan_quality_check.py` | `.devin/scripts/` | Quality check 10 dimensions — validate plan | Python script (CLI) |
| `plan_enforce.py` | `.devin/hooks/` | Enforcement hook — block Write/Edit nếu chưa có approved plan | Python script (hook) |
| `/plan` skill | `.devin/skills/plan/SKILL.md` | Skill instructions — auto-activate orchestrator | Markdown |
| `/full-power` skill | `.devin/skills/full-power/SKILL.md` | Full 3-Phase skill — auto-activate orchestrator cho Phase 1 | Markdown |
| `COMMANDER.md` | `.devin/agents/` | Commander agent prompt — mô tả orchestrator-driven flow | Markdown |
| `REDLINES.md` | `.devin/canon/` | Red lines — rule #19, #20 về Plan phase | Markdown |
| `config.json` | `.devin/` | Hooks config — đăng ký plan_enforce.py cho write/edit matchers | JSON |

---

## 3. FSM State Machine — Cơ chế hoạt động

### Sơ đồ trạng thái

```
                    ┌─────────┐
                    │  INIT   │ ← --init --task "<task>"
                    └────┬────┘
                         │
                         ▼
                    ┌─────────┐
                    │ CLASSIFY│ ← phân loại S/M/L/XL
                    └────┬────┘
                    S    │    M/L/XL
              ┌─────┘    └────┐
              ▼               ▼
         ┌────────┐    ┌─────────┐
         │  DONE   │    │ ANALYZE │ ← dispatch 5 SCOUTs
         │ (skip)  │    └────┬────┘
         └────────┘         │
                            ▼
                      ┌─────────┐
                      │ DESIGN  │ ← dispatch 1 ARCHITECT
                      └────┬────┘
                           │
                           ▼
                      ┌─────────┐
                      │ REVIEW  │ ← dispatch 3 reviewers
                      └────┬────┘
                     BLOCKING?───────┐
                  ┌───┤              │
              No  │   │ Yes          │ Yes + rounds >= 3
                  ▼   ▼              ▼
            ┌──────┐ ┌─────────┐  ┌──────────┐
            │ PLAN │ │ REVISION│  │ ESCALATE │
            └──┬───┘ └────┬────┘  └──────────┘
               │          │
               │          └──→ REVISION → REVIEW (loop, max 3)
               ▼
          ┌─────────┐
          │   QC    │ ← run plan_quality_check.py
          └────┬────┘
         PASS?───────┐
      ┌───┤          │
  Yes │   │ No       │ No + rounds >= 3
      ▼   ▼          ▼
┌──────────┐ ┌─────────┐  ┌──────────┐
│ APPROVAL │ │ DESIGN  │  │ ESCALATE │
└────┬─────┘ └─────────┘  └──────────┘
     │  (loop back, max 3)
     ▼
┌─────────────┐
│ WRITE_STATE │ ← approval_gate.py --approve
└──────┬──────┘
       │
       ▼
┌─────────┐
│  DONE   │ ← Plan phase complete
└─────────┘

Rejected? → REJECTED (stop)
Changes requested? → DESIGN (loop back)
```

### Bảng trạng thái chi tiết

| State | Mô tả | Action output | Transition |
|-------|-------|---------------|------------|
| `INIT` | Khởi tạo state file | (auto → CLASSIFY) | → CLASSIFY |
| `CLASSIFY` | Phân loại tier (S/M/L/XL) | `skip` (S-tier) hoặc `dispatch_scouts` (M+) | → DONE (S) hoặc → ANALYZE (M+) |
| `ANALYZE` | Dispatch 5 SCOUT subagents | `wait_scouts` (chờ collect results) | → DESIGN (sau khi có results) |
| `DESIGN` | Dispatch 1 ARCHITECT | `dispatch_architect` | → REVIEW (sau khi có SDD) |
| `REVIEW` | Dispatch 3 adversarial reviewers | `dispatch_reviewers` | → PLAN (no blocking) hoặc → REVISION (blocking) hoặc → ESCALATE (max rounds) |
| `REVISION` | Resume ARCHITECT với blocking issues | `dispatch_revision` | → REVIEW (sau khi revise) |
| `PLAN` | Decompose SDD thành atomic tasks | `decompose_plan` | → QC (sau khi có plan file) |
| `QC` | Run quality check 10 dimensions | `run_qc` | → APPROVAL (pass) hoặc → DESIGN (fail, loop) hoặc → ESCALATE (max rounds) |
| `APPROVAL` | Present plan cho user | `present_approval` | → WRITE_STATE (approved) hoặc → REJECTED (rejected) hoặc → DESIGN (changes_requested) |
| `WRITE_STATE` | Write plan state file | `write_plan_state` | → DONE |
| `DONE` | Plan phase hoàn thành | `done` | (terminal) |
| `REJECTED` | User từ chối plan | `done` (with reason) | (terminal) |
| `ESCALATE` | Vượt max rounds, escalate human | `escalate` | (terminal, chờ human) |

### Cơ chế transition

Mỗi transition xảy ra khi agent gọi `--step` với results JSON:

```bash
# Agent thực hiện action → collect results → write to temp file → call --step
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>
```

Results JSON format cho mỗi action:

| Action | Results format |
|--------|---------------|
| `wait_scouts` | `{"action": "wait_scouts", "scout_results": [{...}, ...]}` |
| `dispatch_architect` | `{"action": "dispatch_architect", "sdd_path": "docs/plans/<slug>/SOLUTION_DESIGN.md"}` |
| `dispatch_reviewers` | `{"action": "dispatch_reviewers", "findings": [{"severity": "BLOCKING/ADVISORY/INFO", "issue": "..."}, ...]}` |
| `dispatch_revision` | `{"action": "dispatch_revision", "sdd_path": "..."}` |
| `decompose_plan` | `{"action": "decompose_plan", "plan_path": "docs/plans/<slug>/IMPLEMENTATION_PLAN.md"}` |
| `run_qc` | `{"action": "run_qc", "qc_result": {"all_pass": true/false, "report_path": "..."}}` |
| `present_approval` | `{"action": "present_approval", "decision": "approved/rejected/changes_requested", "reason": "...", "modifications": "..."}` |
| `write_plan_state` | `{"action": "write_plan_state"}` |

### Giới hạn vòng lặp

| Loop type | Max rounds | Hành động khi vượt |
|-----------|-----------|-------------------|
| REVISION (blocking issues) | 3 | → ESCALATE (present unresolved issues to human) |
| QC (quality check fail) | 3 | → ESCALATE (present failing dimensions to human) |

---

## 4. Auto-activation từ Skill / CLI

### Cơ chế kích hoạt

Devin CLI hoạt động theo pattern sau:

```
1. User gõ: /plan add JWT authentication
2. Devin CLI nhận diện skill "plan" được trigger
3. Skill content (SKILL.md) được inject vào agent context
4. Agent đọc skill instructions
5. Agent thực hiện FIRST ACTION (auto-activate orchestrator)
6. Agent loop: thực hiện action → báo results → nhận next action → lặp lại
```

**Điểm quan trọng**: Skill là tập hợp **instructions** cho agent. Agent đọc và tự động thực hiện. Không cần "compile" hay "register" — skill tự kích hoạt khi user gõ lệnh.

### Auto-activation trong /plan skill

Section đầu tiên của `/plan` skill (sau frontmatter) chứa **AUTO-ACTIVATION DIRECTIVE**:

```markdown
# AUTO-ACTIVATION — Kích hoạt ngay lập tức

KHI SKILL NÀY ĐƯỢC INVOKE:
1. NGAY LẬP TỨC chạy: python .devin/scripts/plan_orchestrator.py --init --task "<task>"
2. Đọc next_action từ output JSON
3. Thực hiện action (dispatch subagents, viết files, v.v.)
4. Báo results qua --step
5. Lặp lại bước 3-4 cho đến khi state = DONE

KHÔNG HỎI user trước khi init. KHÔNG CHỜ xác nhận. KHÔNG GIẢI THÍCH dài dòng.
Chỉ chạy orchestrator và follow instructions.
```

### Auto-activation trong /full-power skill

`/full-power` skill có 4 bước trước khi đến Plan phase (BOOT, INVENTORY, COMMANDER, TIER CLASSIFICATION). Sau khi xác định M-tier+, skill tự động chuyển sang Phase 1 (PLAN) và kích hoạt orchestrator.

### Tích hợp permissions

Để orchestrator chạy không cần hỏi permission mỗi lần, các commands được thêm vào `config.json` permissions allow list:

```json
{
  "permissions": {
    "allow": [
      "Exec(python .devin/scripts/plan_orchestrator.py:*)",
      "Exec(python .devin/scripts/approval_gate.py:*)",
      "Exec(python .devin/scripts/plan_quality_check.py:*)"
    ]
  }
}
```

### Flow tự động hoàn chỉnh

Khi user gõ `/plan add JWT authentication to the API`:

```
[Agent] Đọc skill → thấy AUTO-ACTIVATION directive
[Agent] Chạy: python .devin/scripts/plan_orchestrator.py --init --task "add JWT authentication to the API"
[Script] Tạo state file → phân loại tier=M → trả next_action=dispatch_scouts
[Agent] Dispatch 5 SCOUT subagents (background, parallel)
[Agent] Collect 5 results → write results.json
[Agent] Chạy: python .devin/scripts/plan_orchestrator.py --step --state <state> --results <results>
[Script] State ANALYZE→DESIGN → trả next_action=dispatch_architect
[Agent] Dispatch 1 ARCHITECT (foreground)
[Agent] Sau architect xong → write results.json
[Agent] Chạy: --step → state DESIGN→REVIEW → trả next_action=dispatch_reviewers
[Agent] Dispatch 3 reviewers (background, parallel)
[Agent] Collect 3 reviews → aggregate → write results.json
[Agent] Chạy: --step → state REVIEW→PLAN (no blocking) → trả next_action=decompose_plan
[Agent] Decompose SDD → write IMPLEMENTATION_PLAN.md → write results.json
[Agent] Chạy: --step → state PLAN→QC → trả next_action=run_qc
[Agent] Chạy: python .devin/scripts/plan_quality_check.py <plan.md>
[Agent] Write QC results → Chạy: --step → state QC→APPROVAL → trả next_action=present_approval
[Agent] Chạy: python .devin/scripts/approval_gate.py <plan.md> --interactive --quality-report <qr.md>
[User] Nhìn plan summary → gõ "y" (approve)
[Agent] Write approval results → Chạy: --step → state APPROVAL→WRITE_STATE → trả next_action=write_plan_state
[Agent] Chạy: python .devin/scripts/approval_gate.py <plan.md> --approve
[Agent] Write results → Chạy: --step → state WRITE_STATE→DONE
[Agent] Plan phase complete → báo user → sẵn sàng execute
```

**Tổng số lần agent gọi CLI**: ~8 lần (init + 7 step calls)
**Tổng số subagents dispatch**: 9 (5 SCOUTs + 1 ARCHITECT + 3 reviewers) + có thể thêm revision rounds
**Thời gian ước tính**: 5-30 phút tùy complexity

---

## 5. Enforcement Hook — Cơ chế chặn

### Cơ chế hoạt động

`plan_enforce.py` là một **PreToolUse hook** — chạy TRƯỚC khi agent thực hiện tool call. Hook đọc stdin (JSON từ Devin CLI), kiểm tra, và trả về allow/block.

```
Agent gọi Write/Edit tool
  ↓
Devin CLI trigger PreToolUse hook
  ↓
plan_enforce.py đọc stdin: {"tool_name": "write", "tool_input": {"file_path": "src/main.py"}}
  ↓
Hook kiểm tra:
  1. Tool có phải Write/Edit? → Nếu không, allow
  2. JSON input parse lỗi? → BLOCK (fail-closed)
  3. Task tier? → Đọc session_state, classify
  4. S-tier? → Allow (no plan needed)
  5. M-tier+?
     - File có thuộc docs/plans/ hoặc docs/templates/? → Allow (cho phép viết plan)
     - Tính task_slug từ task description
     - Load orchestrator state `<task_slug>_orchestrator.json`
     - Nếu orchestrator state DONE + approval_status=approved:
       - Lấy plan_path từ orchestrator state
       - Load approval state theo task_slug (nếu plan trong docs/plans/<task_slug>/)
       - Nếu approved → Allow
     - Không thỏa mãn → BLOCK
  ↓
Trả về: {"allow": true/false, "reason": "..."}
```

### Đăng ký hook trong config.json

Hook được đăng ký cho **2 matchers**: `write`, `edit`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "write",
        "hooks": [
          { "type": "command", "command": "python .devin/hooks/plan_enforce.py", "timeout": 3 }
        ]
      },
      {
        "matcher": "edit",
        "hooks": [
          { "type": "command", "command": "python .devin/hooks/plan_enforce.py", "timeout": 3 }
        ]
      }
    ]
  }
}
```

> **Lưu ý**: `plan_enforce.py` không đăng ký cho matcher `exec` vì logic hook chỉ xử lý Write/Edit tools. Exec bypass (ví dụ: `python -c "open('file.py','w').write('...')"`) cần được kiểm soát ở lớp permissions hoặc OS-level sandbox, không phải hook này.

### Logic phân loại tier trong hook

```python
def _classify_tier(task_description, session_state):
    # S-tier indicators: <50 chars, "typo", "rename", "trivial", v.v.
    s_indicators = [
        len(desc) < 50,
        any(kw in desc for kw in ["typo", "rename", "fix spelling"]),
        any(kw in desc for kw in ["s-tier", "trivial", "one line"]),
    ]
    # XL-tier indicators
    xl_indicators = [
        any(kw in desc for kw in ["architecture", "refactor", "security"]),
        any(kw in desc for kw in ["multi-system", "cross-service", "distributed"]),
        len(desc) > 300,
    ]
    # L-tier indicators
    l_indicators = [
        any(kw in desc for kw in ["multiple files", "integration", "database"]),
        any(kw in desc for kw in ["performance", "cache", "api design"]),
        len(desc) > 150,
    ]
    # Nếu session_state có complexity field → dùng đó
    complexity = session_state.get("complexity", "")
    if complexity in ("S", "s"): return "S"
    if complexity in ("M", "L", "XL"): return complexity
    # XL/L/S fallback
    if sum(xl_indicators) >= 2: return "XL"
    if sum(l_indicators) >= 2: return "L"
    if sum(s_indicators) >= 2: return "S"
    # Default: M (fail-closed)
    return "M"
```

### Fail-closed principle

- Không đọc được session_state → default M → require plan
- Không xác định được task_slug hiện tại → no approved plan → BLOCK
- Task description rỗng → default M → require plan
- JSON parse error → **BLOCK** (fail-closed)
- Plan state file hỏng → coi như chưa approved → BLOCK

### Files được phép viết không cần plan

| Path pattern | Lý do |
|--------------|-------|
| `docs/plans/**` | Plan files — cho phép viết trong Plan phase |
| `docs/templates/**` | Template files — cho phép cập nhật templates |

---

## 6. Approval Gate — Cơ chế phê duyệt

### 5 chế độ hoạt động

| Flag | Mô tả | Exit code |
|------|-------|-----------|
| `--status` | Kiểm tra trạng thái phê duyệt hiện tại | 0 (approved) / 1 (pending/rejected) |
| `--approve` | Đánh dấu plan đã được phê duyệt | 0 |
| `--reject` | Đánh dấu plan bị từ chối (kèm lý do) | 1 |
| `--request-changes` | Đánh dấu plan cần sửa đổi (kèm feedback) | 1 |
| `--interactive` | Present plan summary + hỏi user [y/n/m/i] | 0 (approved) / 1 (other) |

### Interactive mode — Cơ chế

Khi chạy `--interactive`, script:

1. **Parse plan file** — trích Risk Tier, đếm Task IDs (T1.1, T2.1, v.v.), đếm REQ IDs, đếm file paths
2. **Parse quality report** (nếu có `--quality-report`) — đếm PASS/FAIL, overall result
3. **Present summary** — in ra console:
   ```
   ============================================================
     PLAN APPROVAL GATE — Human Review Required
   ============================================================

   ## Plan Summary
     Feature:           add JWT authentication
     Risk Tier:         R2
     Tasks:             5
     Requirements:      3
     Files to change:   4
     Quality scorecard: 8 PASS, 2 FAIL
     Overall:           FAIL

   ------------------------------------------------------------
     Options:
       [y]     Approve — proceed to execute
       [n]     Reject — stop, do not execute
       [m]     Approve with modifications — specify changes
       [i]     Request more information
   ------------------------------------------------------------

     Decision [y/n/m/i]:
   ```
4. **Đợi user input** — `input()` chờ user gõ y/n/m/i
5. **Xử lý response**:
   - `y` → `cmd_approve()` → write state file với status=approved
   - `n` → hỏi reason → `cmd_reject()` → write state file với status=rejected
   - `m` → hỏi modifications → `cmd_request_changes()` → write state file với status=changes_requested
   - `i` → hỏi question → return pending (không thay đổi state)
6. **Output JSON** — in state ra stdout cho agent parse

### State file structure

```json
{
  "plan_file": "docs/plans/add-jwt-auth/IMPLEMENTATION_PLAN.md",
  "status": "approved",
  "reviewer": "human",
  "date": "2026-08-05T13:50:33.146791+00:00",
  "comments": "Approved via interactive mode"
}
```

### State file location

`.devin/plan_state/<task_slug>_approved.json` — nếu plan file nằm trong `docs/plans/<task_slug>/`.

Ví dụ: plan file `docs/plans/add-jwt-auth/IMPLEMENTATION_PLAN.md` → state file `.devin/plan_state/add-jwt-auth_approved.json`

> Tại sao không dùng `<plan_name>.json`? Vì mỗi task có file `IMPLEMENTATION_PLAN.md` riêng; dùng stem sẽ gây conflict giữa các task. `approval_gate.py` tính `task_slug` từ thư mục cha của plan file và lưu state file dạng `<task_slug>_approved.json`.

Nếu plan file nằm ngoài `docs/plans/<task_slug>/` (fallback), state file dùng `plan_path.stem`.

---

## 7. Quality Check — 10 chiều đánh giá

### 10 Dimensions

| ID | Name | What it checks | Pass criteria |
|----|------|----------------|---------------|
| D1 | Requirement Coverage | Mọi REQ ID có task tương ứng? | Mỗi REQ ID xuất hiện trong task table |
| D2 | Task Completeness | Mỗi task có file path + function + acceptance criteria? | Task row có đủ columns |
| D3 | Dependency Correctness | DAG trong Mermaid có acyclic? | Không có cycle trong dependency graph |
| D4 | Key Links Planned | Mọi integration point từ SDD có task? | Integration points được cover |
| D5 | Scope Sanity | Không có orphan task (task ngoài requirement)? | Mọi task maps về REQ ID |
| D6 | Must-Haves Derivation | Acceptance criteria falsifiable (không mơ hồ)? | Không chứa vague words (properly, good, fast, v.v.) |
| D7 | Context Compliance | Plan tuân theo AGENTS.md/CLAUDE.md? | File tồn tại + plan reference đúng |
| D8 | Risk Assessment | Mọi task R3+ có mitigation? | Risk table có mitigation cho R3+ |
| D9 | Test Coverage | Mọi requirement có test case? | Test strategy section có test cho mỗi REQ |
| D10 | Rollback Plan | Mọi task R2+ có rollback? | Rollback plan section có rollback cho R2+ |

### Output

Script output 2 thứ:
1. **JSON scorecard** ra stdout — cho agent parse
2. **Markdown report** vào `docs/plans/QUALITY_REPORT_<plan_name>.md` — cho human đọc

### Exit codes

- `0` = tất cả 10 dimensions PASS
- `1` = có ít nhất 1 dimension FAIL

---

## 8. Subagent Dispatch — Cơ chế song song

### 5 SCOUT subagents (Phase ANALYZE)

| SCOUT | Mission | Profile | Mode | Tools |
|-------|---------|---------|------|-------|
| SCOUT-1 | Scan codebase structure, module boundaries, entry points | subagent_explore | background | grep, glob, read |
| SCOUT-2 | Find relevant files, trace call paths, identify blast radius | subagent_explore | background | grep, glob, read |
| SCOUT-3 | Research cutting-edge solutions, prior art, pitfalls | subagent_explore | background | web_search, webfetch |
| SCOUT-4 | Analyze test coverage gaps, find untested paths | subagent_explore | background | grep, glob, read, exec |
| SCOUT-5 | Check constraints: security, performance, compatibility | subagent_explore | background | grep, read, exec |

**Cơ chế**: Agent dispatch ALL 5 trong **một single response** (parallel). Mỗi SCOUT chạy độc lập. Agent collect results bằng `read_subagent`.

### 1 ARCHITECT subagent (Phase DESIGN)

| Role | Profile | Mode | Input | Output |
|------|---------|------|-------|--------|
| ARCHITECT | glm-executor | foreground | Aggregated findings từ 5 SCOUTs + SDD template | SOLUTION_DESIGN.md |

**Cơ chế**: Foreground (block cho đến khi xong). Agent đợi architect hoàn thành rồi mới proceed.

### 3 Adversarial reviewers (Phase REVIEW)

| Reviewer | Persona | Question | Profile | Mode |
|----------|---------|----------|---------|------|
| SABOTEUR | Hostile attacker | "How do I break this design? What inputs crash it?" | subagent_explore | background |
| NEW_HIRE | Junior engineer, first day | "Can I understand this without asking anyone?" | subagent_explore | background |
| SECURITY_AUDITOR | OWASP-aligned auditor | "What attack surfaces does this design open?" | subagent_explore | background |

**Cơ chế**: Dispatch ALL 3 trong một single response (parallel). Agent collect results, aggregate:
- **Deduplicate**: cùng root cause → giữ 1
- **Promote**: issue do 2+ reviewers tìm thấy → +1 severity
- **Classify**: BLOCKING / ADVISORY / INFO

### Aggregation rules

| Severity | Định nghĩa | Hành động |
|----------|-----------|-----------|
| BLOCKING | Design sẽ fail trong production nếu không fix | → REVISION (fix trước khi proceed) |
| ADVISORY | Nên fix nhưng không critical | → Ghi nhận, proceed |
| INFO | Ghi chú, không cần action | → Ghi nhận, proceed |

---

## 9. Output Files — Cấu trúc artifact

### Directory structure

```
docs/plans/<task_slug>/
├── SOLUTION_DESIGN.md        — SDD (tạo ở Phase DESIGN)
├── IMPLEMENTATION_PLAN.md    — Plan (tạo ở Phase PLAN)
└── QUALITY_REPORT.md         — QC report (tạo ở Phase QC)

.devin/plan_state/
├── <task_slug>_orchestrator.json  — FSM state + history
└── <task_slug>_approved.json      — Approval state (activates enforcement hook; for plans under docs/plans/<task_slug>/)
```

### Task slug generation

```python
def _slugify(text):
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60]
```

Ví dụ: `"Add JWT authentication to the API"` → `"add-jwt-authentication-to-the-api"`

### Orchestrator state file structure

```json
{
  "task_description": "add JWT authentication to the API",
  "task_slug": "add-jwt-authentication-to-the-api",
  "state": "DONE",
  "tier": "M",
  "round": 0,
  "revision_round": 0,
  "qc_round": 1,
  "scout_results": [...],
  "sdd_path": "docs/plans/add-jwt-auth/SOLUTION_DESIGN.md",
  "review_findings": [...],
  "plan_path": "docs/plans/add-jwt-auth/IMPLEMENTATION_PLAN.md",
  "quality_report_path": "docs/plans/add-jwt-auth/QUALITY_REPORT.md",
  "approval_status": "approved",
  "created_at": "2026-08-05T...",
  "updated_at": "2026-08-05T...",
  "history": [
    {"timestamp": "...", "state": "INIT", "action": "init", "detail": "..."},
    {"timestamp": "...", "state": "CLASSIFY", "action": "classify", "detail": "Tier=M"},
    ...
  ]
}
```

---

## 10. CLI Reference — Tham chiếu lệnh

### plan_orchestrator.py

```bash
# Khởi tạo Plan phase
python .devin/scripts/plan_orchestrator.py --init --task "<task description>"

# Xử lý results, chuyển state, nhận next action
python .devin/scripts/plan_orchestrator.py --step --state <state.json> --results <results.json>

# Kiểm tra trạng thái hiện tại
python .devin/scripts/plan_orchestrator.py --status --state <state.json>
```

### approval_gate.py

```bash
# Kiểm tra trạng thái phê duyệt
python .devin/scripts/approval_gate.py <plan_file.md> --status

# Phê duyệt plan
python .devin/scripts/approval_gate.py <plan_file.md> --approve --reviewer "name"

# Từ chối plan
python .devin/scripts/approval_gate.py <plan_file.md> --reject --reason "lý do"

# Yêu cầu sửa đổi
python .devin/scripts/approval_gate.py <plan_file.md> --request-changes --reason "cần sửa"

# Interactive mode (present summary + hỏi user)
python .devin/scripts/approval_gate.py <plan_file.md> --interactive

# Interactive mode với quality report
python .devin/scripts/approval_gate.py <plan_file.md> --interactive --quality-report <qr.md>
```

### plan_quality_check.py

```bash
# Run 10-dimension quality check
python .devin/scripts/plan_quality_check.py <plan_file.md>
```

### plan_enforce.py (hook — không gọi trực tiếp)

Hook tự động chạy khi agent gọi Write/Edit tool. Không cần gọi thủ công.

---

## 11. Tích hợp với Hooks

### PreToolUse hooks chain

Khi agent gọi `write` hoặc `edit` tool, Devin CLI chạy chuỗi hooks:

```
Agent gọi Write tool
  ↓
PreToolUse hooks (matcher: "write")
  ├── aide-memory pre-edit-recall.sh (aide-memory hooks)
  └── plan_enforce.py (Plan enforcement)
       ├── tool_name = "write" → enforce
       ├── tier = M → require plan
       ├── file_path = "src/main.py" → không phải plan file
       ├── plan_state = không có approved → BLOCK
       └── return {"allow": false, "reason": "PLAN ENFORCEMENT: ..."}
  ↓
Devin CLI nhận block → không thực hiện Write
  ↓
Agent nhận error message → phải chạy /plan trước
```

### PostToolUse hooks (sau khi Write/Edit thành công)

```
Agent gọi Write tool (đã có approved plan)
  ↓
PreToolUse → plan_enforce.py → allow
  ↓
Write thực hiện thành công
  ↓
PostToolUse hooks (matcher: "write")
  ├── post_tool_use.py (logging)
  ├── drift_detect.py (behavioral fingerprinting)
  ├── self_heal.py (self-healing)
  ├── schema_gate.py (deterministic validation)
  └── coverage_enforce.py (track plan items)
```

---

## 12. Troubleshooting

### Vấn đề thường gặp

| Vấn đề | Nguyên nhân | Giải pháp |
|---------|------------|-----------|
| `plan_enforce.py` không block | Hook không đăng ký cho write/edit matcher, hoặc plan state file naming conflict | Thêm hook vào config.json cho write + edit matchers; đảm bảo approval state file dùng task_slug_approved.json |
| Orchestrator trả `action: skip` | Task bị classify S-tier | Task quá ngắn/trivial. Thêm chi tiết để upgrade lên M-tier |
| Stuck ở REVISION loop | Blocking issues không resolve sau 3 rounds | Orchestrator tự escalate. Review issues với user |
| Stuck ở QC loop | Quality check fail sau 3 rounds | Orchestrator tự escalate. Review failing dimensions |
| `approval_gate.py --interactive` không đợi input | Chạy trong non-interactive context | Agent cần chạy qua `exec` với `tty: true` hoặc tự simulate input |
| State file không tạo | Permission lỗi hoặc path sai | Kiểm tra `.devin/plan_state/` tồn tại + writable |
| `plan_orchestrator.py` không tìm thấy | `.gitignore` ignore `scripts/` | `git add -f` hoặc thêm `!.devin/scripts/` vào .gitignore |

### Debug commands

```bash
# Kiểm tra orchestrator state
python .devin/scripts/plan_orchestrator.py --status --state .devin/plan_state/<slug>_orchestrator.json

# Kiểm tra approval state
python .devin/scripts/approval_gate.py docs/plans/<slug>/IMPLEMENTATION_PLAN.md --status

# Test plan_enforce manually
echo '{"tool_name":"write","tool_input":{"file_path":"src/test.py"},"task":"add auth"}' | python .devin/hooks/plan_enforce.py

# Test orchestrator init
python .devin/scripts/plan_orchestrator.py --init --task "test task"
```
