#!/usr/bin/env bash
# Script đồng bộ an toàn từ Upstream Ruflo mà không làm mất HLK Layer

set -e

UPSTREAM_URL="https://github.com/ruvnet/ruflo.git"
UPSTREAM_REMOTE="upstream"
TARGET_BRANCH="main"

echo "[HLK UPSTREAM SYNC] 🔄 Đang kiểm tra Git remote..."

if ! git remote | grep -q "^${UPSTREAM_REMOTE}$"; then
    echo "[HLK UPSTREAM SYNC] ➕ Thêm remote upstream: ${UPSTREAM_URL}"
    git remote add ${UPSTREAM_REMOTE} ${UPSTREAM_URL}
fi

echo "[HLK UPSTREAM SYNC] 📥 Fetching từ upstream (${TARGET_BRANCH})..."
git fetch ${UPSTREAM_REMOTE}

echo "[HLK UPSTREAM SYNC] 🔀 Đang merge upstream/${TARGET_BRANCH} vào workspace hiện tại..."
git merge ${UPSTREAM_REMOTE}/${TARGET_BRANCH} --no-ff -m "chore: merge updates from upstream ruflo"

echo "[HLK UPSTREAM SYNC] ✅ Cập nhật thành công! Kiểm tra trạng thái HLK..."
node HLK/wrappers/hlk-loader.js
