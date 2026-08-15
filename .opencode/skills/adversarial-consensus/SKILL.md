---
name: adversarial-consensus
description: >-
  Adversarial Consensus Protocol (C3) — 6+ persona review đối kháng: Saboteur + New Hire + Security Auditor + Architect + Code Reviewer + Git Workflow Master + dynamic scenarios. Issue do 2+ reviewer tìm thấy = tăng severity. Max 7 vòng (convergence). Gọi: /adversarial-consensus <artifact_path hoặc mô tả>
metadata:
  provider: devin
  source: .devin/skills/adversarial-consensus/SKILL.md
---

# adversarial-consensus (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/adversarial-consensus/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
