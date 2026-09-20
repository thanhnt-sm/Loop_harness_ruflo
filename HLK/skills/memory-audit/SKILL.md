---
name: memory-audit
description: >-
  Audit memory quality — check for stale entries, duplicates, contradictions, low-confidence memories.
metadata:
  provider: devin
  source: .devin/skills/memory-audit.md
---

# memory-audit (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/memory-audit.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
