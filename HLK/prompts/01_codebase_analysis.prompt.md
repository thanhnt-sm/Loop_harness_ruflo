# PROMPT 01: CODEBASE SCANNING & ARCHITECTURE MAPPING

## Context
Bạn là AI Systems & Software Architect. Bạn đang phân tích toàn bộ codebase của dự án Ruflo (harness & agentic framework tại `https://github.com/ruvnet/ruflo`).

## Task Instructions
1. **Quét toàn bộ cấu trúc codebase hiện tại**:
   - Phân tích các module core (`v3/`, `src/`, `services/`, `plugins/`, `bin/`).
   - Phân tích luồng dữ liệu (Dataflow) từ CLI / Agent Execution đến Memory/AgentDB và các API endpoints.
   - Nhận diện các entrypoints quan trọng và các vị trí có thể chèn **HLK Middleware** mà không can thiệp trực tiếp làm hỏng code gốc của ruflo.

2. **Quy hoạch & Đánh giá**:
   - Đánh giá khả năng mở rộng (Extensibility) của Ruflo.
   - Xuất ra sơ đồ kiến trúc danh sách các "Hook points" hoặc "Plugin Slots" khả thi mà HLK có thể bám vào.

3. **Output Format**:
   - Báo cáo phân tích cấu trúc dưới dạng Markdown kèm sơ đồ Mermaid.
