# harness-upgrade — Detail: UPGRADE TEMPLATE LIBRARY (Phase 3)

**Áp dụng từng upgrade nhỏ nhất, verify sau mỗi cái. KHÔNG bulk-merge.**

## Safe zones
- ✅ `src/`, `.devin/skills/`, `.devin/agents/`, `.devin/canon/`, `AGENTS.md`, `.devin/scripts/`
- ❌ `HLK/`, security policies, `.env` — KHÔNG đụng (trừ khi task chính là HLK nâng cấp được chỉ định rõ).

## Token-efficiency templates (U-H1..U-H12)
**U-H1 — Nén canon bằng Caveman** (khi canon dài + cấu trúc rõ): rút prose → bullet action; cắt redundancy;
giữ mọi RED LINE + semantic. Verify: đọc lại canon cũ→mới, không mất instruction.

**U-H2 — Deterministic gate thay LLM judgment**: thêm sensor/script check thay "hãy kiểm tra kỹ".
Verify: script pass/fail deterministic.

**U-H3 — Lazy-load canon**: file dài → tách load-on-demand khỏi always-on. Verify: `wc -c` payload boot giảm; không tham chiếu file bị xóa.

**U-H4 — Slop removal**: xóa filler phrase, prose thừa. Verify: grep slop giảm; không mất instruction.

**U-H5 — Memory reuse**: trỏ về aide-memory/loop-memory thay vì ghi context lại. Verify: path memory tồn tại.

**U-H6 — Tool slimdown** *(Vercel cắt 80% tool)*: tool hiếm/trùng/ít giá trị → gỡ hoặc lazy-load. Verify: registry giảm; model vẫn xong task.

**U-H7 — Progressive / 2-phase skill loading** *(Glean -45%, OpenDev)*: skill → metadata index always-on; full body load khi gọi. Verify: boot payload giảm; skill vẫn load được.

**U-H8 — Context-sensitive conditional composition** *(OpenDev)*: instruction → section có `condition` + `priority`; chỉ inject section hợp lệ. Verify: context giảm khi điều kiện sai; không mất section cần thiết.

**U-H9 — Compaction protocol** *(Anthropic/Glean)*: giữ load-bearing state (intent, decisions, failed approaches, next steps); offload raw → filesystem. Verify: context_projection giảm; resume đúng.

**U-H10 — Token-efficient output format**: internal pipeline dùng YAML/TSV thay JSON; CoD cho reasoning. Verify: token/output giảm; parser đọc được.

**U-H11 — Prompt caching friendly**: prefix ổn định (system+skill) → cache hit. Verify: cache hit tăng.

**U-H12 — Model routing**: task đơn giản → glm/kimi (free); phức → lightning. Verify: cost giảm, quality không giảm.

## Compensation templates (U-H13..U-H16)
**U-H13 — Self-consistency voting layer** *(Wang 2022 +5-15%)*: task discrete answer quan trọng → N≥10 chains (T≈0.5-0.7), majority vote. Verify: accuracy tăng.

**U-H14 — Ranked/self-certainty voting** *(RankedVotingSC 2505.10772, tốt 3B-8B)*: model yếu xếp hạng nhiều candidate; ranked vote. Verify: thắng best-of-N, không cần reward model.

**U-H15 — Adversarial review gate** *(adversarial-consensus, fable-judge)*: flow Critical → persona độc lập review + fable done-gate. Verify: catch sai tăng; không phụ thuộc 1 model tự đánh giá mình.

**U-H16 — Verifier/grader injection** *(claim-grader, llm_as_judge)*: verifier đánh giá output thay producer tự nhận xét. Verify: grade khách quan; phát hiện regression tự động.

## Sau mỗi upgrade
1. Chạy `harness-sensor` (code mode) — `.devin/skills/harness-sensor.md`.
2. Chạy test nếu có: `pytest` (theo `pytest.ini` / `pyproject.toml`).
3. Nếu skill file mới sửa → verify cú pháp frontmatter + nội dung actionable.