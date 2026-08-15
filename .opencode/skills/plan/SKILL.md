---
name: plan
description: >-
  Plan Phase — Tự động orchestrate qua plan_orchestrator.py. Phân tích → Thiết kế → SDD Approval → Plan → Quality Check → Plan Approval. Human approval gate bắt buộc.
metadata:
  provider: devin
  source: .devin/skills/plan/SKILL.md
---

# plan (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/plan/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
