# Workspace Governance — Quy hoạch file/folder cho MỌI AI agent

> File gốc (canonical) quy định **file/folder vào đúng nơi**, **không sinh rác**, và **khớp plan ↔ act**.
> Áp dụng cho mọi AI agent (Cline, Claude Code, Devin CLI, opencode, Aide, Codex/Khuym, Cursor...) và human.
> Entry file của từng provider chỉ trỏ về đây. Kiểm tra tuân thủ: `python3 tools/check_governance.py`

## 1. Mục tiêu

1. **Không file rác** trong workspace (scratch, `.bak`, `.tmp`, test thử, file vô danh...).
2. **Mọi file/folder mới vào đúng nơi quy định** — xem bản đồ mục 2 và cheat sheet mục 8.
3. **Khớp plan ↔ act**: mọi thay đổi code thuộc plan đã duyệt; mọi plan đã duyệt đều có execution report.

## 2. Bản đồ thư mục (đâu được đặt gì)

| Đường dẫn | Được phép đặt | Cấm |
|-----------|---------------|-----|
| `.devin/scripts/*.py` | Source runtime của harness | Script tạm, file 1 lần, test lẻ |
| `.devin/hooks/*.py` | Hook guard (lifecycle Devin) | Code không liên quan hook |
| `.devin/canon/` | Protocol files (AHD-owned) | **Cấm sửa trực tiếp** |
| `.devin/reports/` | Báo cáo nội bộ harness (audit) | Báo cáo feature thông thường |
| `tests/test_*.py` | Unit/integration test | Test ở nơi khác (trừ self-test có sẵn trong `.devin/scripts/`) |
| `tools/*.py\|ps1\|sh` | Tiện ích dùng lại được | Tiện ích 1 lần cho task cụ thể |
| `docs/plans/<slug>/` | Plan artifacts: `IMPLEMENTATION_PLAN.md`, `SOLUTION_DESIGN.md`, `EXECUTION_REPORT.md`, `FINAL_REPORT.md`, review files | File không thuộc feature |
| `docs/reports/*.md` | Báo cáo chung — format `<SUBJECT>_<YYYY-MM-DD>.md` | Plan artifact |
| `docs/templates/` | Template dùng chung | File 1 lần |
| `docs/research/` | Ghi chú nghiên cứu (chủ đề) | Kết quả task cụ thể |
| Root (`/`) | CHỈ entry/config files (mục 3) | Mọi file mới khác |
| `tmp/`, `logs/` | Scratch tạm (gitignored) — phải dọn | Giữ lâu dài |

## 3. File root — danh sách được phép (CHỈ những file này, không thêm bừa)

- Entry/rules: `AGENTS.md`, `CLAUDE.md`, `.clinerules/`, `opencode.json`, `README.md`, `SECURITY.md`, `REPOS.md`, `LICENSE`
- Config/deps: `pyproject.toml`, `pytest.ini`, `package.json`, `package-lock.json`, `requirements-lock.txt`, `renovate.json`, `.gitignore`, `.gitattributes`, `.ignore`
- Launcher: `activate.*`, `devin-run.*`, `devin-swe.*`, `loop`, `session`

> **File markdown mới ở root = vi phạm.** Đưa vào `docs/` (theo bản đồ mục 2) hoặc `docs/plans/<slug>/`.

## 3b. Bộ lọc runtime — mọi write/edit đều bị kiểm soát

Các hook chạy trước mỗi tool call sẽ chặn ngay nếu agent cố ghi file sai chỗ:

- `pre_tool_use.py` → Gate 1.8: workspace layout enforcement.
- `plan_enforce.py` → workspace layout enforcement cho write tools.
- Source of truth: `tools/source_map_data.py` (root allowlist), `.devin/scripts/path_zones.py` (safe zones, blocked zones, junk patterns).

Danh sách **file được phép ở root** (cập nhật ở `path_zones.ALLOWED_ROOT_FILES`):
`AGENTS.md`, `CLAUDE.md`, `SECURITY.md`, `REPOS.md`, `README.md`, `LICENSE`, `.gitignore`, `.gitattributes`, `.ignore`, `opencode.json`, `pyproject.toml`, `pytest.ini`, `package.json`, `package-lock.json`, `requirements-lock.txt`, `renovate.json`, `loop`, `session`, `activate.*`, `devin-run.*`, `devin-swe.*`.

