# EXECUTION ROOT CAUSE ANALYSIS (5 Whys) — Iteration 4

---

## EXEC-01: Redis Backend Deployment Failure

| Why Level | Analysis |
|-----------|----------|
| **1. Why** does Redis deployment fail silently? | Deployment script doesn't validate Redis health before flipping feature flag |
| **2. Why** no validation? | "Infrastructure as code" assumed to work; no contract between deploy and app |
| **3. Why** no contract? | "Redis is infrastructure" mindset; app assumes infrastructure works |
| **4. Why** no contract enforcement? | No deployment-time contract verification; feature flags used as safety net instead |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Deployment-Time Contract Verification** — the application has no mechanism to verify its runtime dependencies (Redis, PostgreSQL, etc.) meet their contracts before accepting traffic. Feature flags are runtime, not deploy-time. |

**Classification**: **[STRUCTURAL]** — Requires Deployment-Time Contract Verification

---

## EXEC-02: EventStore Migration Data Loss

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can migration lose data? | Migration script crashes mid-way, no checkpoint/resume |
| **2. Why** no checkpoint? | "One-shot migration" assumption; didn't anticipate failures |
| **3. Why** no failure anticipation? | Migration tested only on clean/small datasets; not chaos-tested |
| **4. Why** not chaos-tested? | "Migration is one-time" mindset; no investment in migration robustness |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Migration Resilience Pattern** — migrations are treated as one-off scripts, not production-grade pipelines with checkpoints, idempotency, and rollback. |

**Classification**: **[STRUCTURAL]** — Requires Migration Pipeline with Checkpoints

---

## EXEC-03: Dual-Write Adapter Race Conditions

| Why Level | Analysis |
|-----------|----------|
| **1. Why** do dual-writes diverge? | Two separate write operations without atomic coordination |
| **2. Why** no atomic coordination? | Each store has independent API; no distributed transaction manager |
| **3. Why** no distributed transactions? | "Dual-write is simple enough" assumption; saga pattern seen as over-engineering |
| **4. Why** saga seen as over-engineering? | Original dual-write was "write to both, hope for best"; no saga implementation |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Transactional Migration Abstraction** — dual-write is implemented as two independent writes with hope, not as a coordinated saga with compensating transactions. |

**Classification**: **[STRUCTURAL]** — Requires Saga Pattern Migration Coordinator

---

## EXEC-04: Blocking I/O in Async Runtime

| Why Level | Analysis |
|-----------|----------|
| **1. Why** does blocking I/O starve event loop? | Runner functions use synchronous libraries (`httpx.get()`, `subprocess.run()`) |
| **2. Why** synchronous libraries? | Easier to write; async versions not available for all tools; legacy code |
| **3. Why** not wrapped in thread pool? | Migration focused on "async graph" not "async execution"; assumed runners already async |
| **4. Why** assumed runners async? | Original `dag_executor` used ThreadPoolExecutor (blocking OK there) |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Blocking I/O Boundary** — the async runtime doesn't enforce "no blocking calls in event loop"; it's a convention not enforced by architecture. |

**Classification**: **[STRUCTURAL]** — Requires Blocking Call Isolation (mandatory `to_thread`)

---

## EXEC-05: FanOut Resource Exhaustion

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can FanOut spawn unlimited parallel nodes? | No cardinality limit on FanOutEdge targets |
| **2. Why** no limit? | LangGraph doesn't enforce by default; assumed tasks self-limit |
| **3. Why** assumed self-limit? | Original FSM had fixed 8 SCOUTs; dynamic graph removes this constraint |
| **4. Why** constraint removed? | Dynamic graph designed for flexibility; didn't anticipate malicious/erroneous input |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Resource Quota in Graph Engine** — the graph engine has no concept of resource budgets (parallelism, tokens, cost); it executes whatever the graph defines. |

**Classification**: **[STRUCTURAL]** — Requires Resource Quota System

---

## EXEC-06: SubGraph State Isolation Failure

| Why Level | Analysis |
|-----------|----------|
| **1. Why** does SubGraph modify parent state? | State passed by reference (same object) |
| **2. Why** pass by reference? | Performance; copying large state is expensive |
| **3. Why** not copy? | Optimization; assumed subgraphs only read or explicitly return updates |
| **4. Why** assumed read-only? | Original FSM had no subgraphs; no precedent for isolation |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No State Ownership Model** — the graph engine has no formal ownership/permission model for state; any node can mutate any field. |

**Classification**: **[STRUCTURAL]** — Requires State Ownership + Copy-on-Write

---

## EXEC-07: Backend Behavior Leakage

| Why Level | Analysis |
|-----------|----------|
| **1. Why** does code behave differently on Redis vs FileBackend? | Interface doesn't specify consistency guarantees per operation |
| **2. Why** no consistency spec? | Interface designed for "key-value store" not "distributed state store" |
| **3. Why** not specify? | FileBackend was only implementation; Redis added later without contract update |
| **4. Why** contract not updated? | "It works on both" assumption; no multi-backend testing |
| **5. Why** does this persist? | **[STRUCTURAR ROOT CAUSE]**: **No Consistency Contract in Interface** — the StateStore ABC doesn't define consistency levels per method (strong/eventual), so implementations diverge. |

