---
name: loop-memory
description: >-
  Sync loop state across sessions — regenerate registry, archive completed loops, restore in-progress loops.
metadata:
  provider: devin
  source: .devin/skills/loop-memory.md
---

# loop-memory (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/loop-memory.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
