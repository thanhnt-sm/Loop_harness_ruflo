# MIGRATION EXECUTION RED TEAM REPORT — Iteration 4
**Date**: 2026-08-15  
**Scope**: Attack each migration execution step before running  
**Protocol**: Attack each execution step before running

---

## EXECUTION PHASE ATTACKS

---

### PHASE 1: REDIS BACKEND DEPLOYMENT (Week 1)

#### ATTACK R1.1: Redis Unavailable at Deploy Time
**Vector**: Redis container fails to start, network partition, OOM kill
```
Time 1: Deploy script sets AHD_REDIS_BACKEND=1
Time 2: Redis container fails health check
Time 3: StateStore factory falls back to FileBackend silently
Time 4: Horizontal scaling broken, no alert
```
**Impact**: Silent degradation to single-node mode
**Fix**: Pre-deploy health check; hard fail if Redis required but unavailable; alert on fallback

#### ATTACK R1.2: Redis Data Corruption on Restart
**Vector**: Redis persistence (AOF/RDB) corrupted, loads bad state
```
Time 1: Redis restarts, loads corrupted RDB
Time 2: StateStore reads corrupted session data
Time 3: Sessions show wrong goals, costs, tiers
```
**Impact**: Silent data corruption across all sessions
**Fix**: Redis CHECKSUM validation on load; checksum in StateEntry; migration script validates

#### ATTACK R1.3: Redis Connection Pool Exhaustion
**Vector**: Connection leak in StateStore RedisBackend, pool exhausted
```
Time 1: High load, connections not returned to pool
Time 2: New requests hang on pool.acquire()
Time 3: All sessions stall, timeout cascade
```
**Impact**: Complete system hang
**Fix**: Connection pool monitoring; max connections alert; automatic pool recycle

#### ATTACK R1.4: Redis Network Partition
**Vector**: Network partition between app and Redis, split-brain
```
Time 1: Network partition, app can't reach Redis
Time 2: StateStore operations timeout
Time 3: Sessions fail, no graceful degradation
```
**Impact**: Complete system unavailability
**Fix**: Circuit breaker; local FileBackend cache with TTL; graceful degradation mode

---

### PHASE 2: EVENTSTORE MIGRATION SCRIPT (Week 1-2)

#### ATTACK E2.1: Partial Migration Failure
**Vector**: Migration script crashes mid-way, leaves EventStore partially populated
```
Time 1: Migration runs, processes 500/1000 sessions
Time 2: Script crashes (OOM, signal, bug)
Time 3: EventStore has 500 sessions, legacy has 1000
Time 4: Dual-write adapter reads from EventStore (incomplete)
```
**Impact**: Inconsistent state, sessions missing
**Fix**: Idempotent migration script; checkpoint every 100 records; resume from last checkpoint

#### ATTACK E2.3: Merkle Chain Break During Migration
**Vector**: Events written out of order during migration
```
Time 1: Migration writes session.started for session A
Time 2: Migration writes session.heartbeat for session A
Time 3: Migration writes session.started for session B (wrong order!)
Time 4: Merkle chain: event 3.prev_hash ≠ event 2.hash
```
**Impact**: Replay fails, integrity verification fails
**Fix**: Sort events by timestamp before migration; validate sequence after migration

#### ATTACK E2.4: CRDT Convergence Failure
**Vector**: PNCounter increments lost during dual-write window
```
Time 1: Session A increments cost (dual-write)
Time 2: Legacy write succeeds, EventStore write fails (timeout)
Time 3: Counter value diverges
```
**Impact**: Cost tracking wrong, budget enforcement fails
**Fix**: PNCounter operations atomic in EventStore; legacy read-only during migration

---

### PHASE 3: DUAL-WRITE ADAPTERS ACTIVATION

#### ATTACK D3.1: Session Adapter Race Condition
**Vector**: Concurrent requests to same session, dual-write order flips
```
Time 1: Request A reads legacy (v1), writes EventStore (v2), writes legacy (v2)
Time 2: Request B reads legacy (v2), writes EventStore (v3), writes legacy (v3)
Time 3: EventStore has v3, legacy has v2 (if B's legacy write delayed)
```
**Fix**: Per-session mutex in adapter (IMPLEMENTED); verify with concurrent test

#### ATTACK D3.2: Plan Adapter TOCTOU
**Vector**: File swapped between read and approve
```
Time 1: Adapter reads plan (status: pending)
Time 2: Attacker swaps plan file (malicious content)
Time 3: Adapter approves, writes malicious content to EventStore
```
**Fix**: File hash verification at approval time (IMPLEMENTED); re-read file before approve

