# Verification Protocol — Maker ≠ Checker (Caveman Compressed)

> Producer never verifies. Models self-grade leniently. Fresh observer catches what author misses. OpenAI/Anthropic/Cloudflare/Stripe converge on separation.

---

## Why
Models self-grade leniently (arXiv 2306.05685). Author invested → skewed incentives. Fresh observer with same criteria catches blind spots. Not theory — top production lever.

---

## Verification Methods by Output

| Output | Method | Anchor |
|--------|--------|--------|
| File write | Fresh-context `read(path,offset,limit)` | Weak ⚠️ |
| Code | CLI gate: build/typecheck/lint/test | Strong ⚓ |
| Config sync | `tools/verify-workspace.ps1` read-backs | Strong ⚓ |
| Visual | Vision-capable agent, never self-judge | Weak ⚠️ |
| High-risk judgment | 2 independent agents, integrate diff | Weak ⚠️ |
| Rules/docs | `read`+`grep` version headers/links/paths; evidence-grade claims | Weak ⚠️ |
| Claims | `claim-grader`: tag `[fact]`/`[inference]`/`[unverified-guess]` | Weak ⚠️ |
| DB schema | `DESCRIBE`/`\d` vs spec; idempotent migrations; FK indexes | Strong ⚓ |
| API contracts | OpenAPI validate; response vs schema; status/error/pagination | Strong ⚓ |
| IaC | `terraform plan`/`cdk diff`; validate; drift check; `tfsec`/`checkov` | Strong ⚓ |
| ML artifacts | Model card (purpose/data/metrics/limits); weight hash; holdout test; bias | Strong ⚓ |

---

## Fresh-Context Verification (L/XL)
Give verifier: file paths, AC, minimal context (<2KB). No history/reasoning. Cold read.

---

## Report Contract
```
## Verdict [PASS|FAIL|PARTIAL|NEEDS_ESCALATION]
## Evidence-graded
- [fact] <claim> — <file:line|cmd>
- [inference: <basis>] <claim> — <basis>
- [unverified-guess] <claim> — action: <what to verify>
## Checked
- [criterion]: file:line — [evidence]
## Problems
- severity | file:line | issue | fix
## Uncertain
- [item]: [why]
## Partial details (U33, only if PARTIAL)
- AC met: <count>/<total> (<pct>%)
- AC remaining: <list>
- Blocked by: <dep>
- Next steps: <what>
- Value delivered: <what usable>
```

---

## PARTIAL Verdict (U33)
**Criteria**: ≥50% AC met, remaining blocked by external dep, value delivered.

| Use PARTIAL | Use FAIL |
|-------------|----------|
| Most AC met, blocked by external (API/upstream/env) | Core AC not met, not usable, fixable in-session |
| Completed work shippable standalone | — |

**Requirements**: List met AC (evidence), unmet AC (blocker), dep blocking, value delivered, next steps.

---

## Circuit Breakers (stop & ask human)
- Verification fails same way 2 rounds
- Destructive side effect imminent (delete/force-push/bulk)
- AC ambiguous (2+ interpretations)
- Cost spike: >20 files, >10 min, >10 file mods
- Taste/aesthetic decision required

---

## Self-Verification ONLY for
S-tier: <5 lines, 1 file, no verification chain (e.g., update date in `loop_state.md`). Else → external verify.

---

## SHA Discipline (Stale Evidence Trap)
**Rule**: Review/verification status only valid for exact version run. After any write → re-verify. Never carry verdict across versions.

---

## Verification Anchor Tiers (Strong vs Weak)

| Tier | What | Examples | Gameable? |
|------|------|----------|-----------|
| **Strong ⚓** | Deterministic execution vs evidence system can't see/alter | `verify.py` read-back, real test pass/fail, holdout exam, real money/churn, human spot-check | No |
| **Weak ⚠️** | Probabilistic agent judgment / cross-report | Fresh-context read-back, LLM-as-judge, multi-agent debate, report consistency, public benchmark | Yes — bias, familiarity, blind spots |

### Why LLM-as-judge is Weak
- arXiv 2306.05685: Models score own writing higher; humans can't detect
- arXiv 2404.13076: Bias = familiarity (prefers "reads like me"); cross-family same tier doesn't fix
- **Network of weak anchors = louder echo chamber, not strong anchor.** Need ≥1 link to reality no agent can alter.

