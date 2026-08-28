---
description: Plan Phase — Tự động orchestrate qua plan_orchestrator.py. Phân tích → Thiết kế → SDD Approval → Plan → Quality Check → Plan Approval. Human approval gate bắt buộc. Gọi: /plan <task>
agent: build
---

Bạn đang chạy skill `plan`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/plan/SKILL.md` (source of truth).
2. Mở Plan phase: `python .devin/scripts/plan_orchestrator.py --init --task "$ARGUMENTS"`.
3. Tuần theo orchestrator FSM (BRAINSTORM → SDD → SDD approval → GAP_SCAN → 10-D QC → PLAN_ENHANCE → plan approval gate), báo results qua `--step` cho đến DONE.
4. Mọi M/L/XL task BẮT BUỘC có approved plan trước khi act. S-tier sửa trực tiếp.
5. Không đụng HLK/, .env, security policies.

$ARGUMENTS
