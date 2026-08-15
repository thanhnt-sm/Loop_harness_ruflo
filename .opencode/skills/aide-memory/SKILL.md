---
name: aide-memory
description: >-
  >- How aide-memory works in this project — persistent cross-session memory. Consult this when an aide-memory hook fires (a PreToolUse "call aide_recall" nudge, the Stop checkpoint, or correction detection), or before recalling or storing project knowledge. Covers when to call aide_recall / aide_remember / aide_search, the memory layers (preferences, technical, area_context, guidelines), and how to format a memory.
metadata:
  provider: devin
  source: .devin/skills/aide-memory/SKILL.md
---

# aide-memory (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/aide-memory/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
