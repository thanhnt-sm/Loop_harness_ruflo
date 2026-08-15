---
name: hlk-git-tools
description: >-
  Bộ git tools an toàn cho workspace Ruflo — doctor kiểm tra repo, commit chặn secrets, push không force, safe-sync một lệnh. Dùng khi cần commit/push an toàn, kiểm tra sức khỏe repo, hoặc sync đầy đủ doctor→commit→push.
metadata:
  provider: devin
  source: .devin/skills/hlk-git-tools/SKILL.md
---

# hlk-git-tools (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/hlk-git-tools/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
