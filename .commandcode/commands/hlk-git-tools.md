Bạn đang chạy skill `hlk-git-tools` (HLK git commit/push/doctor) qua cmdc.

1. Đọc `.devin/skills/hlk-git-tools/SKILL.md` (source of truth, HLK git workflow).
2. Có sẵn: `node HLK/wrappers/hlk-git.mjs <subcommand>` (commit, push, doctor, status).
3. Tuân thủ HLK guard: bắt buộc chạy `hlk-git doctor` trước mỗi commit/push.
4. Không force-push. Không ghi đè `HLK/config/secrets.*`. Không destructive.

Action: $ARGUMENTS
