# Báo Cáo 04 — Kế Hoạch Cập Nhật Upstream Ruflo Không Phá Hỏng HLK

> **Pipeline HLK — Prompt 04: Upstream Update & Maintenance Plan**
> Phạm vi: repo cục bộ `Loop_harness_ruflo`, remote `upstream` trỏ về `https://github.com/ruvnet/ruflo.git`.
> Vai trò: DevOps & Release Manager — thiết kế quy trình và cung cấp script mẫu để đồng bộ upstream mà vẫn giữ nguyên lớp bọc HLK.

---

## 1. Tóm Tắt Điều Hành

Trạng thái hiện tại đã có sẵn remote `upstream` và một script `HLK/wrappers/git-upstream-sync.sh`. Tuy nhiên, quy trình cần siết thêm ở các điểm sau để đảm bảo an toàn tuyệt đối:

1. **Backup `hlk.config.json` trước merge** — phòng trường hợp merge strategy `ours` bị sai hoặc người dùng vô tình bỏ `.gitattributes`.
2. **Dry-run mode** — cho phép xem trước diff mà không ghi bất kỳ thay đổi nào.
3. **Post-merge integrity check đúng file** — hiện tại đã được sửa từ `hlk-loader.js` sang `hlk-verify-integrity.js` (một lỗi typo trong phiên bản trước).
4. **Giữ bản ghi log mỗi lần merge** trong `HLK/logs/`.
5. **Xử lý rủi ro đặc biệt: `agentdb.rvf`/`agentdb.rvf.lock` đang bị git track** — cần `git rm --cached` + bổ sung `.gitignore` ngay trong lần merge tới.

---

## 2. Cấu Trúc Git Remote & Branching

```text
origin    → remote cá nhân/nội bộ có chứa HLK (repo hiện tại)
upstream  → https://github.com/ruvnet/ruflo.git (không có quyền push)
```

Xác minh thực tế:

```bash
$ git remote -v
upstream	https://github.com/ruvnet/ruflo.git (fetch)
upstream	https://github.com/ruvnet/ruflo.git (push)
```

Nguyên tắc:
- Không bao giờ push HLK lên `upstream`.
- Tất cả thay đổi HLK chỉ commit trên `origin` (hoặc local).
- Khi `git merge upstream/main`, thư mục `HLK/` được bảo vệ bởi `.gitattributes` (dòng 7–25).

---

## 3. Cơ Chế Chống Xung Đột

### 3.1. `.gitattributes` — merge strategy `ours` cho toàn bộ HLK

File `.gitattributes` hiện tại (25 dòng) đã khai:

```gitattributes
HLK/config/hlk.config.json merge=ours
HLK/wrappers/** merge=ours
HLK/security/** merge=ours
HLK/prompts/** merge=ours
HLK/README.md merge=ours
HLK/loop/** merge=ours
HLK/reports/** merge=ours
```

Ý nghĩa: khi merge upstream, git sẽ luôn giữ phiên bản **local** cho các file trên, bất kể upstream có thay đổi gì trong các path tương ứng.

### 3.2. `.gitignore` — bảo vệ secrets, logs, runtime DB

Các rule quan trọng đã có:

```gitignore
# HLK Local Secrets & Private Override
HLK/config/secrets.*
HLK/config/*.local.json
HLK/logs/
```

**Lỗ hổng còn lại:** `.gitignore` chưa có rule cho `agentdb.rvf`, `*.rvf`, `*.rvf.lock` — hai file này đang bị git track (xem Báo cáo 06, mục 3.3). Đây là kênh rò rỉ nghiêm trọng cần vá trong Prompt 07.

### 3.3. `HLK/` nằm ngoài source tree của upstream

`github.com/ruvnet/ruflo` không có thư mục `HLK/`. Do đó, xung đột nội dung trực tiếp là rất hiếm. Rủi ro chính là:
- Người dùng tự xóa/sửa `.gitattributes`.
- Upstream thay đổi root files (`package.json`, `.gitignore`, `README.md`) và tạo conflict cần resolve bằng tay.

---

## 4. Quy Trình Bảo Trì Từng Bước

### Bước 1: Chuẩn bị

```bash
# 1.1 Chuyển về branch làm việc (thay "master" bằng branch bạn dùng)
git checkout master

# 1.2 Đảm bảo working tree sạch hoặc đã commit hết
# Không nên merge khi có thay đổi đang mở

git status --short
```

### Bước 2: Backup HLK config

```bash
mkdir -p HLK/logs

cp HLK/config/hlk.config.json "HLK/logs/hlk.config.json.backup.$(date +%Y%m%d-%H%M%S).json"
```

### Bước 3: Fetch upstream

```bash
git fetch upstream
```

### Bước 4: Xem trước thay đổi (tùy chọn, khuyến nghị)

```bash
git log --oneline --graph --left-right --decorate master...upstream/main

git diff --stat master upstream/main
```

### Bước 5: Merge

