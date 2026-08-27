# AI Agent Solutions 2026 (English Summary)

> Research on solutions to enhance AI strengths and eliminate AI weaknesses in software development.
> Date: 2026-08-27 | Sources: 19+ (arXiv, ACL, Martin Fowler, Microsoft, industry)
> This is the **English version** of the Vietnamese research (docs/research/AI_AGENT_SOLUTIONS_2026.md).

---

## Executive Summary

Found **15 solutions**. **7 ADOPT NOW**, 5 MONITOR+PLAN, 3 RESEARCH.

Key insight: Industry moving toward **deterministic enforcement > model goodwill**, **artifact-verified > self-report**, **behavioral testing > line coverage**.

---

## ADOPT NOW (7 solutions)

### S1 — Self-Healing Framework
- **Source**: arxiv.org/abs/2605.06737
- **What**: failure detection → reliability assessment → adaptive replanning → corrective prompting
- **AHD Map**: matches `.devin/hooks/self_heal.py` + spc_monitor
- **Action**: Add reliability metrics + adaptive replanning

### S2 — Adversarial Review (C3 Protocol)
- **Source**: arxiv.org/html/2608.18167
- **What**: minimal 3-agent review (coder + reviewer + critic) with explicit structured disagreement
- **AHD Map**: mirrors `adversarial-consensus` skill (6+ personas)
- **Action**: Add explicit "disagreement" prompt

### S3 — Agentic Engineering Best Practices
- **Source**: arxiv/pdf/2512.08769
- **What**: 9 practices: tool-first, pure-function invocation, single-tool/single-responsibility agents, externalized prompt mgmt, KISS, containerized
- **AHD Map**: aligns with single-responsibility workers
- **Action**: Audit agents against 9 practices checklist

### S4 — Continuous Self-Improving Loops
- **Sources**: addyosmani, arxiv:2510.16079 (EvolveR), 2410.04444 (Gödel Agent), 2407.18219 (RISE)
- **AHD Map**: matches `hlk-loop` + `loop-memory`
- **Action**: Integrate EvolveR "strategic principles repo" pattern

### S5 — Plan-Then-Execute Pattern
- **Source**: agentic-patterns.com
- **What**: planning improves completion **40-70%**, reduces hallucination **~60%**
- **AHD Map**: Core 3-Phase architecture
- **Action**: Already implemented, maintain

### S6 — Deterministic Hook Enforcement
- **Sources**: htek.dev, Endor Labs, Codacy, Microsoft Agent Governance
- **AHD Map**: 49 Python hooks (pre_tool_use, plan_enforce, schema_gate...)
- **Action**: Already strongest in industry, document contracts

### S7 — Token Efficiency (Caveman Protocol)
- **Source**: JuliusBrussee/caveman
- **AHD Map**: `context_compactor` skill, `CAVEMAN_PROTOCOL.md`
- **Action**: Already implemented, monitor metrics

---

## MONITOR + PLAN (5 solutions)

| # | Solution | Source | AHD Map | Priority |
|---|----------|--------|---------|----------|
| S8 | Context as Tool (CAT) | 2026.findings-acl.1032 | `context_compactor` | MED-HIGH |
| S9 | MCP Tools Orchestrator | inbarajaldrin/mcp-tools | 4 MCP servers | MED-HIGH |
| S10 | Budget-Aware Routing (BoPO) | arxiv:2602.21227 | model tier routing | MED-HIGH |
| S11 | Prompt Optimization | arxiv:2601.13118 | plan_enhance/nuwa | MED |
| S12 | SolidCoder (execute don't imagine) | 2026.findings-acl.361 | TDD + verify protocol | MED |

---

## RESEARCH (3 solutions)

| # | Solution | Source | Action |
|---|----------|--------|--------|
| S13 | Scalable Best-of-N | arxiv:2502.18581 | Feasibility for best_of_n.py |
| S14 | Gödel Self-Improvement | arxiv:2410.04444 | Research paper depth |
| S15 | RISE Recursive Introspection | arxiv:2407.18219 | Monitor (needs fine-tuning infra) |

---

## Mapping Pain Points → Solutions

| Pain Point | Solutions |
|------------|-----------|
| Verification Load | S1, S6, S5 |
| Over-Editing | S6, S3, S5 |
| Code Gen Weaknesses | S12, S11 |
| Testing Bottleneck | S2, S5 |
| Hallucination | S5, S8, S13 |
| Agentic Failure Modes | S4, S1, S3 |
| False Positive Review | S2, S6 |
| Context Rot | S7, S8 |
| Security | S6, S3 |
| LLM-as-Judge Bias | S2, pairwise |
| Trust Gap | S5, S6, artifact verification |

---

*Updated: 2026-08-27 | 15 solutions | 7 ADOPT NOW | 5 MONITOR | 3 RESEARCH*
