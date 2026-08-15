---
name: lightning
description: >-
  Use the active model as a lean planner and reviewer while SWE-1.7 Lightning executes concrete software-engineering work.
metadata:
  provider: devin
  source: .devin/skills/lightning/SKILL.md
---

# lightning (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/lightning/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
