---
name: gap-scan
description: >-
  Scan for gaps between current state and goal. Find missing pieces, untested paths, incomplete coverage.
metadata:
  provider: devin
  source: .devin/skills/gap-scan.md
---

# gap-scan (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/gap-scan.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
