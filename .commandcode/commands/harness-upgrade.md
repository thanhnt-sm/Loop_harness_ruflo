Bạn đang chạy skill `harness-upgrade` (rà soát + nâng cấp workspace thành best harness) qua cmdc.

1. Đọc `.devin/skills/harness-upgrade/SKILL.md` (source of truth, full chain).
2. Mặc định FULL CHAIN: PREFLIGHT → REVIEW → LEARN → UPGRADE → VERIFY → RED-TEAM v2.0 + V5 → COMPENSATION → REPORT → APPLY.
3. Routing: `--check` / `--no-apply` → AUDIT_ONLY. `--red-team` → nhấn mạnh. `--no-red-team` → bỏ red-team.
4. V5 cần Runtime Manifest đầy đủ → thiếu → BLOCKED, chỉ static analysis.
5. Mọi upgrade M+ phải qua `/full-power` (Plan → Approve → Execute). S-tier sửa trực tiếp.
6. Không đụng `HLK/`, `.env`. Ghi kết quả vào `docs/reports/HARNESS_UPGRADE_REPORT.md` + `docs/reports/harness-upgrade-log.md`.

Arguments: $ARGUMENTS
