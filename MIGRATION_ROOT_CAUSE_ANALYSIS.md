# MIGRATION ROOT CAUSE ANALYSIS (5 Whys) — Iteration 3

---

## MIG-01: Dual-Write Inconsistency (Adapters)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** do dual-writes diverge? | Two separate write operations (EventStore + legacy) with no atomic coordination |
| **2. Why** no atomic coordination? | Each store has its own API; no distributed transaction manager |
| **3. Why** no transaction manager? | Architecture treats stores as independent; migration designed as "dual-write" not "transactional" |
| **4. Why** designed as dual-write? | Simplicity; Strangler Fig pattern typically uses dual-write; assumed low conflict rate |
| **5. Why** does this persist as root cause? | **[STRUCTURAL ROOT CAUSE]**: **No Transactional Migration Abstraction** — dual-write is an implementation pattern, not a guaranteed consistency model. The migration layer lacks a saga/orchestration coordinator that ensures atomicity across heterogeneous stores. |

**Classification**: **[STRUCTURAL]** — Requires Migration Coordinator with saga pattern

---

## MIG-02: Stale Reads During Shadow Mode (Adapters)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** do shadow reads return stale data? | Read replicas (or legacy files) not updated synchronously with primary |
| **2. Why** async replication? | Performance; sync replication adds latency |
| **3. Why** no read-your-writes guarantee? | Migration designed for eventual consistency; didn't identify critical read paths |
| **4. Why** critical paths not identified? | Migration treated as "backend swap" not "consistency boundary change" |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Consistency Contract for Migration** — the migration doesn't define which operations need strong consistency vs eventual. Critical reads (approvals, budgets) need explicit read-your-writes guarantee. |

**Classification**: **[STRUCTURAL]** — Requires Consistency Contract + Read-Your-Writes enforcement

---

## MIG-03: Event Log Mutability During Migration (EventStore)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can event log be modified during migration? | Migration process has write access to event log; no immutable enforcement |
| **2. Why** no immutable enforcement? | EventStore designed for normal operation (append-only); migration is special case |
| **3. Why** migration has write access? | Migration script uses same EventStore.append() API as normal operation |
| **4. Why** use same API? | Code reuse; migration script imports EventStore directly |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Migration-Specific Access Control** — migration runs with same privileges as production; no read-only or write-once enforcement for migration window. |

**Classification**: **[STRUCTURAL]** — Requires Migration Mode (read-only log, write-once)

---

## MIG-04: Blocking I/O in Async Runtime (ThreadPoolExecutor → Async)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** does blocking I/O starve event loop? | Runner functions use synchronous libraries (httpx sync, subprocess.run) |
| **2. Why** synchronous libraries? | Easier to write; async versions not available for all tools; legacy code |
| **3. Why** not wrapped in thread pool? | Migration focused on "async graph" not "async execution"; assumed runners already async |
| **4. Why** assumed runners async? | Original dag_executor used ThreadPoolExecutor (blocking OK there) |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Blocking I/O Boundary** — the async runtime doesn't enforce "no blocking calls in event loop"; it's a convention not enforced by architecture. |

**Classification**: **[STRUCTURAL]** — Requires Blocking Call Isolation (mandatory to_thread)

---

## MIG-05: FanOut Resource Exhaustion (Graph Engine)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can FanOut spawn unlimited parallel nodes? | No cardinality limit on FanOutEdge targets |
| **2. Why** no limit? | LangGraph doesn't enforce by default; assumed tasks self-limit |
| **3. Why** assumed self-limit? | Original FSM had fixed 8 SCOUTs; dynamic graph removes this constraint |
| **4. Why** constraint removed? | Dynamic graph designed for flexibility; didn't anticipate malicious/erroneous input |
| **5. Why** does this persist? | **[STRUCTURAR ROOT CAUSE]**: **No Resource Quota in Graph Engine** — the graph engine has no concept of resource budgets (parallelism, tokens, cost); it executes whatever the graph defines. |

