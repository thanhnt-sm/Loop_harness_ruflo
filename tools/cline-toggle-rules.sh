#!/usr/bin/env bash
# tools/cline-toggle-rules.sh
# Bật / tắt toàn bộ rules layer (.clinerules/) của workspace cho Cline.
# Cline CLI tự động nạp .clinerules/ mỗi session (workspace convention). Đổi tên
# thư mục là cách bật/tắt rules an toàn, không cần flag CLI.
#
# Dùng:  ./tools/cline-toggle-rules.sh [on|off|status|toggle]   (mặc định status)
# Exit:  0 = ok, 1 = lỗi.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES_DIR="$ROOT/.clinerules"
OFF_DIR="$ROOT/.clinerules.off"
ACTION="${1:-status}"

current() { [ -d "$RULES_DIR" ] && echo on || echo off; }

case "$ACTION" in
  on)
    if [ -d "$RULES_DIR" ]; then
      echo "OK: Cline rules ON (.clinerules/)"
    elif [ -d "$OFF_DIR" ]; then
      mv "$OFF_DIR" "$RULES_DIR"
      echo "OK: Cline rules ON — đã khôi phục .clinerules/"
    else
      echo "ERR: không tìm thấy .clinerules/ hay .clinerules.off/" >&2
      exit 1
    fi
    ;;
  off)
    if [ -d "$OFF_DIR" ]; then
      echo "OK: Cline rules OFF (.clinerules.off/)"
    elif [ -d "$RULES_DIR" ]; then
      mv "$RULES_DIR" "$OFF_DIR"
      echo "OK: Cline rules OFF — đã đổi .clinerules/ -> .clinerules.off/"
    else
      echo "ERR: không tìm thấy .clinerules/" >&2
      exit 1
    fi
    ;;
  toggle)
    if [ "$(current)" = "on" ]; then "$0" off; else "$0" on; fi
    ;;
  status)
    s="$(current)"
    target="$RULES_DIR"; [ "$s" = "off" ] && target="$OFF_DIR"
    echo "Cline rules: $s ($target)"
    ;;
  *)
    echo "Dùng: $0 [on|off|status|toggle]" >&2
    exit 1
    ;;
esac
