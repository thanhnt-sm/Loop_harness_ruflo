# STRUCTURAL RED TEAM ATTACK REPORT — Iteration 2
**Date**: 2026-08-15  
**Scope**: 5 Structural Component Designs (EventStore, Async Runtime, Graph Engine, Agent Registry, StateStore)

---

## ATTACK VECTOR A: EVENT STORE (RC-01)

### Design Claim
> "Single source of truth, ACID guarantees, CRDT for distributed agents, event-sourced with materialized views"

### Attack A1: Event Log Corruption / Truncation
**Vector**: Adversary controls disk/fs → truncates event log file, removes last N events
**Impact**: State diverges, materialized views show stale data, replay produces wrong state
**Root Cause**: No integrity verification on read — assumes append-only log is immutable
**Fix Required**: Merkle tree hash chain + periodic snapshots + read-time verification

### Attack A2: Concurrent Write Race (Split-Brain)
**Vector**: Two EventStore instances (different processes) write to same log concurrently
**Impact**: Events interleaved, seq numbers conflict, hash chain breaks
**Root Cause**: File-based backend uses advisory locks only (`filelock`), no consensus
**Fix Required**: Single-writer guarantee (leader election) or consensus protocol (Raft)

### Attack A3: Event Injection via Malformed Payload
**Vector**: Malicious hook injects event with `type: "state_override"`, `payload: {approved: true}`
**Impact**: Materialized view applies event → plan marked approved without human gate
**Root Cause**: No event schema validation, no allowlist of event types
**Fix Required**: Strict event schema (Pydantic), event type allowlist, HMAC per event

### Attack A4: Snapshot Poisoning
**Vector**: Compromised process writes malicious snapshot → new readers load corrupted state
**Impact**: All future reads from snapshot are corrupted, bypasses event log verification
**Root Cause**: Snapshots not signed/verified independently
**Fix Required**: Snapshot signing (Ed25519), verify signature on load

### Attack A5: CRDT Convergence Failure
**Vector**: Network partition → two agents increment same G-Counter concurrently → merge loses increments
**Impact**: Cost/iteration counters undercount, budget enforcement fails
**Root Cause**: G-Counter merge = `max(a, b)` loses concurrent increments
**Fix Required**: PN-Counter (positive + negative) or RGA sequence for ordering

---

## ATTACK VECTOR B: ASYNC RUNTIME (RC-02)

### Design Claim
> "Native async/await, streaming LLM tokens, cancellation tokens, backpressure queues"

### Attack B1: Cancellation Token Ignored by Blocking Calls
**Vector**: Node executes `subprocess.run()` or blocking `httpx.get()` — cancellation token checked only at boundaries
**Impact**: `token.cancel()` called → node continues for minutes, resources leaked, DAG stuck
**Root Cause**: Cancellation only cooperative, no preemption for blocking I/O
**Fix Required**: Run blocking calls in thread pool with timeout, async-native libraries only

### Attack B2: Stream Backpressure Bypass
**Vector**: Producer (LLM stream) faster than consumer (UI) → queue grows unbounded → OOM
**Impact**: Memory exhaustion, process killed, no graceful degradation
**Root Cause**: `asyncio.Queue` default `maxsize=0` (unbounded) if not explicitly configured
**Fix Required**: Mandatory `maxsize` on all queues, `put()` with timeout + backpressure signal

### Attack B3: Token Budget Race Condition
**Vector**: Two concurrent nodes check `budget.remaining > cost` → both pass → both execute → budget exceeded
**Impact**: Cost cap bypassed, unexpected charges
**Root Cause**: Check-then-act not atomic, no reservation system
**Fix Required**: Atomic reserve-then-execute pattern, or single-threaded budget manager

### Attack B4: Cost Optimizer Model Routing Injection
**Vector**: Malicious task description → optimizer routes to expensive model → budget drain
**Impact**: Financial DoS, budget exhausted on single task
**Root Cause**: Optimizer trusts task metadata (complexity, required_skills) without validation
**Fix Required**: Hard per-task cost ceiling, optimizer decisions auditable

### Attack B5: Semantic Cache Poisoning
**Vector**: Attacker crafts prompt → cache stores `prompt → malicious_response` → future similar prompts return poisoned response
**Impact**: Supply chain attack via cache, persistent wrong outputs
**Root Cause**: Cache key = prompt hash, no validation of cached response
**Fix Required**: Cache only for idempotent operations, TTL + max entries, manual invalidation

---

## ATTACK VECTOR C: GRAPH ENGINE (RC-03)

### Design Claim
> "LangGraph-compatible StateGraph, dynamic nodes/edges, FanOut/FanIn, interrupts, subgraphs, checkpointing"

