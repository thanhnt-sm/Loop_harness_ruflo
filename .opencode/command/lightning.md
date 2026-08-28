---
description: Executor SWE-1.7 Lightning — dùng active model làm lean planner/reviewer, SWE-1.7 Lightning execute. Chỉ dùng sau khi plan approved. Gọi: /lightning <task>
agent: build
---

Bạn đang chạy skill `lightning`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/lightning/SKILL.md` (source of truth).
2. Chỉ thực thi task khi đã có approved plan (M/L/XL) hoặc S-tier sửa trực tiếp.
3. Dùng executor SWE-1.7 Lightning (subagent `lightning-executor`) để implement theo plan.
4. Tuân guardrails: smallest coherent diff, chạy test/typecheck, không destructive, không đụng HLK/.env.
5. Báo kết quả ngắn gọn: what changed | what verified | what risk.

$ARGUMENTS
