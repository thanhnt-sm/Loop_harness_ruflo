Bạn đang chạy skill `hlk-sanitize` (sanitize file/text theo HLK redact patterns) qua cmdc.

1. Load `HLK/config/hlk.config.json` → lấy `security_rules.redact_patterns` + `redact_replacement`.
2. Nếu `$ARGUMENTS` là file path:
   - Đọc file → apply từng pattern bằng `node -e` (regex replace) hoặc load
     `HLK/security/sanitizer.js` (ESM import).
   - In ra stdout (KHÔNG ghi đè file trừ khi user dùng `--in-place`).
3. Nếu `$ARGUMENTS` là text inline → echo text + apply pattern, in kết quả.
4. Dùng `redact_replacement` mặc định = `"[REDACTED]"` trừ khi user override.
5. Báo cáo: số match theo từng pattern + nội dung đã redact.

Lưu ý: KHÔNG sửa `HLK/config/secrets.*`. KHÔNG in secret đã match ra
trước khi redact.

Ví dụ:
```
/hlk-sanitize ./src/auth.ts
/hlk-sanitize "sk-abc1234567890abcdef1234567890abcdef"
/hlk-sanitize --in-place ./src/leaky-config.json
```

Action: $ARGUMENTS
