# PROMPT 06: DEEP-DIVE AI CODING AGENT HARNESS HARDENING & AGENTDB AUDIT

## Context
Tôi muốn tiếp tục một phiên phân tích chuyên sâu về AI Coding Agent Harness (Khung chuẩn AI tự động viết code) dựa trên toàn bộ ngữ cảnh kỹ thuật đã được đồng thuận từ phiên trước. Dưới đây là tóm tắt thiết lập hệ thống của tôi:

### 1. TIÊU CHÍ HỆ THỐNG
- **Mục tiêu**: Vận hành hệ thống AI tự động viết code dùng xen kẽ AI Cloud (Claude/OpenAI) và AI Local (Ollama/vLLM).
- **Yêu cầu Bảo mật**: Minh bạch mã nguồn 100% (White-box), KHÔNG dùng các repo dính file đóng gói ẩn (.exe) hoặc lớp runtime độc quyền (như EverOS). Bảo mật tuyệt đối tri thức mã nguồn độc quyền, chống rò rỉ dữ liệu khi Prompt rời máy lên Cloud.
- **Yêu cầu Kiểm toán**: Khóa chặt hoàn toàn các cơ chế Telemetry/Logs sâu ngầm (OpenTelemetry, Langfuse, LangSmith) hoặc bẫy Prompt Injection trong mô hình mô tả công cụ để giữ log nằm chết tại Local Disk.

### 2. REPOSITORY ĐƯỢC CHỌN LÀM LÕI CHÍNH: `thanhnt-sm/Loop_harness_ruflo` (Meta-Harness)
- **Lý do chọn**: Repo tự chứa, kiến trúc Plugin phân tách rõ ràng, có bộ lọc PII giúp ẩn danh hóa dữ liệu nhạy cảm trước khi gửi lên Cloud, và có tính năng tách thành bộ công cụ độc lập.

---

## Nhiệm Vụ (Task Instructions)

Hãy đóng vai trò là một **Chuyên gia Kỹ thuật Hệ thống kiêm Kiểm toán viên An toàn Thông tin (Security Auditor)**. Chúng ta sẽ bắt tay vào việc hiện thực hóa và cấu hình "Khóa chặt" (Hardening) hệ thống `thanhnt-sm/Loop_harness_ruflo` tại môi trường Local.

Vui lòng triển khai sâu các bước kỹ thuật sau:

- **Step 1**: Hướng dẫn rà soát mã nguồn file cấu hình (`config.toml`/`.env`) của Ruflo để cấu hình cứng vô hiệu hóa mọi cổng gRPC/HTTP Telemetry của OpenTelemetry, ép hệ thống chỉ xuất log dạng "File Exporter" cục bộ tại thư mục `./.ruflo/logs` và kích hoạt flag `strip_source_code = true`.
- **Step 2**: Cấu hình chi tiết file JSON của plugin `ruflo-aidefence` để thiết lập cơ chế tự động Redact (Xóa bỏ/Thay thế) các đoạn chuỗi chứa Thuật toán độc quyền, API Keys, và chuỗi kết nối DB.
- **Step 3**: Phân tích cấu trúc lưu trữ của cơ sở dữ liệu bộ nhớ cục bộ AgentDB (`agentdb.rvf`) dựa trên thuật toán HNSW của Ruflo để xem nó lưu trữ mã nguồn của tôi dưới dạng Vector ra sao trên đĩa cứng và cách đảm bảo file DB này không bị đồng bộ ngầm ra ngoài.

> **Response Requirements**: Trả lời bằng ngôn ngữ Tiếng Việt, ngắn gọn, scannable, tập trung vào code cấu hình và giải pháp kỹ thuật thực tế!
