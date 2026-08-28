# Harness Upgrade Log

Nhật ký các lần upgrade harness. Mỗi entry: date · scope · applied upgrades · verify · verdict.

---

## 2026-08-27 — opencode full integration

- **Scope**: wrap/link để opencode nhận diện đầy đủ `.devin`, `HLK`, `.agents`, `AGENTS.md`.
- **Root cause**: `.opencode/config.json` bị bỏ lỡ (sai tên file). Schema opencode `additionalProperties:false` → không merge nguyên, chỉ bổ sung field hợp lệ.
- **Applied**:
  - `opencode.json`: `skills.paths` += `.devin/skills`; thêm `references` (canon, agents-state, hlk-docs, hlk-prompts, docs).
  - 8 slash command: full-power, plan, lightning, glm, kimi, adversarial-consensus, hlk-git-tools, hlk-integrity-check, hlk-loop.
  - 2 skill wrapper: hlk-loop, hlk-upstream-pull.
- **Verify**: JSON OK; `check_governance.py` errors=0; không đụng HLK/.env.
- **Verdict**: ✅ PASS. Cần restart opencode.
- **Plan**: `docs/plans/opencode-full-integration/`.

---

## 2026-08-27 — opencode full integration (Phase 2)

- **Scope**: hoàn tất MCP integration + plugin cleanup + wrap domain-adapters cho opencode.
- **Root cause (plugin)**: `harness.ts` cũ nằm ở `.opencode/plugin/` (số ít — không auto-load theo docs opencode; đúng là `.opencode/plugins/`). `harness-plugin.js` dùng hook surface cũ (`preToolUse`/`sessionStart`) + `module.exports` object (không phải plugin function) → không load được. Đường dẫn python tham chiếu `.venv/bin/python` (Unix) không tồn tại trên Windows.
- **Applied**:
  - `opencode.json`: thêm `mcp` — `aide-memory` (`npx -y aide-memory mcp .`) + `ruflo-hlk-mcp` (`node HLK/wrappers/ruflo-hlk-mcp.mjs mcp start`), cả 2 local, free, `timeout` 20s/30s.
  - `.opencode/plugins/harness.ts` (mới): migrate logic hữu ích từ `.js` cũ (nén output git diff/status/ls), giữ bridge hook `.devin/hooks/*.py` (advisory, fail-open), **bật mặc định**, opt-out `OPENCODE_HARNESS_HOOKS=0`, fix path `.venv/Scripts/python.exe` cho Windows.
  - Xóa `.opencode/plugins/harness-plugin.js` (API cũ) + `.opencode/plugin/harness.ts` (sai thư mục, dư).
  - `.opencode/skills/domain-adapters/SKILL.md` (mới): wrapper index expose trigger `/domain`, trỏ tới `.devin/skills/domain-adapters/` (12 adapter).
  - `.gitignore`: thêm `!.opencode/plugins/` + `!.opencode/plugins/**` (legacy `plugins/` rule chặn cả `.opencode/plugins/`).
- **Verify**: `opencode mcp list` → 2 server **connected**; JSON OK; `check_governance.py` errors=0. **Lưu ý**: `aide-memory` package thật là `aide-memory` (không phải `aide-memory-mcp` như `.devin/mcp_config.json` cũ ghi). Cần **restart opencode** để MCP + plugin mới có hiệu lực.
- **Verdict**: ✅ PASS (chờ restart opencode).
- **Plan**: `docs/plans/opencode-full-integration/`.
