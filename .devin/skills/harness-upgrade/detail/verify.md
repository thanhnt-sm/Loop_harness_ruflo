# harness-upgrade — Detail: VERIFY, REGRESSION, REPORT (Phase 4-5)

## VERIFY (Phase 4)

### Full verify
```bash
python .devin/scripts/hook_integrity.py --verify 2>/dev/null || echo "skip"
python .devin/scripts/context_projection.py --report 2>/dev/null || echo "skip"
pytest -q 2>/dev/null || echo "no tests"
```
So sánh trước/sau: `wc -c` canon, boot payload, always-on context.

### Regression check
- Không upgrade nào phá RED LINE / CORE_CANON.
- Không file nào mất instruction so với trước.
- Không destructive op.

### Token-delta regression (bắt buộc mọi upgrade)
```bash
wc -c AGENTS.md .devin/canon/*.md 2>/dev/null   # boot/input
wc -c .devin/skills/*/SKILL.md 2>/dev/null       # skill bodies (giảm nếu U-H7)
```
- Input giảm + quality không giảm = **thành công**.
- Input không giảm + quality tăng = chấp nhận (ghi lý do).
- Cả hai không đổi + không tăng quality = **hoàn tác** upgrade.

### Cập nhật tracker + báo cáo
- Ghi vào `.devin/upgrade/UPGRADE_TRACKER.json` / `_V2.json` hoặc tạo `HARNESS_UPGRADE_REPORT.md`.
- `HARNESS_UPGRADE_REPORT.md`: baseline metrics, upgrades applied (trước→sau, **token delta riêng input/output**),
  verification results, next candidates, nguồn tham khảo. Ghi rõ **loại token savings**: input / output / cost / round-trip.

## REPORT (Phase 5)

Báo cáo ngắn gọn cho user:
```
- Baseline → After (tokens, boot_payload, always_on)
- Upgrades applied: N (liệt kê ngắn)
- Compensation layers added: C1/C2/C5... (chỉ số sức mạnh harness)
- Verification: PASS/FAIL (what ran)
- Quality verdict: "model yếu + harness này đạt tầm Opus/Fable?" (có/không + lý do)
- Next candidates (chưa làm, có score)
- Path: HARNESS_UPGRADE_REPORT.md
```

## Guardrails đầy đủ
1. Smallest coherent diff — không scope creep.
2. Preserve pre-existing user changes.
3. No destructive ops (chặn bởi hooks).
4. Token savings KHÔNG làm giảm correctness/safety.
5. Verify sau mỗi upgrade, không gom rồi mới verify.
6. HLK/ & .env không đụng (trừ khi chỉ định rõ).
7. `--check` / `--check-only` → chỉ đo + lập plan, KHÔNG edit.
8. `--apply` → chỉ Phase 3-5 (dùng plan trước). Mặc định = full: dry-run trước rồi apply.
9. Upgrade M+ → bắt buộc `/full-power` / `/plan`. S-tier sửa trực tiếp.
10. Không cập nhật AGENTS.md skill table trừ khi thật cần (tránh token mỗi boot).
11. Chỉ tự viết file mới khi thật cần (skill, script) — không tạo docs thừa.
12. Max power ≠ reckless — parallelism nhưng mỗi write vẫn verify; không bulk-merge.
13. Dry-run xong trước apply — không apply khi chưa có plan được review.
14. `--red-team` cấm quick-fix — 5 Whys + re-attack + DoD 4 tick trước khi chuyển hạng mục.
15. Token-efficiency dẫn dắt quyết định — mọi candidate phải có token-delta đo được.
16. Lock-in dependency cũng là nợ — không dùng nhưng không gỡ = token sink; quyết định rõ.
17. Weak-model mode luôn được ưu tiên — model yếu/context nhỏ tuân detail/adaptation.md.
18. Self-audit bắt buộc — artifact phải pass "model yếu đọc có fail không".
19. Mọi output quan trọng phải có deterministic gate — cấm model yếu tự verify chính nó.
20. Harness là thước đo sức mạnh, không phải model — bổ sung compensation, không đổ lỗi model.