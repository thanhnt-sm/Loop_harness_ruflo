---
description: >-
  Rà soát + nâng cấp workspace thành best harness cho AI model yếu + context nhỏ
  (token-efficiency, giảm always-on context, red-team v5.0). Chạy full chain.
  Alias tham số: --check | --apply | --no-red-team | --no-apply | --red-team | <focus-area> | <repo-id>
agent: build
---

Bạn đang chạy skill `harness-upgrade`. Thực thi theo đúng launcher:

1. Đọc `/workspace/.devin/skills/harness-upgrade/SKILL.md` (đây là source of truth, chứa full chain).
2. Nếu `$ARGUMENTS` rỗng → MẶC ĐỊNH FULL CHAIN (không cần tham số): PREFLIGHT → REVIEW → LEARN →
   UPGRADE → VERIFY → RED-TEAM v2.0 + V5 (load-on-demand `detail/redteam-v5.md` + `detail/v5-redteam-prompt.md`)
   → COMPENSATION → REPORT → APPLY.
3. Nếu `$ARGUMENTS` có flag/focus (ví dụ: `--check`, `--red-team`, `skills`, `canon`, `<repo-id>`) →
   áp dụng đúng mode theo SKILL.md (mode map + routing), đặc biệt:
   - `--check`/`--no-apply` → AUDIT_ONLY, không patch.
   - `--no-red-team` → bỏ redteam + v5.
4. Tuân guardrails trong SKILL.md + detail/adaptation.md (model yếu / context < 50K → chunk, 1 upgrade 1 lần).
5. Chạy đúng quy trình Plan: mọi upgrade M+ đi qua `/full-power`; S-tier (1 file, <5 dòng) sửa trực tiếp.
   Nếu chưa có approved plan cho task M+, gọi `plan_orchestrator.py --init` trước khi sửa.
6. Không đụng `HLK/`, `.env`, security policies. Không destructive op.
7. Ghi kết quả vào `HARNESS_UPGRADE_REPORT.md` + `harness-upgrade-log.md`, báo cáo ngắn: baseline→after,
   upgrades applied, verification, quality verdict, next candidates.

$ARGUMENTS