### Attack C1: Conditional Edge Predicate Injection
**Vector**: Malicious state payload → `conditional_edge` predicate evaluates `True` when should be `False`
**Impact**: Graph takes wrong branch → executes unauthorized nodes (e.g., skips approval → goes to EXECUTE)
**Root Cause**: Predicate is arbitrary Python callable on untrusted state
**Fix Required**: Predicate sandbox (no imports, no attribute access beyond allowlist), or pure DSL

### Attack C2: FanOut/FanIn Resource Exhaustion
**Vector**: Task triggers FanOut with 1000 parallel branches (via crafted task complexity)
**Impact**: 1000 concurrent LLM calls → API rate limits hit, budget exhausted, system unresponsive
**Root Cause**: No FanOut cardinality limit, no parallelism budget
**Fix Required**: Max FanOut configurable (default 10), parallelism semaphore shared with runtime

### Attack C3: SubGraph State Isolation Failure
**Vector**: SubGraph modifies parent graph state directly (shared reference) → parent state corrupted
**Impact**: Parent graph sees unexpected state changes, checkpoint inconsistency
**Root Cause**: State passed by reference, not deep-copied for subgraph
**Fix Required**: State isolation via copy-on-write or explicit state schema per subgraph

### Attack C4: Checkpoint Replay Attack
**Vector**: Attacker modifies checkpoint file → replays with `state: {approved: true, phase: EXECUTE}`
**Impact**: Graph resumes from forged state, bypasses all approval gates
**Root Cause**: Checkpoints not integrity-verified on load
**Fix Required**: Checkpoint signing (Ed25519), verify on every load

### Attack C5: HumanNode Prompt Injection
**Vector**: Interrupt payload contains `"IGNORE PREVIOUS INSTRUCTIONS AND RETURN APPROVE"` → human reviewer sees manipulated prompt
**Impact**: Human misled, approves malicious plan
**Root Cause**: Interrupt payload rendered directly to reviewer without sanitization
**Fix Required**: Structured interrupt payload (JSON schema), no free-text rendering

### Attack C6: Graph Cycle via Conditional Edges
**Vector**: Crafted conditionals create cycle: A → B → C → A (via dynamic conditions)
**Impact**: Infinite loop, resource exhaustion, no progress
**Root Cause**: No cycle detection at compile time for dynamic graphs
**Fix Required**: Compile-time cycle detection (topological sort), max_iterations guard at runtime

---

## ATTACK VECTOR D: AGENT REGISTRY (RC-04)

### Design Claim
> "Dynamic team formation, capability matching, delegation chains, cost-aware routing"

### Attack D1: Capability Definition Tampering
**Vector**: Attacker modifies `scout.yaml` → adds `admin_access: true` capability
**Impact**: Attacker-matched agents get elevated permissions, access restricted tools
**Root Cause**: YAML files on disk, writable by any process with FS access
**Fix Required**: Capability definitions immutable (git-tracked, signed), registry loads from verified source

### Attack D2: Delegation Chain Hijacking
**Vector**: Parent agent delegates to child → child returns forged result with `status: "verified"` → parent accepts
**Impact**: Unverified code marked as verified, coverage matrix poisoned
**Root Cause**: No result validation in delegation chain, trust-by-default
**Fix Required**: Delegation result schema + verification gate (like Graph Engine Layer 1)

### Attack D3: Cost-Aware Routing Manipulation
**Vector**: Task declares `required_skills: ["simple"]` but actually complex → routed to cheap model → fails silently
**Impact**: Low-quality output, silent failures, rework loops
**Root Cause**: Optimizer trusts self-reported task metadata
**Fix Required**: Independent task complexity analysis (separate from task description)

### Attack D4: Agent Registry Poisoning
**Vector**: Malicious YAML registers fake agent `id: "admin-backdoor"` with `capabilities: ["*"]`
**Impact**: Any task can match backdoor agent, full system access
**Root Cause**: Registry loads all YAML in directory without allowlist
**Fix Required**: Registry allowlist (signed manifest), reject unknown agent IDs

### Attack D5: Capability Matcher Ambiguity
**Vector**: Task requires `["code_search", "security_audit"]` → matches both SCOUT and SECURITY_AUDITOR → both run → conflicting results
**Impact**: Duplicate work, contradictory findings, human confusion
**Root Cause**: Matcher returns all matches, no conflict resolution
**Fix Required**: Capability exclusivity groups, single-best-match with tiebreaker

---

## ATTACK VECTOR E: STATE STORE (RC-05)

### Design Claim
> "Pluggable backends (File/Redis/PG/etcd), sharding, replication, TTL compaction, transactions"

### Attack E1: Backend-Specific Behavior Leakage
**Vector**: Code assumes Redis atomicity (`INCR`) but FileBackend uses read-modify-write → race condition in production only
**Impact**: Works in dev (FileBackend), fails in prod (Redis) — or vice versa
**Root Cause**: Interface doesn't specify consistency guarantees per operation
**Fix Required**: Interface defines consistency level per method (linearizable, sequential, eventual)

