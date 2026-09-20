---
name: auditor
description: >-
  Adversarial code review — find security holes, false assumptions, failure modes. Always-on red-team analysis.
metadata:
  provider: devin
  source: .devin/skills/auditor.md
---

# auditor (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/auditor.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
