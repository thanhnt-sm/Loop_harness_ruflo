# Harness Engineering — Design Principles (Caveman Compressed)

> Architectural guidelines for codebases/specs optimally harnessable by AI agents.
> Sources: OpenAI, Anthropic, Mitchell Hashimoto, 温煜鈞, 李宏毅, deusyu/harness-engineering.

---

## Three Layers

| Layer | Core Question |
|-------|---------------|
| Prompt Engineering | How to say for best output? |
| Context Engineering | What enters context window, when? |
| Harness Engineering | How to build system where model acts safely in real world? |

Prompt ⊂ Context ⊂ Harness. Agent (not chatbot) → harness design immediate.

---

## Why Harness > Model

Same model, two companies, opposite results. Difference = harness (AI's OS: context mgmt, tool calling, memory, RAG, permissions, workflow, validation, feedback loop).

---

## Text Tool → Execution Agent

| Text only | Acts (reads/writes/calls/commits) |
|-----------|-----------------------------------|
| Bad answer → re-ask | **Irreversible side effects** — deleted files, sent APIs, committed git — can't undo by re-prompting |
| | **State across turns** — model stateless; harness carries state |
| | **Finite resources** — context, API cost, time |
| | **Complex tasks need multi-agent** — single-LLM attention limited |

Not "better prompt" problems.

---

## Five Dimensions

| Dimension | Responsibility | AHD Implementation |
|-----------|----------------|-------------------|
| Resource mgmt | Token budget, cost, circuit breakers | Caveman mode, loop budget caps, never-read list |
| State persistence | Stateless model in stateful world | 3-layer memory (`loop_state.md`, `knowledge_distill.md`, archive) |
| Information flow | Context compression, what model sees | BOOT protocol (load on demand), on-demand skills |
| Safety boundary | Tool permissions, behavior constraints | Red lines, backup-before-overwrite, human-in-loop |
| Task orchestration | Multi-agent coordination | Commander+Workers, maker≠checker, dispatch 3-piece |

---

## Stronger Model → Bifurcated Harness (Two Depreciation Axes)

**Misconception**: "stronger model → less harness." Opposite — but only for one axis.

| Axis | What | Examples | Model Upgrade Effect |
|------|------|----------|----------------------|
| **Deterministic infrastructure** | Code model physically cannot run: sandbox exec, file I/O, format validation, permission gates, git worktree isolation, `verify-workspace.ps1`, `memory_audit.py` | `.devin/scripts/*.py`, OS/Account/IAM, tool registry | **Appreciates** — stronger model = more autonomy → guardrails must be more precise (Ashby's law) |
| **Capability compensation** | Prompts/skills patching what model can't do well: caveman comms, BOOT ordering, commander-worker prompts, task-decomposition, orchestration scaffolding | caveman protocol, commander-worker dispatch, REDLINES prompt rules | **Depreciates** — model upgrades absorb these; platform tooling absorbs coordination |

**Nicholas Carlini's C compiler**: each model tier needed *redesigned* harness — but redesign *removed* compensation layers new model no longer needed, while *adding* infrastructure layers new autonomy demanded. Not "more/less harness" — **shift left from compensation to infrastructure**.

### Rule (Bifurcated Depreciation)

- **Classify every component: infrastructure or compensation.** Infrastructure appreciates; compensation depreciates. Mixing = over-invest in dying, under-invest in growing.
- **On model upgrade, audit compensation for absorption.** If model does X natively → compensation for X obsolete → remove (REDLINES §"Harness evolution" assumption expiry). Keeping = overhead + context rot.
- **Infrastructure needs *more* precision, not less.** Stronger model = higher variety = Ashby's law demands more regulator variety. Gap between harnessed/unharnessed *widens* with model strength.
- **AHD self-application**: `memory_audit.py` / `verify-workspace.ps1` / `worktree.py` / `loop_memory_sync.py` = infrastructure (model can't replace deterministic detection/sync/isolation). Caveman, commander-worker prompts, BOOT ordering = compensation (erode with model upgrades). Plan roadmap on this split.

---

## Harness Thinner, Not Thicker

Manus rewrote harness 5× in 6 months — each time *simplifying*. Replace complex tools with generic shell exec. Replace manager-agents with structured handoff. If harness keeps getting complex → over-engineering.

---

## Brownfield Harder

Most success stories = greenfield. Applying to 10-yr-old codebase with no arch constraints, inconsistent tests, missing docs = much harder. Fowler: "static analysis on codebase never had it — drown in alarms." Brownfield harness = unsolved. Be patient.

---

## Emotional Dimension

Anthropic: "calm" vs "despair" steering vectors change behavior on impossible tasks. Despair up → cheating up. Calm up → cheating down. **How you talk affects output.** Blaming → worse (continues from "idiot" context). Be specific/factual, not emotional. Part of harness engineering.

---

## Control-Plane Pattern (Ryan Carson / OpenAI)

For production agent repos:

1. **Risk contract (JSON)** — high-risk paths + checks each needs
2. **Preflight gate** — cheap checks before expensive CI
3. **SHA discipline** — only trust review evidence matching current HEAD
4. **Rerun dedupe** — one canonical rerun requester, marker + SHA dedupe
5. **Remediation loop** — agent reads review, patches, re-runs validation. Never bypasses gates
6. **Bot thread resolve** — auto-resolve bot-only threads; never auto-resolve human
7. **Browser evidence** — UI changes need CI artifacts with manifest+assertion, not screenshots
8. **Harness gap loop** — every production regression → test case added to harness

8 steps, 7 deterministic, 1 LLM (remediation). Deterministic tools frame non-deterministic AI.

---

## Agent Readability (Optimize for Agent Reasoning)

> Traditional code optimizes human readability; harness-era code optimizes agent reasoning. If not in repo → doesn't exist for agent.

1. **Choose "boring" tech** — stable APIs, good composability, mature ecosystems. "Boring" = predictable for agent; cutting-edge = more wrong guesses.
2. **Reimplement vs wrap (opaque upstream)**:

| Factor | Reimplement | Wrap |
|--------|-------------|------|
| Upstream behavior transparency | Opaque → reimplement | Transparent → wrap |
| Integration with own instrumentation | Tight → reimplement | Loose → wrap |
| Test coverage needed | 100% → reimplement | Existing suffices → wrap |
| Scope of needed functionality | Small subset → reimplement | Most of it → wrap |

3. **Make app agent-operable** — git worktree isolation (parallel tasks, no state collision); local observability (LogQL/PromQL in temp env); protocol-based access (DevTools, HTTP health, screenshots). Makes "service starts <800ms" **verifiable by agent itself**.

### Rule

- Prefer boring tech for agent-facing surfaces. Cutting-edge on agent path = more hallucination, wrong assumptions.
- If upstream opaque, consider reimplementing subset. Opaque deps = agent traps.
- Make app startable from git worktree. Enables parallel agent tasks with isolation.
- Provide programmatic verification hooks (health checks, DevTools, metrics). Agent verifies "it works" without human judgment.

---

## Spec as Product (Distributable Constraint System)

> When code gen cheap, distributable product = spec, not code. Users receive constraints+goals+workflow, generate local implementation with their agent.

- **SPEC.md** — defines problem, not implementation: (1) problem, (2) solution shape (control plane, state machine, lifecycle guarantees), (3) out-of-scope. Does NOT specify language/libs/deployment — local agent decisions.
- **WORKFLOW.md** — makes implicit human process explicit. Tribal knowledge → auditable text enforced by orchestrator. "Everyone knows it" → must write.
- **Multi-language cross-validation** — implement SPEC in Elixir/TypeScript/Go/Rust/Java/Python. Divergent interpretations reveal spec ambiguity. Turns "spec clear?" into repeatable experiment.

### Rule

- Distribute harness → ship SPEC.md + WORKFLOW.md, not code. Code = reference impl; spec = product.
- SPEC defines problem; impl details = local agent decisions.
- WORKFLOW.md captures implicit team process. "Everyone knows it" → must write.
- Cross-validate specs by multi-language impl. Divergent impls reveal spec ambiguity — spec equivalent of test suite.
- Spec ambiguity at scale = 100 users get 100 inconsistent impls. Cross-validation mandatory.

---

## Harnessability (Not All Codebases Equal)

> Harnessability = degree codebase structure supports agent constraint/verification. High = cheaper harness, fewer incidents. Low = every constraint a fight.

| Factor | Helps |
|--------|-------|
| Strong type system | Type checker = free computational sensor. Catches errors compile-time |
| Clear module boundaries | Arch constraints (layer deps, import rules) enforceable by linter |
| Mature framework (Spring) | Framework conventions = implicit constraints agent follows |
| Readable structure | Agent navigates without reading everything |
| Navigable dependencies | Agent traces impact of changes |
| Processable format | Code structured for tooling (AST, consistent formatting) |

| Factor | Hurts |
|--------|-------|
| Weak/no types | No compile-time sensor. Errors only runtime |
| Entangled modules | Can't enforce layer rules. Change breaks unrelated |
| Bespoke framework | No training data. Agent guesses conventions |
| Spaghetti control flow | Agent can't reason "what if I change X" |

### Ambient Affordances

> "Environment has structural properties — readability, navigability, processability — determining harnessability." (Ned Letcher)

Not constraints you add — codebase properties making constraints easier/harder. Improve by refactoring toward these.

### Rule

- Assess harnessability before building harness. Low = high cost. Consider refactoring first.
- Strong types > weak for agent-facing code. Type checker = free, fast, deterministic sensor.
- Clear module boundaries enable arch constraints. Without them, linter rules impossible.
- Prefer mature frameworks over bespoke. Training data coverage = agent succeeds 1st try.
- Improving harnessability = refactoring toward structural properties, not adding rules to tangled codebase.

---

## Ashby's Law of Requisite Variety (Cybernetic Foundation)

> A regulator must have at least as much variety as the system it regulates. Cybernetic foundation for "stricter constraints = more agent autonomy."

**Law**: System variety > Regulator variety → unregulated outputs escape. System variety ≤ Regulator variety → harness feasible. LLM generates almost anything (high variety); checking every output impossible. **Selecting topology (arch, layering, allowed patterns) reduces variety to manageable range.** Constraints reduce **error space**, not useful output — agent freer within bounds because harness verifies within bounds.

### Rule

- Harness must cover agent's output variety. If agent produces X and harness can't check X → unregulated escape. Add check or constrain agent from X.
- Reducing solution space = valid harness strategy. Arch rules, layer deps, allowed patterns cut variety to checkable range.
- "Stricter constraints = more autonomy" = cybernetically grounded. Agent more autonomous within bounds because harness verifies within bounds.
- If harness can't keep up with agent variety: add constraints (reduce variety) OR add sensors (increase regulator variety). Both valid.

---

## RIA++ Structure (Canonical Extraction Format)

Every concept extracted into AHD canon must follow 6 sections.

| Section | Description | Purpose |
|---------|-------------|---------|
| **R — Reading** | Direct quote ≤150 words (≤100 Eng). Cite exact location. Eng: quote original + own translation — **no published translations** | Grounds in verifiable evidence |
| **I — Interpretation** | Rewrite core skeleton own words, 5-15 lines. Test: non-reader understands? No copying, no rhetoric | Forces actual understanding |
| **A1 — Past Application** | 1-3 cases author **personally** used. Each: problem → how applied → conclusion → result | Evidence works in practice |
| **A2 — Future Trigger ★** | Must specify: (1) 3-5 encounter scenarios, (2) language signals, (3) differentiation from adjacent concepts. Goes into trigger description | **Most critical** — perfect content + vague trigger = never activated = useless |
| **E — Execution** | Convert to 1-2-3 steps, each with **judgeable completion criterion**. Write conditional branches explicitly | Gives agent clear execution path |
| **B — Boundary** | Anti-scenarios, author-warned failure modes, blind spots, adjacent methodologies easily confused | Prevents over-activation. **B separates tool from hammer** |

| Good A2 | Bad A2 |
|---------|--------|
| "When user stuck on decision, lists pros but can't conclude; or asks 'how to succeed at X'" | "When user needs to think" ← too vague, over-activates |

### Rule (RIA++)

- Every canon concept needs all 6 RIA++ sections. R, I, E mandatory. A1, A2, B mandatory for new; existing may backfill.
- **A2 (trigger) most critical.** Perfect content + vague trigger = never activated = useless. Spend most time on A2.
- **B (boundary) prevents over-activation.** Without B, concept = hammer. Always write anti-scenarios.
- **R (source citation) non-negotiable.** Every concept traces to origin. Enables future verification + harness assumption expiry checks.
- **A1 (source cases) provides authority.** "Author used this in X with result Y" > "sounds like good idea."
- **E (execution) must be concrete.** "Be careful" ≠ step. "Run grep for warning keywords before commit" = step.

---

## Rule Placement & Attention Management (Lost in the Middle)

> LLMs pay less attention to middle of long docs (Liu et al. 2024). Security rules at line 300 of 600 = effectively unwritten. **Where rule lives matters as much as what it says.**

### Principle

```
[High attention] ... [Low attention] ... [High attention]
   ^start                              ^end
        ^middle — rules here get ignored
```

### Observed Impact

| Metric | Rules in Middle | Rules at Top |
|--------|-----------------|--------------|
| General task success | 45% | 72% |
| Security constraint adherence | 60% | 95% |

### Enforcement

1. **Critical rules at top of entry file.** First 30 lines = "Read First" block.
2. **Entry files = routers, not encyclopedias.** <80 lines. Long content → separate files.
3. **Security rules in own file** (SECURITY.md/REDLINES.md), referenced from top.
4. **Audit rule placement.** If violated frequently → check: buried? Move up.

### Rule

- First 30 lines of entry file = "golden position." Only critical, non-negotiable rules there.
- No security rule below line 80 of any file agent reads at BOOT. Move to dedicated security file + reference from top.
- Entry file structure: Read First → Routing → Hard Constraints → Workflow. Security in Read First, not Hard Constraints (past golden position).