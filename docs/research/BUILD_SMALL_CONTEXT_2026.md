# BUILD: Small-Context & Weak-Model Harness (T9)

> **RESEARCH BỔ SUNG** (Iteration 4) — Build harness cho **agent kém thông minh + context windows nhỏ**.
> Định hướng user: dùng được với nhiều provider/model kể cả agent yếu. 
> Ngày: 2026-08-27. English + Vietnamese. KHÔNG duplicate T3/T4.

---

## 1. Luận điểm nền: "Externalization" (arXiv 2604.08224)

> "Agent được build ngày càng ít bằng đổi model weights, nhiều hơn bằng **tổ chức lại runtime** quanh model." [fact]

Externalization biến **cognitive burden thành dạng model giải quyết đáng tin hơn**:
- **Memory** externalizes state across time (thay đổi từ recall → recognition: retrieve từ persistent store, không regenerate từ latent weights).
- **Skills** externalizes procedural expertise (thay đổi từ inventing workflow → chọn + theo workflow). [fact]
- **Protocols** externalizes interaction structure.
- **Harness engineering = unification layer** phối hợp 3 thứ trên thành governed execution. [fact]

**Hệ quả cho agent yếu**: agent kém thông minh + context nhỏ có thể mạnh nhờ harness bù phần "state management" — giữ semantic decisions cho model, mechanical bookkeeping cho harness (exact bài Harness-1). ⭐ CỐT LÕI cho user.

---

## 2. Harness-1 (20B search agent) — mẫu "state-externalizing harness" ⭐

Policy giữ **semantic decisions** (search gì, keep/discard doc nào, verify gì, khi nào dừng); **harness giữ mechanical bookkeeping**. [fact]

- **State-machine harness** quanh per-episode **WORKING MEMORY** — mỗi turn render compact search state, không raw tool outputs. [fact]
- **Derived-state rendering** ⭐ (quan trọng cho context nhỏ):
  - **Evidence graph**: regex extract entities → frequent/bridge/singleton, render compact block. Model đổi câu hỏi "Tôi đã thấy X ở đâu?" thành lookup trực tiếp, không reread transcript. [fact]
  - **Sentence-BM25 compression**: search outputs bị score BM25 vs query, render top-K=4 sentences. [fact]
  - **Two-level dedup** (chunk ID + content fingerprint). [fact]
  - **Budget-aware context rendering**: kết hợp system prompt + rendered working memory + recent actions, **truncate older reasoning**, clip long observations. [fact]
- **Auto-seeding**: first successful search seeds curated set (top-k) → model refine thay vì build từ zero (tốt cho weak models). [fact]
- Kết quả: 20B model đạt +11.4 pts vs open search subagent, competitive frontier-model searchers. [fact]

---

## 3. Agent Engineering "Eight Pillars" framework (98.4% harness)

8 pillar: Orchestration, **Context**, **Memory**, **Tools**, **Reliability**, **Evaluation**, **Cost**, **Governance**. [fact]
Context là "finite resource, diminishing marginal returns" — target là **smallest high-signal token set**, không fullest window (Anthropic). [fact]

**4 failure modes của context + fix** (⭐ quan trọng):

| Failure | Mô tả | Fix |
|---------|--------|-----|
| **Poisoning** | hallucination/error vào context, copy lan, build strategy trên false premise | verify trước khi write; isolate untrusted; rollback-able state |
| **Distraction** | context dài → model replay past actions thay vì synthesize plan mới | compress/summarize; coi "distraction ceiling" |
| **Confusion** | irrelevant info (quá nhiều tool descriptions) giảm quality | load tools on-demand; chỉ select relevant context |
| **Clash** | context tự mâu thuẫn (nhiều source, nhiều MCP) | de-conflict, unify sources |

**4 chiến lược context (Write/Select/Compress/Isolate)** ⭐:
- **Write (out)**: persist ngoài window — scratchpad, state fields, external storage, memory tools.
- **Select (in)**: pull only relevant mỗi turn — RAG, memory retrieval, on-demand tool mounting.
- **Compress**: summarize (không crude truncate).
- **Isolate**: schema-shaped state (chỉ expose `messages` field); hoặc isolate subtask vào subagent's own context. [fact]

**4 memory layers**:
- **Working** = current context window (fastest, expensive, rot-prone).
- **Episodic** = records past sessions (SQLite + FTS + LLM summaries).
- **Semantic** = abstracted facts (MEMORY.md, knowledge graphs, vector).
- **Procedural** = "how to do something" (hardest để externalize, valuable nhất). [fact]
- Minimal impl: curated `MEMORY.md` load at start. **Failure: memory stale + conflict** → cần versioning/freshness + conflict resolution. [fact]

