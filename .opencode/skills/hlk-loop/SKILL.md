---
name: hlk-loop
description: >-
  HLK Loop Runner — vòng lặp tự học theo pipeline HLK (wave song song từ đồ thị phụ thuộc,
  checkpoint, học hỏi vào HLK/reports/learnings.md). Dùng khi cần chạy/xem trạng thái/dry-run/
  reset pipeline HLK loop. Nguồn canonical: .devin/skills/hlk-loop/SKILL.md.
---

# hlk-loop (opencode wrapper)

Load và thực thi theo canonical skill tại **`.devin/skills/hlk-loop/SKILL.md`**.

## Tóm tắt nhanh

| Lệnh | Mục đích |
|------|----------|
| `node HLK/loop/hlk-loop.mjs` | Chạy 1 iteration (các wave còn thiếu) |
| `node HLK/loop/hlk-loop.mjs --dry-run` | Chỉ in kế hoạch wave |
| `node HLK/loop/hlk-loop.mjs --status` | Xem trạng thái checkpoint |
| `node HLK/loop/hlk-loop.mjs --reset` | Reset checkpoint (destructive — cần confirm) |

Exit codes: `0` = CONTINUE, `1` = ERROR, `3` = DONE.

Yêu cầu: Node.js 18+ và `npx claude-flow`. Script cross-platform (`.mjs`).
