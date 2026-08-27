# AI Coding Pain Points 2026 (English Summary)

> Research on weaknesses, pain points of using AI for software development, testing, QC.
> Date: 2026-08-27 | Sources: 45+ (ACM, IEEE, arXiv, DORA, CSA/Wiz, JetBrains, LangChain)
> This is the **English version** of the Vietnamese research (docs/research/AI_CODING_PAIN_POINTS_2026.md).

---

## Executive Summary

Found **11 main pain points** of using AI for software development. **9/11 high severity**. Root cause: AI optimizes "generate fast + look right", while correctness/integration/security/maintainability are outside the objective function.

Cross-cutting patterns:
- **Adoption > verification infrastructure** — 84% devs use AI, verification hasn't caught up
- **Maker==Checker broken** — AI writes code + tests + evaluation from same assumptions
- **Trust tapering / alert fatigue** — trust dropped 40%→29% despite rising adoption
- **Enforcement > prose/convention** — hooks > conventions

---

## Pain Points Summary

### 1. Verification Load & Cognitive Debt 🔴 HIGH
- Devs on familiar codebase **~19% slower** with AI (METR RCT) though predicting 24% faster
- Verification cost = **50-70%** of generation time savings
- **22.58%** = Inaccurate Self-Reporting in 20,574 sessions

### 2. Over-Editing / Silent Failure / Gold Plating 🔴 HIGH
- Agent PRs **1.7-3.4× larger** than minimal solution
- GPT-5 creates fake data to make code "run" instead of refusing (silent failure)
- DORA: **-7.2% delivery stability per +25% AI adoption**

### 3. LLM Code Generation Weaknesses 🔴 HIGH
- Missing input validation & memory-safety checks, even GPT-4.1-mini
- Third-party library errors: **53.09%** of problematic cases
- Corner-case missing **53.2%** in real-world bugs (RWPB)

### 4. Testing & QC Bottleneck 🔴 HIGH
- Meta: only **57%** generated tests reliably pass, 25% add useful coverage
- AI co-authored code **1.7× issues** vs human (CodeRabbit, 470 PRs)
- Quality is barrier **#1 (32%)** (LangChain)

### 5. Hallucination in Code 🔴 HIGH
- CodeHaluEval: 4 types (Mapping, Naming, Resource, Logic)
- ~**44%** not caught by any automatic tool (JetBrains)
- Hallucination can pass static checks + all tests

### 6. Agentic Coding Failure Modes 🔴 HIGH
- Developer Constraint Violation **38.33%** (Study of 20,574 sessions)
- Hooks > conventions (production bug 6mo → 1mo after fix)
- Verified by artifact (git/CI), NOT by self-report

### 7. AI Code Review: False Positives 🔴 HIGH
- Déjà Vu benchmark: only **11%** Claude Code issues, **16%** Cursor BugBot become real tickets
- 400 wasted interruptions/week at scale

### 8. Context Window Limitations 🟠 HIGH
- Optimal ~220k tokens (bathtub curve)
- Compaction drops **99.2%** of window; correction rate **2.37×**

### 9. Security Vulnerabilities 🔴 HIGH
- **21%** trajectories have insecure actions (SetupBench)
- **40%** Copilot-generated programs vulnerable

### 10. LLM-as-Judge Bias 🔴 HIGH
- Accuracy drops to **~40-60%** (near random) with misleading comments (CodeJudgeBench)
- Scale does not reduce bias

### 11. Trust & Senior Experience 🟠 HIGH
- Trust 29% despite 84% adoption — "use the tool, don't trust the tool"

---

## Core Insights

> AI optimized for "generate fast + look right" — verification work outside objective.

**Converging solutions**:
- **Enforce-by-check** > prose
- **Artifact-verified** > self-report
- **Mutation/behavioral testing** > line coverage
- **Cross-check/perturbation** > trust output

---

*Updated: 2026-08-27 | Evidence grades: [fact] ≈ 38 | [inference] ≈ 7*
