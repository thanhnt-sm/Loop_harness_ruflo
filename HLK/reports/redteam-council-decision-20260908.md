# HỘI ĐỒNG RED-TEAM: Xác định và sửa lỗi Loop_harness_ruflo

## 1. Thành phần hội đồng
- **Kiến trúc/Bảo mật**: Chịu trách nhiệm đánh giá rủi ro hệ thống, lỗ hổng bảo mật và sự toàn vẹn của HLK/AHD.
- **Kiểm thử/Độ tin cậy**: Tập trung vào tự phục hồi, xử lý lỗi (circuit breaker, timeout) và độ bền của loop.
- **Researcher Online**: Tìm kiếm các giải pháp, best practices (allowlist web) để đối chiếu.

## 2. Các Finding được đề xuất

### Finding 1 (Kiến trúc/Bảo mật): Lỗi xử lý context oversized trong loop_memory_sync.py
- **Giả thuyết**: Khi session state phình to (vd: log tích luỹ quá lớn), việc đọc/ghi liên tục `.devin/session_state/<sid>.json` không có cơ chế chặn cứng sẽ làm quá tải context, hoặc gây memory leak trong các tool call liên tiếp. Mặc dù có `context_compactor`, nhưng nếu base JSON bị "nhiễm" slop, loop_memory_sync có thể truyền chuỗi độc hại/thừa vào `loop_state.md`.
- **Bằng chứng (Dự kiến)**: Thiếu giới hạn size nghiêm ngặt trước khi parse JSON trong các hook.

### Finding 2 (Kiểm thử/Độ tin cậy): Lỗi timeout không được cô lập (Self-healing gap)
- **Giả thuyết**: Trong `plan_orchestrator.py` hoặc các call tới `command_code_client.py` (HLK), nếu subprocess bị treo (vd: node không load được module như trong `khuym_status.mjs`), cơ chế timeout có thể không kill hẳn process, dẫn đến session bị "zombie" nhưng status không được update là `crashed`.
- **Bằng chứng**: Chạy `node .codex/khuym_status.mjs` thất bại với exit code nhưng nếu process hang (trong trường hợp khác), loop sẽ chờ mãi hoặc retry vô hạn.

### Finding 3 (Researcher Online): Độ tin cậy của circuit breaker trong subprocess
- **Nghiên cứu (docs.python.org)**: Theo tài liệu Python `subprocess.run(timeout=X)`, nếu dùng shell=True (mặc dù nên tránh), process con có thể không bị kill hoàn toàn khi timeout.
- **Áp dụng**: HLK có `command_code_client.py` dùng circuit breaker nhưng cần verify `timeout` có đi kèm `kill/terminate` đúng chuẩn (độ tin cậy coding, context nhỏ).

## 3. Phản biện và Chọn lựa

- **Phản biện Finding 1**: Sửa phần parse JSON cần can thiệp sâu vào `session_manager.py` và `loop_memory_sync.py`, độ rủi ro (side-effect) cao cho một thay đổi "nhỏ".
- **Phản biện Finding 2 & 3**: Sửa lỗi subprocess/timeout trong `HLK/chain/command_code_client.py` (hoặc `_platform_utils.py` nơi chứa `run_python`) là một thay đổi nhỏ, độc lập, tăng độ tin cậy coding rõ rệt và giúp hệ thống "tự phục hồi" tốt hơn khi đối mặt với các tool call bị treo.

## 4. Quyết định (Decision)
**Phương án được chọn**: Bổ sung/gia cố cơ chế timeout (kill process group / force terminate) trong tiện ích gọi subprocess của HLK (cụ thể là `HLK/chain/_platform_utils.py` hoặc `command_code_client.py`). Đây là thay đổi có *context nhỏ*, giúp *tự phục hồi* khỏi zombie process, tăng *độ tin cậy coding*.

**Nguyên nhân gốc**: Subprocess không phải lúc nào cũng exit sạch khi hit timeout, cần clear cleanup.

**Tiêu chí xác minh**:
1. Đọc code `HLK/chain/_platform_utils.py` và `HLK/chain/command_code_client.py`.
2. Xác định điểm gọi subprocess.
3. Patch an toàn.
4. Chạy test `tests/test_platform_utils.py` hoặc các test liên quan để đảm bảo không phá vỡ tính năng.