---

## 4. Setup agent-harness đúng cho weak models ⭐

- **Working memory budget tự-derived từ context window**: `working_memory_max_tokens=None` → auto từ `input_token_budget`; compacts ở `0.8 × budget`, để 20% headroom cho system prompt/memory/tool schemas. **Adaptive khi swap model**: 8K model → ~6K WM; 200K → ~159K. [fact]
- **Prefix-cache aware**: giữ full prompt byte-identical trong compaction window; memory context trong **pinned user-message prior** (system prompt thuần identity + tools — static, cached). Warm cache hit mỗi turn, chỉ 1 cold compaction. [fact] ⭐
- **Compaction theo context-size pressure, không turn count**: `compact_at_context_fraction=0.5`; sau compact `retain_context_fraction=0.15` giữ newest verbatim, fold older thành rolling summary. [fact]
- **Background memory accumulation, foreground cache stable**: non-blocking reconcile mỗi N turns, không evict cache. [fact]
- **cheap model cho side tasks**: classifier/router (≈300 tok) → cheap; planner/synthesis → premium. [fact]
- **Tool layer trả "receipts, not just NL observations"** (Restate lesson) — stdout+stderr+exit code, giúp weak model verify. [fact]

---

## 5. Skills vs Subagents vs Multi-Agent vs Dynamic Workflows (decision tree ⭐)

Từ Yue Shui: **tìm giải pháp đơn giản nhất trước**, thêm complexity chỉ khi cần. [fact]

| Approach | Cung cấp | Khi dùng |
|----------|----------|----------|
| **Skills** | reusable procedure | process ổn định, dùng lặp lại |
| **Subagents** | delegated worker, context riêng, trả summary (1-2K tok) | side task sinh nhiều intermediate output làm ô nhiễm main context |
| **Multi-Agent (Agent Teams)** | coordinated sessions, shared task list, lead quản lý | split project thành chunks, sync workers |
| **Dynamic Workflows** ⭐ | script orchestrate nhiều subagent, schedule + cross-check | task quá lớn, cần verification + stopping conditions |

**Dynamic Workflows (Anthropic 2026d)**: agent tự sinh **dedicated harness (JS code) at runtime** để spawn/coordinate subagents — không ép 1 agent trong 1 context. Harness là runtime scheduler trên subagents; mỗi subagent focus local objective; workflow giữ global state, concurrent schedule, verification, stop condition. [fact] ⭐

**Câu hỏi quyết định** (áp dụng thẳng cho AHD):
1. Process ổn định lặp lại? → Skill.
2. Subtask sinh nhiều info ô nhiễm main? → Subagent.
3. Task parallelizable + independent verifiable + info > 1 context? → Multi-Agent.
4. Cần strong verification/auto schedule/repeatable control? → Dynamic Workflows.
5. Sequential dependent / single agent đủ mạnh → **giữ Single Agent — đừng complexity cho complexity**. [fact]

---

## 6. Recommendations cho harness AHD ⭐

| # | Pattern | Áp dụng | Ưu tiên |
|---|---------|---------|---------|
| W1 | **State-externalizing harness** (Harness-1) | Model giữ semantic, harness giữ bookkeeping — cho phép dùng model yếu/rẻ | 🔴 HIGH |
| W2 | **Derived-state rendering** | Evidence graph + BM25 top-K thay raw tool outputs | 🔴 HIGH |
| W3 | **Auto WM budget từ context window** | Tự thích nghi khi swap model 8K↔200K | 🔴 HIGH |
| W4 | **Prefix-cache aware compaction** | Static system prompt, pinned memory, compact theo budget | 🔴 HIGH |
| W5 | **4 chiến lược Context (W/S/C/I)** | Write ngoài window, select relevant, compress, isolate | 🟠 MED |
| W6 | **Decision tree** | Chọn Skill/Subagent/Multi-Agent/Dynamic đúng chỗ — tránh complexity thừa | 🟠 MED |
| W7 | **Dynamic Workflow generation** | Agent yếu 1 context → gen harness runtime | 🟡 LOW |

---

## Sources (MỚI)

- arxiv.org/html/2604.08224 (Externalization), async arxiv 2606.02373 + github.com/pat-jj/harness-1 (Harness-1)
- ghost blog cubxxw.com/ai-agent (Eight Pillars 98.4), syhya.github.io (choose agent architecture), arxiv 2603.25723 (NLAH/IHR)
- github.com/ramannanda9/agent-harness (weak-model adaptive WM, prefix-cache)

---

*Iteration 4 output | 2026-08-27 | Small-context/weak-model build (MỚI) | Confidence: High*
