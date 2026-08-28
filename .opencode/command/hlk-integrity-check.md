---
description: Kiểm tra tính toàn vẹn của HLK layer sau khi merge upstream hoặc pull update. Phát hiện mất PreToolUse hook, MCP wrapper, .gitignore rules, file nhạy cảm bị track. Gọi: /hlk-integrity-check
agent: build
---

Bạn đang chạy skill `hlk-integrity-check`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/hlk-integrity-check/SKILL.md` (source of truth).
2. Phát hiện mất: PreToolUse hook, MCP wrapper, .gitignore rules, file nhạy cảm bị track.
3. Báo cáo trạng thái tính toàn vẹn của HLK layer; không tự ý sửa ngầm.