**Classification**: **[STRUCTURAL]** — Requires Resource Quota System in Graph Engine

---

## MIG-06: SubGraph State Isolation Failure (Graph Engine)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** does SubGraph modify parent state? | State passed by reference (same object) |
| **2. Why** pass by reference? | Performance; copying large state is expensive |
| **3. Why** not copy? | Optimization; assumed subgraphs only read or explicitly return updates |
| **4. Why** assumed read-only? | Original FSM had no subgraphs; no precedent for isolation |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No State Ownership Model** — the graph engine has no formal ownership/permission model for state; any node can mutate any field. |

**Classification**: **[STRUCTURAL]** — Requires State Ownership + Copy-on-Write

---

## MIG-07: Backend Behavior Leakage (StateStore)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** does code behave differently on Redis vs FileBackend? | Interface doesn't specify consistency guarantees per operation |
| **2. Why** no consistency spec? | Interface designed for "key-value store" not "distributed state store" |
| **3. Why** not specify? | FileBackend was only implementation; Redis added later without contract update |
| **4. Why** contract not updated? | "It works on both" assumption; no multi-backend testing |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Consistency Contract in Interface** — the StateStore ABC doesn't define consistency levels per method (strong/eventual), so implementations diverge. |

**Classification**: **[STRUCTURAL]** — Requires Consistency Contract in ABC

---

## MIG-08: Capability Definition Tampering (Agent Registry)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can YAML files be modified at runtime? | Registry loads from filesystem; no integrity verification |
| **2. Why** no integrity verification? | Registry designed for development flexibility; git-tracked but not enforced |
| **3. Why** filesystem-based? | Simplicity; YAML files easy to edit; no DB required |
| **4. Why** no signature verification? | "Trusted environment" assumption; dev machines considered trusted |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Supply Chain Integrity for Definitions** — capability definitions are treated as config not code; no signing, no verification, no allowlist. |

**Classification**: **[STRUCTURAL]** — Requires Signed Manifest + Immutable Definitions

---

## MIG-09: Cost Budget Race Condition (Async Runtime)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can two tasks both pass budget check? | Check-then-reserve not atomic |
| **2. Why** not atomic? | TokenBudget.reserve() does check then set; no lock around check+set |
| **3. Why** no lock? | "Budget check is fast" assumption; didn't anticipate concurrent tasks |
| **4. Why** not anticipate? | Original ThreadPoolExecutor had implicit serialization; async removes it |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Atomic Budget Primitive** — budget management is a check-then-act pattern, not a reservation system. |

**Classification**: **[MECHANICAL]** — Already fixed in TokenBudget (atomic reserve)

---

## MIG-10: Agent Registry Poisoning (YAML Tampering)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can fake agent be registered? | Registry loads all YAML in directory; no allowlist |
| **2. Why** no allowlist? | Dynamic discovery was a feature; "drop YAML to add agent" |
| **3. Why** dynamic discovery? | Flexibility for developers; no central registration process |
| **4. Why** no central process? | "Move fast" culture; no agent onboarding workflow |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Agent Identity Authority** — agent identity is file-based not cryptographically verified; no central registry authority. |

**Classification**: **[STRUCTURAL]** — Requires Signed Manifest + Identity Authority

---

## MIG-11: Supply Chain via Dependencies (All Components)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can malicious package execute code? | `pip install` runs arbitrary code (setup.py, pyproject.toml) |
| **2. Why** no verification? | `pip install` doesn't verify signatures by default |
| **3. Why** no signatures? | PyPI doesn't require signing; ecosystem standard is trust-on-first-use |
| **4. Why** no pinned hashes? | "Convenience" — pinned hashes break on dependency updates |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Supply Chain Integrity Pipeline** — no `pip install --require-hashes`, no cosign verification, no SBOM enforcement in CI. |

**Classification**: **[MECHANICAL]** — Requires Supply Chain Pipeline (require-hashes + cosign + SBOM)

---

## MIG-11: Cross-Component Consistency (EventStore + Graph Engine + StateStore)