**Hậu quả nếu vi phạm:** tool call bị từ chối với lý do `Root file '<name>' is not allowed` hoặc `Junk file blocked`.

## 4. Quy tắc "không rác" (bắt buộc)

1. Không tạo scratch file ở root, `docs/`, `.devin/` — dùng `tmp/` (đã gitignore) hoặc `/tmp`, xóa khi xong.
2. Không để `*.bak`, `*.tmp`, `*.orig`, `*.swp`, `*~`, `untitled*`, `scratch*`, `.DS_Store`, `*.log` (tracked) trong workspace.
3. Mọi file mới phải được **commit trong git** khi kết thúc task; file chưa dùng → xóa, không để lại.
4. Không tạo file `.py` ở root; không tạo test ngoài `tests/`.
5. File/variable name tiếng Anh, không dấu. Python `snake_case.py`; shell/PowerShell `kebab-case.*`.

## 5. Plan ↔ Act contract (khớp plan và act)

> Mẫu plan: `docs/templates/PLAN_TEMPLATE.md`; SDD: `docs/templates/SDD_TEMPLATE.md`.
> Slug plan: lowercase, hyphen (theo `slugify()` trong `.devin/scripts/plan_fsm/storage.py`).

1. **PLAN phase** — trước khi sửa code: viết `docs/plans/<slug>/IMPLEMENTATION_PLAN.md`.
   Mỗi task khai báo: `File Path`, `Function`, `Acceptance Criteria`, `REQ ID` (có sẵn trong template).
   Plan chưa duyệt (Status ≠ Approved) thì không được Act đối với M/L/XL tasks.
2. **ACT phase** — CHỈ sửa:
   - File có trong cột `File Path` của plan, **và**
   - Test file của task (đặt trong `tests/`).
   Không sửa file ngoài plan (drift) — nếu phát hiện cần thiết, cập nhật plan trước, xin duyệt lại.
3. **SAU ACT** — viết `docs/plans/<slug>/EXECUTION_REPORT.md`:
   - Commits, files changed (đầy đủ), kết quả test + coverage, residual risks.
   - Self-check: `git diff --name-only` (và untracked) ⊆ files đã khai trong plan/report.
4. **VERIFY** — `python3 tools/check_governance.py` phát hiện:
   - Plan không có execution report (plan chưa act xong).
   - File code (`.devin/scripts/`, `.devin/hooks/`, `tests/`) thay đổi nhưng **không nằm trong plan nào** (act không plan).
5. Không tự ý chạy `plan_orchestrator.py` từ Cline — đó là cơ chế Devin CLI (xem `.clinerules/04-workflow.md`).

## 6. Đa provider — ai đọc gì, ghi ở đâu

| Provider | Config / auto-load | Ghi chú |
|----------|--------------------|---------|
| Cline | `.clinerules/` (auto mỗi session) + `AGENTS.md` + `CLAUDE.md` | `05-file-governance.md` = bản rút gọn file này |
| Claude Code | `CLAUDE.md` (auto) + `AGENTS.md` | `.claude/` gitignored — không commit |
| Devin CLI | `AGENTS.md` + `.devin/AGENTS.md` + `.devin/config.json` | hooks `plan_enforce.py` chặn write nếu chưa plan |
| opencode | `opencode.json` → `instructions` trỏ về file này | `.opencode/` wrapper — không đụng `.devin/` |
| Aide | `.aide/config.json` | memory/cache gitignored |
| Codex/Khuym | `AGENTS.md` (Khuym block) + `.khuym/state.json` | state theo Khuym, không commit |
| Cursor | `.cursor/` (gitignored, được tạo lại) | Không commit |

**Quy tắc chéo provider:**
- KHÔNG ghi state của provider này vào thư mục provider khác (`.devin/` state chỉ Devin, `.khuym/` chỉ Khuym, `.opencode/` chỉ opencode, `.aide/` chỉ Aide).
- Runtime state (`.devin/loop_state/`, `session_state/`, `plan_state/`, `telemetry/`, `blackboard/`, `context_flags/`...) là gitignored — không commit, không đọc làm nguồn.
- `.devin/canon/` và `HLK/` = vùng cấm sửa trực tiếp (sửa qua quy trình chính thức của harness).

## 7. Enforcement

### 7.1 Governance lint

```bash
python3 tools/check_governance.py            # lint đầy đủ (junk + layout + plan-act)
python3 tools/check_governance.py --plan-act # chỉ kiểm tra khớp plan ↔ act
```

