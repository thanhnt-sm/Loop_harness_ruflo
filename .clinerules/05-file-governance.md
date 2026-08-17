# 05 — File Governance (bắt buộc, mọi session)

> Bản rút gọn của `.devin/rules/WORKSPACE_GOVERNANCE.md` (canonical). Khi có mâu thuẫn, theo canonical.
> Enforcement: `python3 tools/check_governance.py` (lint junk + layout + plan↔act).

## 1. Không sinh file rác

- **KHÔNG** tạo scratch/`*.bak`/`*.tmp`/`*.orig`/`*~`/`untitled*`/`scratch*`/`.DS_Store` trong workspace.
- File tạm → `tmp/` (gitignored) hoặc `/tmp`, **xóa khi xong**.
- Mọi file mới phải **commit trong git** khi kết thúc task; file chưa dùng → xóa.
- Không tạo `.py` ở root; không tạo test ngoài `tests/` (trừ self-test có sẵn).

## 2. File mới phải vào đúng nơi (cheat sheet)

| Loại | Nơi đặt |
|------|---------|
| Script harness | `.devin/scripts/<name>.py` + `tests/test_<name>.py` |
| Hook | `.devin/hooks/<name>.py` + `tests/test_<name>.py` |
| Test | `tests/test_*.py` |
| Utility dùng lại | `tools/<name>.py` / `.ps1` / `.sh` |
| Plan feature | `docs/plans/<slug>/IMPLEMENTATION_PLAN.md` |
| Execution report | `docs/plans/<slug>/EXECUTION_REPORT.md` |
| Báo cáo chung | `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md` |
| Nghiên cứu | `docs/research/<topic>.md` |
| Template | `docs/templates/<NAME>_TEMPLATE.md` |
| Ghi chú task | KHÔNG tạo ở root — bỏ vào plan dir hoặc xóa |

**Root chỉ chứa:** entry/rules (`AGENTS.md`, `CLAUDE.md`, `.clinerules/`, `opencode.json`...), config (`pyproject.toml`, `pytest.ini`, `package.json`...), launcher (`devin-run.*`, `activate.*`, `loop`, `session`), và các file đã commit.
**Markdown mới ở root = vi phạm.**

## 3. Khớp plan ↔ act (bắt buộc M-tier+)

1. **Plan trước** — M/L/XL: viết `docs/plans/<slug>/IMPLEMENTATION_PLAN.md` (template `docs/templates/PLAN_TEMPLATE.md`), mỗi task khai `File Path` + `Acceptance Criteria` + `REQ ID`. Chờ approve trước khi sửa code.
2. **Act đúng plan** — chỉ sửa file có trong cột `File Path` (+ test file của task trong `tests/`). Không sửa file ngoài plan; nếu cần, cập nhật plan trước.
3. **Report sau act** — viết `docs/plans/<slug>/EXECUTION_REPORT.md` (commits, files changed, test/coverage, risks).
4. **Verify** — `python3 tools/check_governance.py` (phát hiện: file code đổi không nằm plan nào; plan không có report).

## 4. Đa provider — không đụng nhau

- KHÔNG ghi state của provider này sang provider khác: `.devin/` (Devin), `.khuym/` (Khuym), `.opencode/` (opencode), `.aide/` (Aide).
- Runtime state (`.devin/loop_state/`, `session_state/`, `plan_state/`, `telemetry/`, `blackboard/`...) gitignored — không commit, không đọc làm nguồn.
- `.devin/canon/` + `HLK/` = cấm sửa trực tiếp.
- Cline: `.clinerules/` auto-load. opencode: `opencode.json` `instructions`. Claude Code: `CLAUDE.md`. Devin: `AGENTS.md`.

## 5. Quy ước đặt tên

- Python `snake_case.py`; shell/PowerShell `kebab-case.*`.
- Slug plan: lowercase, hyphen (theo `slugify()` trong `.devin/scripts/plan_fsm/storage.py`).
- Report: `<SUBJECT>_<YYYY-MM-DD>.md`.

## 6. Kiểm tra trước khi kết thúc task

1. `python3 tools/check_governance.py` — exit 0 (hoặc 2 = warning đã giải thích).
2. `git status` + `git diff --stat` — rà scope, đúng nơi.
3. Nếu đổi cấu trúc: `python3 tools/gen_source_map.py` — refresh `.clinerules/00-source-map.md`.
