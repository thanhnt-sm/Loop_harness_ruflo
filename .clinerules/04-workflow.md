# 04 — Workflow làm việc

> Quy trình chung cho MỌI task trong workspace. Khớp với văn hoá 3-Phase của harness
> (Plan → Approve → Execute), rút gọn cho môi trường Cline.

## 1. Phân loại tier

| Tier | Tiêu chí | Cách xử lý |
|------|----------|------------|
| Câu hỏi/giải thích | Yêu cầu thông tin | Trả lời trực tiếp, không edit |
| S | <5 dòng, 1 file, không cần verify | Sửa thẳng + báo cáo ngắn |
| M | 1 file, cần test/verify | Plan ngắn → thực thi → test |
| L/XL | Nhiều file, đụng harness | **Bắt buộc plan trước**, user approve, rồi thực thi theo plan |

- L/XL: hỏi user 2-4 câu (scope, acceptance criteria, constraints) trước khi viết plan
  (interview-mode — xem `CORE_CANON.md` §6).
- Khi đụng `.devin/scripts/plan_orchestrator.py` hoặc core harness: đọc
  `docs/PLAN_ORCHESTRATOR_GUIDE.md` trước.

## 2. Plan trước khi edit (M-tier+)

- Viết plan ngắn: goal → files sẽ sửa/tránh → acceptance criteria → risks.
- Trình plan, chờ user xác nhận **trước khi edit**. Không tự ý chạy cả chain
  `plan_orchestrator.py` trừ khi user yêu cầu (đó là cơ chế Devin CLI, không phải Cline).

## 3. Verify bắt buộc (maker ≠ checker)

- Sau khi sửa code: chạy test của module đó:
  `python3 -m pytest tests/test_<module>.py -q`
- Toàn bộ suite (coverage gate 80% trên `.devin/scripts` + hooks):
  `python3 -m pytest -q` — chạy khi thay đổi nhiều file.
- **Governance** (file rác / sai vị trí / plan↔act): `python3 tools/check_governance.py`
  — exit 0 là sạch; lỗi → sửa trước khi kết thúc. Canonical: `.devin/rules/WORKSPACE_GOVERNANCE.md`.
- Verify diff: nhỏ nhất, đúng scope, không sót file.

## 4. Git workflow

- Commit message tiếng Anh, format: `feat|fix|docs|refactor|test|chore(scope): mô tả ngắn`.
- Commit riêng từng logical change. Không force-push, không `reset --hard`,
  không `clean -fd` (chặn cứng bởi config).
- Trước khi commit: `git status` + `git diff --stat` để rà lại scope.

## 5. Sau khi thay đổi cấu trúc

1. `python3 tools/gen_source_map.py` — refresh `.clinerules/00-source-map.md`.
2. `pwsh tools/verify-workspace.ps1` (nếu pwsh có) — verify workspace integrity.
3. `pwsh tools/health-check.ps1` — kiểm tra sức khỏe nếu nghi ngờ hỏng state.

## 6. Report format (cuối task)

- **Đã làm gì** (what changed) + **key files** đụng tới.
- **Verification** đã chạy (test nào, kết quả).
- **Residual risks / blockers** còn lại + bước kế tiếp (nếu có).
- Trả lời tiếng Việt có dấu, ngắn gọn, lead with the answer.
