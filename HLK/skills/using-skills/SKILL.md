---
name: using-skills
description: >-
  Use before responding to any user request. Enforces skill-first methodology: check if a skill matches the request, invoke it before acting. Prevents ad-hoc work that bypasses the harness.
metadata:
  provider: devin
  source: .devin/skills/using-skills.md
---

# using-skills (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/using-skills.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
