---
name: ruflo-autopilot
description: "[DEPRECATED — use /lightning or /glm instead] Legacy Ruflo MCP-only orchestration. Kept for manual swarm/memory control. For execution tasks, prefer /lightning (SWE-1.7 Lightning, fast) or /glm (GLM-5.2, free tier) which use native Devin subagents."
triggers: []
---

# Ruflo Autopilot Skill [DEPRECATED]

> **Không tự kích hoạt.** Skill này đã tắt trigger `model` để tránh xung đột với `/lightning` và `/glm`.
> Chỉ dùng thủ công qua `/ruflo-autopilot` khi cần orchestration MCP trực tiếp (swarm, cost tracking, memory CRUD).
> Cho task coding thông thường, dùng `/lightning` (SWE-1.7 Lightning, nhanh) hoặc `/glm` (GLM-5.2, free) — native Devin, rẻ hơn.

## Khi nào dùng
Dùng skill này MỌI khi user yêu cầu:
- Viết code / tạo feature mới
- Viết test
- Review code
- Refactor
- Tạo documentation
- Fix bug
- Bất kỳ task coding nào

## Quy trình tự động

> **Lưu ý Devin CLI**: Trong Devin, MCP tools có namespace `mcp__claude-flow__<tool>`.
> Thay `memory_search` bằng `mcp__claude-flow__memory_search`, `swarm_init` bằng `mcp__claude-flow__swarm_init`, v.v.

1. **memory_search** — Tìm pattern tương tự:
   ```
   mcp__claude-flow__memory_search(query="<task keywords>", namespace="patterns")
   ```
   Nếu tìm thấy (score > 0.7), dùng pattern đó.

2. **swarm_init** — Khởi tạo swarm:
   ```
   swarm_init(topology="hierarchical-mesh", maxAgents=15)
   ```

3. **agent_spawn** — Spawn agents theo task:
   - coder (viết code)
   - tester (viết test)
   - reviewer (review)
   - architect (thiết kế)

4. **hooks_route** — Chọn model:
   ```
   hooks_route(task="<task description>")
   ```

5. **agent_execute** — Chạy task trên agent

6. **verify** — Kiểm tra chất lượng trước khi lưu pattern (BẮT BUỘC):
   - Chạy build: `npm run build` trong package bị thay đổi
   - Chạy test: `npm test` (hoặc vitest run cho file cụ thể)
   - Chạy typecheck: `npm run typecheck` (nếu package có script này)
   - Nếu CẢ BA pass → tiếp tục bước 7. Nếu FAIL → sửa lỗi rồi verify lại.
     Chỉ khi sửa không được mới skip bước 7 và báo cáo rõ lý do.
   - Mục đích: tránh lưu pattern lỗi vào memory (học sai từ lần sau).

7. **memory_store** — Lưu pattern (CHỈ khi verify pass):
   ```
   memory_store(key="<pattern-name>", value="<what worked>", namespace="patterns")
   ```

8. **swarm_status** — Báo cáo

## Lưu ý
- LUÔN gọi memory_search TRƯỚC khi bắt đầu
- LUÔN gọi memory_store SAU khi hoàn thành
- KHÔNG dừng sau swarm_init — tiếp tục spawn + execute ngay
- Agent spawn là record, KHÔNG phải agent chạy code — BẠN (Devin) chạy code
