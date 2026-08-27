# AI Agent Solutions 2026

> Nghiên cứu giải pháp tăng cường điểm mạnh, triệt tiêu điểm yếu của AI trong software development.
> Ngày: 2026-08-27 | Nguồn: 19+ sources (arXiv, ACL, Martin Fowler, Microsoft, industry)

---

## Executive Summary

Tìm thấy **15 giải pháp** từ research online, mỗi giải pháp mapping cụ thể với AHD workspace. **7 giải pháp ADOPT NOW**, 5 MONITOR+PLAN, 3 RESEARCH.

Key insight: Industry đang move về hướng **deterministic enforcement > model goodwill**, **artifact-verified > self-report**, **behavioral testing > line coverage**.

---

## Solutions by Priority

### ADOPT NOW (7 solutions)

---

#### S1 — Self-Healing Framework

**Source**: arxiv.org/abs/2605.06737

**What**: Reliability-aware framework: failure detection → reliability assessment → adaptive replanning → corrective prompting.

**Effectiveness**: Increases task success, reduces failure propagation. [fact]

**AHD Map**: Direct match với `.devin/hooks/self_heal.py` + spc_monitor concept.

**Action**: Hook up existing `self_heal.py` với reliability assessment metrics. Add adaptive replanning capability.

**Priority**: HIGH — Already partially implemented, need metrics + adaptive replanning.

---

#### S2 — Adversarial Review (C3 Protocol)

**Source**: arxiv.org/html/2608.18167

**What**: Minimal 3-agent review (coder + reviewer + critic) với explicit structured disagreement. Highest pass rate trên LiveCodeBench. [fact]

**Effectiveness**: Best F1 trên SWE-PRBench after adding disagreement prompt. [fact]

**AHD Map**: Mirrors `adversarial-consensus` skill (6+ personas).

**Action**: Add explicit "disagreement" prompt template. Validate existing C3 protocol against benchmark results.

**Priority**: HIGH — Already implemented, validate effectiveness.

---

#### S3 — Agentic Engineering Best Practices

**Source**: arxiv/pdf/2512.08769

**What**: 9 practices: tool-first over MCP, pure-function invocation, single-tool/single-responsibility agents, externalized prompt mgmt, KISS, containerized.

**Effectiveness**: Industry-validated practices. [fact]

**AHD Map**: Strongly aligns — single-responsibility workers (Scout, Builder, Verifier, Auditor, Memory Keeper).

**Action**: Audit existing agents against 9 practices checklist. Document compliance gaps.

**Priority**: HIGH — Validate existing alignment, fix any gaps.

---

#### S4 — Continuous Self-Improving Loops

**Sources**: addyosmani.com, arxiv:2510.16079 (EvolveR), arxiv:2410.04444 (Gödel Agent), arxiv:2407.18219 (RISE)

**What**: Multiple approaches:
- **Ralph Wiggum loop**: stateless-but-iterative, AGENTS.md persistent context, compound learning [fact]
- **EvolveR**: offline self-distillation → strategic principles → online apply → GRPO policy update [fact]
- **Gödel Agent**: self-referential recursive self-improvement via prompting [fact]
- **RISE**: fine-tune to recursively correct own mistakes over turns [fact]

**AHD Map**: Matches `hlk-loop` + `loop-memory` + continuous loop already in workspace.

**Action**: Integrate EvolveR's "strategic principles repo" pattern into loop-memory. Add compound learning tracking.

**Priority**: HIGH — Already have infrastructure, enhance with new patterns.

---

#### S5 — Plan-Then-Execute Pattern

**Source**: agentic-patterns.com (Mar 2026), multiple industry sources

**What**: Planning trước improves task completion **40-70%**, reduces hallucinations **~60%**. Planner commits to bounded action graph. [fact]

**Effectiveness**: Industry-standard, proven across multiple frameworks. [fact]

**AHD Map**: Core 3-Phase architecture (Plan → Approve → Execute).

