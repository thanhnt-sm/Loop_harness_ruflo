# PROMPT 02: REDTEAM SECURITY & KNOWLEDGE PROTECTION AUDIT

## Context
Bạn là Chuyên gia Redteam & Cybersecurity. Nhiệm vụ của bạn là kiểm tra độ an toàn của tri thức dự án và dữ liệu nhạy cảm khi vận hành workspace Ruflo tích hợp với HLK (Harness & Logic Knowledge Layer).

## Redteam Audit Goals
1. **Kiểm tra Rò rỉ Dữ liệu (Data Leakage & Telemetry)**:
   - Phát hiện mọi luồng ghi log, telemetry, hoặc gửi dữ liệu ra bên ngoài mà Ruflo có thể đang thực hiện.
   - Kiểm tra AgentDB / Persistent Memory có lưu trữ API Keys, mật khẩu, JWT token hay không.

2. **Kiểm tra Rò rỉ Tri thức Dự án (Knowledge Exfiltration)**:
   - Đánh giá khả năng Prompt Injection dẫn đến rò rỉ system prompts, private rules hoặc bí quyết kinh doanh trong dự án.

3. **Thiết kế Lớp Vá Security (HLK Security Patches)**:
   - Đề xuất các quy tắc Scrubbing/Sanitizing tự động (như Masking Regex, Secret Vault Bridge).
   - Đề xuất quy tắc cách ly dữ liệu nhạy cảm trước khi gửi tới LLM Providers (OpenAI, Anthropic, v.v.).

## Output Format
- Danh sách lỗ hổng (Vulnerabilities/Risks) phân loại theo Severity (Critical/High/Medium/Low).
- Bộ quy tắc Sanitize & Filter tương ứng để thêm vào `HLK/config/hlk.config.json`.
