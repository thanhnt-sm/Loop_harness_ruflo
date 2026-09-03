Bạn đang chạy executor `glm` (GLM-5.2, free tier) qua cmdc.

1. Đọc `.devin/skills/glm/SKILL.md` (source of truth, glm-executor role).
2. Sử dụng agent `executor-glm` để thực thi. Phù hợp: simple_edit, read, grep, glob, ls, small code generation.
3. Constraints: no destructive op, không đụng `HLK/`, `.env`. Stay inside workspace.
4. Báo cáo: changed/verified/risks.

Task: $ARGUMENTS
