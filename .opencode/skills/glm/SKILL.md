---
name: glm
description: >-
  Use the active model as a lean planner and reviewer while GLM-5.2 executes concrete software-engineering work. Free tier (200K context).
metadata:
  provider: devin
  source: .devin/skills/glm/SKILL.md
---

# glm (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/glm/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
