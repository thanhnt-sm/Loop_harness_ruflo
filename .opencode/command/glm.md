---
description: Executor GLM-5.2 — free tier, high reasoning. Dùng active model làm lean planner/reviewer, GLM-5.2 execute. Chỉ dùng sau khi plan approved. Gọi: /glm <task>
agent: build
---

Bạn đang chạy skill `glm`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/glm/SKILL.md` (source of truth).
2. Chỉ thực thi task khi đã có approved plan (M/L/XL) hoặc S-tier sửa trực tiếp.
3. Dùng executor GLM-5.2 (subagent `glm-executor`, free tier) để implement theo plan.
4. Tuân guardrails: smallest coherent diff, chạy test/typecheck, không destructive, không đụng HLK/.env.
5. Báo kết quả ngắn gọn: what changed | what verified | what risk.

$ARGUMENTS
