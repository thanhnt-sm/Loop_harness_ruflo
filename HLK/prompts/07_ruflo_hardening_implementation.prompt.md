# 🛡️ Hướng Dẫn Kỹ Thuật Chi Tiết: Hardening Ruflo (Tắt Telemetry, Config AIDefence & Bảo Vệ AgentDB)

## Step 1: Tắt hoàn toàn Telemetry và chỉ lưu log ra file

- **Chỉnh sửa biến môi trường/config của Ruflo:** Trong file cấu hình (ví dụ `~/.ruflo/config.toml` hoặc file `.env` của dự án), thiết lập tắt mọi xuất dữ liệu tới Collector bên ngoài. Ví dụ:
  ```bash
  # Tắt Claude/Ruflo Telemetry
  export CLAUDE_CODE_ENABLE_TELEMETRY=0
  export DISABLE_TELEMETRY=1
  # Cấu hình OpenTelemetry: chỉ xuất logs/metrics ra file cục bộ
  export OTEL_TRACES_EXPORTER=none
  export OTEL_METRICS_EXPORTER=file
  export OTEL_LOGS_EXPORTER=file
  # Chỉ định đường dẫn lưu file logs
  export OTEL_EXPORTER_METRICS_PATH="./.ruflo/logs/metrics.jsonl"
  export OTEL_EXPORTER_LOGS_PATH="./.ruflo/logs/telemetry.jsonl"
  ```
  Các biến OTEL trên khởi tạo OpenTelemetry exporter thành **file**, đảm bảo không gửi gRPC/HTTP ra ngoài (thay vì giá trị mặc định `console` hay `otlp`). Đồng thời, bật cờ loại bỏ mã nguồn khỏi log (`strip_source_code = true`) để tránh ghi đè nội dung code nhạy cảm vào logs:
  ```toml
  [security]
  strip_source_code = true
  ```
  Cuối cùng, khởi tạo thư mục `./.ruflo/logs/` và cấu hình `File Exporter` để ghi log JSON tại đó. Điều này đảm bảo toàn bộ log chỉ được ghi nội bộ, ví dụ: chỉ sử dụng `FileExporter` của OTel với đường dẫn trên.

---

## Step 2: Cấu hình `ruflo-aidefence` JSON để tự động **redact** thông tin nhạy cảm

- **Tạo file JSON config cho plugin aidefence:** Ví dụ `aidefence-config.json` với các mẫu (pattern) cần xóa/mã hóa. Ví dụ:
  ```json
  {
    "mode": "redact",
    "patterns": {
      "proprietary_code": ["(?i)\\bSECRET_ALGO_CODE_[A-Za-z0-9]+\\b"],
      "api_keys": ["(?i)\\b(api_key|secret|token)=[^\\s]+\\b"],
      "db_connection": ["(?i)(mongodb\\+srv://[^\\s]+)", "(?i)(postgresql://[^\\s]+)"]
    },
    "replacement": "[REDACTED]"
  }
  ```
  Trong đó:
  - Mục `"patterns"` liệt kê các chuỗi regex của **các thuật toán độc quyền**, **API keys** và **chuỗi kết nối DB** cần xóa/mã hóa.
  - `"mode": "redact"` chỉ thị plugin chuyển chuỗi nhạy cảm thành `[REDACTED]` hoặc ký tự thay thế. 
- **Kích hoạt plugin:** Đảm bảo plugin `ruflo-aidefence` được bật. Cấu hình JSON trên cho phép **lược bỏ** (redact) tự động các thông tin nhạy cảm trước khi bất cứ dữ liệu nào được gửi lên Cloud. Ví dụ, nếu một đoạn log chứa `api_key=ABC123`, nó sẽ tự động thành `[REDACTED]`.

---

## Step 3: Phân tích `agentdb.rvf` (AgentDB) và bảo vệ dữ liệu

- **Cấu trúc lưu trữ:** AgentDB của Ruflo sử dụng file `.rvf` để chứa vector memory (HNSW index). Mọi văn bản (ví dụ code) được nhúng thành mảng số thực (vector) và lưu trong cấu trúc HNSW nội bộ. File `agentdb.rvf` là *có cấu trúc nhị phân đặc biệt* chứa cả vectors và index HNSW của chúng (không phải SQLite thuần túy). Khi viết mã nguồn vào bộ nhớ, Ruflo xây dựng embedding (chẳng hạn 384 chiều) và cập nhật HNSW tree trong file `.rvf`.
- **Bảo vệ file `agentdb.rvf`:** 
  - **Giữ cục bộ tuyệt đối:** Không lưu `agentdb.rvf` lên Git hay dịch vụ cloud nào. Thêm vào `.gitignore` dự án (ví dụ `/.ruflo/agentdb.rvf`) và không cài plugin đồng bộ (như `ruflo-federation`) nếu không cần thiết.
  - **Chặn chia sẻ ngầm:** Đảm bảo không gọi lệnh federated hoặc setup `federation`—nếu dùng plugin “federation”, Ruflo có cơ chế chia sẻ (zero-trust) nhưng với dữ liệu PII đã bị gắn cờ. Nếu không dùng, tắt plugin này để tránh truyền file bộ nhớ sang nodes khác.
  - **Quyền truy cập hạn chế:** Đảm bảo file chỉ người dùng hiện tại có quyền đọc/ghi, và không có tiến trình nào khác tự động đồng bộ. Có thể đặt file tại `./.ruflo/` với permission chặt (e.g. `chmod 600`).
- **Kiểm toán:** Dùng công cụ như `lsof` hoặc `auditd` để theo dõi nếu bất cứ tiến trình nào mở file này. Do .rvf là định dạng nhị phân, không thể đọc thông qua text; nếu muốn xem nội dung, chỉ có thể dùng thư viện AgentDB (JS). Phần cơ chế HNSW đã được công nhận là *nhanh và phù hợp cho vector memory*. Việc giữ .rvf offline đảm bảo **an toàn tri thức** (nội dung code lẫn vector) không bị lọt ra ngoài.

---

## Nguồn tham khảo & Đánh giá an toàn

Các plugin của Ruflo như AIDefence (phát hiện PII, prompt-injection) và AgentDB (vector memory với HNSW) được thiết kế cho bảo mật và hiệu suất cao. Các biến môi trường OpenTelemetry trong Ruflo/Claude (ví dụ `CLAUDE_CODE_ENABLE_TELEMETRY`, `OTEL_LOGS_EXPORTER`) được dùng để điều khiển việc ghi log. Trên cơ sở đó, cấu hình nêu trên đảm bảo **hardening** triệt để: chỉ log file nội bộ, mã hóa/chặn dữ liệu nhạy cảm, và giữ file bộ nhớ agent luôn ở local.
