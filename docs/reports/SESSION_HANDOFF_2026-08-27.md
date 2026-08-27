# SESSION HANDOFF — Build Multi-Provider Agent Harness (AHD)

> **PROMPT CONTEXT cho SESSION MỚI** — đọc file này để có đủ context tiếp tục.
> Ngày: 2026-08-27 | Repo: Loop_harness_ruflo | Branch: main (synced origin/main, 0 ahead/0 behind)
> Ngôn ngữ: tiếng Việt có dấu (theo AGENTS.md). Code comments tiếng Việt. Technical terms giữ EN.

---

## 0. TL;DR cho session mới

Workspace này là **AHD (Agent Harness Deploy)** — harness AI agent đa provider, đa model, chạy quy trình 3-Phase (Plan→Approve→Execute) với 49 hooks + governance enforcement.

**Mục tiêu lớn đang theo đuổi:** build hệ thống/framework **cạnh tranh giá trị** với harness của Claude (Fable/Opus/Sonnet), Codex, GPT-5.6 (Sol) — nhưng chạy được với **NHIỀU AI provider + NHIỀU model** (kể cả agent kém thông minh, context nhỏ), phục vụ **phiên dài/phức tạp, logic nghiệp vụ phức tạp, phối hợp đồng thời, theo quy trình**.

**Trạng thái:** Đã xong **research build-strategy** (7 BUILD files, 48 recommendations). Đã có **backlog + preliminary plan** (19 tickets). **CHƯA implement** bất kỳ recommendation nào → session mới bắt đầu Phase 1 implementation.

---

## 1. Research đã làm (đã commit, đừng re-research)

Commit gần nhất: `3f6cc25` (merge origin/main). Các research files quan trọng:

| File | Nội dung | Góc |
|------|----------|-----|
| `docs/research/TECH_OVERVIEW_2026.md` | Harness engineering discipline, Context Rot, SWE-bench 2026, MCP security crisis | Baseline tech |
| `docs/research/BUILD_ORCHESTRATION_2026.md` | Multi-agent orchestration build (R1-R10) | Orchestration |
| `docs/research/BUILD_MULTI_PROVIDER_2026.md` | Đa AI provider gateway (M1-M5) | Multi-provider |
| `docs/research/BUILD_SMALL_CONTEXT_2026.md` | Agent yếu + context nhỏ (W1-W7) | Small-context |
| `docs/research/BUILD_LONG_SESSION_2026.md` | Durable execution (L1-L6) | Long-session |
| `docs/research/BUILD_VERIFY_COMPETE_2026.md` | Eval harness + compete (V1-V8) | Verification |
| `docs/research/BUILD_EMERGING_STANDARDS_2026.md` | A2A/AAIF/3-layer stack (S1-S5) | Standards |
| `docs/research/BUILD_PRODUCTION_PAIN_POINTS_2026.md` | Production failures (P1-P8) | Prod-pain |
| `docs/research/RESEARCH_COVERAGE_LOG.md` | Log chống duplicate — T4,T7-T14 đều `[covered]` | Anti-dup |

**3 subagent reports (session trước, đã register trong log, KHÔNG re-research):** `orchestration_patterns.md`, `planning_best_practices.md`, `qc_enforcement_mechanisms.md` — nằm `docs/research/`.

---

## 2. Backlog (đã tổng hợp) — `docs/reports/AHD_BUILD_STRATEGY_BACKLOG_2026-08-27.md`

48 recommendations grouped 7 themes → **19 phased tickets**:
- **Phase 1 (HIGH — cạnh tranh trực tiếp Claude/Codex/GPT):** 
  - `[R3+M1+M4]` Model tiering + per-call budget
  - `[P1]` Structured-error MCP layer + circuit breaker
  - `[P2+P3]` Loop + context guards (step limit, progressive tool discovery)
  - `[W3+W4]` Adaptive WM + prefix-cache compaction
  - `[L1+L2]` Durable step boundaries + checkpoint resume
  - `[V1+V3]` Private golden set + trajectory eval
  - `[S1]` 3-layer stack adoption (MCP+A2A+WebMCP)
- **Phase 2 (MED — hardening):** R2, R4, W1+W2, L3+L4, V4+V5+V6, P4+P5, R6
- **Phase 3 (LOW — nice-to-have):** R7-R10, W5-W7, V7+V8, S2-S5, P6-P8

**2 HIGH-most-urgent:** (1) MCP gap P1 (security), (2) Governance Decay A1 từ TECH_OVERVIEW (correctness under compaction — pin REDLINES).

---

## 3. Plan sơ bộ đã build — `docs/plans/ahd-build-strategy-implementation/IMPLEMENTATION_PLAN.md`

File plan chi tiết Phase 1 tickets: mỗi task có File Path, Function, Acceptance Criteria, REQ ID (theo template governance). Session mới đọc plan này → implement theo từng ticket.

---

## 4. Quy tắc bắt buộc khi implement (GOVERNANCE)

- Mọi code change phải thuộc `File Path` của plan (đã duyệt) + test file.
- Không tạo file rác; file mới đúng nơi: script→`.devin/scripts/`, hook→`.devin/hooks/`, test→`tests/`, util→`tools/`, plan→`docs/plans/<slug>/`, report→`docs/reports/`.
- Sau implement: viết `EXECUTION_REPORT.md`, chạy `python tools/check_governance.py` (phải 0 errors).
- Commit messages tiếng Anh. Không commit secrets. Không force-push.
- Tiếng Việt có dấu cho mọi response + code comments.

---

## 5. Bắt đầu như thế nào (new session first actions)

1. Đọc `docs/plans/ahd-build-strategy-implementation/IMPLEMENTATION_PLAN.md` (Phase 1).
2. Pick ticket `[P1]` (Structured-error MCP) hoặc `[R3+M1+M4]` (Model tiering) — cả 2 là HIGH, ít phụ thuộc.
3. Cho mỗi ticket: deep-read BUILD source file tương ứng → viết plan chi tiết → implement + test + EXECUTION_REPORT.
4. Chạy `python tools/check_governance.py` trước khi commit.
5. Theo dõi tiến độ trong backlog report.

---

## 6. Key technical facts đã research (dùng làm tham chiếu)

- **A2A v1.0** (Linux Foundation, 150+ orgs): agent-to-agent, signed Agent Cards, async task lifecycle. KHÔNG cạnh tranh với MCP (MCP = tool, A2A = agent).
- **AAIF** (Dec 2025): MCP + goose + AGENTS.md + A2A dưới 1 roof. 3-layer stack: WebMCP → MCP → A2A.
- **MCP crisis**: 110M downloads, 78% enterprises in prod, NHƯNG 52% servers abandoned, 88% agent pilots never reach prod.
- **Cost**: multi-agent ≈ 15× tokens của single chat. Dùng cheap model cho classifier/router.
- **Harness-1 (20B)**: state-externalizing harness → model yếu vẫn mạnh nhờ harness giữ bookkeeping.
- **Eval = control plane**: SWE-bench Verified contaminated → dùng SWE-bench Pro + private golden set. Trajectory eval bắt cái layer 5 Anthropic thiếu.

---

*Handoff ready | 2026-08-27 | Next session: implement Phase 1 tickets từ plan.*