- Exit code `0` = sạch; `1` = có lỗi cần sửa; `2` = có warning nên xử lý.
- Chạy **trước khi kết thúc task M-tier+** và khi nghi ngờ workspace bẩn.
- Sau khi thay đổi cấu trúc: chạy `python3 tools/gen_source_map.py` để refresh `.clinerules/00-source-map.md`.

### 7.2 Junk file scanner (cross-platform Windows + macOS)

```bash
python3 tools/junk_file_scanner.py            # scan tất cả (tracked + untracked)
python3 tools/junk_file_scanner.py --staged   # chỉ scan staged area (cho pre-commit)
python3 tools/junk_file_scanner.py --tracked  # chỉ scan tracked files
python3 tools/junk_file_scanner.py --json     # output JSON cho CI
python3 tools/junk_file_scanner.py --fix      # git rm --cached junk đã tracked
```

Phát hiện:
- OS junk: `.DS_Store`, `Thumbs.db`, `desktop.ini`, `*.swp`, `*.swo`, `*~`, `*.orig`, `*.rej`, `*.bak`, `*.tmp`, `*.temp`
- Provider runtime state đã commit: `.khuym/`, `.aide/`, `.codegraph/`, `.opencode/session_state/`, `.omo/`, `.serena/`, `.claude/`, `.cursor/`
- Filler content: file chỉ chứa 1 ký tự lặp lại (vd `xxxx...` hàng nghìn lần)
- Scratch/untitled files

### 7.3 .gitignore audit (cross-platform)

```bash
python3 tools/gitignore_audit.py              # audit + báo cáo
python3 tools/gitignore_audit.py --json       # output JSON cho CI
python3 tools/gitignore_audit.py --strict     # exit 1 nếu thiếu rule
```

Kiểm tra `.gitignore` có rule cho tất cả provider runtime dirs + OS junk.
Required rules: `.khuym/`, `.aide/`, `.codegraph/`, `.opencode/session_state/`, `.omo/`, `.serena/`, `.claude/`, `.cursor/`, `.agents/`, `.DS_Store`, `Thumbs.db`, `desktop.ini`, `*.swp`, `*.swo`, `*~`, `*.orig`, `*.rej`, `*.bak`, `*.tmp`, `*.temp`, `backups/`.

### 7.4 Pre-commit hook (4 gates — git bash, cross-platform)

Hook `.githooks/pre-commit` chạy 4 gates trước mỗi commit:

| Gate | Tool | Chặn nếu |
|------|------|----------|
| 1 — Redaction | `dist-cjs/src/hooks/redaction-hook.js` | API key/secret trong staged files |
| 2 — Junk scanner | `tools/junk_file_scanner.py --staged` | Junk file/provider runtime trong staged area |
| 3 — .gitignore audit | `tools/gitignore_audit.py --strict` | .gitignore thiếu required rule |
| 4 — Governance | `tools/check_governance.py --layout-only` | File sai vị trí (root markdown, junk) |

**Bất kỳ gate FAIL → commit bị chặn.** Agent phải fix issue trước khi commit lại.

### 7.5 CI integration

Thêm vào CI workflow:
```yaml
- name: Junk file scanner
  run: python3 tools/junk_file_scanner.py --json
- name: .gitignore audit
  run: python3 tools/gitignore_audit.py --strict
- name: Governance check
  run: python3 tools/check_governance.py
```

## 8. Cheat sheet — file mới đặt ở đâu

| Loại file mới | Nơi đặt |
|---------------|---------|
| Script harness | `.devin/scripts/<name>.py` (+ `tests/test_<name>.py`) |
| Hook | `.devin/hooks/<name>.py` (+ `tests/test_<name>.py`) |
| Test | `tests/test_*.py` |
| Utility dùng lại | `tools/<name>.py` / `.ps1` / `.sh` |
| Plan feature | `docs/plans/<slug>/IMPLEMENTATION_PLAN.md` |
| Execution report | `docs/plans/<slug>/EXECUTION_REPORT.md` |
| Báo cáo chung | `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md` |
| Nghiên cứu | `docs/research/<topic>.md` |
| Template | `docs/templates/<NAME>_TEMPLATE.md` |
| Scratch tạm | `tmp/` (gitignored — phải dọn) |
| Ghi chú task nội bộ | KHÔNG tạo ở root — bỏ vào plan dir hoặc xóa |

