# EXECUTION REPORT — opencode-full-integration

> Plan: `docs/plans/opencode-full-integration/IMPLEMENTATION_PLAN.md`
> Status: **COMPLETE** — apply theo plan đã user duyệt (Duyệt, apply ngay).

## Summary

Làm lớp wrap/link để opencode nhận diện và dùng đầy đủ các cài đặt của `.devin`, `HLK`,
`.agents`, `AGENTS.md` và các cấu hình khác. Root cause: `.opencode/config.json` bị bỏ lỡ
(sai tên file — opencode chỉ đọc `opencode.json`). Theo schema opencode (`additionalProperties: false`,
không có key `hooks`, `tools` chỉ nhận boolean), **KHÔNG merge nguyên config.json** vào root (sẽ vỡ
opencode). Thay vào đó bổ sung các field hợp lệ.

## Commits / thay đổi

Không commit (user chưa yêu cầu commit).

## Files changed

| File | Loại | Mục đích |
|------|------|----------|
| `opencode.json` | Sửa | Thêm `skills.paths` += `.devin/skills`; thêm `references` (canon, agents-state, hlk-docs, hlk-prompts, docs). Giữ nguyên `instructions` + `permission`. |
| `.opencode/command/full-power.md` | Mới | Slash command `/full-power` (3-Phase). |
| `.opencode/command/plan.md` | Mới | Slash command `/plan` (Phase 1). |
| `.opencode/command/lightning.md` | Mới | Slash command `/lightning` (executor SWE-1.7). |
| `.opencode/command/glm.md` | Mới | Slash command `/glm` (executor GLM-5.2). |
| `.opencode/command/kimi.md` | Mới | Slash command `/kimi` (executor Kimi K2.7). |
| `.opencode/command/adversarial-consensus.md` | Mới | Slash command `/adversarial-consensus`. |
| `.opencode/command/hlk-git-tools.md` | Mới | Slash command `/hlk-git-tools`. |
| `.opencode/command/hlk-integrity-check.md` | Mới | Slash command `/hlk-integrity-check`. |
| `.opencode/command/hlk-loop.md` | Mới | Slash command `/hlk-loop`. |
| `.opencode/skills/hlk-loop/SKILL.md` | Mới | Wrapper skill `hlk-loop` (trỏ canonical `.devin/skills/hlk-loop`). |
| `.opencode/skills/hlk-upstream-pull/SKILL.md` | Mới | Wrapper skill `hlk-upstream-pull` (trỏ canonical `HLK/skills/hlk-upstream-pull`). |
| `docs/plans/opencode-full-integration/IMPLEMENTATION_PLAN.md` | Mới | Plan artifact. |

## Verification

- `node` JSON.parse `opencode.json` → OK. Top-level keys: `$schema, instructions, skills, references, permission` (đều hợp lệ theo schema; không key tùy chỉnh gây ConfigInvalidError).
- `python tools/check_governance.py` → errors=0 (warnings: 2 pre-existing plan + 1 của plan này, đã xử lý bằng EXECUTION_REPORT.md).
- Không đụng `HLK/`, `.env`, security policies.
- Không destructive; không xóa `.opencode/config.json`.

## Residual risks / notes

1. **Plugin hooks/custom-tools**: opencode hooks + custom tools cấu hình qua **plugin**, không qua config JSON. Plugin `harness.ts` (auto-discover từ `.opencode/plugin/`) đúng chuẩn opencode nhưng **OFF by default** (cần `OPENCODE_HARNESS_HOOKS=1`). Plugin `harness-plugin.js` (`.opencode/plugins/`) dùng hook surface cũ (`preToolUse`/`postToolUse`/`sessionStart`) — có thể không tương thích opencode hiện tại. → Không ép bật để tránh rủi ro; nên xử lý riêng (phase sau).
2. **MCP** (aide-memory, spark-memory, deepwiki, devin, ruflo-hlk-mcp): CHƯA thêm vào config (user chọn apply ngay, không bàn MCP; cần cài package/network/key). → Phase-2 riêng.
3. **opencode không hot-reload config**: user phải **restart opencode** để `opencode.json`, command, skill mới có hiệu lực.
4. `domain-adapters` wrapper index chưa tạo riêng — nhưng `skills.paths += .devin/skills` cho phép opencode scan được chính nguồn `.devin/skills/domain-adapters`. Có thể wrap thêm nếu cần expose trigger.
5. Không commit — chờ user yêu cầu.

---

## PHASE 2 (2026-08-27) — MCP + plugin + domain-adapters

> User duyệt: MCP = aide-memory + ruflo-hlk-mcp; Plugin = migrate `harness.ts` + enable + bỏ `.js` cũ; domain-adapters = tạo wrapper index nhẹ.

### Files changed (Phase-2)

| File | Loại | Mục đích |
|------|------|----------|
| `opencode.json` | Sửa | Thêm `mcp` block: `aide-memory` (`["npx","-y","aide-memory","mcp","."]`) + `ruflo-hlk-mcp` (`["node","HLK/wrappers/ruflo-hlk-mcp.mjs","mcp","start"]`), local + free. |
| `.opencode/plugins/harness.ts` | Mới (thay `.opencode/plugin/harness.ts` + `harness-plugin.js`) | Migrate logic hữu ích (nén git output) + bridge `.devin/hooks`; **bật mặc định** (opt-out `OPENCODE_HARNESS_HOOKS=0`); fix python Windows `.venv/Scripts/python.exe`. Đặt đúng thư mục auto-load `.opencode/plugins/`. |
| `.opencode/plugin/harness.ts` | Xóa | Sai thư mục (không auto-load), dư sau migrate. |
| `.opencode/plugins/harness-plugin.js` | Xóa | Hook surface cũ + `module.exports` object (không phải plugin function) — không load được. |
| `.opencode/skills/domain-adapters/SKILL.md` | Mới | Wrapper index `/domain`, trỏ `.devin/skills/domain-adapters/` (12 adapter). |
| `.gitignore` | Sửa | Thêm `!.opencode/plugins/` + `!.opencode/plugins/**` (legacy `plugins/` rule chặn cả `.opencode/plugins/`). |

### Verification (Phase-2)

- `opencode mcp list` → **2 server connected**: `aide-memory` (✓), `ruflo-hlk-mcp` (✓).
- `opencode.json` JSON.parse OK; top-level keys hợp lệ.
- `python tools/check_governance.py` → **errors=0** (warnings=3 pre-existing: AHD build-strategy + 2 plans cũ).
- Không đụng `HLK/`, `.env`, security; không destructive.
- **Lưu ý package aide-memory**: `.devin/mcp_config.json` cũ ghi `aide-memory-mcp` (không tồn tại trên npm, 404). Package đúng là **`aide-memory`** (v0.6.4). Đã dùng package đúng trong `opencode.json`.

### Residual risks (Phase-2)

1. `ruflo-hlk-mcp` spawn `npx ruflo@latest mcp start` → cần **network** lần đầu để fetch `ruflo` CLI (không hoàn toàn offline). HLK preload (telemetry/sanitizer/vault) vẫn chạy.
2. Plugin missing optional feature: custom tools (`harness-verify`, `harness-route`, ...) từ `.js` cũ **không migrate** (chồng lấp với slash commands đã có + tốn context). Có thể thêm sau nếu cần.
3. **opencode không hot-reload**: user phải **restart opencode** để MCP + plugin mới có hiệu lực.
4. Không commit — chờ user yêu cầu.
