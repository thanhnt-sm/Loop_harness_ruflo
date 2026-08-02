# 🛡️ Cẩm Nang Cấu Hình "Khóa Chặt" Ruflo Chống Rò Rỉ Dữ Liệu Tuyệt Đối

Vì bạn thích trường phái Meta-Harness của `ruflo` nhưng muốn soi xét và làm chủ 100% dữ liệu, đây là quy trình 3 bước buộc phải làm để biến nó thành một "hộp đen" nội bộ, không thể đẩy một byte dữ liệu nào ra ngoài:

---

## Bước 1: Vô hiệu hóa và Làm sạch biến môi trường (Hard Hardening)

Khi khởi tạo dự án bằng `npx ruflo@latest init wizard`, hệ thống sẽ tạo ra file `.env` và `settings.json`. Bạn cần mở ra và rà soát, đảm bảo các biến sau được thiết lập cấu hình như sau:

```bash
# Tắt tuyệt đối các cổng kết nối SaaS bên thứ ba
LANGSMITH_TRACING=false
LANGFUSE_TRACING=false

# Ép OpenTelemetry CHỈ được ghi file cục bộ (File Exporter), KHÔNG gửi qua HTTP/gRPC
OTEL_TRACES_EXPORTER=file
OTEL_METRICS_EXPORTER=file
OTEL_LOGS_EXPORTER=file

# KHÓA CHẶT "cửa sau" log chi tiết mã nguồn của Tool
OTEL_LOG_TOOL_DETAILS=0
```

> **Lưu ý**: Hãy thận trọng khi sử dụng mã.

---

## Bước 2: Cấu hình config.toml ép OpenTelemetry ghi log Offline

Bạn cần cấu hình cho lõi Ruflo chỉ được phép xuất dữ liệu logging ra thư mục local của máy thông qua cấu hình tệp tin tĩnh:

```toml
[observability]
enabled = true
backend = "file"
log_level = "info"
output_dir = "./.ruflo/logs" # Dữ liệu nằm chết tại đây

[observability.privacy]
strip_source_code = true      # Cưỡng bức xóa bỏ nội dung code thô trong các nhãn Span Tracing
hash_repository_urls = true   # Băm mã hóa URL của repo
```

> **Lưu ý**: Hãy thận trọng khi sử dụng mã.

---

## Bước 3: Tận dụng ruflo-aidefence để lọc sạch Prompt rời máy

Trước khi Prompt chứa code của bạn bị gửi lên các AI Cloud như Claude hay OpenAI, hãy vào thư mục `plugins/ruflo-aidefence/`, bật cấu hình nghiêm ngặt nhất cho bộ lọc dữ liệu nhạy cảm (PII Pipeline):

```json
{
  "pii_scanner": {
    "enabled": true,
    "policy": "REDACT", 
    "types": ["API_KEY", "PRIVATE_KEY", "DATABASE_URL", "PASSWORD", "SOURCE_ALGORITHM"]
  }
}
```

> **Lưu ý**: Hãy thận trọng khi sử dụng mã.

---

## Kết quả đạt được

Cơ chế này đảm bảo: Ngay cả khi AI Cloud bị hack hoặc lưu lại lịch sử chat, các tri thức cốt lõi như thuật toán độc quyền hay mật mã hệ thống của bạn đã bị biến đổi thành ký tự ẩn danh `[REDACTED]` từ trước khi rời khỏi máy tính của bạn.
