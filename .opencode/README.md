# opencode registration layer for the Devin harness

> Lớp đăng ký (wrapper) để **opencode** tái sử dụng toàn bộ skills / agents / hooks của harness
> Devin mà **KHÔNG đụng** cấu hình của các provider khác (Devin `.devin/`+`AGENTS.md`, Claude
> `CLAUDE.md`, Aide `.aide/`, Khuym `.khuym/`). Mọi thứ ở đây chỉ được opencode đọc.

## Cách hoạt động

| Thành phần | Vị trí | Nguồn gốc |
|---|---|---|
| Skill wrappers | `.opencode/skills/<name>/SKILL.md` | `name`+`description` trích từ `.devin/skills/...`; body bảo agent **nạp file gốc** |
| Agent wrappers | `.opencode/agent/<name>.md` | nạp `.devin/agents/...` (COMMANDER = primary, còn lại = subagent) |
| Hook bridge | `.opencode/plugin/harness.ts` | gọi `.devin/hooks/*.py` qua subprocess, **best-effort + fail-open** |
| Command | `.opencode/command/harness-upgrade.md` | launcher `/harness-upgrade` |
| Config | `opencode.json` | `skills.paths`, `instructions`, `permission` |

## Đảm bảo an toàn (không làm hỏng provider khác)

- Chỉ **thêm** file vào `.opencode/` + `opencode.json`. Không sửa/xóa gì trong `.devin/`, `CLAUDE.md`,
  `.aide/`, `.khuym/`, `AGENTS.md`.
- `opencode.json` chỉ được opencode đọc (đúng chuẩn schema `https://opencode.ai/config.json`).
- **Hook bridge tắt mặc định** (`OPENCODE_HARNESS_HOOKS` không set = plugin trả `{}`, không làm gì).
  Chỉ khi set `OPENCODE_HARNESS_HOOKS=1` mới gọi `.devin/hooks/*.py`, và vẫn fail-open + fire-and-forget
  (timeout 1.5s, không block tool path). Lý do: hook Devin ghi state dùng chung `.devin/`; tắt mặc định
  tránh nhiễm chéo provider. Cài python: ưu tiên `OPENCODE_HARNESS_PYTHON` → `.venv/bin/python` → `python3`.
- Skill/agent wrapper **không nhân đôi logic** — chỉ trỏ agent về file gốc, tránh drift. Wrapper cũng
  chứa guardrail "không apply/install/đổi state trừ khi user yêu cầu" (chạy phần read-only trước, xác nhận rồi mới sửa).
- `opencode.json` permission: `git push --force`/`-f`, `rm -rf`, `drop table`, install-script
  (`curl|sh`, `wget|sh`), `mkfs`, `chmod -R 777` bị deny; còn lại ask (thứ tự rule: `*` đầu, rule đặc thù sau).

## Kích hoạt

1. Khởi động lại opencode (config nạp một lần, không hot-reload).
2. Test:
   - `/harness-upgrade` (full chain)
   - Gõ từ khoá trigger của skill (VD: "adversarial review", "nâng cấp harness") để opencode gợi skill wrapper.
   - `@agent` → chọn `scout`, `verifier`, `saboteur`, `commander`, … (các wrapper).
3. Muốn bật hook bridge: `OPENCODE_HARNESS_HOOKS=1 opencode` (tùy chọn, mặc định tắt).
   Đổi python: `OPENCODE_HARNESS_PYTHON=/path/to/python`.
   Muốn tắt hẳn plugin: xoá `.opencode/plugin/harness.ts`.

## Ghi chú

- Nếu skill gốc đổi `name`/`description`, chạy lại generator để refresh wrapper:
  `.venv/bin/python /tmp/gen_wrappers.py` (script nằm trong git history / doc này; tái tạo tương đương).
- Model executor (glm/kimi/lightning) **không** được pin vào wrapper agent để tránh lỗi provider
  chưa cấu hình trong opencode; agent dùng model mặc định của opencode và nạp role từ file gốc.
