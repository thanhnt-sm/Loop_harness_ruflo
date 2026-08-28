---
description: Bộ git tools an toàn cho workspace Ruflo — doctor kiểm tra repo, commit chặn secrets, push không force, safe-sync một lệnh. Gọi: /hlk-git-tools <thao tác>
agent: build
---

Bạn đang chạy skill `hlk-git-tools`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/hlk-git-tools/SKILL.md` (source of truth; cũng có ở HLK/skills).
2. Doctor: `node HLK/git-tools/hlk-git-doctor.mjs`
3. Commit an toàn (chặn secrets): `node HLK/git-tools/hlk-git-commit.mjs <message>`
4. Push không force: `node HLK/git-tools/hlk-git-push.mjs`
5. Safe-sync một lệnh (doctor→commit→push): `node HLK/git-tools/hlk-git-safe-sync.mjs`
6. Không bao giờ `git push --force`/`-f`. Chỉ commit khi user yêu cầu.

$ARGUMENTS
