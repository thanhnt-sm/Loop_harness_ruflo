# Handoff — Restart opencode sau Phase-2 integration (2026-08-27)

> Mục đích: chuyển context đầy đủ sang session mới **sau khi restart opencode**.
> Bối cảnh: vừa hoàn tất Phase-2 opencode full integration (MCP + plugin + domain-adapters).
> Sau restart, các cấu hình mới (MCP servers, plugin `harness.ts`, skill wrapper) mới có hiệu lực.

---

## 1. ĐÃ LÀM (trước restart — session trước)

### Phase-1 opencode full integration (COMPLETE)
- `opencode.json`: `skills.paths` += `.devin/skills`; thêm `references` (canon, agents-state, hlk-docs, hlk-prompts, docs).
- 8 slash command: `/full-power`, `/plan`, `/lightning`, `/glm`, `/kimi`, `/adversarial-consensus`, `/hlk-git-tools`, `/hlk-integrity-check`, `/hlk-loop`.
- 2 skill wrapper: `hlk-loop`, `hlk-upstream-pull`.

### Phase-2 opencode full integration (COMPLETE)
- `opencode.json`: thêm `mcp` → `aide-memory` + `ruflo-hlk-mcp` (local, free). `opencode mcp list` = **2 server connected**.
- Plugin: migrate → `.opencode/plugins/harness.ts` (**bật mặc định**, opt-out `OPENCODE_HARNESS_HOOKS=0`; bridge `.devin/hooks/*.py` advisory fail-open; nén git output; fix python `.venv/Scripts/python.exe` cho Windows). Xóa `harness-plugin.js` (API cũ) + `.opencode/plugin/harness.ts` (sai thư mục).
- domain-adapters: wrapper index `.opencode/skills/domain-adapters/SKILL.md` (trigger `/domain`).
- `.gitignore`: un-ignore `.opencode/plugins/`.
- Verify: `check_governance.py` errors=0 (3 warnings pre-existing, không phải của task này).

> ⚠️ **Phát hiện quan trọng**: package `aide-memory` đúng là **`aide-memory`** (v0.6.4), KHÔNG phải `aide-memory-mcp` như `.devin/mcp_config.json` cũ ghi (`aide-memory-mcp` = 404 trên npm).

---

## 2. VIỆC CẦN LÀM SAU RESTART (ưu tiên)

### 2.1 Verify sau restart (BƯỚC 1 — bắt buộc)
```bash
opencode mcp list                              # phải thấy 2 server connected: aide-memory, ruflo-hlk-mcp
# Test slash commands chạy được (trong TUI):
/domain                                        # wrapper domain-adapters load
/full-power <task>                              # flow 3-phase
/plan <task>                                    # phase 1
# Test plugin không vỡ opencode:
#   - chạy 1 task đơn giản, không được crash
#   - IDE nếu cần: kiểm tra log plugin không có error load
```
- Kiểm tra `OPENCODE_HARNESS_HOOKS` không cần set (plugin bật mặc định). Nếu muốn tắt hẳn: `OPENCODE_HARNESS_HOOKS=0`.

### 2.2 Công việc DANG DỞ (từ session/plugin khác — KHÔNG phải của task này)
> Quan trọng: các file sau đang being sửa dở bởi AHD Build-Strategy P1-02 (security, URGENT). KHÔNG xóa, KHÔNG overwrite mà không kiểm tra.

| Plan | Trạng thái | File đang sửa dở | Việc còn lại |
|------|-----------|-------------------|--------------|
| `ahd-build-strategy-implementation/P1-02` (URGENT security: MCP structured-error + circuit breaker) | Act đang dở, thiếu sub-EXECUTION_REPORT | `.devin/hooks/post_tool_mcp_guard.py` (mới), `tests/test_mcp_guard.py` (mới), `.devin/hooks/post_tool_engine.py` (mod), `.devin/config.json` (mod) | Viết `docs/plans/ahd-build-strategy-implementation/EXECUTION_REPORT.md` (hoặc P1-02/EXECUTION_REPORT.md) cho phần act đã làm; hoàn tất test + mạch `post_tool_config.py`; chạy security audit. |
| `fix-14-failed-36-errors-pre-existing-tests-test-cost-guard-3` | DRAFT — awaiting Plan approval gate (chưa execute) | — | Nếu muốn tiếp: chạy `/full-power` để approve plan rồi execute (fix 14 failed + 36 collection errors trong các test pre-existing). |

### 2.3 Next candidates — opencode integration (optional, sau 2.1/2.2)
1. **Custom tools optional**: migrate `harness-verify`/`harness-route`/... từ `.js` cũ đã xóa thành custom tools opencode (chồng lấp với slash commands, nên cân nhắc).
2. **Wrap thêm**: skill `update_from_repos`, `hlk-integrity-check` full launcher.
3. **Kiểm tra offline `ruflo-hlk-mcp`**: hiện spawn `npx ruflo@latest mcp start` → cần network lần đầu (không hoàn toàn offline).
4. **Red-team v5** harness-upgrade dedicate (nếu muốn phiên đầy đủ red-team/root-cause).

---

## 3. Verification sau restart — check nhanh
- `python tools/check_governance.py` → errors=0 (warnings hiện tại = 3: `test_mcp_guard.py` ngoài plan + `ahd-build-strategy-implementation` + `fix-14...` thiếu exec report — là của P1-02 dang dở).

---

## 4. CẢNH BÁO / GUARDRAILS
- **Restart opencode là bắt buộc** để MCP + plugin + command mới có hiệu lực (opencode không hot-reload config).
- KHÔNG đụng `HLK/`, `.env`, security policies.
- KHÔNG destructive; KHÔNG commit trừ khi user yêu cầu.
- Ngôn ngữ: tiếng Việt có dấu (per AGENTS.md).
- Các file của AHD P1-02 đang dở: xử lý cẩn thận, không overwrite mù.

---

## 5. Plan artifacts liên quan
- Phase 1+2: `docs/plans/opencode-full-integration/IMPLEMENTATION_PLAN.md` + `EXECUTION_REPORT.md`
- Báo cáo: `docs/reports/HARNESS_UPGRADE_REPORT.md`, `docs/reports/harness-upgrade-log.md`
- AHD Build-Strategy: `docs/plans/ahd-build-strategy-implementation/`

*Handoff generated 2026-08-27 | Phase-2 opencode integration complete | Verify sau restart*
