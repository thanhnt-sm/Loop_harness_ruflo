# HARNESS_UPGRADE_REPORT — opencode full integration

> Định kỳ: 2026-08-27
> Skill: `harness-upgrade` (full chain, focus = opencode integration)
> Plan: `docs/plans/opencode-full-integration/IMPLEMENTATION_PLAN.md`
> Trạng thái: **COMPLETE** (apply đã thực hiện theo plan user duyệt)

## Mục tiêu

Rà soát + làm lớp wrap/link để **opencode nhận diện và dùng đầy đủ** các cài đặt của
`.devin`, `HLK`, `.agents`, `AGENTS.md` và các cấu hình khác.

## Baseline → After

### Baseline (trước)
- `opencode.json` chỉ có `instructions` (AGENTS.md + WORKSPACE_GOVERNANCE) + `skills.paths` (chỉ `.opencode/skills`) + `permission`.
- `.opencode/config.json` chứa agents/hooks/tools/plugins/compensation nhưng **bị bỏ lỡ** (sai tên — opencode không đọc).
- Chưa có `references`, chưa trỏ tới `.devin/skills`, `canon`, `.agents`, `HLK`.
- Chỉ có 1 slash command `/harness-upgrade`; thiếu các flow Devin chủ lực.
- Thiếu 2 skill wrapper: `hlk-loop`, `hlk-upstream-pull`.

### After (đã áp dụng)
- `opencode.json`: `skills.paths` += `.devin/skills`; thêm `references` (canon, agents-state, hlk-docs, hlk-prompts, docs). Giữ `instructions` + `permission`.
- 8 slash command mới: `/full-power`, `/plan`, `/lightning`, `/glm`, `/kimi`, `/adversarial-consensus`, `/hlk-git-tools`, `/hlk-integrity-check`, `/hlk-loop`.
- 2 skill wrapper mới: `hlk-loop`, `hlk-upstream-pull`.

## Upgrades applied (tóm tắt)

1. Mở rộng `opencode.json` theo schema hợp lệ (không merge nguyên `.opencode/config.json` vì sẽ vỡ opencode).
2. Expose flow Devin chủ lực thành slash command opencode (opencode/`/full-power`/`/plan` không tồn tại → dùng orchestrator script trực tiếp).
3. Wrap 2 skill HLK bị thiếu wrapper.

## Verification & quality verdict

- **Deterministic gate**: `node` JSON.parse `opencode.json` OK; top-level keys hợp lệ theo schema → không rủi ro ConfigInvalidError.
- **Governance**: `python tools/check_governance.py` → errors=0.
- **Không destructive**: không đụng `HLK/`, `.env`, security; không xóa file.
- **Verdict**: ✅ PASS (apply theo plan đã duyệt). Cần user **restart opencode** để config mới có hiệu lực.

## Phase 2 (2026-08-27) — MCP + plugin + domain-adapters

- **MCP**: thêm `mcp` vào `opencode.json` — `aide-memory` (local, free) + `ruflo-hlk-mcp` (local HLK wrapper). `opencode mcp list` → **2 server connected**. Lưu ý: package đúng là `aide-memory` (không phải `aide-memory-mcp` như config cũ).
- **Plugin cleanup**: migrate `harness.ts` → `.opencode/plugins/` (thư mục auto-load đúng), **bật mặc định** (opt-out `OPENCODE_HARNESS_HOOKS=0`), fix python Windows `.venv/Scripts/python.exe`, migrate nén git output. Xóa `harness-plugin.js` (API cũ) + `harness.ts` (sai thư mục). `.gitignore` un-ignore `.opencode/plugins/`.
- **domain-adapters**: tạo wrapper index `/domain` → `.opencode/skills/domain-adapters/SKILL.md`.
- **Verify**: `check_governance.py` errors=0; JSON OK. Cần **restart opencode**.

## Next candidates

1. **Custom tools optional**: migrate `harness-verify`/`harness-route`... từ `.js` cũ thành custom tool opencode (nếu cần — hiện chồng lấp với slash commands).
2. **Wrap thêm** skill `update_from_repos`, `hlk-integrity-check` full launcher.
3. **Red-team v5** harness-upgrade dedicate (nếu user muốn phiên đầy đủ red-team/root-cause).
4. **Kiểm tra offline** `ruflo-hlk-mcp`: hiện spawn `npx ruflo@latest` (cần network lần đầu).