### Frozen Nodes (Holdout Principle)
- Test data agent never sees (holdout exam, frozen AC written before start)
- Real-world outcomes (deploy synced? customer paid? CI passed?)
- Human judgment ("right thing to build?")
- **Frozen node agent can read = no longer frozen** (will overfit). Enforce at OS/permission, not prompt.

### Rules
- Classify each method as strong/weak before relying. "Fresh-context verified" = weak. "verify.py passed" = strong.
- Prefer ≥1 strong anchor when available. If both feasible → use both. If only fresh-context → deploy passes per REDLINES #9, add "Uncertain" note.
- Weak anchors additive, not substitutive. Two weak ≠ one strong.
- LLM-as-judge bias systematic. Cross-family reduces but doesn't eliminate.
- Frozen nodes must be physically inaccessible (OS/permission, not prompt).

---

## Multi-Agent Debate (High-Risk)
For security/architecture/irreversible:
1. Dispatch 2 independent verifiers (diff context, ideally diff model family)
2. Collect both verdicts
3. Agree → high confidence. Disagree → finding = disagreement; escalate to human with both + diff
4. Cross-family catches family-blind spots (Claude-only misses Claude biases; mix Claude+GPT+Gemini triangulates)

---

## U10: Cross-Family Verification Enforcement (L/XL)

**Mandatory for L/XL, recommended for M**

Verification MUST include ≥1:
1. **Cross-family verifier** — diff model family than producer (e.g., producer=GLM-5.2 → verifier=SWE-1.7 or Claude)
2. **Strong anchor** — deterministic (verify.py, test suite, CLI gate) producer can't game

If neither available → CANNOT mark complete. Mark `NEEDS_ESCALATION`, ask human.

**Implementation**:
- Producer model family in session_state (`producer_model`)
- Verifier checks `producer_model`, selects diff family
- If only one family → strong anchor REQUIRED
- Record in report:
  ```
  ## Cross-family verification
  - Producer: <model family>
  - Verifier: <model family> (different)
  - Method: <fresh-context read-back | CLI gate | test suite>
  ```

---

## No Gold-Plating
Scope fence = task boundary; no-gold-plating = change boundary (diff minimal).

| Rule | Check |
|------|-------|
| Diff 1:1 to request | Bug fix touches bug only |
| No helpers for single call site | Inline |
| No design for non-existent reqs | Simplest wins |
| Validate only at boundaries | Inside trust invariants |
| Prefer code over shims/flags | Unless public interface |
| Adjacent work | Note only, don't do |

### Pre-Diff Self-Check
1. Could reviewer trace every hunk to request? No → cut
2. Added function/param/branch "just in case"? Yes → cut
3. New error path reachable? State cannot occur → cut
4. Refactored untouched thing? Yes → revert, note as suggestion

| Principle | Question |
|-----------|----------|
| Scope fence | "Am I working on right thing?" (task boundary) |
| No gold-plating | "Is diff bigger than ask?" (change boundary) |

---

## Bottleneck Shift
Before AI: bottleneck = writing code. After AI: bottleneck = defining + verifying correct.

| Before | After |
|--------|-------|
| Write code | Define + verify |

Coding speed without verification speed = unlimited risk amplification (1000 gen/min, 100 verified = 900 unverified/min).

**Rules**:
- Verification budget ≥ production budget (≥X verify per X generate)
- Requirements never "done" first pass — design for spec iteration
- Optimize verification speed, not generation speed

---

## Three QA Strategies (All Required)

| # | Strategy | Meaning |
|---|----------|---------|
| 1 | Understand what AI wrote | Human "略懂" — discuss without coding. Else: rubber-stamp |
| 2 | Use AI for QA | AI generates tests/edge cases/verification from PRD. Bad PRD = bad QA |
| 3 | Design for worst case | Assume AI mistakes. Guardrails: credit limits, kill switches, blast radius |

**Rules**:
- All three required. One/two = gap.
- Strategy 1 non-negotiable for L3/L4 unattended loops.
- Strategy 2 requires correct PRD — iterate PRD first.
- Strategy 3 = defense in depth. No single guardrail enough.