```bash
git merge upstream/main --no-ff -m "chore: merge updates from upstream ruflo"
```

Nếu có conflict ở root files, resolve thủ công, KHÔNG resolve theo upstream cho bất kỳ file trong `HLK/`.

### Bước 6: Kiểm tra tính toàn vẹn HLK

```bash
node HLK/wrappers/hlk-verify-integrity.js
```

### Bước 7: Khôi phục config nếu bị hỏng

Nếu `hlk.config.json` bị mất hoặc parse lỗi (ít xảy ra nhưng cần có kế hoạch):

```bash
cp "$(ls -t HLK/logs/hlk.config.json.backup.*.json | head -1)" HLK/config/hlk.config.json
```

### Bước 8: Commit kết quả merge

```bash
git commit --amend --no-edit
```

---

## 5. Script Mẫu — `git-upstream-sync.sh` (đã cải tiến)

Script hiện có `HLK/wrappers/git-upstream-sync.sh` đã đúng flow cơ bản. Dưới đây là phiên bản cải tiến có thêm backup, dry-run, log.

```bash
#!/usr/bin/env bash
# HLK Upstream Sync — v2.1.0
# Đồng bộ từ upstream ruflo mà KHÔNG làm mất lớp HLK.

set -e

UPSTREAM_URL="https://github.com/ruvnet/ruflo.git"
UPSTREAM_REMOTE="upstream"
TARGET_BRANCH="main"
DRY_RUN=false

# Parse args đơn giản
if [[ "$1" == "--dry-run" || "$1" == "-n" ]]; then
  DRY_RUN=true
fi

echo "[HLK UPSTREAM SYNC] 🔄 Kiểm tra Git remote..."
if ! git remote | grep -q "^${UPSTREAM_REMOTE}$"; then
  echo "[HLK UPSTREAM SYNC] ➕ Thêm remote upstream: ${UPSTREAM_URL}"
  git remote add ${UPSTREAM_REMOTE} ${UPSTREAM_URL}
else
  git remote set-url ${UPSTREAM_REMOTE} ${UPSTREAM_URL}
fi

echo "[HLK UPSTREAM SYNC] 📥 Fetching từ upstream (${TARGET_BRANCH})..."
git fetch ${UPSTREAM_REMOTE}

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[HLK UPSTREAM SYNC] 🧪 DRY-RUN — chỉ hiển thị thống kê thay đổi:"
  git diff --stat HEAD..${UPSTREAM_REMOTE}/${TARGET_BRANCH}
  echo "[HLK UPSTREAM SYNC] ✅ Dry-run hoàn tất. Không có gì được ghi."
  exit 0
fi

# Backup HLK config trước merge
mkdir -p HLK/logs
BACKUP_FILE="HLK/logs/hlk.config.json.backup.$(date +%Y%m%d-%H%M%S).json"
cp HLK/config/hlk.config.json "$BACKUP_FILE"
echo "[HLK UPSTREAM SYNC] 💾 Đã backup HLK config → ${BACKUP_FILE}"

echo "[HLK UPSTREAM SYNC] 🔀 Đang merge upstream/${TARGET_BRANCH}..."
git merge ${UPSTREAM_REMOTE}/${TARGET_BRANCH} --no-ff -m "chore: merge updates from upstream ruflo"

echo "[HLK UPSTREAM SYNC] 🔍 Kiểm tra tính toàn vẹn HLK..."
node HLK/wrappers/hlk-verify-integrity.js

# Ghi log upgrade
LOG_FILE="HLK/logs/upstream-sync.$(date +%Y%m%d-%H%M%S).log"
{
  echo "Upstream sync completed at $(date -Iseconds)"
  echo "Upstream commit: $(git rev-parse ${UPSTREAM_REMOTE}/${TARGET_BRANCH})"
  echo "Backup config: ${BACKUP_FILE}"
} > "$LOG_FILE"

echo "[HLK UPSTREAM SYNC] ✅ Hoàn tất! Log: ${LOG_FILE}"
```

### PowerShell tương đương — `git-upstream-sync.ps1`

Script `HLK/wrappers/git-upstream-sync.ps1` đã tồn tại. Dưới đây là nội dung tối thiểu cần có (có thể cải tiến tương tự):

