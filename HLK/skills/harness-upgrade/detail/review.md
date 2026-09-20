# harness-upgrade — Detail: REVIEW (Phase 1 — đo lường, không đụng code)

Mở phiên ghi chú. Chạy full review, ghi vào `docs/reports/HARNESS_UPGRADE_REPORT.md`.

## 1. Inventory
```bash
ls -la AGENTS.md .devin/AGENTS.md 2>/dev/null
ls .devin/skills/ ; ls .devin/canon/ ; ls .devin/scripts/ ; ls .devin/hooks/ ; ls .devin/agents/
```

## 2. Đo token footprint (bắt buộc)
```bash
.venv/bin/python .devin/scripts/context_projection.py --report 2>/dev/null || echo "no context_projection"
wc -c AGENTS.md .devin/canon/CORE_CANON.md .devin/canon/REDLINES.md 2>/dev/null
```
Ghi baseline: `always_on_tokens`, `boot_payload_kb`, `per_task_tokens` nếu đo được.

## 3. Quét slop / noise
```bash
grep -rniE "importantly|essentially|it is worth noting|in order to|please note|additionally," AGENTS.md .devin/canon/*.md 2>/dev/null
```

## 4. Đánh giá 9 chiều
- **Context**: gì nằm always-on không đáng? Có **context rot** (mọi frontier model degrade khi context dài — Chroma/Morph 2025)?
- **Tool registry**: bao nhiêu tool/schema inject upfront? Vercel cắt 80% tool → reliability cao, latency 3.5x thấp. Có tool idle?
- **Canon**: mâu thuẫn / trùng lặp / quá dài? Có context-sensitive load không?
- **Skills**: skill nào dài mà hiếm dùng (token sink)? Thiếu actionable steps? Có 2-phase skill loading không?
- **Scripts**: script nào auto-chạy tốn token? Script nào chưa deterministic gate?
- **Hooks**: hook nào chặn đúng, hook nào gây friction?
- **Instruction density**: bao nhiêu instruction/system prompt? (LLM tuân theo ít hơn khi tăng số lượng — arXiv 2507.11538)
- **Compensation coverage**: flow nào đang tin model yếu tự verify (thiếu C1/C2/C5)? Flow Critical nào chưa adversarial review? (detail/compensation.md)
- **Repos**: technique hiện đại nào trong REPOS.md chưa distill?

## 5. Context-rot & signal-to-noise scan (bắt buộc)
```bash
grep -rniE "git workflow|subagent|orchestration|deployment" .devin/canon/CORE_CANON.md 2>/dev/null
.venv/bin/python -c "import json;d=json.load(open('.devin/tool_registry.json'));print('tools:',len(d.get('tools',d)) if isinstance(d,(dict,list)) else 'n/a')" 2>/dev/null || echo "no tool_registry"
grep -rniE "no destructive|no secrets|verify" AGENTS.md CLAUDE.md .devin/AGENTS.md 2>/dev/null | wc -l
```
> **stale info trong repo không phân biệt được với latest truth** (OpenAI harness engineering).
> Context dài = tự gây degradation. Ưu tiên compaction + offload ra filesystem.

## 6. Priority scoring (v2 — đo theo token, không theo effort)
```
Priority = (quality_gain 0-5) × (token_saved_est 0-5) × (determinism_gain 0-5)
           ─────────────────────────────────────────────────────────
                              (risk 1-5) × (effort 1-5)
```
Ưu tiên mục giảm **input context** (bottleneck model yếu): tool idle → lazy-load; skill hiếm → metadata-only;
instruction stale/trùng → gộp/cắt. Chỉ chọn candidate có lợi ích ròng rõ ràng, smallest coherent diff.