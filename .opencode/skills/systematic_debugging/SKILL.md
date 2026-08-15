---
name: systematic_debugging
description: >-
  Systematic debugging methodology — reproduce, isolate, hypothesize, test, fix, verify. Prevent shotgunning.
metadata:
  provider: devin
  source: .devin/skills/systematic_debugging.md
---

# systematic_debugging (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/systematic_debugging.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