**Action**: Already implemented. Continue to enforce mandatory Plan phase for M-tier+ tasks.

**Priority**: HIGH — Maintain and reinforce.

---

#### S6 — Deterministic Hook Enforcement

**Sources**: htek.dev (Feb 2026), Endor Labs, Codacy Guardrails, Microsoft Agent Governance Toolkit

**What**: Hooks run BEFORE tool call, deterministic, auditable — not dependent on model goodwill. "The model layer alone cannot be the security control." [fact]

- Microsoft Agent Governance Toolkit: stateless, fail-closed policy decision runtime, pure Rust core. [fact]
- Codacy Guardrails: deterministic code analysis inside agentic workflow. [fact]

**AHD Map**: 49 Python hooks (pre_tool_use, plan_enforce, schema_gate, coverage_enforce, drift_detect, self_heal).

**Action**: Already implemented. Document event contracts clearly. Consider Microsoft's fail-closed pattern for critical hooks.

**Priority**: HIGH — Already strongest in industry, maintain edge.

---

#### S7 — Token Efficiency (Caveman Protocol)

**Source**: JuliusBrussee/caveman, AHD canon

**What**: Structured compression achieving ~65% context reduction. Lazy-load canon, progressive skill loading.

**Effectiveness**: ~65% token reduction. [fact]

**AHD Map**: `context_compactor` skill, `CAVEMAN_PROTOCOL.md` canon, lazy-load in BOOT_PROTOCOL.

**Action**: Already implemented. Monitor effectiveness metrics, consider CAT (Context as a Tool) enhancement.

**Priority**: HIGH — Maintain, monitor metrics.

---

### MONITOR + PLAN (5 solutions)

---

#### S8 — Context as a Tool (CAT)

**Source**: 2026.findings-acl.1032.pdf

**What**: Context management as callable tool. Workspace = stable tasks + condensed LTM + high-fidelity STM. SWE-Compressor: **57.6% solved on SWE-Bench Verified**. [fact]

**AHD Map**: Maps to `context_compactor` skill + memory on disk (not context).

**Action**: Evaluate CAT pattern for enhancement of existing context_compactor. Consider "stable task" decomposition.

**Priority**: MED-HIGH — Potential significant improvement.

---

#### S9 — MCP Tools Orchestrator

**Source**: github.com/inbarajaldrin/mcp-tools-orchestrator

**What**: Meta-MCP server, "Code as Policies", unified Python API over servers, **10-100x faster** via single exec vs N round-trips. [fact]

**AHD Map**: Gap — current MCP config is basic (4 servers).

**Action**: Evaluate MCP tools orchestrator for integration. Consider unified API pattern.

**Priority**: MED-HIGH — Could improve MCP performance significantly.

---

#### S10 — Budget-Aware Agentic Routing (BoPO)

**Source**: arxiv/html/2602.21227

**What**: Boundary-Guided Training picks cheap/expensive model per step under per-task budgets. Improves cost-success frontier. [fact]

**AHD Map**: Matches orchestrator → cheap executor (glm/kimi free tier) routing.

**Action**: Enhance existing model routing with budget-aware decision logic. Add per-task budget tracking.

**Priority**: MED-HIGH — Cost optimization opportunity.

---

#### S11 — Prompt Optimization for Codegen

**Source**: arxiv/pdf/2601.13118

**What**: Iterative test-driven prompt refinement; 10 elicited guidelines (I/O spec, pre/post conditions, examples, ambiguity); validated with 50 practitioners. [fact]

**AHD Map**: Feed into `plan_enhance`/`nuwa` prompt tuning.

**Action**: Apply 10 guidelines to plan_orchestrator prompts. Measure correction cycle reduction.

**Priority**: MED — Incremental improvement.

---

#### S12 — SolidCoder (Execute, Don't Imagine)

**Source**: 2026.findings-acl.361.pdf