| Why Level | Analysis |
|-----------|----------|
| **1. Why** can Graph Engine read stale approval from StateStore replica? | Graph Engine uses StateStore adapter; doesn't specify read consistency |
| **2. Why** no consistency spec? | StateStore adapter doesn't expose consistency level choice |
| **3. Why** no consistency choice? | StateStore ABC doesn't define consistency levels |
| **4. Why** not in ABC? | "Eventual is fine" assumption; critical reads not identified |
| **5. Why** does this persist? | **[STRUCTURAL ROOT CAUSE]**: **No Cross-Component Consistency Contract** — components don't declare their consistency requirements; no system-wide consistency model. |

**Classification**: **[STRUCTURAL]** — Requires System-Wide Consistency Model

---

## ROOT CAUSE REGISTER (Migration)

| ID | Root Cause | Type | Severity | Fix |
|----|------------|------|----------|-----|
| **MIG-01** | Dual-Write Inconsistency | STRUCTURAL | CRITICAL | Migration Coordinator (saga pattern) |
| **MIG-02** | Stale Reads in Shadow Mode | STRUCTURAL | HIGH | Consistency Contract + Read-Your-Writes |
| **MIG-03** | Event Log Mutability | STRUCTURAL | HIGH | Migration Mode (read-only log) |
| **MIG-04** | Blocking I/O in Async Runtime | STRUCTURAL | CRITICAL | Blocking Call Isolation (mandatory to_thread) |
| **MIG-05** | FanOut Resource Exhaustion | STRUCTURAL | HIGH | Resource Quota System |
| **MIG-06** | SubGraph State Isolation | STRUCTURAL | HIGH | State Ownership + Copy-on-Write |
| **MIG-07** | Backend Behavior Leakage | STRUCTURAL | HIGH | Consistency Contract in ABC |
| **MIG-08** | Capability Definition Tampering | STRUCTURAL | HIGH | Signed Manifest + Immutable Definitions |
| **MIG-09** | Cost Budget Race | MECHANICAL | MEDIUM | Atomic Budget Primitive (FIXED) |
| **MIG-10** | Agent Registry Poisoning | STRUCTURAL | HIGH | Signed Manifest + Identity Authority |
| **MIG-11** | Supply Chain Integrity | MECHANICAL | HIGH | Supply Chain Pipeline (require-hashes + cosign) |
| **MIG-12** | Cross-Component Consistency | STRUCTURAL | HIGH | System-Wide Consistency Model |

---

## META ROOT CAUSE: "Migration as Afterthought"

All 12 migration root causes share a meta-pattern:

| Pattern | Manifestation |
|---------|---------------|
| **Treating migration as feature not architecture** | Migration layer added on top, not designed into components |
| **No migration-specific threat model** | Red team only on production, not migration window |
| **Assuming "dual-write = consistency"** | Dual-write is a pattern, not a guarantee |
| **No migration observability** | No diff tools, no parity metrics, no rollback triggers |
| **Feature flags as safety net** | Flags used for rollout, not for isolation |

**Meta Root Cause**: **Migration is not a first-class architectural concern** — it's treated as a deployment detail, not a distinct phase with its own invariants, threat model, and verification criteria.

---

## RISK MATRIX (Migration Root Causes)

| | CRITICAL | HIGH | MEDIUM |
|---|---|---|---|
| **HIGH LIKELIHOOD** | MIG-01, MIG-04 | MIG-02, MIG-03, MIG-05, MIG-06, MIG-07, MIG-08, MIG-10, MIG-12 | MIG-09 |
| **MEDIUM LIKELIHOOD** | | MIG-11 | |

**Key Insight**: Unlike Iteration 1 (mechanical CVEs with known fixes), Iteration 3's migration risks are **architectural** — they require new abstractions (Migration Coordinator, Consistency Contract, Resource Quota System) not just patches.

---

*Next: Phase 3 — Research Migration Patterns (industry standards for each root cause)*