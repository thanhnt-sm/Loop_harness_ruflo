---
name: hlk-loop
description: >-
  HLK Loop Runner — vòng lặp tự học theo pipeline HLK. Tính wave song song từ
  đồ thị phụ thuộc, spawn session agent độc lập cho mỗi bước, thu hoạch
  learnings vào HLK/reports/learnings.md. Dùng khi cần chạy/hỏi trạng thái/
  reset pipeline HLK loop.
triggers:
  - "hlk-loop"
  - "hlk loop"
  - "chạy loop hlk"
  - "hlk pipeline"
  - "self-learn loop"
  - "hlk-loop status"
  - "hlk-loop reset"
keywords:
  - hlk
  - loop
  - pipeline
  - self-learn
  - wave
  - checkpoint
---

# Skill: hlk-loop

## Khi nào dùng

Kích hoạt khi người dùng muốn:

- Chạy pipeline HLK loop (vòng lặp tự học)
- Xem trạng thái checkpoint hiện tại
- Reset checkpoint để chạy lại từ đầu
- Dry-run xem kế hoạch wave không chạy thật

## Script

| Lệnh | Mục đích |
|------|----------|
| `node HLK/loop/hlk-loop.mjs` | Chạy 1 iteration (1 lượt các wave còn thiếu) |
| `node HLK/loop/hlk-loop.mjs --dry-run` | Chỉ in kế hoạch wave, không chạy |
| `node HLK/loop/hlk-loop.mjs --status` | Xem trạng thái checkpoint |
| `node HLK/loop/hlk-loop.mjs --reset` | Xóa checkpoint, bắt đầu lại |

## Exit codes

| Code | Ý nghĩa |
|------|---------|
| 0 | CONTINUE — còn bước chưa xong, gọi lại để tiếp |
| 1 | ERROR |
| 3 | DONE — toàn bộ pipeline hoàn thành |

## Pipeline (HLK/loop/hlk-loop.config.json)

| Step | Name | Depends on | Writes code |
|------|------|------------|-------------|
| 01 | codebase_analysis | — | không |
| 05 | data_leak_hardening_guide | — | không |
| 02 | redteam_security | 01 | không |
| 06 | harness_deepdive_hardening | 01, 02 | không |
| 03 | solution_architect | 01, 02 | không |
| 07 | ruflo_hardening_implementation | 01, 05, 06 | có (serial_only) |

## Cách dùng

```bash
# Xem trạng thái
node HLK/loop/hlk-loop.mjs --status

# Chạy 1 iteration
node HLK/loop/hlk-loop.mjs

# Dry-run xem kế hoạch
node HLK/loop/hlk-loop.mjs --dry-run

# Reset checkpoint
node HLK/loop/hlk-loop.mjs --reset
```

## Cross-platform

Script Node.js (`.mjs`) — chạy trên Windows + macOS + Linux.
Yêu cầu: Node.js 18+ và `npx claude-flow` (cho `mode=command`).

## Output artifacts

- `HLK/logs/loop-state.json` — checkpoint state
- `HLK/reports/learnings.md` — sổ tích lũy tri thức
- `HLK/reports/0X_*.md` — báo cáo từng bước


## Nightly skill_bench (Phase 7 wire)

Tu dong chay `skill_bench.py` moi dem de benchmark pass-rate cua tat ca skills.

```bash
# Wire vao cron (Linux/macOS) hoac Task Scheduler (Windows)
# Moi ngay 2:00 AM
0 2 * * * cd /path/to/repo && py .devin/scripts/skill_bench.py .devin/skills docs/reports/skill_bench_$(date +%Y-%m-%d).md --schedule-cron
```

Behavior:
- `--schedule-cron` flag: skip neu da chay trong ngay (dua tren `.devin/state/skill_bench_last_run`)
- State file chua date hom nay -> exit 0, khong chay lai
- State file la date hom qua hoac khong ton tai -> chay + update state

Output: `docs/reports/skill_bench_<date>.md` voi pass-rate, avg confidence, scenarios count cho moi skill.
