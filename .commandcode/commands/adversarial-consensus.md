Bạn đang chạy skill `adversarial-consensus` (3-persona adversarial review) qua cmdc.

1. Đọc `.devin/skills/adversarial-consensus/SKILL.md` (source of truth, protocol).
2. Sử dụng 3 agents personas song song: `persona-architect` + `persona-saboteur` + `persona-security-auditor` (hoặc `persona-code-reviewer`).
3. Aggregate findings theo severity (Critical/High/Medium/Low). Tier 1 = Critical, fix ngay trong session.
4. Output: attack report + recommendation + re-attack evidence.

Artifact cần review: $ARGUMENTS
