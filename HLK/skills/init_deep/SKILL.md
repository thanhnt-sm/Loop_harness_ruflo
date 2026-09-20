---
name: init_deep
description: >-
  Deep initialization for large repos — scan structure, build index, identify conventions, create registry.
metadata:
  provider: devin
  source: .devin/skills/init_deep.md
---

# init_deep (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/init_deep.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
