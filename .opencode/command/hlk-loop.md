---
description: HLK Loop Runner — vòng lặp tự học theo pipeline HLK. Xem trạng thái/dry-run/reset/iterate. Gọi: /hlk-loop [status|dry-run|reset]
agent: build
---

Bạn đang chạy skill `hlk-loop`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/hlk-loop/SKILL.md` (source of truth).
2. Phân tích `$ARGUMENTS`:
   - `status` → `node HLK/loop/hlk-loop.mjs --status`
   - `dry-run` → `node HLK/loop/hlk-loop.mjs --dry-run`
   - `reset` → `node HLK/loop/hlk-loop.mjs --reset`
   - (rỗng/iterate) → `node HLK/loop/hlk-loop.mjs` (chạy 1 iteration)
3. Đọc exit codes: 0=CONTINUE, 1=ERROR, 3=DONE. Báo tiếp theo.
4. Không tự ý reset khi chưa được yêu cầu (destructive).

$ARGUMENTS