**Classification**: **[STRUCTURAL]** — Requires Consistency Contract in ABC

---

## EXEC-08: Agent Registry Capability Tampering

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can YAML files be modified at runtime? | Registry loads from filesystem; no integrity verification |
| **2. Why** no integrity verification? | Registry designed for development flexibility; git-tracked but not enforced |
| **3. Why** filesystem-based? | Simplicity; YAML files easy to edit; no DB required |
| **4. Why** no signature verification? | "Trusted environment" assumption; dev machines considered trusted |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Supply Chain Integrity for Definitions** — capability definitions are treated as config not code; no signing, no verification, no allowlist. |

**Classification**: **[STRUCTURAL]** — Requires Signed Manifest + Immutable Definitions

---

## EXEC-09: Cost Budget Race Condition

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can two tasks both pass budget check? | Check-then-reserve not atomic |
| **2. Why** not atomic? | TokenBudget.reserve() does check then set; no lock around check+set |
| **3. Why** no lock? | "Budget check is fast" assumption; didn't anticipate concurrent tasks |
| **4. Why** not anticipate? | Original ThreadPoolExecutor had implicit serialization; async removes it |
| **5. Why** does this persist? | **[MECHANICAL ROOT CAUSE]**: **No Atomic Budget Primitive** — budget management is a check-then-act pattern, not a reservation system. **ALREADY FIXED** in TokenBudget (atomic reserve under lock). |

**Classification**: **[MECHANICAL]** — **ALREADY FIXED** in TokenBudget

---

## EXEC-10: Agent Registry Poisoning

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can fake agent be registered? | Registry loads all YAML in directory; no allowlist |
| **2. Why** no allowlist? | Dynamic discovery was a feature; "drop YAML to add agent" |
| **3. Why** dynamic discovery? | Flexibility for developers; no central registration process |
| **4. Why** no central process? | "Move fast" culture; no agent onboarding workflow |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Agent Identity Authority** — agent identity is file-based not cryptographically verified; no central registry authority. |

**Classification**: **[STRUCTURAL]** — Requires Signed Manifest + Identity Authority

---

## EXEC-11: Supply Chain Integrity

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can malicious package execute code? | `pip install` runs arbitrary code (setup.py, pyproject.toml) |
| **2. Why** no verification? | `pip install` doesn't verify signatures by default |
| **3. Why** no signatures? | PyPI doesn't require signing; ecosystem standard is trust-on-first-use |
| **4. Why** no pinned hashes? | "Convenience" — pinned hashes break on dependency updates |
| **5. Why** does this persist? | **[MECHANICAL ROOT CAUSE]**: **No Supply Chain Integrity Pipeline** — no `pip install --require-hashes`, no cosign verification, no SBOM enforcement in CI. |

**Classification**: **[MECHANICAL]** — Requires Supply Chain Pipeline

---

## EXEC-12: Cross-Component Consistency

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can Graph Engine read stale approval from StateStore replica? | Graph Engine uses StateStore adapter; doesn't specify read consistency |
| **2. Why** no consistency spec? | StateStore adapter doesn't expose consistency level choice |
| **3. Why** no consistency choice? | StateStore ABC doesn't define consistency levels |
| **4. Why** not in ABC? | "Eventual is fine" assumption; critical reads not identified |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Cross-Component Consistency Contract** — components don't declare their consistency requirements; no system-wide consistency model. |

**Classification**: **[STRUCTURAL]** — Requires System-Wide Consistency Model

---

## META ROOT CAUSE: "Execution as Afterthought"

All 12 execution root causes share a meta-pattern:

| Pattern | Manifestation |
|---------|---------------|
| **Treating execution as feature not architecture** | Migration execution layer added on top, not designed into components |
| **No execution-specific threat model** | Red team only on production, not migration window |
| **Assuming "dual-write = consistency"** | Dual-write is a pattern, not a guarantee |
| **No execution observability** | No diff tools, no parity metrics, no rollback triggers |
| **Feature flags as safety net** | Flags used for rollout, not for isolation |

**Meta Root Cause**: **Execution is not a first-class architectural concern** — it's treated as a deployment detail, not a distinct phase with its own invariants, threat model, and verification criteria.

---

## RISK MATRIX (Execution Root Causes)

| | CRITICAL | HIGH | MEDIUM |
|---|---|---|---|
| **HIGH LIKELIHOOD** | EXEC-01, EXEC-04 | EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06, EXEC-07, EXEC-08, EXEC-12 | EXEC-09 |
| **MEDIUM LIKELIHOOD** | | EXEC-11 | |

**Key Insight**: Unlike Iteration 1 (mechanical CVEs with known fixes), Iteration 4's execution risks are **architectural** — they require new abstractions (Deployment Contract Verification, Migration Pipeline, Saga Coordinator, Blocking Call Isolation, Resource Quota System) not just patches.

---

*Next: Phase 3 — Execute EventStore Migration (Session/Plan/Execution)*