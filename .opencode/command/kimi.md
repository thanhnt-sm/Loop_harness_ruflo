---
description: Executor Kimi K2.7 — free tier until 2026-07-05. Dùng active model làm lean planner/reviewer, Kimi K2.7 execute. Chỉ dùng sau khi plan approved. Gọi: /kimi <task>
agent: build
---

Bạn đang chạy skill `kimi`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/kimi/SKILL.md` (source of truth).
2. Chỉ thực thi task khi đã có approved plan (M/L/XL) hoặc S-tier sửa trực tiếp.
3. Dùng executor Kimi K2.7 (subagent `kimi-executor`, free tier) để implement theo plan.
4. Tuân guardrails: smallest coherent diff, chạy test/typecheck, không destructive, không đụng HLK/.env.
5. Báo kết quả ngắn gọn: what changed | what verified | what risk.

$ARGUMENTS
