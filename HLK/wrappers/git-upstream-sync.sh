#!/usr/bin/env bash
# HLK Upstream Sync — v2.1.0
# ===========================
# Mục đích tổng thể:
#   Đồng bộ từ upstream Ruflo mà KHÔNG làm mất lớp HLK.
#
# Quy trình:
#   1. Kiểm tra / thêm remote upstream
#   2. Fetch upstream
#   3. Backup hlk.config.json
#   4. Merge upstream/main --no-ff
#   5. Chạy hlk-verify-integrity.js
#   6. Ghi log
#
# Cách dùng:
#   bash HLK/wrappers/git-upstream-sync.sh
#   bash HLK/wrappers/git-upstream-sync.sh --dry-run

set -e

UPSTREAM_URL="https://github.com/ruvnet/ruflo.git"
UPSTREAM_REMOTE="upstream"
TARGET_BRANCH="main"
DRY_RUN=false

# ---------------------------------------------------------------------------
# Bước 1: Parse args
# ---------------------------------------------------------------------------

if [[ "$1" == "--dry-run" || "$1" == "-n" ]]; then
  DRY_RUN=true
fi

# ---------------------------------------------------------------------------
# Bước 2: Kiểm tra / thêm remote upstream
# ---------------------------------------------------------------------------

echo "[HLK UPSTREAM SYNC] 🔄 Kiểm tra Git remote..."

if ! git remote | grep -q "^${UPSTREAM_REMOTE}$"; then
  echo "[HLK UPSTREAM SYNC] ➕ Thêm remote upstream: ${UPSTREAM_URL}"
  git remote add ${UPSTREAM_REMOTE} ${UPSTREAM_URL}
else
  git remote set-url ${UPSTREAM_REMOTE} ${UPSTREAM_URL}
fi

# ---------------------------------------------------------------------------
# Bước 3: Fetch upstream
# ---------------------------------------------------------------------------

echo "[HLK UPSTREAM SYNC] 📥 Fetching từ upstream (${TARGET_BRANCH})..."
git fetch ${UPSTREAM_REMOTE}

# ---------------------------------------------------------------------------
# Bước 4: Dry-run (nếu được yêu cầu)
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[HLK UPSTREAM SYNC] 🧪 DRY-RUN — chỉ hiển thị thống kê thay đổi:"
  git diff --stat HEAD..${UPSTREAM_REMOTE}/${TARGET_BRANCH}
  echo "[HLK UPSTREAM SYNC] ✅ Dry-run hoàn tất. Không có gì được ghi."
  exit 0
fi

# ---------------------------------------------------------------------------
# Bước 5: Backup HLK config
# ---------------------------------------------------------------------------

mkdir -p HLK/logs
BACKUP_FILE="HLK/logs/hlk.config.json.backup.$(date +%Y%m%d-%H%M%S).json"
cp HLK/config/hlk.config.json "$BACKUP_FILE"
echo "[HLK UPSTREAM SYNC] 💾 Đã backup HLK config → ${BACKUP_FILE}"

# ---------------------------------------------------------------------------
# Bước 6: Merge upstream
# ---------------------------------------------------------------------------

echo "[HLK UPSTREAM SYNC] 🔀 Đang merge upstream/${TARGET_BRANCH}..."
git merge ${UPSTREAM_REMOTE}/${TARGET_BRANCH} --no-ff -m "chore: merge updates from upstream ruflo"

# ---------------------------------------------------------------------------
# Bước 7: Kiểm tra tính toàn vẹn HLK
# ---------------------------------------------------------------------------

echo "[HLK UPSTREAM SYNC] 🔍 Kiểm tra tính toàn vẹn HLK..."
node HLK/wrappers/hlk-verify-integrity.js

# ---------------------------------------------------------------------------
# Bước 8: Ghi log
# ---------------------------------------------------------------------------

LOG_FILE="HLK/logs/upstream-sync.$(date +%Y%m%d-%H%M%S).log"
{
  echo "Upstream sync completed at $(date -Iseconds)"
  echo "Upstream commit: $(git rev-parse ${UPSTREAM_REMOTE}/${TARGET_BRANCH})"
  echo "Backup config: ${BACKUP_FILE}"
} > "$LOG_FILE"

echo "[HLK UPSTREAM SYNC] ✅ Hoàn tất! Log: ${LOG_FILE}"
