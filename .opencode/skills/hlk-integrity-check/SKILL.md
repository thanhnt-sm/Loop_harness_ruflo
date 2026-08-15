---
name: hlk-integrity-check
description: >-
  Kiểm tra tính toàn vẹn của HLK layer sau khi merge upstream hoặc pull update. Phát hiện mất PreToolUse hook, MCP wrapper, .gitignore rules, file nhạy cảm bị track. Dùng khi nghi ngờ upstream đã ghi đè cấu hình HLK, hoặc sau mỗi git pull/merge.
metadata:
  provider: devin
  source: .devin/skills/hlk-integrity-check/SKILL.md
---

# hlk-integrity-check (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/hlk-integrity-check/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