**What**: "Don't imagine—execute". Fixes Specification Gap (edge-case awareness) + Verification Gap (sandboxed property-based execution). SOTA: **95.7% HumanEval, 77.0% CodeCon, 26.7% APPS**. [fact]

**AHD Map**: Sandboxed execution = TDD + verification protocol.

**Action**: Consider "execute don't imagine" principle in executor agent prompts. Ensure sandboxed execution.

**Priority**: MED — Principle alignment check.

---

### RESEARCH (3 solutions)

---

#### S13 — Scalable Best-of-N (Self-Certainty)

**Source**: arxiv/html/2502.18581

**What**: Reward-free selection metric from output prob distributions; scales with N, complements CoT, generalizes. [fact]

**AHD Map**: Could improve self-heal/corrective prompting.

**Action**: Research feasibility for integration with existing best_of_n.py and self_consistency.py scripts.

**Priority**: LOW-MED — Needs sampling infrastructure evaluation.

---

#### S14 — Gödel Agent Self-Improvement

**Source**: arxiv:2410.04444

**What**: Self-referential recursive self-improvement via prompting, surpasses hand-crafted agents. [fact]

**AHD Map**: Theoretical foundation for hlk-loop enhancement.

**Action**: Research paper in depth. Evaluate applicability to harness upgrade loop.

**Priority**: LOW — Theoretical, long-term.

---

#### S15 — RISE (Recursive Introspection)

**Source**: arxiv:2407.18219

**What**: Fine-tune models to self-improve over turns. RWR objective, self-consistency ignore-oracle mode. [fact]

**AHD Map**: Long-term improvement for executor model quality.

**Action**: Monitor research progress. Not applicable until fine-tuning infrastructure available.

**Priority**: LOW — Model-level improvement, not harness-level.

---

## Priority Matrix

| Priority | Solutions | Action |
|----------|-----------|--------|
| **ADOPT NOW** | S1, S2, S3, S4, S5, S6, S7 | Validate existing implementation + gaps |
| **MONITOR+PLAN** | S8, S9, S10, S11, S12 | Research + plan integration |
| **RESEARCH** | S13, S14, S15 | Deep-dive papers, evaluate feasibility |

---

## Mapping to Pain Points

| Pain Point | Solutions |
|------------|-----------|
| Verification Load | S1 (self-heal), S6 (hooks), S5 (plan-execute) |
| Over-Editing | S6 (hooks), S3 (best practices), S5 (plan) |
| Code Gen Weaknesses | S12 (execute don't imagine), S11 (prompt optimization) |
| Testing Bottleneck | S2 (adversarial review), S5 (plan-execute) |
| Hallucination | S5 (plan-then-execute reduces 60%), S8 (CAT), S13 (best-of-N) |
| Agentic Failure Modes | S4 (self-improving loops), S1 (self-heal), S3 (best practices) |
| False Positive Review | S2 (adversarial review), S6 (deterministic hooks) |
| Context Rot | S7 (caveman), S8 (CAT), memory on disk |
| Security | S6 (hooks), S3 (best practices) |
| LLM-as-Judge Bias | S2 (adversarial review), pairwise comparison |
| Trust Gap | S5 (plan-execute), S6 (hooks), artifact verification |

---

## Key Insight

> The most effective solutions are NOT about making AI "smarter" — they're about **wrapping AI in deterministic infrastructure** that catches what AI misses. Hooks, gates, adversarial review, and self-healing are engineering solutions, not model improvements.

---

## Sources

19+ sources: arxiv (S1, S2, S4, S10, S11, S13, S14, S15), ACL (S8, S12), Martin Fowler, Microsoft Agent Governance, htek.dev, Endor Labs, Codacy, addyosmani.com, agentic-patterns.com, inbarajaldrin (MCP orchestrator).

---

*Cập nhật: 2026-08-27 | 15 solutions | 7 ADOPT NOW | 5 MONITOR | 3 RESEARCH*
