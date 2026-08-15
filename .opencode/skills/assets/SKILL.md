---
name: assets
description: >-
  Internal asset store for slop patterns and vault templates. Not directly invoked by users.
metadata:
  provider: devin
  source: .devin/skills/assets/SKILL.md
---

# assets (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/assets/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
