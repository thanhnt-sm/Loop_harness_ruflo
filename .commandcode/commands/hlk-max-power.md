Bạn đang chạy skill `hlk-max-power` (MAX POWER: cập nhật + verify + status toàn diện) qua cmdc.

1. Kiểm tra hiện trạng:
   ```bash
   node HLK/bin/hlk-status.mjs --self-test
   node HLK/wrappers/hlk-verify-integrity.js
   ```
2. Cập nhật (nếu user chấp thuận):
   ```bash
   node HLK/bin/hlk-update.mjs --yes
   ```
3. Sau update → chạy lại integrity + status.
4. Nếu user chỉ định `--verify` → skip update, chỉ chạy status + integrity.
5. Nếu user chỉ định `--doctor` → chạy thêm `hlk-git-doctor.mjs`.

Hard guardrails:

- KHÔNG sửa `HLK/config/hlk.config.json` trừ khi user yêu cầu rõ.
- KHÔNG đụng `HLK/config/secrets.*`.
- KHÔNG force-push.
- Báo cáo: `version | status | integrity | doctor | next`.

Action: $ARGUMENTS
