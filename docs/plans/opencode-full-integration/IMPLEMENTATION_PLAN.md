# IMPLEMENTATION PLAN — opencode-full-integration

> Task: rà soát + làm lớp wrap/link để **opencode nhận diện và dùng đầy đủ** các cài đặt của
> `.devin`, `HLK`, `.agents`, `AGENTS.md` và các cấu hình khác.
> Skill: `harness-upgrade` (full chain, focus = opencode integration).

## Status

- **Plan approval**: CHƯA DUYỆT (chờ user duyệt trước khi Execute).
- **Loại**: L (liên quan config opencode + nhiều file mới wrapper/command).

---

## 1. Baseline (thực trạng — đã khảo sát)

### 1.1 Khảo sát đã làm (PREFLIGHT/REVIEW)

- Đọc `opencode.json` (root).
- So sánh `.opencode/skills/` (29 skill) vs `.devin/skills/` (15 skill).
- Liệt kê `.opencode/agent/*.md` (15 wrapper) + `.opencode/agents/*.md` (6 harness agent).
- Đọc `.devin/mcp_config.json`, `.devin/config.json`, `HLK/`, `.agents/`.
- Fetch schema `https://opencode.ai/config.json`.
- Delegate explore agent tổng hợp báo cáo gap đầy đủ.

### 1.2 Root cause (phát hiện then chốt)

| File | opencode có đọc? | Vai trò |
|------|------------------|---------|
| `opencode.json` (root) | ✅ CÓ | Config opencode thực sự. Hiện chỉ có `instructions` + `skills.paths` + `permission`. |
| `.opencode/config.json` | ❌ KHÔNG | Chứa agents/hooks/tools/plugins/compensation đã viết sẵn, nhưng **sai tên file** (opencode chỉ đọc `opencode.json` hoặc `.opencode/opencode.json`). Toàn bộ "chết". |
| `.opencode/agent/*.md` + `.opencode/agents/*.md` | ✅ auto-discover | Agents dạng file — **đã được opencode nhận diện tự động**, không cần khai config. |

### 1.3 Cảnh báo schema (quan trọng — quyết định cách wrap)

Schema `https://opencode.ai/config.json` — Config có `additionalProperties: false`:

- **KHÔNG có key `hooks`** trong config JSON → không thể khai hooks trong config. Hooks opencode cấu hình qua **plugin**.
- `tools` chỉ chấp nhận `{ <tool>: boolean }` (bật/tắt builtin), **KHÔNG** phải object `{command, description}` → custom tools qua **plugin**, không qua config JSON.
- Các key `compensation`, `token_efficiency`, `model_routing`, `agents` (số nhiều) trong `.opencode/config.json` **KHÔNG hợp lệ** → **KHÔNG merge nguyên file này vào root** (sẽ làm opencode không start được).

→ **Kết luận**: KHÔNG merge nguyên `.opencode/config.json`. Chỉ thêm các field HỢP LỆ theo schema. Agents/hooks/custom-tools/compensation đều đã/được xử lý qua cơ chế plugin + agent file auto-discover.

---

## 2. Giải pháp (UPGRADE candidates)

### A. Mở rộng `opencode.json` (root) — theo đúng schema

Chỉ thêm các field hợp lệ (giữ nguyên `instructions`, `skills.paths`, `permission` hiện có):

1. **`skills.paths`**: thêm `".devin/skills"` → opencode scan skill từ `.devin/skills` (thêm các skill `hlk-loop`, `domain-adapters`... từ nguồn Devin).
2. **`references`** (mới): trỏ tới các thư mục để model tra cứu:
   - `canon` → `.devin/canon`
   - `agents-state` → `.agents`
   - `hlk-docs` → `HLK/docs`
   - `hlk-prompts` → `HLK/prompts`
   - `docs` → `docs`
3. **`plugin`** (array, hợp lệ theo schema): nạp rõ ràng `".opencode/plugin/harness.ts"` để đảm bảo plugin harness hook bridge + custom tools được load (song song với auto-discover).
4. **(tùy chọn) `mcp`**: NÊN thêm để opencode nói chuyện với MCP. Tuy nhiên attract MCP servers cần runtime (npx aider-memory-mcp...). Đề xuất thêm `aide-memory` + `ruflo-hlk-mcp`; để `spark-memory`/`deepwiki`/`devin` nếu có command sẵn. → Đánh dấu là optional/phase-2 vì có thể yêu cầu token/key + network; xin user quyết định.
   > ⚠️ MCP là quyết định riêng (cần cài packages, network). Tách thành item phase-2, hỏi user trước khi bật.

### B. Commands opencode (slash) — tạo wrapper `.opencode/command/*.md`

Theo yêu cầu user: expose flow Devin chủ lực thành slash command opencode (opencode KHÔNG có `/full-power`/`/plan` — dùng orchestrator script trực tiếp).

Tạo các command (theo format `harness-upgrade.md` — frontmatter `description` + `agent: build` + body hướng dẫn gọi orchestrator script):

