---
name: claim-grader
description: >-
  Grade claims as [fact], [inference], or [unverified]. Prevent hallucinated assertions.
metadata:
  provider: devin
  source: .devin/skills/claim-grader.md
---

# claim-grader (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/claim-grader.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
