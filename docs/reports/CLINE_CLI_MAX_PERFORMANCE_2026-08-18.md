# Cline CLI — Max Performance / Full Chain (knowledge base)

> **Verified sources** (fetched `docs.cline.bot`): `usage/cli.md`, `cli/cli-reference.md`,
> `features/plan-and-act.md`. Cài đặt: `npm i -g cline`. Auth: `cline auth`.
> Workspace convention: `.clinerules/` = Cline rules layer (CLAUDE.md/AGENTS.md là entry).

## 1. Cài đặt + auth nhanh

```bash
npm i -g cline          # cài CLI
cline auth              # chọn provider (cline / clinepass / own key)
cline                   # interactive TUI / chat
```

- Provider mặc định `-P, --provider <id>` = `cline` ([fact] cli-reference).
- `ClinePass` (US$9.99/tháng) tăng quota 2-5x so với usage-billing.

## 2. Full chain: Plan → Act (headless)

Cline có built-in **Plan & Act Mode**. `-p` bắt đầu ở **Plan mode** (chỉ đọc/search, **không sửa file**);
mặc định (không có `-p`) là **Act mode** (thực thi). `--auto-approve` mặc định `true`.

```bash
# 1. Plan phase (headless, chỉ khám phá — không thay đổi file)
cline -p "lên migration plan cho module X"

# 2. Act phase (cùng context, thực thi) — auto-approve bật sẵn
cline "cài đặt migration theo plan ở trên"

# One-shot (act trực tiếp)
cline "refactor module X sang async/await"
```

- Dài hạn/complex: dùng `/deep-planning` (trong interactive TUI) → khám phá code, dự thức dependency, viết kế hoạch. [fact — plan-and-act.md]
- Phân chia model: cài đặt "Use different models for Plan and Act" → Plan=strong reasoning, Act=nhanh/rẻ. [fact — plan-and-act.md]

## 3. Headless / CI (xử lý không cần duyệt từng thao tác)

Headless kích hoạt khi dùng `--json`, stdin pipe, hoặc redirect stdout.

```bash
cline --json "summarize key setup steps" | jq -r '.text'
git diff | cline "review these changes"              # pipe context vào
git diff | cline "explain these changes" | cline "write a commit message"  # chain
```

## 4. Max performance (tốc độ + chi phí)

| Flag | Mục đích |
|------|----------|
| `-m, --model <model-id>` | Chọn model (override provider) |
| `-P, --provider <id>` | Chọn provider (mặc định `cline`) |
| `--thinking <none\|low\|medium\|high\|xhigh>` | Mức reasoning (default `medium`); `xhigh` để plan, `low` để act |
| `--auto-approve <bool>` | Tự động approve toàn bộ tools (mặc địng `true`) — bật cho headless |
| `--timeout <seconds>` | Timeout task |
| `--retries <n>` | Số retry tối đa |
| `--cwd <path>` | Thư mục làm việc (dùng repo này) |
| `--config <dir>` | Thư mục config riêng (cách ly state) |
| `--data-dir <path>` | Cách ly toàn bộ state (~/.cline) |
| `--system <prompt>` | Override system prompt (custom chain) |
| `--id <session-id>` | Resume session |
| `--verbose` / `-v` | Debug |

**Chiến lược max perf:** Plan dùng model mạnh (`--thinking xhigh`), Act dùng model nhanh/rẻ (`--thinking low`), `--auto-approve true`, `--timeout` to keep runs bounded, `--cwd` để trỏ repo.

## 5. Security / sandbox (bắt buộc cho headless)

```bash
# Chạy trong sandbox (ClinePass/local)
export CLINE_SANDBOX=true
export CLINE_SANDBOX_DATA_DIR=/tmp/cline-sandbox

# Restrict shell commands (deny luôn precedence)
export CLINE_COMMAND_PERMISSIONS='{"allow":["git *","npm test"],"deny":["rm -rf *","sudo *","curl *"]}'
```

- `--config <empty-dir>` hoặc `--data-dir /tmp/cline-run` để chạy CI mà **không nạp global keys/rules** của dev. [fact — cli-reference]
- `--auto-approve false` nếu muốn review từng tool (dev mode).

## 6. 2 chế độ On/Off all rules + command chuyển nhanh

Cline native: project rules dir = `.cline/rules/`, global = `~/.cline/data/settings/rules/`.
Disable native: `mv .cline/rules .cline/rules.off` (hoặc `--config <dir_không_rule>`).

Workspace THƯỢP dụng `.clinerules/` làm rules layer (xem §2 canonical `WORKSPACE_GOVERNANCE.md`). Để bật/tắt nhanh:

```bash
./tools/cline-toggle-rules.sh status     # in trạng thái
./tools/cline-toggle-rules.sh off        # .clinerules/ -> .clinerules.off/ (tắt all rules)
./tools/cline-toggle-rules.sh on         # khôi phục (bật lại)
./tools/cline-toggle-rules.sh toggle     # chuyển nhanh
```

- Windows: `pwsh tools\cline-toggle-rules.ps1 off`
- ⚠️ `[inference]` docs Cline chưa liệt kê `.clinerules/` trong project-rules (chỉ `.cline/rules/`). Nếu Cline không native load `.clinerules/`, hãy symlink: `ln -s .clinerules .cline/rules` rồi toggle `.clinerules/`. Workspace coi `.clinerules/` là nguồn rules (CLAUDE.md/AGENTS.md cũng trỏ tới), nên toggle `.clinerules/` vẫn là cách tắt rules layer của repo.

## 7. Cheat sheet — câu lệnh full chain max perf

```bash
cd "$(git rev-parse --show-toplevel)"

# Full chain: plan → act (headless, max perf, secure)
cline -p -m claude-3-7-sonnet-20250219 --thinking xhigh \
  "lên plan triển khai X" \
  | tee /tmp/plan.md
cline -m google/gemini-2.0-flash --thinking low --auto-approve true \
  -c "$(pwd)" --cwd "$(pwd)" \
  "cài đặt X theo /tmp/plan.md"

# CI / automation (processable)
git diff | CLINE_SANDBOX=true CLINE_COMMAND_PERMISSIONS='{"deny":["rm -rf *","sudo *"]}' \
  cline --json "review for regressions, return JSON" | jq -r '.text'
```

## 8. Lưu ý khi dùng Cline trên repo này (Loop_harness_ruflo)

- Repo là **Devin/Claude Code/opencode/Khuym/Cursor** harness (được mô tả trong `AGENTS.md` + `.clinerules/01-orientation.md`). Cline chỉ là một consumer của `.clinerules/`.
- Trước khi Cline sửa code: bật rules ON (`./tools/cline-toggle-rules.sh on`) để Cline nạp đủ canon/governance; bật `CLINE_COMMAND_PERMISSIONS` để chặn `rm -rf`/`sudo`.
- Sau task: chạy `python3 tools/check_governance.py` + `python3 tools/gen_source_map.py` để verify rác + refresh map.
- Để dùng full chain của HARNESS này (không phải Cline): `/full-power <task>` (Devin CLI) hoặc `.devin/scripts/plan_orchestrator.py --init --task "<task>"`.
