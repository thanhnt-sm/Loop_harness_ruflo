# Prompt chuyển giao — Xử lý findings từ Comprehensive Quality Audit

> Sử dụng prompt này ở session mới để tiếp tục fix các vấn đề audit.

---

## Context

Bạn đang tiếp tục từ báo cáo audit toàn diện của repo `Loop_harness_ruflo`.

- **Audit report:** `docs/reports/COMPREHENSIVE_QUALITY_AUDIT_2026-08-11.md`
- **Implementation plan:** `docs/plans/comprehensive-quality-audit-plan/IMPLEMENTATION_PLAN.md`
- **SDD:** `docs/plans/comprehensive-quality-audit-plan/SOLUTION_DESIGN.md`

---

## Mission

Thực hiện remediation (khắc phục) cho toàn bộ findings trong audit report theo thứ tự ưu tiên:
1. **P0 (Critical)** trước
2. **P1 (High)** tiếp theo
3. **P2 (Medium)** nếu còn budget/time

---

## Danh sách findings cần xử lý

### P0 — Critical (7)

| ID | Track | Finding | Evidence chính | Hành động mong muốn |
|---|---|---|---|---|
| K-01 | Khuym | Thiếu toàn bộ `.codex/` dù onboarding báo complete | `.khuym/onboarding.json:19-28`; `.codex/` missing | Xác định cách khôi phục `.codex/` scripts hoặc cập nhật onboarding state; tạo script thay thế nếu cần |
| C-01 | Code | Thiếu `tests/test_spc_monitor.py` | `.devin/scripts/spc_monitor.py` (352 dòng) | Viết tests đầy đủ cho 6 metrics và 5 Western Electric rules |
| C-02 | Code | Thiếu `tests/test_state_router.py` | `.devin/scripts/state_router.py` (355 dòng) | Viết tests cho conditional edges, state transitions, error handling |
| S-01 | Security | `schema_gate.py` fail-open khi exception | `.devin/hooks/schema_gate.py:522-525` | Đổi mặc định thành fail-closed (block) khi exception |
| S-03 | Security | SSRF bypass qua IP encoding | `.devin/hooks/pre_tool_use.py:267-318` | Thêm decode decimal/hex/octal trước khi check `ipaddress.ip_address` |
| A-01 | Adversarial-consensus | Mâu thuẫn max rounds (3 vs 7) | `.devin/skills/adversarial-consensus/SKILL.md:38,147,249` | Đồng nhất thành 7 rounds với convergence check |
| T-01 | Token | `AGENTS.md` 186KB (46.5K tokens) waste | `.devin/AGENTS.md`; `REDTEAM_REPORT.md:93-148` | Truncate `AGENTS.md` xuống ~5KB; tách full canon sang `AGENTS_full.md`; load canon on-demand |

### P1 — High (8)

| ID | Track | Finding | Evidence chính | Hành động mong muốn |
|---|---|---|---|---|
| K-02 | Khuym | Onboarding state "complete" nhưng thiếu file | `.khuym/onboarding.json:6` | Sửa state hoặc tài liệu để đồng nhất với thực tế |
| C-03 | Code | 42 lần `except Exception` quá rộng | `.devin/scripts/*` nhiều file | Refactor sang exception cụ thể hoặc `sys.exit` trong security gates |
| S-02 | Security | 5 gate trong `pre_tool_use.py` dùng `pass` khi exception | `.devin/hooks/pre_tool_use.py:420-422,465-467,510-512,540-542,614-616` | Thay `pass` bằng block hoặc log severity cao |
| S-04 | Security | `config.json` deny list thiếu destructive patterns | `.devin/config.json:56-79` | Bổ sung `mkfs.*`, `fdisk`, `parted`, `lvremove`, `vgremove`, `cryptsetup` |
| A-02 | Adversarial-consensus | Thiếu logic aggregation/deduplication | `.devin/skills/adversarial-consensus/SKILL.md:136-141` | Thiết kế/implement `consensus_aggregator.py` |
| A-03 | Adversarial-consensus | Dynamic scenarios trùng persona cố định | `.devin/scripts/plan_fsm/missions.py:144-225` | Thêm deduplication hoặc exclude logic |
| T-02 | Token | BOOT sequence ~158KB (10× over target) | `REDTEAM_REPORT.md` | Lazy-load steps 9-16 theo `BOOT_PROTOCOL.md` |
| T-03 | Token | Model tier escalation không có cost cap | `.devin/agents/model_tiers.md` | Thêm cost cap cho escalation path |
| G-02 | Git | HLK git tools thiếu audit tracked artifacts | `HLK/git-tools/lib/hlk-git-lib.mjs:135-162` | Thêm `auditTrackedArtifacts()` và tích hợp `hlk-git-doctor.mjs` |

### P2 — Medium (4)

| ID | Track | Finding | Evidence chính | Hành động mong muốn |
|---|---|---|---|---|
| K-03 | Khuym | state.json idle | `.khuym/state.json:4-6` | Xác nhận expected state; cập nhật nếu cần |
| C-04 | Code | `.gitignore` duplicate `.env` | `.gitignore:61-63,167-169,193` | Cleanup duplicate và thống nhất template policy |
| C-05 | Code | BRAINSTORM edge case thiếu test | `state_machine.py:51-64`; `test_plan_fsm.py:334-342` | Thêm test cho brainstorm_results rỗng/malformed |
| G-01 | Git | `__pycache__` patterns trùng lặp | `.gitignore:90,251-252,263` | Giữ pattern tổng quát, xóa redundant |
| G-03 | Git | `worktree.py` thiếu health check | `.devin/scripts/worktree.py:180-219` | Thêm gọi `hlk-git-doctor` trước khi tạo worktree |

---

## Constraints (KHÔNG VI PHẠM)

- Không chỉnh sửa `AGENTS.md`, `HLK/` (trừ `HLK/git-tools/`), `.env`, security policies, canon, hoặc critical files nếu chưa có plan approved.
- Không `rm -rf`, force-push, drop table, payment, hoặc destructive operation mà không xác nhận.
- Mọi thay đổi code phải có test tương ứng hoặc giải trình rõ nếu không thể.
- Chạy `pytest` hoặc test liên quan sau mỗi thay đổi; không để test bị hỏng.
- Commit từng logical change riêng biệt; push chỉ khi được yêu cầu.

---

## Acceptance criteria

- [ ] Tất cả P0 được fix hoặc có lý do rõ ràng tại sao không fix.
- [ ] Tất cả P1 được fix hoặc được chuyển thành P0/P2 với giải trình.
- [ ] Có test mới cho `spc_monitor.py` và `state_router.py`.
- [ ] Security hooks không còn fail-open mặc định.
- [ ] `AGENTS.md` được truncate + lazy-load canon.
- [ ] `pytests` pass (hoặc giải thích nếu có test fail pre-existing).
- [ ] Cập nhật `docs/reports/COMPREHENSIVE_QUALITY_AUDIT_2026-08-11.md` hoặc tạo `FIX_STATUS_2026-08-XX.md` theo dõi tiến độ.

---

## Suggested slash skill

```
/full-power "Fix all P0/P1 findings from docs/reports/COMPREHENSIVE_QUALITY_AUDIT_2026-08-11.md in Loop_harness_ruflo"
```

Hoặc nếu muốn bắt đầu nhanh:

```
/lightning "Fix schema_gate.py fail-open and pre_tool_use.py SSRF bypass per audit report"
```