```powershell
#requires -Version 5.1
$ErrorActionPreference = "Stop"

$UpstreamUrl = "https://github.com/ruvnet/ruflo.git"
$UpstreamRemote = "upstream"
$TargetBranch = "main"
$DryRun = $args -contains "-DryRun"

Write-Host "[HLK UPSTREAM SYNC] 🔄 Kiểm tra Git remote..."
$remotes = git remote
if (-not ($remotes -contains $UpstreamRemote)) {
    Write-Host "[HLK UPSTREAM SYNC] ➕ Thêm remote upstream: $UpstreamUrl"
    git remote add $UpstreamRemote $UpstreamUrl
}

Write-Host "[HLK UPSTREAM SYNC] 📥 Fetching từ upstream..."
git fetch $UpstreamRemote

if ($DryRun) {
    Write-Host "[HLK UPSTREAM SYNC] 🧪 DRY-RUN — thống kê thay đổi:"
    git diff --stat HEAD.."$UpstreamRemote/$TargetBranch"
    exit 0
}

$backupDir = "HLK/logs"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupFile = "$backupDir/hlk.config.json.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
Copy-Item HLK/config/hlk.config.json $backupFile
Write-Host "[HLK UPSTREAM SYNC] 💾 Backup config → $backupFile"

git merge "$UpstreamRemote/$TargetBranch" --no-ff -m "chore: merge updates from upstream ruflo"

Write-Host "[HLK UPSTREAM SYNC] 🔍 Kiểm tra tính toàn vẹn HLK..."
node HLK/wrappers/hlk-verify-integrity.js

$logFile = "$backupDir/upstream-sync.$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
@(
    "Upstream sync completed at $(Get-Date -Format 'o')"
    "Upstream commit: $(git rev-parse "$UpstreamRemote/$TargetBranch")"
    "Backup config: $backupFile"
) | Out-File -FilePath $logFile -Encoding utf8

Write-Host "[HLK UPSTREAM SYNC] ✅ Hoàn tất! Log: $logFile"
```

---

## 6. Danh Sách Kiểm Tra Post-Merge (Checklist)

| # | Kiểm tra | Cách thực hiện | Kỳ vọng |
|---|---|---|---|
| 1 | `HLK/` còn nguyên vẹn | `ls HLK/config HLK/wrappers HLK/security` | Các file quan trọng vẫn tồn tại |
| 2 | `hlk.config.json` còn đọc được | `node HLK/wrappers/hlk-verify-integrity.js` | PASS |
| 3 | Remote upstream còn đúng | `git remote -v` | `upstream` vẫn trỏ `ruvnet/ruflo` |
| 4 | Không có file `.rvf`/`.db` nào bị track mới | `git status --porcelain \| grep -E '\.(rvf\|db\|db-journal\|db-wal)$'` | Rỗng |
| 5 | Không có thay đổi HLK trong diff | `git diff --name-only HEAD~1` | Không có path bắt đầu `HLK/` từ upstream |
| 6 | Backup log được tạo | `ls HLK/logs/` | Có file `.json` backup + `.log` mới |

---

## 7. Rủi Ro Đặc Biệt Cần Xử Lý Ở Prompt 07

1. **`agentdb.rvf`/`agentdb.rvf.lock` đang tracked** — cần chạy `git rm --cached` và bổ sung `.gitignore`.
2. **`.gitignore` chưa có rule `*.rvf`** — sửa ngay trước lần merge kế tiếp.
3. **`git-upstream-sync.sh` hiện tại đã sửa typo** (gọi `hlk-verify-integrity.js` thay vì `hlk-loader.js`) nhưng chưa có backup/dry-run/log.

---

## 8. Hướng Dẫn Khẩn Cấp — Khi Merge Làm Hỏng HLK

```bash
# 1. Dừng ngay, đừng commit
git merge --abort

# 2. Khôi phục HLK config từ backup mới nhất
cp "$(ls -t HLK/logs/hlk.config.json.backup.*.json | head -1)" HLK/config/hlk.config.json

# 3. Kiểm tra integrity
node HLK/wrappers/hlk-verify-integrity.js

# 4. Nếu vẫn sai, checkout lại HLK từ origin
git checkout origin/master -- HLK/
```

---

## Learnings

- **Backup trước merge là phòng thủ cuối cùng khi `.gitattributes` bất ngờ mất hiệu lực**: `merge=ours` chỉ hoạt động nếu file `.gitattributes` tồn tại trên branch hiện tại; nếu ai đó xóa nó trước khi merge, HLK config có thể bị ghi đè. Backup tự động + log là lớp bảo vệ thứ hai.
- **Dry-run là yêu cầu không thể thiếu đối với quy trình tự động hóa upstream**: cho phép người dùng xem trước khối lượng thay đổi, tránh merge nhầm khi upstream có breaking change lớn.
- **Post-merge check phải trỏ đúng script**: lỗi typo `hlk-loader.js` thay vì `hlk-verify-integrity.js` trong phiên bản trước minh chứng rằng một dòng lệnh sai cũng khiến toàn bộ quy trình kiểm tra mất ý nghĩa.
- **Rủi ro lớn nhất của upstream sync không phải conflict thư mục HLK mà là root files và gitignore**: upstream không có `HLK/` nên xung đột trực tiếp hiếm; nguy hiểm hơn là upstream thay đổi `.gitignore` root, vô tình mở đường cho `agentdb.rvf`/`.db` bị commit.
- **Script cần `set -e` hoặc `$ErrorActionPreference = "Stop"` để fail fast**: nếu `git fetch` hoặc `git merge` lỗi, script phải dừng ngay thay vì tiếp tục chạy integrity check trên trạng thái chưa merge.