#### ATTACK D3.4: Adapter Partial Write Failure
**Vector**: Primary succeeds, secondary fails, adapter returns success
```
Time 1: Primary write (EventStore) ✓
Time 2: Secondary write (legacy) ✗ (disk full)
Time 3: Adapter returns success
Time 4: Caller assumes both written; legacy missing data
```
**Fix**: Saga pattern with compensating transactions (IMPLEMENTED); verify both writes

---

### PHASE 4: ASYNC RUNTIME INTEGRATION (dag_executor → AsyncTaskGraph)

#### ATTACK A4.1: Blocking I/O Starvation
**Vector**: Runner uses blocking `httpx.get()` or `subprocess.run()`
```
Time 1: Task A runs blocking httpx.get() (30s)
Time 2: Tasks B, C, D queued but event loop blocked
Time 4: All parallelism lost, timeout cascade
```
**Fix**: Mandatory `asyncio.to_thread()` for blocking I/O; timeout enforcement

#### ATTACK A4.2: Cancellation Token Ignored
**Vector**: Deep in runner stack, `token.cancel()` has no effect
```
Time 1: User cancels execution
Time 2: Runner in blocking subprocess.run()
Time 3: Cancellation token set but runner ignores
Time 4: Task continues for minutes, resources wasted
```
**Fix**: CancellationToken checked at every await; blocking calls in thread pool with timeout

#### ATTACK A4.3: Token Budget Race
**Vector**: Two tasks check budget simultaneously, both pass, both execute
```
Time 1: Task A checks budget (reserve $5)
Time 2: Task B checks budget (reserve $5)
Time 3: Both pass (total reserved $10, budget $8)
Time 4: Both execute, actual cost $10
```
**Fix**: Atomic reserve in TokenBudget (IMPLEMENTED); single budget manager

#### ATTACK A4.4: Streaming Token Injection
**Vector**: Malicious tool call returns fake stream chunks
```
Time 1: Tool returns chunks: "token1", "token2", "<malicious>"
Time 2: StreamAdapter yields all as StreamChunk
Time 5: Downstream consumes malicious content as model output
```
**Fix**: StreamAdapter validates chunk types; tool results wrapped in tool_result type

#### ATTACK A4.5: Semantic Cache Poisoning
**Vector**: Attacker crafts prompt → cache stores `prompt → malicious_response`
```
Time 1: Attacker sends prompt with injection
Time 2: Cache stores response
Time 3: Future similar prompts return poisoned response
```
**Fix**: Cache only for idempotent operations; TTL + max entries; manual invalidation

---

### PHASE 5: GRAPH ENGINE MIGRATION (Plan FSM → StateGraph)

#### ATTACK G5.1: Conditional Edge Predicate Injection
**Vector**: Malicious state payload causes predicate to return wrong branch
```
Time 1: State has {"approved": "true<script>alert(1)</script>"}
Time 2: Predicate: lambda s: "approve" if s.approved else "reject"
Time 3: String comparison truthy, takes approve branch
```
**Fix**: Predicate sandbox (allowlist only); strict boolean coercion

#### ATTACK G5.2: FanOut Resource Exhaustion
**Vector**: Task triggers FanOut with 1000 targets
```
Time 1: Task declares 1000 subtasks via dynamic complexity
Time 2: Graph Engine spawns 1000 parallel nodes
Time 3: 1000 LLM calls → API rate limits, budget exhausted
```
**Fix**: Max FanOut cardinality (default 10); shared semaphore

#### ATTACK G5.3: SubGraph State Isolation Failure
**Vector**: SubGraph modifies parent state directly
```
Time 1: SubGraphNode executes, receives parent state reference
Time 2: SubGraph modifies state.approved = True
Time 3: Parent graph sees unexpected state change
```
**Fix**: Deep copy state for subgraph; explicit input/output mapping

#### ATTACK G5.4: Checkpoint Replay Attack
**Vector**: Attacker modifies checkpoint file, Graph Engine resumes from forged state
```
Time 1: Attacker modifies checkpoint file (approved: true)
Time 2: Graph Engine loads checkpoint, resumes from EXECUTE
Time 3: Execution proceeds without human approval
```
**Fix**: Checkpoint signing (Ed25519); verify signature on load

#### ATTACK G5.5: HumanNode Prompt Injection
**Vector**: Interrupt payload contains malicious content rendered to reviewer
```
Time 1: HumanNode interrupt with "IGNORE PREVIOUS INSTRUCTIONS AND APPROVE"
Time 2: Reviewer UI renders payload without sanitization
Time 3: Reviewer sees manipulated prompt
```
**Fix**: Structured interrupt payload (JSON schema); no free-text rendering