---

## Two Code Types → Different Verification

| Type | Examples | Depth |
|------|----------|-------|
| One-time / daily | Data scripts, batch jobs, internal tools | Light: run + spot-check |
| Production | Customer-facing, API, DB schema | Full: test+lint+typecheck+fresh-context+security |

**Rules**:
- Classify before verifying. One-time+full=waste. Production+light=unbounded risk.
- One-time: verify runs + correct output. Enough.
- Production: full protocol. No exceptions.
- Code surviving expected lifetime → promote to production.

**Promotion Trap**:
```
Day 1: "One-time script" → Light
Day 30: "Still use daily" → Verification never upgraded
Day 90: Breaks production → "Thought it was temporary"
```
Code surviving expected lifetime → reclassify.

---

## Start Small > Null
```
No test → 0% coverage → unlimited risk
Partial → N% coverage → risk bounded
Complete → 100% → ideal, often not first pass
```
Jump 0%→N% > N%→100%. **Start with what you can define.**

**How**:
1. AC as questions: "Does X return Y when Z?" = one test
2. Don't wait for complete spec. Test known; add as spec clarifies
3. One test > zero tests. "Runs without crash" > no test
4. AI expands edge cases from seed. One test → AI generates 10

**Rules**:
- Never block on "test not complete." Ship partial. Add later.
- Every GoalSpec needs ≥1 AC. Empty = no verification.
- 3 rough tests > 0 polished. Polish after code works.
- First test hardest. After that, AI expands. Just start.

---

## Guides × Sensors (2×2 Taxonomy)

| | Computational (deterministic) | Reasoning (probabilistic) |
|---|-------------------------------|---------------------------|
| **Guides** (before) | Bootstrap, LSP | AGENTS.md, Skills, arch docs |
| **Sensors** (after) | Linter, ArchUnit, typecheck, coverage | AI review, LLM-as-judge |

| Quadrant | Examples | Purpose |
|----------|----------|---------|
| Q1: Comp Guides | Bootstrap, LSP auto-import | Fast, cheap, deterministic — pre-config for 1st-try |
| Q2: Reason Guides | AGENTS.md, Skills, arch | Slow, expensive, probabilistic — steer before acting |
| Q3: Comp Sensors | Linter, typecheck, ArchUnit, coverage | Fast, cheap, deterministic — catch violations, zero ambiguity |
| Q4: Reason Sensors | AI review, LLM-as-judge, auditor | Slow, expensive, probabilistic — catch semantic errors |

**Why all 4 needed**:
- Sensors w/o guides → repeat mistakes
- Guides w/o sensors → can't know if guides worked
- Comp w/o reasoning → catches syntax, misses semantic
- Reasoning w/o comp → slow, expensive, can't scale

**AHD Mapping**:
| Component | Q |
|-----------|---|
| AGENTS.md/CLAUDE.md/REDLINES.md/BOOT_PROTOCOL.md | Q2 |
| pre_tool_use hooks / L0-L4 permission | Q1 |
| post_tool_use/verify.py/memory_audit/warning keywords/security benchmark | Q3 |
| Nuwa cognitive / Auditor / Fresh-context verifier | Q4 |

**Rule**: Harness must cover all 4 quadrants. Missing = blind spot. Comp sensors every commit. Reasoning sensors selectively (L/XL, high-risk, or Q3 passes but feels wrong). Guides=prevention; sensors=detection. Classify new components.

---

## Behavior Harness Gap (Elephant in Room)

| Dimension | Maturity | Tools |
|-----------|----------|-------|
| Maintainability | Most mature | Linter, formatter, complexity, duplication |
| Architecture fitness | Medium | ArchUnit, deps rules, layer constraints |
| **Behavior** | **Weakest** | ??? — no reliable automated answer |

**Why weak**: Maintainability/arch = computational (Q3). Behavior = reasoning (Q4), Q4 unreliable: tests verify code≠spec≠intent, LLM-as-judge shares blind spots, human review doesn't scale.

**AHD defense in depth**: PRD iteration + start small > null + 3 QA strategies + bottleneck shift + fresh-context verification.

