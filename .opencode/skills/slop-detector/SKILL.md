---
name: slop-detector
description: >-
  Use after generating user-facing prose, docs, commit messages, naming, or code. Detects AI-generated filler, generic abstractions, and meaningless identifiers.
metadata:
  provider: devin
  source: .devin/skills/slop-detector.md
---

# slop-detector (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/slop-detector.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
