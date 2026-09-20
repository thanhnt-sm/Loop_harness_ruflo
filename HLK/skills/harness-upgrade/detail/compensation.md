# harness-upgrade — Detail: FRONTIER-QUALITY COMPENSATION + TOKEN-EFFICIENCY PLAYBOOK

> **Nguyên lý nền (Binding Constraint Thesis, arXiv 2605.23950)**: trong agent long-horizon,
> **harness quyết định hiệu năng hơn model.** Bằng chứng: giữ model cố định, chỉ đổi harness →
> +9.5pp (SWE-bench Pro, Opus 4.5); giữ harness cố định, đổi 6 frontier model → chỉ ±4.9pp.
> Nghĩa là: **model yếu + harness mạnh có thể đánh bại model mạnh + harness yếu.**
> → Mục tiêu KHÔNG phải "mua model đắt", mà **xây harness bù toàn bộ thiếu hụt của model yếu**
> để output đạt tầm Opus/GPT-5/Fable.

## Phần 1 — Compensation Ladder (bù thiếu hụt model yếu, tăng dần sức mạnh)

| # | Kỹ thuật | Bù cái gì | Bằng chứng | Chi phí |
|---|----------|-----------|-----------|---------|
| C1 | **Deterministic verify** (test, schema, script) | Model yếu hay declare-done-sai | Anthropic "verify completion with tests" | thấp |
| C2 | **Self-consistency / majority vote** | Model yếu hay slip từng bước | Wang 2022: +5-15% over single CoT; rẻ nhất | 30-50x tokens |
| C3 | **Ranked voting / self-certainty** | Model yếu trong multi-choice/code | RankedVotingSC 2505.10772: thắng best-of-N, tốt cho 3B-8B | trung bình |
| C4 | **Best-of-N + reward/verifier** | Model yếu output open-ended | Cần reward model | cao |
| C5 | **Adversarial multi-persona review** | Model yếu thiếu self-critique | C3 pattern, fable-judge, adversarial-consensus | trung bình |
| C6 | **Sub-agent isolation** | Model yếu lạc hướng sau nhiều turn | OpenDev, Glean | trung bình |
| C7 | **Progressive disclosure (2-phase load)** | Model yếu lost-in-middle | OpenDev | thấp |

### Khi nào dùng cái nào
- **Nhiệm vụ xác định được đáp án** (test pass/fail, số, boolean) → **C2/C3 voting** (rẻ, hiệu quả nhất).
- **Nhiệm vụ open-ended** (viết code, docs) → **C1 + C5** (deterministic gate + adversarial review),
  hoặc **C4** nếu có reward model.
- **Task dài nhiều bước** → **C6** (subagent) để tránh model yếu mất lái.
- **Always**: C1 (đừng bao giờ tin model yếu tự nói "xong").

### Rule triển khai
1. Mỗi artifact/flow sinh ra phải có **ít nhất 1 deterministic gate** (C1) — cấm để model yếu tự verify.
2. Nếu task có discrete answer → áp dụng **C2/C3 voting** (N≥10, T≈0.5-0.7). *(self-consistency)*
3. Nếu task quan trọng (Critical) → **C5 adversarial review** với persona độc lập.
4. Ghi rõ trong report: kỹ thuật bù nào đã áp dụng cho từng flow. Đây là **chỉ số sức mạnh harness**.
5. **Thước đo thành công cuối**: "model yếu + harness này đạt quality tầm Opus/Fable không?" —
   nếu chưa, bổ sung compensation layer, KHÔNG đổ lỗi model.

### Self-check (mỗi phiên upgrade phải hỏi)
- Flow nào đang tin model yếu tự verify → cần C1/C2?
- Flow nào quan trọng nhưng chưa có adversarial review → cần C5?
- Task nào lặp lại sai do model yếu → cần C2 voting?
- Harness đã có ít nhất 1 deterministic gate trên mọi output quan trọng chưa?

---

## Phần 2 — TOKEN-EFFICIENCY PLAYBOOK (giảm token, ưu tiên mọi phiên)

### A. Giảm INPUT CONTEXT (bottleneck lớn nhất với model yếu + context nhỏ)
1. **Progressive skill loading** (U-H7) — metadata-only cho skill hiếm dùng. *(Glean -45% system prompt)*
2. **Tool slimdown** (U-H6) — bỏ/ẩn tool idle. *(Vercel 80% tool cắt → reliability cao, latency 3.5x giảm)*
3. **Context-sensitive composition** (U-H8) — chỉ inject section hợp lệ. *(OpenDev)*
4. **Context-rot cleanup** — xóa stale/trùng instruction. *(Morph: all 18 frontier models degrade theo context length)*
5. **Compaction** (U-H9) — giữ load-bearing state, offload raw → filesystem.

### B. Giảm OUTPUT TOKENS
6. **YAML/TSV thay JSON** cho internal pipeline (JSON ≈ 2x tokens).
7. **Chain of Draft (CoD)** — reasoning ~7.6% tokens, giữ accuracy.
8. **Report compact** — executor chỉ báo changed/verified/risks, không paste full file.

### C. Giảm CHI PHÍ (model routing + caching)
9. **Model routing** (U-H12) — task đơn giản → glm/kimi (free), phức → lightning/stronger.
10. **Prompt caching** (U-H11) — prefix ổn định → cache hit, cache-read ~0.

### D. Giảm LẶP LẠI (memory + verification)
11. **Memory reuse** (U-H5) — tránh rediscovery giữa session.
12. **Deterministic verify** (U-H2) — script check thay LLM re-read → ít token, ít sai.
13. **Eager-build + batch exec** (OpenDev) — gộp nhiều read/tool call 1 turn, giảm round-trip.

### Nguyên tắc vàng
- **Small signal set**: nhóm token tối thiểu đủ cao-signal (Anthropic effective context engineering).
- **Mỗi dòng = 1 hành động**: instruction không làm → cắt. Mỗi dòng prose thừa = token chết.
- **1 feature 1 lần** (OpenAI) — tránh one-shot problem, giảm rework (~59% token vào review/rework).
- Phân vân giảm token vs tăng quality → ưu tiên giảm input context (bottleneck model yếu).