---
name: tdd
description: >-
  Test-Driven Development — write failing test first, implement to pass, refactor. Red-Green-Refactor cycle.
metadata:
  provider: devin
  source: .devin/skills/tdd.md
---

# tdd (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/tdd.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