| File command | Nội dung |
|--------------|----------|
| `.opencode/command/full-power.md` | 3-Phase đầy đủ (Plan→Approve→Execute) qua `plan_orchestrator.py` + DAG execute. |
| `.opencode/command/plan.md` | Phase 1 Plan (SDD → approval → plan → quality → plan approval) qua `plan_orchestrator.py`. |
| `.opencode/command/lightning.md` | Executor SWE-1.7 Lightning (sau plan approved). |
| `.opencode/command/glm.md` | Executor GLM-5.2 (free). |
| `.opencode/command/kimi.md` | Executor Kimi K2.7 (free). |
| `.opencode/command/adversarial-consensus.md` | Adversarial review 6+ persona. |
| `.opencode/command/hlk-git-tools.md` | Git tools an toàn (doctor/commit/push/safe-sync). |
| `.opencode/command/hlk-integrity-check.md` | Verify HLK layer sau merge/pull. |
| `.opencode/command/hlk-loop.md` | HLK pipeline loop (status/dry-run/reset/iterate). |

### C. Wrap skill bị thiếu — tạo `.opencode/skills/<name>/SKILL.md` wrapper

Wrapper launcher nhỏ trỏ về canonical `.devin/skills/...` (pattern như wrapper existing):

| Skill | Nguồn canonical | Việc làm |
|-------|----------------|----------|
| `hlk-loop` | `.devin/skills/hlk-loop/SKILL.md` | Tạo wrapper `.opencode/skills/hlk-loop/SKILL.md` |
| `hlk-upstream-pull` | `HLK/skills/hlk-upstream-pull/SKILL.md` | Tạo wrapper `.opencode/skills/hlk-upstream-pull/SKILL.md` |
| `domain-adapters` | `.devin/skills/domain-adapters/` | Tạo wrapper index trỏ tới; hoặc thêm path scan qua `skills.paths` `.devin/skills` (đã có ở A1). |

> Lưu ý: với `domain-adapters` + `hlk-loop`, việc thêm `skills.paths: .devin/skills` (mục A1) đã giúp opencode scan được source trực tiếp; wrapper tạo thêm để expose mô tả/trigger đúng chuẩn opencode.

### D. (Không làm — tránh)

- ❌ KHÔNG sửa/commit tới `HLK/`, `.env`, security policies (guardrail).
- ❌ KHÔNG merge nguyên `.opencode/config.json` (sẽ vỡ opencode).
- ❌ KHÔNG xóa `.opencode/config.json` (không destructive; để nguyên tham chiếu Devin).

---

## 3. File Path / Function / Acceptance Criteria (REQ)

| REQ | File Path | Function | Acceptance Criteria |
|-----|-----------|----------|---------------------|
| R1 | `opencode.json` | Thêm `skills.paths: [".opencode/skills", ".devin/skills"]`, `references`, `plugin: [".opencode/plugin/harness.ts"]` | JSON hợp lệ theo schema; opencode vẫn start được; không mất `instructions`/`permission` hiện có. |
| R2..R10 | `.opencode/command/{full-power,plan,lightning,glm,kimi,adversarial-consensus,hlk-git-tools,hlk-integrity-check,hlk-loop}.md` | Slash command wrapper | Mỗi file có frontmatter hợp lệ (`description` + `agent: build` + body gọi orchestrator script đúng path). |
| R11 | `.opencode/skills/hlk-loop/SKILL.md` | Wrapper launcher | Load canonical `.devin/skills/hlk-loop/SKILL.md`, mô tả/trigger đúng, format opencode skill. |
| R12 | `.opencode/skills/hlk-upstream-pull/SKILL.md` | Wrapper launcher | Load canonical `HLK/skills/hlk-upstream-pull/SKILL.md`. |
| R13 | `docs/plans/opencode-full-integration/EXECUTION_REPORT.md` | Report sau execute | Ghi commits, files changed, test, residual risks. |
| R14 | `docs/reports/HARNESS_UPGRADE_REPORT.md` | Báo cáo upgrade | Ghi baseline→after, upgrades, verify, verdict, next candidates. |

---

## 4. Verification plan

1. **JSON validate**: `node -e "JSON.parse(require('fs').readFileSync('opencode.json','utf8'))"` → hợp lệ.
2. **Đối chiếu schema**: chạy script kiểm tra mọi top-level key của `opencode.json` nằm trong danh sách hợp lệ (từ schema) — tránh ConfigInvalidError.
3. **Governance**: `python tools/check_governance.py` (junk + layout + plan-act) → exit 0.
4. **Regression**: không đụng `HLK/`/`.env`; `git diff --name-only` ⊆ files khai trong plan.
5. **Manual**: yêu cầu user restart opencode để config mới có hiệu lực (opencode không hot-reload).

---

## 5. Guardrails & scope

- Smallest coherent diff — chỉ sửa file trong bảng REQ.
- Không destructive; không đụng HLK/.env/security.
- Model yếu/context nhỏ → chunk: thực hiện từng nhóm (A → B → C), báo sau mỗi nhóm.
- Không tạo file rác ở root; mọi file mới đúng nơi (.opencode/, docs/plans/).

---

## 6. Next steps

PLAN PHASE chưa complete → chờ user duyệt plan, sau đó EXECUTE theo thứ tự:
A (config) → B (commands) → C (skills wrapper) → Verify → Report.