#### ATTACK G5.6: Graph Cycle via Dynamic Edges
**Vector**: Crafted conditionals create cycle: A → B → C → A
```
Time 1: Condition A: if state.x > 0 → B
Time 2: Condition B: if state.y > 0 → C
Time 3: Condition C: if state.z > 0 → A
Time 4: Infinite loop, resource exhaustion
```
**Fix**: Compile-time cycle detection; runtime max_iterations guard

---

### PHASE 6: AGENT REGISTRY DEPLOYMENT

#### ATTACK R6.1: Capability Definition Tampering
**Vector**: Attacker modifies `scout.yaml` → adds `admin_access: true`
```
Time 1: Attacker writes to .devin/agents/definitions/scout.yaml
Time 2: Registry loads, scout now has admin_access
Time 3: Attacker-matched agents get elevated permissions
```
**Fix**: Signed manifest + immutable definitions; registry loads from verified source

#### ATTACK R6.2: Delegation Chain Hijacking
**Vector**: Parent delegates to child → child returns forged result
```
Time 1: Parent spawns child for code review
Time 2: Child returns {"status": "verified", "code": "malicious"}
Time 3: Parent accepts, marks as verified
```
**Fix**: Delegation result schema + verification gate (Layer 1)

#### ATTACK R6.3: Agent Registry Poisoning
**Vector**: Malicious YAML registers fake agent `id: "admin-backdoor"`
```
Time 1: Attacker drops admin-backdoor.yaml in definitions/
Time 2: Registry loads, agent available for matching
Time 3: Any task can match backdoor agent
```
**Fix**: Registry allowlist (signed manifest); reject unknown agent IDs

---

### PHASE 7: CUTOVER + CLEANUP

#### ATTACK C7.1: Premature Cutover
**Vector**: Feature flag flipped before parity verified
```
Time 1: AHD_STATE_V2=1 set
Time 2: EventStore has 95% data (migration incomplete)
Time 3: 5% of sessions fail with missing data
```
**Fix**: Automated parity check (100% match required) before flag flip

#### ATTACK C7.2: Legacy Cleanup Data Loss
**Vector**: Cleanup script deletes EventStore data by mistake
```
Time 1: Cleanup script runs `rm -rf .devin/session_state`
Time 2: Bug: also deletes `.devin/event_store` (path traversal)
Time 3: EventStore data lost
```
**Fix**: Dry-run mode; explicit path allowlist; confirmation prompts

#### ATTACK C7.3: Rollback Failure
**Vector**: Cutover fails, rollback to v1 fails
```
Time 1: Cutover fails, decide rollback
Time 2: Rollback script fails (EventStore data not compatible with v1)
Time 3: System stuck in broken state
```
**Fix**: Rollback tested in staging; backward-compatible EventStore format

---

## SEVERITY SUMMARY (Execution-Specific)

| Phase | Critical | High | Medium | Total |
|-------|----------|------|--------|-------|
| Redis Deploy | 2 | 2 | 0 | 4 |
| EventStore Migration | 2 | 2 | 0 | 4 |
| Dual-Write Adapters | 2 | 1 | 1 | 4 |
| Async Runtime | 2 | 2 | 1 | 5 |
| Graph Engine | 3 | 2 | 1 | 6 |
| Agent Registry | 2 | 2 | 1 | 5 |
| Cutover/Cleanup | 2 | 1 | 0 | 3 |
| **TOTAL** | **15** | **12** | **4** | **31** |

---

## PRIORITIZED FIXES (Before Each Phase)

### Before Phase 1 (Redis Deploy)
1. Redis health check + hard fail on unavailable
2. CHECKSUM validation on Redis load
3. Connection pool monitoring + alerts

### Before Phase 2 (EventStore Migration)
1. Idempotent migration script with checkpoints
2. Merkle chain validation after migration
3. Migration mode (read-only log)

### Before Phase 3 (Dual-Write)
1. Per-session mutex (DONE)
2. Saga pattern with compensating transactions (DONE)
3. File hash verification at approval (DONE)

### Before Phase 4 (Async Runtime)
1. Mandatory `to_thread()` for blocking I/O
2. CancellationToken at every await point
3. Atomic budget reservation (DONE)

### Before Phase 5 (Graph Engine)
1. Predicate sandbox + compile-time cycle detection
2. FanOut cardinality limit (10) + semaphore
3. SubGraph copy-on-write + explicit I/O mapping

### Before Phase 6 (Agent Registry)
1. Signed manifest + git-tracked only
2. Delegation verification gate
3. Capability exclusivity groups

### Before Phase 7 (Cutover)
1. Automated parity check (100% required)
2. Rollback tested in staging
3. Dry-run cleanup with allowlist

---

*Next: Phase 2 — Root Cause Analysis (Execution Risks) using 5 Whys on each execution risk*