**Rule**: Name gap. "Does code do what user wants?" Tests verify code=spec — not spec=intent. Clean/well-typed code can still do wrong thing. Behavior requires multiple layers: PRD iteration + test cases + AI QA + human review. Behavior gap = where most AI incidents live. Track maturity: "Human reads output says yes/no" = weakest.

---

## Sensor Output = Fix Instructions (Positive Prompt Injection)

**Bad**: `ERROR: naming convention violation line 42`  
**Good**: `ERROR: line 42 uses camelCase. Project uses snake_case. Rename 'fooBar' to 'foo_bar'. See AGENTS.md §Naming.`

Error message guides next action → closes feedback loop → Q3 sensor becomes Q1 guide.

```yaml
rule: no-restricted-imports
message: >
  Don't import @prisma/client directly in route handlers.
  Use src/services/ instead. See AGENTS.md §Architecture.
```

```
FAIL: test_user_service
  Expected: user.email lowercase | Actual: "User@Example.COM"
  Fix: Apply .toLowerCase() in UserService.create() before saving. See AGENTS.md §Data normalization.
```

**Rule**: Every sensor error must include fix instruction. "ERROR" alone = dead end. "ERROR + how to fix" = feedback loop. Fix specific. Reference canonical rule. Include example. Anti-pattern: "as" casts, "any" types, bypasses. Update fix when rules change.

---

## Triple Verification (Knowledge Extraction Quality Gate)

Every candidate concept must pass 3 independent checks before canon admission.

| Check | Q | Pass | Fail |
|-------|---|------|------|
| **V1 Cross-domain** | ≥2 independent contexts? | "Mechanical enforcement" in OpenAI PR, Anthropic test arch, Fowler linter (3) | Quote only appears once → demote to example |
| **V2 Predictive** | Extrapolates to novel situation? | Novel scenario → non-trivial conclusion | Only platitudes ("plan ahead") |
| **V3 Exclusivity** | Non-obvious to competent practitioner? | "Ashby's Law applied to harness" — most don't connect | "Test your code" — everyone knows |

**Application**:
| Phase | Checks |
|-------|--------|
| Source analysis | ≥2 times in source? (V1) |
| Concept drafting | Explains scenario source didn't cover? (V2) |
| Canon admission | Non-obvious to competent AI engineer? (V3) |

**Failure modes**:
| Failure | Defense |
|---------|---------|
| V1 cheating (same example rephrased) | Require: diff chapters + objects + conclusions |
| V2 cheating (source discusses, reworded) | Novel question should make unsure what source says |
| V3 too loose (well-phrased common knowledge) | Judge content, not wording |

**Pass rates**: Methodology-dense 30-50%. Opinion 5-15%. <5% = extractor problem. >80% = standards too loose.

**Rules**:
- Every concept MUST pass V1+V2+V3. No exceptions. Prevents canon rot.
- Rejected concepts logged with reasons. Keep `rejected/` audit trail.
- User light confirmation: show "N passed + M rejected" before canon write.
- Pass rate diagnostic. Too low = extractor problem. Too high = verification loose.
- Apply to existing canon periodically. Prune failing V2/V3 on re-examination.

---

## Pressure Test with Decoy Prompts (Trigger Precision)

No decoy tests = no quality gate. Over-activation = primary production failure mode.

| Type | Count | Purpose |
|------|-------|---------|
| `should_trigger` | 3-5 | Activates when should |
| `should_not_trigger` (decoy) | 2-3 | Stays silent when shouldn't |
| `edge_case` | 1-3 | Reasonable judgment on ambiguous |

**Cross-concept confusion test (mandatory)**: ≥1 decoy must trigger DIFFERENT concept in same canon family.

```
Scenario: "Harness assumption expiry" + "Thinner not thicker"
Decoy: "My harness getting too complex after model upgrade"
  → Should trigger: "Thinner not thicker" | NOT: "Harness assumption expiry"
  → If wrong fires → fix A2/description
```

**Blind testing**: Prefer independent sub-agent (fresh context) — give concept+desc+prompt, not expected answer. Fallback: self-test (lower confidence).

**Thresholds**:
| Pass rate | Action |
|-----------|--------|
| 100% | Accept |
| ≥80% | Analyze failures: fix concept or test (beware self-justification) |
| <80% | **Reject and redo.** Re-examine trigger, not surface fix. |

