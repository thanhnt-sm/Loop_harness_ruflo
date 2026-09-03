Bạn đang chạy skill `hlk-status` (HLK diagnostic + integrity check) qua cmdc.

1. Chạy self-test:
   ```bash
   node HLK/bin/hlk-status.mjs --self-test
   ```
2. Chạy integrity check:
   ```bash
   node HLK/wrappers/hlk-verify-integrity.js
   ```
3. Báo cáo kết quả gọn:
   - `version` + `hlk_enabled` từ `HLK/config/hlk.config.json`.
   - Tổng số feature bật/tắt (`features.*`).
   - Số `redact_patterns` đang active.
   - Tổng số file thiếu (nếu có).
   - Sanitizer smoke test pass/fail.
4. Nếu có lỗi → ghi vào `HLK/logs/status-<DATE>.log` + khuyến nghị fix.

Lưu ý: KHÔNG tự sửa HLK. Nếu cần fix, dispatch `/hlk-integrity-check <file>` hoặc
escalate user.

Action: $ARGUMENTS
