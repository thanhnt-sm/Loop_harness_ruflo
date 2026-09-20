---
name: comment_checker
description: >-
  Use after any code edit that touches comments, or before declaring a code task complete. Detects AI-slop comments — filler, over-explanation, restating the obvious, hedge words — and flags them for removal. Code should read like a senior engineer wrote it.
metadata:
  provider: devin
  source: .devin/skills/comment_checker.md
---

# comment_checker (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/comment_checker.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
