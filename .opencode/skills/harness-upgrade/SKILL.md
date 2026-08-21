---
name: harness-upgrade
description: >-
  >- Skill rà soát + nâng cấp + tự-tăng-cường workspace này thành best harness cho AI model kém thông minh + context nhỏ: tối đa token-efficiency, tối thiểu always-on context, chất lượng output cao nhất (mục tiêu: đạt tầm Opus/GPT-5/Fable). Launcher nhỏ gọn cho model yếu — chi tiết load-on-demand theo file detail. Output: docs/reports/HARNESS_UPGRADE_REPORT.md + applied upgrades.
metadata:
  provider: devin
  source: .devin/skills/harness-upgrade/SKILL.md
---

# harness-upgrade (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/harness-upgrade/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
