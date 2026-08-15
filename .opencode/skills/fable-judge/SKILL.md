---
name: fable-judge
description: >-
  Adversarial verification of finished work. Fires on every 'done' declaration — re-runs claimed verifications, diffs what actually changed, detects weakened tests and false completion, sweeps verbatim gate lines (INTENT/AUTH/TWINS/PENDING). Use after any agent or worker claims work is complete: 'fable-judge', 'judge this work', 'verify what it did', 'did that actually work?'.
metadata:
  provider: devin
  source: .devin/skills/fable-judge.md
---

# fable-judge (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/fable-judge.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
