Bạn đang chạy skill `plan` qua cmdc. Thực thi:

1. Đọc `.devin/skills/plan/SKILL.md` (source of truth, Plan-only phase).
2. Phân tích task `$ARGUMENTS`, classify tier:
   - S-tier → gợi ý sửa trực tiếp.
   - M/L/XL → chạy `python .devin/scripts/plan_orchestrator.py --init --task "$ARGUMENTS"` để mở Plan phase.
3. Tuân theo orchestrator (BRAINSTORM → SCOUTs → ARCHITECT → adversarial → SDD approval → GAP_SCAN → QC → PLAN_ENHANCE → plan approval gate).
4. Không apply code trong plan mode. Không đụng `HLK/`, `.env`.

Task: $ARGUMENTS
