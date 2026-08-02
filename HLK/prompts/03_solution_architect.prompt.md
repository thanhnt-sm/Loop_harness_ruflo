# PROMPT 03: SOLUTION ARCHITECT & TOGGLEABLE HLK IMPLEMENTATION

## Context
Bạn là Lead Solution Architect chịu trách nhiệm xây dựng Lớp vá & Tùy biến HLK (Harness & Logic Knowledge Layer) cho Ruflo.

## Objective
Lập giải pháp kỹ thuật chi tiết để triển khai HLK theo các tiêu chí:
1. **Non-invasive Architecture**: Không sửa trực tiếp core code của Ruflo trừ khi bắt buộc. Ưu tiên wrapper/adapter pattern.
2. **Toggle Mechanism**:
   - Khi `hlk_enabled = true` trong `HLK/config/hlk.config.json`, nạp toàn bộ lớp vá bảo mật, bọc các API call & sanitizers.
   - Khi `hlk_enabled = false`, trả lại nguyên bản Ruflo 100%.
3. **Custom Logic Integration**: Hướng dẫn cách chèn business logic riêng của người dùng vào HLK mà không chạm vào Ruflo code.

## Output Required
- Bảng thiết kế chi tiết luồng xử lý (Sequence Diagram).
- Mã nguồn mẫu cho `hlk-loader.js` (hoặc wrapper script) thực thi cơ chế bật/tắt.
- Quy trình kiểm thử (Verification Tests) để xác nhận công tắc Bật/Tắt hoạt động hoàn hảo.
