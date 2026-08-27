# LOOP EXHAUST REPORT — Research Build-Strategy for Multi-Provider Harness

> Báo cáo kết thúc chuỗi research loop — hướng build harness cạnh tranh Claude/Codex/GPT.
> Ngày: 2026-08-27 | Trạng thái: RESEARCH EXHAUSTED (Build-Strategy coverage complete) | Song ngữ EN + VI.

---

## 1. Tóm tắt (Executive Summary)

Chuỗi loop đã research **6 iteration** và tạo **6 file research mới** (bổ sung, không duplicate baseline), chuyển định hướng từ "research chung" sang **build-strategy**: cách build harness/framework cạnh tranh giá trị với Claude (Fable/Opus/Sonnet), Codex, GPT-5.6 (Sol), đa AI provider, agent kém thông minh + context nhỏ, phiên dài/phức tạp.

HLK-loop báo **DONE** (3/3 iterations, learnings tích lũy). `check_governance.py`: **0 errors**, 1 warning pre-existing (plan thiếu exec report).

---

## 2. Các iteration đã chạy

| Iter | Focus | File research tạo | Góc MỚI |
|------|-------|-------------------|---------|
| 0 (baseline, session trước) | Harness landscape / pain points / solutions | 3 files VI (root) + 3 files EN (en/) | Đã commit `9ce8489` |
| 2 | Harness engineering discipline, context rot, SWE-bench, MCP security | `TECH_OVERVIEW_2026.md` | Guides vs Sensors, Governance Decay/Constraint Pinning, SWE-bench near-saturation, MCP security crisis |
| 3 | Build orchestration đa agent | `BUILD_ORCHESTRATION_2026.md` | Decompose by context boundary, approve-intent-not-args, cheap classifier+premium planner, Z3 formal verify, Planner-Generator-Evaluator isolation |
| 3-4 | Build multi-provider gateway | `BUILD_MULTI_PROVIDER_2026.md` | LiteLLM+OpenRouter defense-in-depth, 6 routing strategies, cost-ladder, per-call-site budget, context-window fallback |
| 4 | Build small-context/weak-model | `BUILD_SMALL_CONTEXT_2026.md` | Externalization, Harness-1 state-externalizing (20B), 8 Pillars, W/S/C/I context, decision tree Skills/Subagent/Multi/Dynamic-Workflows |
| 4 | Build durable long-session | `BUILD_LONG_SESSION_2026.md` | Temporal/DBOS/Restate, workflow-activity split, idempotency, saga, signals, Continue-as-New |
| 4 | Build verification/compete | `BUILD_VERIFY_COMPETE_2026.md` | Eval as control plane, SWE-bench contamination collapse, 6-layer harness, trajectory eval, judge bias, per-line ablation, CI gates |

+ Cập nhật `RESEARCH_COVERAGE_LOG.md`: mark T4, T7-T11 `[covered]`; register 3 subagent reports (session trước) chống duplicate.

---

## 3. Key findings cho build harness cạnh tranh ⭐

### Cạnh tranh = evals, không phải model
- Eval là **control plane** — agents/scaffolds/model là disposable, eval hệ thống là durable selection layer. Anthropic ship 3 regressions 6 tuần, eval suite KHÔNG bắt được. [fact]
- SWE-bench Verified bị **contamination** (model reproduce gold patches) → OpenAI bỏ báo Verified; dùng SWE-bench Pro (~46%) + private versioned golden set. [fact]

### Đa provider (mục tiêu user)
- Build **LiteLLM-style core + OpenRouter upstream** (defense-in-depth): 1 OpenAI-compatible endpoint, 100+ providers, fallback chain, cooldown, context-window fallback, per-team budget. Cho phép Claude/Gemini/DeepSeek/Kimi/GLM/local vLLM. [fact]
- **cheap model cho classifier/router (~300 tok), premium cho planner/synthesis** → giảm token cost lớn. [fact]

### Agent kém thông minh + context nhỏ (mục tiêu user)
- **State-externalizing harness** (Harness-1 20B): model giữ semantic decisions, harness giữ mechanical bookkeeping. [fact]
- **Derived-state rendering** (evidence graph + BM25 top-K) thay raw tool outputs; **Write/Select/Compress/Isolate** (8 Pillars). [fact]
- **Auto WM budget từ context window** (8K→6K, 200K→159K) → adaptive khi swap model. [fact]

### Phiên dài/phức tạp (mục tiêu user)
- **Durable execution**: workflow (deterministic coordination) / activity (recorded side effects) split; idempotency keys; saga compensation; signals/queries cho durable HITL; Continue-as-New chống history phình. [fact]
- DBOS-style (library, Postgres) cho harness local; Temporal-style nếu cần cluster scale. [fact]

---

## 4. Anti-duplicate xác nhận

Mỗi file research mới đều:
1. Đọc `RESEARCH_COVERAGE_LOG.md` trước.
2. Chọn **góc MỚI** / topic chưa `[covered]`.
3. Cập nhật log sang `[covered]` + metadata (file, ngày, nguồn).

3 file subagent report cũ (`orchestration_patterns.md`, `planning_best_practices.md`, `qc_enforcement_mechanisms.md`) đã được **register trong log** để không re-research.

---

## 5. Files changed (lần này)

- `docs/research/TECH_OVERVIEW_2026.md` (MỚI, Iteration 2)
- `docs/research/BUILD_ORCHESTRATION_2026.md` (MỚI, T7)
- `docs/research/BUILD_MULTI_PROVIDER_2026.md` (MỚI, T8)
- `docs/research/BUILD_SMALL_CONTEXT_2026.md` (MỚI, T9)
- `docs/research/BUILD_LONG_SESSION_2026.md` (MỚI, T11)
- `docs/research/BUILD_VERIFY_COMPETE_2026.md` (MỚI, T10)
- `docs/research/RESEARCH_COVERAGE_LOG.md` (CẬP NHẬT)
- `docs/CONSTRAINT_LEDGER.md` (MỚI — từ session trước, chưa commit)
- `docs/research/en/` (3 files EN iteration 0 MỚI, chưa commit)

---

## 6. Residual risks / next steps

- **Chưa bão hòa tuyệt đối**: T12 (emerging tech 2026), T13 (production pain points góc mới), T14 (multi-agent comm) vẫn `[pending]` trong log — nhưng phần nằm ngoài scope build-strategy hiện tại; cần iteration riêng nếu user muốn.
- **Chưa implement** — đây là research build-strategy; các recommendation (V1-V8, L1-L6, W1-W7, R1-R10) là blueprint chưa chuyển thành code AHD. Cần plan riêng để triển khai.
- **HLK-loop** chạy learnings đã DONE — nên commit để lock state.
- Warning governance 1 (plan thiếu exec report) — pre-existing, không do chuỗi này.
- Scout subagent endpoint lỗi ở iteration 0 — research làm thủ công qua websearch (ok).

---

*End of LOOP EXHAUST REPORT | 2026-08-27 | Confidence: High*
