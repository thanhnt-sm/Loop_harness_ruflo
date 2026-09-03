Bạn đang chạy skill `hlk-integrity-check` (verify HLK layer integrity) qua cmdc.

1. Đọc `.devin/skills/hlk-integrity-check/SKILL.md` (source of truth, integrity protocol).
2. Chạy `node HLK/wrappers/hlk-verify-integrity.js` để kiểm tra.
3. Output PASS/FAIL + remediation steps. KHÔNG tự sửa HLK trừ khi task chính là nâng cấp HLK được chỉ định rõ.
4. Nếu FAIL → log vào `docs/reports/HLK_INTEGRITY_<DATE>.md` + escalate.

Action: $ARGUMENTS