**Rules**:
- Every canon concept MUST have decoy tests.
- ≥1 decoy cross-concept confusion test.
- Blind testing > self-testing (author has confirmation bias).
- <80% pass = redo, not patch. Wrong trigger def → surface fixes hide problem.
- Test trigger description (A2), not just content.
- Edge cases test boundary reasoning. "Should fire for trivial version?" — must have defensible answer.

---

## AI-Specific Slop Sensor (Q3 Subcategory)

Traditional linters assume idioms/intent/real imports/honesty. AI violates all: mixes 6+ langs, generates `pass`/`TODO`, hallucinates imports (20% non-existent), writes hedges.

### AI Slop Taxonomy

| Axis | Detects | Examples | Linter? |
|------|---------|----------|---------|
| Hallucinations | Non-existent imports/functions | `from nonexistent_pkg import foo` | ❌ |
| Cross-language leakage | Wrong-language patterns | `.push()` in Python, `.length` in Python | ❌ |
| Placeholder code | Functions doing nothing | `def validate(x): pass` | ❌ |
| Confident wrongness | Looks right, fails runtime | Type sigs ≠ runtime | ❌ |
| Hedging | Comments revealing uncertainty | `# should work hopefully` | ❌ |
| Over-engineering | God functions, deep nesting | 500-line fn, 8 levels deep | ⚠️ |
| Debug artifacts | Leftover `print()`, redundant comments | `print(x)` above `return x` | ⚠️ |
| Explanation bloat | Comments restating code | `# loop through items` above `for x in items:` | ❌ |
| Version stacking | In-file version markers/changelog | `<!-- v2 fixed X -->`, `# v3`, `<!-- updated 2026-07-15 -->` | ❌ |

### Four Slop Axes (sloppylint)

| Axis | Name | Measures |
|------|------|----------|
| 📢 **Noise** | Info Utility | Debug artifacts, redundant comments, explanation bloat — no value |
| 🤥 **Lies** | Info Quality | Hallucinations, placeholders, confident wrongness — claims work but doesn't |
| 💀 **Soul** | Style/Taste | Over-engineering, god functions, hedging, version stacking — works but bad |
| 🏗️ **Structure** | Structural Issues | Bare except, star imports, anti-patterns — structurally wrong |

### Slop Score = `/goal` Convergence Metric
```
/goal loop: "reduce slop score to <50"
  - Check: sloppylint --ci --max-score 50
  - Exit: score <50 AND no critical/high issues
  - Stop: 3 consecutive iterations no improvement
```

**Benchmark**: slop-scan pins mature OSS to pre-AI commits (before 2025-01-01). **AI repos score 6.91x higher slop.**

**Rules**:
- Sensor fleet MUST include AI-specific slop detectors. Traditional linters miss AI slop.
- AI slop ≠ human error. "We have linter" ≠ "we catch AI slop."
- Slop score = `/goal` convergence metric. "Reduce slop to <N" > "make code better."
- Benchmark against pre-AI mature OSS for fair baseline.
- Cross-language leakage is AI-specific. AI mixes 6+ langs.
- Hallucinated imports = highest-severity slop (20% non-existent → `ImportError`). Detect at CI.
- Placeholder code (`pass`, `TODO`) = AI gave up. Worse than no function. Flag all.
- Hedging comments = AI uncertainty. `# should work hopefully` → human review signal.
- Explanation bloat = restating code. `# loop through items` above `for x in items:` = zero info, consumes tokens, rots when code changes. Detect: comment text ≈ code semantics (arXiv 2605.02741).
- Version stacking = context rot in-file. `<!-- v2 -->`, `# v3 fixed X`, `<!-- updated 2026-07-15 -->` accumulated. Version truth = git + append-only `CHANGELOG.md`. `scripts/sync.py --canon` rejects canon with stacked headers.

---

## Verbatim Execution Gates (Fable-Method)

Models leave named lines verbatim in report when condition holds. Missing owed line = skipped step.

