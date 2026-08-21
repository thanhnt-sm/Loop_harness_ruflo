# 01 — Định hướng Workspace

> Workspace này là **Agent Harness Deploy (AHD) loop harness** — hệ thống rule + skills + agents + hooks + scripts
> tự triển khai cho Devin CLI. Cline là một agent khách: **dùng chung canon, không phá cấu trúc harness.**

## 3 lớp chính (xem chi tiết trong `00-source-map.md`)

1. **`.devin/`** — AHD engine (Python): canon (15 protocol files), skills (14 packages + flat), agents
   (COMMANDER + workers + personas + 3 executors), 17 hooks, 64+ scripts, config.
2. **`.opencode/`** — wrapper layer: opencode tái sử dụng skills/agents/hooks của harness **mà không đụng**
   `.devin/`. Hook bridge tắt mặc định.
3. **`HLK/`** — security layer (Node): sanitizer, vault, git-tools. **KHÔNG đụng** (chỉ đọc khi cần).

Kèm theo: `tests/` (pytest, coverage gate 80%), `docs/`, `tools/` (PowerShell/Python utilities),
`.github/workflows/` (CI/CD), `specs/` (TLA+), `sbom/`.

## Hệ thống phân cấp nguồn chân lý

|| Chủ đề | Nguồn |
||--------|-------|
|| Universal rules | `.devin/canon/CORE_CANON.md` (tool-agnostic — sửa canon, không sửa entry files) |
|| AHD entry | `.devin/AGENTS.md` (summary). `AGENTS_full.md` = 186KB — **KHÔNG đọc** trừ khi cần |
|| Devin CLI config | `.devin/config.json` (permissions L0-L4, hooks, model routing) |
|| Skill index | `.devin/skills/skill_index.json` (2KB, nạp boot) |
|| Cline entry (file này) | `AGENTS.md`, `CLAUDE.md`, `.clinerules/` — tự nạp đầu session |
|| opencode | `.opencode/README.md` + `opencode.json` |
|| HLK | `HLK/README.md` |
|| Repos tham khảo | `REPOS.md` |

## Nguyên lý cốt lõi của harness

- **Caveman comms** — nói ngắn gọn, bỏ filler, tiết kiệm token (~65%).
- **Commander + workers** — main quyết định/dispatch; workers scan/edit.
- **Maker ≠ checker** — producer không tự verify output của mình.
- **Memory trên disk, không trong context** — state nằm ở `.devin/loop_state.md` + runtime dirs.
- **Evidence-graded** — claim phải gắn nhãn `[fact]` / `[inference]` / `[unverified]`.
- **Progressive disclosure** — chỉ nạp đúng file đúng lúc (xem `03-load-on-demand.md`).
- **Loops converge** — mỗi iteration ghi state, check stop condition, dừng khi đạt.
