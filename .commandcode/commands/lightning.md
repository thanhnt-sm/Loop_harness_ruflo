Bạn đang chạy executor `lightning` (SWE-1.7 Lightning, 1000 tok/s, paid) qua cmdc.

1. Đọc `.devin/skills/lightning/SKILL.md` (source of truth, lightning-executor role).
2. Sử dụng agent `executor-lightning` để thực thi. Nếu task quá nhỏ (S-tier), consider dùng `executor-glm` hoặc `executor-kimi` (free) thay thế.
3. Constraints: no destructive op, không đụng `HLK/`, `.env`. Stay inside workspace.
4. Báo cáo: changed/verified/risks.

Task: $ARGUMENTS