| Gate | When | Verbatim Line Owed | Prevents |
|------|------|-------------------|----------|
| **INTENT** | Before behavior-changing edit | `INTENT: code does <X>; failing check expects <Y>; spec says <Z>` | Editing wrong side of spec-vs-test-vs-code |
| **AUTH** | Before irreversible/outward action | `AUTH: user said "<exact words>"` | Acting on docs not authorization |
| **TWINS** | When defect fixed | `TWINS: searched <pattern> - found <N> other sites: <files or "none">` | Completeness fraud: "fixed it" no search elsewhere |
| **PENDING** | Prescribed follow-up not taken | `PENDING: <action> - awaiting your authorization` | Silently skipping/taking prescribed follow-up |
| **RECALL** | Before first use of unopened this session | Stop and open source. If none reachable → label `memory, unverified` | Invented APIs/fabricated config/stale prices |

**Authority order**: User statement > spec > tests > current code behavior. "Fix the code" NOT statement of intent.

**Hard bounds**:
- 3 failed fix-verify cycles same issue → stop, report tried/output/hypothesis
- 2 fruitless lookups → stop. 3rd needs stated reason.
- Cannot name verification → ask pointed question (states recommended interpretation)

**Artifact gate** (last sweep before sending report):
- Behavior changed no `INTENT:` → add
- Outward action no `AUTH:` → add
- Defect fixed no `TWINS:` → add
- Follow-up untaken no `PENDING:` → add
- Claim about API/config/figure used w/o source no `memory, unverified` → add label or open source

**Rules**:
- Every owed line MUST appear verbatim. Paraphrase = skipped step.
- Documentation ≠ authorization. AUTH gate core.
- Completeness claim no search = costume failure. TWINS with `none` = honest; no TWINS = fraud.
- Gates compose with maker≠checker. Maker leaves lines; `fable-judge` verifies lines match reality.
- Gates don't replace judgment. They make judgment auditable.
- Recall gate = anti-hallucination. INTENT aligns code/check/spec; RECALL prevents fabricating building blocks.
- Fit gate runs once before loop. Five gates run during loop.

---

## In This Harness
- `.devin/canon/VERIFICATION_PROTOCOL.md` — rule shipped to every tool
- `.devin/agents/workers/VERIFIER.md` — Verifier worker (fresh context, checklist)
- `.devin/agents/workers/AUDITOR.md` — Auditor worker (fresh context, adversarial)
- `.devin/skills/fable-judge.md` — adversarial "done" gate; re-runs verifications, hunts frauds, sweeps gate lines
- `.devin/skills/harness-sensor.md` — computational sensor (deterministic checks)
- `tools/verify-workspace.ps1` — workspace integrity verification (read-back after patch)

---

## The Honest Limit
Verification confirms: file exists, build passes, criteria met, marker present. **Cannot confirm**: design good, taste right, best choice among valid options. Escalate to human. Not failure — honest clause.

---

## U25: Nuwa ROI Measurement

**Problem**: Nuwa cognitive verification expensive. Without ROI, can't justify cost or know when to reduce.

**Metrics in session_state**:
```json
{
  "nuwa_metrics": {
    "nuwa_runs": 0, "nuwa_bugs_caught": 0, "nuwa_token_cost": 0,
    "standard_runs": 0, "standard_bugs_caught": 0, "standard_token_cost": 0,
    "last_nuwa_run": "", "last_standard_run": ""
  }
}
```

**ROI formula**:
- `bugs_per_10k_tokens = bugs_caught / (token_cost / 10000)`
- `nuwa_roi = nuwa_bugs_per_10k / standard_bugs_per_10k`
- If `nuwa_roi < 3.0` → reduce Nuwa to high-stakes only
- Minimum 20 runs before meaningful

**Usage**:
```bash
# Record Nuwa run
.venv/bin/python .devin/scripts/nuwa_roi.py --session <sid> --record-nuwa --bugs 3 --tokens 5000
# Record standard run
.venv/bin/python .devin/scripts/nuwa_roi.py --session <sid> --record-standard --bugs 1 --tokens 1500
# Get report
.venv/bin/python .devin/scripts/nuwa_roi.py --session <sid> --report
# Reset
.venv/bin/python .devin/scripts/nuwa_roi.py --session <sid> --reset
```

**Threshold**: 3.0x — Nuwa must catch 3x more bugs per 10K tokens than standard review.