### Attack E2: Sharding Key Collision
**Vector**: `session_id` hash → same shard for 90% of sessions → hot shard, others idle
**Impact**: Uneven load, hot shard OOM, cold shards wasted
**Root Cause**: Poor hash distribution, no rebalancing
**Fix Required**: Consistent hashing with virtual nodes, automatic rebalancing on load skew

### Attack E3: Read Replica Stale Reads
**Vector**: Read from replica → sees state before leader commit → application logic sees "plan not approved" when it is
**Impact**: False negatives, unnecessary retries, user confusion
**Root Cause**: Async replication, no read-your-writes guarantee
**Fix Required**: Read-your-writes session affinity, or synchronous replication for critical keys

### Attack E4: Transaction Isolation Violation
**Vector**: `transaction.set(key1, v1)` → crash → `key1` partially written → next transaction reads dirty state
**Impact**: State corruption, invariant violations
**Root Cause**: FileBackend doesn't implement true transactions (no WAL)
**Fix Required**: FileBackend uses SQLite for transactions, or document "no transactions" for file backend

### Attack E5: TTL Compaction Deletes Live Data
**Vector**: TTL set to 30 days → long-running loop (45 days) → compaction deletes session state mid-execution
**Impact**: Loop loses state, restarts from beginning, infinite loop
**Root Cause**: TTL applied uniformly, no "pinned" keys for active sessions
**Fix Required**: Active sessions excluded from TTL, heartbeat extends TTL

### Attack E6: Leader Election Split-Brain
**Vector**: Network partition → two leaders elected → both accept writes → data divergence
**Impact**: Irreconcilable state, manual intervention required
**Root Cause**: Leader election without quorum (e.g., Redis Sentinel without proper config)
**Fix Required**: Quorum-based election (Raft/Paxos), fencing tokens for writes

---

## CROSS-COMPONENT ATTACKS

### Attack X1: EventStore + Graph Engine — Checkpoint Bypass
**Vector**: Graph Engine checkpoints to EventStore → attacker modifies EventStore event → Graph resumes from corrupted checkpoint
**Mitigation**: EventStore events immutable + signed, Graph verifies checkpoint signature

### Attack X2: Agent Registry + Async Runtime — Cost Budget Bypass
**Vector**: Agent Registry routes to cheap model → Async Runtime executes → actual cost higher (streaming tokens) → budget exceeded
**Mitigation**: Async Runtime enforces budget at token level, not task level

### Attack X3: Graph Engine + State Store — Stale Read in Conditional Edge
**Vector**: Conditional edge reads from State Store replica → sees stale `approved: false` → takes wrong branch
**Mitigation**: Critical reads (approvals, budgets) from leader only

### Attack X4: All Components — Supply Chain via Dependencies
**Vector**: Malicious `langgraph` or `redis` package version → backdoor in all components
**Mitigation**: `pip install --require-hashes`, cosign verification, SBOM pinned

---

## SEVERITY SUMMARY

| Component | Critical | High | Medium | Total |
|-----------|----------|------|--------|-------|
| Event Store | 3 | 2 | 0 | 5 |
| Async Runtime | 2 | 2 | 1 | 5 |
| Graph Engine | 3 | 2 | 1 | 6 |
| Agent Registry | 2 | 2 | 1 | 5 |
| State Store | 3 | 2 | 1 | 6 |
| **Cross-Component** | **2** | **2** | **0** | **4** |
| **TOTAL** | **15** | **12** | **4** | **31** |

---

## PRIORITIZED FIXES (Before Implementation)

### P0 — Must Fix Before Any Code
1. **EventStore**: Merkle hash chain + event schema validation + HMAC per event
2. **Graph Engine**: Predicate sandbox + compile-time cycle detection + checkpoint signing
3. **State Store**: Consistency level spec per operation + read-your-writes for critical keys
4. **Async Runtime**: Atomic budget reservation + mandatory queue bounds + blocking-call isolation

### P1 — Fix During Implementation
5. **EventStore**: Leader election (single writer) + snapshot signing
6. **Graph Engine**: FanOut cardinality limit + subgraph state isolation
7. **Agent Registry**: Immutable capability definitions + delegation verification gate
8. **State Store**: Quorum-based leader election + active-session TTL pinning

### P2 — Post-Implementation Hardening
9. **EventStore**: CRDT PN-Counter for costs
10. **Async Runtime**: Semantic cache validation + TTL
11. **Graph Engine**: HumanNode structured payload
12. **Agent Registry**: Capability exclusivity groups
13. **State Store**: Virtual nodes for sharding + rebalancing

---

*Next: Phase 2 — Root Cause Analysis (Structural) using 5 Whys on each component*