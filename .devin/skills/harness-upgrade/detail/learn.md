# harness-upgrade — Detail: LEARN (Phase 2 — học từ REPOS.md + web)

## Bảng nguồn học hiện đại (2026, đã research)

| Nguồn | Kỹ thuật để distill |
|-------|---------------------|
| OpenAI Harness Engineering (2026-02) | Repo hygiene, golden principles, GC agents, work depth-first một feature/lần |
| Anthropic Long-Running Agents (2025-11) | Compaction giữ load-bearing state, offload raw output ra filesystem |
| Glean "Harness as context manager" (2026-04) | Giảm system prompt 45% bằng progressive skill loading; compaction; sub-agent isolation |
| Vercel "removed 80% of tools" (2026) | Tool slimdown → reliability +, latency 3.5x giảm |
| Augment "context is a junk drawer" / Morph context-rot (2025) | More context ≠ better; stale info degrade model |
| OpenDev arXiv 2603.05344 | Priority-ordered conditional composition, 2-phase skill load, eager-build, batch exec |
| Anthropic effective context engineering | Tìm smallest high-signal token set |
| Chain of Draft (CoD) | ~7.6% reasoning tokens, giữ accuracy CoT |
| JSON ≈ 2x YAML/TSV (tokenoptimize) | Dùng format ít token cho internal pipeline |
| WebFetch ~1.5KB vs Playwright MCP ~10-33KB | CLI/WebFetch 20x token-efficient hơn MCP |
| prompt caching | Giảm tới 90% input tokens (cache-read rẻ) |
| model routing | 60-95% savings theo task complexity |
| `repos.md` Caveman family | Token compression ~65% |
| `repos.md` obra/superpowers | Subagent TDD, systematic debugging |
| **Binding Constraint Thesis (arXiv 2605.23950)** | Harness quyết định hiệu năng hơn model — nền tảng compensation |
| **IFScale (arXiv 2507.11538)** | Model yếu exponential decay — nền tảng weak-model adaptation |
| **Liu et al. Lost-in-the-Middle (TACL 2024)** | Thông tin giữa context bị mất — nền tảng đặt rule ở đầu |

## Khi cần technique mới nhất ngoài REPOS.md
- Chạy `websearch` từ khóa hiện đại (VD: "harness engineering 2026", "context compression agents 2026",
  "small context agent workflow", "token efficient tool use", "weak model match frontier model").
- Chỉ adopt khi có **evidence** (eval công khai / paper / case study) + phù hợp tiêu chí tối ưu.
- **Ghi lại nguồn** vào `HARNESS_UPGRADE_REPORT.md` (chống link-rot, cập nhật REPOS.md nếu đáng dùng).
- So sánh ≥2-3 phương án, trả lời: **"Loại bỏ vấn đề tận gốc hay chỉ giảm triệu chứng?"** — loại cái chỉ giảm nhẹ.

## Kiểm tra upstream trước khi cherry-pick
```bash
.venv/bin/python .devin/scripts/check_updates.py --check 2>/dev/null || echo "skip check_updates"
```
Nếu repo trong REPOS.md có upstream mới → xử lý theo `.devin/skills/update_from_repos/`.