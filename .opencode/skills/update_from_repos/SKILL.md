---
name: update_from_repos
description: >-
  >- Update workspace an toàn theo các repo được liệt kê trong REPOS.md. Phát hiện upstream mới, đánh giá rủi ro, cherry-pick / copy từng phần, bảo vệ HLK và local upgrades (U01–U70), chạy verify, tạo báo cáo MICROSCOPIC_REVIEW_REPORT.md.
metadata:
  provider: devin
  source: .devin/skills/update_from_repos/SKILL.md
---

# update_from_repos (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/update_from_repos/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
