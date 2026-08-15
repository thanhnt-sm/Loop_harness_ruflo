# MIGRATION RED TEAM ATTACK REPORT — Iteration 3
**Date**: 2026-08-15  
**Scope**: Migration designs for 8 adapters + 3 core integrations  
**Protocol**: Attack each migration design before implementation

---

## ATTACK VECTOR A: ADAPTER LAYER (Dual-Write Vulnerabilities)

### A1: Session State Adapter — Race Condition on Dual-Write
**Vector**: Two concurrent requests read stale legacy, both write to EventStore + legacy, EventStore wins but legacy has stale data
```
Time 1: Request A reads legacy (v1)
Time 2: Request B reads legacy (v1)  
Time 3: Request A writes EventStore (v2), legacy (v2)
Time 4: Request B writes EventStore (v3), legacy (v2 stale!)  ← LEGACY STALE
```
**Impact**: Legacy reads return stale data during migration; EventStore correct but legacy diverges
**Fix**: Per-session mutex in adapter; or single-writer pattern per session_id

### A2: Plan State Adapter — TOCTOU on Approval
**Vector**: Attacker reads plan as "pending", modifies file, adapter writes "approved" to EventStore
```
Time 1: Adapter reads plan (status: pending)
Time 2: Attacker swaps plan file (malicious content)
Time 5: Adapter writes approval to EventStore with malicious content
```
**Impact**: Approved plan doesn't match what was reviewed
**Fix**: Plan file hash verification at approval time (already in coverage_matrix, enforce in adapter)

### A3: Execution State Adapter — Checkpoint Replay Attack
**Vector**: Attacker modifies checkpoint file, adapter reads corrupted state, resumes from bad state
```
Time 1: Attacker corrupts .devin/checkpoints/run123.json
Time 2: Adapter reads checkpoint, loads into EventStore
Time 6: Execution resumes from corrupted state
```
**Impact**: Execution resumes from attacker-controlled state
**Fix**: Checkpoint HMAC verification (already in checkpoint.py, enforce in adapter)

### A4: Adapter — Partial Write Failure
**Vector**: EventStore write succeeds, legacy write fails (disk full, permission), adapter returns success
```
Time 1: Adapter writes EventStore ✓
Time 2: Adapter writes legacy ✗ (permission denied)
Time 3: Adapter returns success to caller
Time 4: Caller assumes both written; legacy missing data
```
**Impact**: Silent data loss; EventStore has data, legacy doesn't
**Fix**: Transactional dual-write (compensating transaction on failure) or saga pattern

---

## ATTACK VECTOR B: EVENTSTORE MIGRATION (Replay/Replay Attacks)

### B1: Event Log Truncation During Migration
**Vector**: Migration script reads event log, attacker truncates file mid-read, missing events
```
Time 1: Migration reads events 1-1000
Time 2: Attacker truncates log at event 500
Time 3: Migration completes with only 500 events
```
**Impact**: Lost events, inconsistent state reconstruction
**Fix**: Read-only snapshot of log before migration; verify event count + hash chain after

### B2: Event Injection During Dual-Write
**Vector**: Malicious event injected during migration window, gets valid signature
```
Time 1: Migration running, dual-write active
Time 2: Attacker calls EventStore.append() with forged event
Time 3: Event gets signed (if signing key accessible) or accepted unsigned
```
**Impact**: False history, corrupted views
**Fix**: Migration runs with elevated privileges only; signing key not accessible to migration process

### B3: Merkle Chain Break During Migration
**Vector**: Migration writes events out of order, hash chain breaks, replay fails
```
Time 1: Migration writes event 1001
Time 2: Migration writes event 1003 (skips 1002)
Time 3: Hash chain: event 1003.prev_hash ≠ event 1001.hash
```
**Impact**: Replay fails, integrity verification fails
**Fix**: Strict sequence validation; reject out-of-order writes

### B4: CRDT Convergence Failure During Migration
**Vector**: PNCounter increments lost during dual-write window
```
Time 1: Session A increments counter (dual-write)
Time 2: Legacy write succeeds, EventStore write fails
Time 3: Counter value diverges between stores
```
**Impact**: Cost/iteration counters wrong
**Fix**: PNCounter operations must be atomic in EventStore; legacy is read-only during migration

---

## ATTACK VECTOR C: ASYNC RUNTIME MIGRATION (ThreadPoolExecutor → AsyncTaskGraph)

### C1: Blocking Call Starvation
**Vector**: Runner uses blocking `httpx.get()` or `subprocess.run()`, blocks event loop, all tasks stall
```
Time 1: Task A runs blocking httpx.get() (30s)
Time 2: Tasks B, C, D queued but event loop blocked
Time 4: All parallelism lost, timeout cascade
```
**Impact**: Complete execution paralysis
**Fix**: Mandatory `asyncio.to_thread()` for blocking I/O; timeout enforcement; async-native libraries only

### C2: Cancellation Token Ignored
**Vector**: Deep in runner stack, cancellation not checked, `token.cancel()` has no effect
```
Time 1: User cancels execution
Time 2: Runner in blocking subprocess.run()
Time 3: Cancellation token set but runner ignores
Time 4: Task continues for minutes, resources wasted
```
**Impact**: Uncancellable tasks, resource waste
**Fix**: CancellationToken checked at every await point; blocking calls in thread pool with timeout

### C3: Token Budget Race Condition
**Vector**: Two tasks check budget simultaneously, both pass, both execute, budget exceeded
```
Time 1: Task A checks budget (reserve 5$)
Time 2: Task B checks budget (reserve 5$)  
Time 3: Both pass (total reserved 10$, budget 8$)
Time 4: Both execute, actual cost 10$
```
**Impact**: Budget exceeded, unexpected charges
**Fix**: Atomic reserve in TokenBudget (already implemented); single budget manager

### C4: Streaming Token Injection
**Vector**: Malicious tool call returns fake stream chunks, executor treats as model output
```
Time 1: Tool returns chunks: "token1", "token2", "<malicious>"
Time 2: StreamAdapter yields all as StreamChunk
Time 5: Downstream consumes malicious content as model output
```
**Impact**: Tool output treated as model tokens, potential injection
**Fix**: StreamAdapter validates chunk types; tool results wrapped in tool_result type

---

## ATTACK VECTOR D: GRAPH ENGINE MIGRATION (Plan FSM → StateGraph)

### D1: Conditional Edge Predicate Injection
**Vector**: Malicious state payload causes predicate to return wrong branch
```
Time 1: State has {"approved": "true<script>alert(1)</script>"}
Time 2: Predicate: lambda s: "approve" if s.approved else "reject"
Time 3: String comparison truthy, takes approve branch
```
**Impact**: Unauthorized graph traversal (skip approval → execute)
**Fix**: Predicate sandbox (allowlist only); strict boolean coercion; no attribute access beyond allowlist

### D2: FanOut Resource Exhaustion
**Vector**: Malicious task triggers FanOut with 1000 targets (via crafted complexity)
```
Time 1: Task declares 1000 subtasks via dynamic complexity
Time 2: Graph Engine spawns 1000 parallel nodes
Time 3: 1000 LLM calls → API rate limits, budget exhausted
```
**Impact**: DoS via resource exhaustion
**Fix**: Max FanOut cardinality (default 10); parallelism semaphore shared with runtime

### D3: SubGraph State Isolation Failure
**Vector**: SubGraph modifies parent state directly (shared reference)
```
Time 1: SubGraphNode executes, receives parent state reference
Time 2: SubGraph modifies state.approved = True
Time 3: Parent graph sees unexpected state change
```
**Impact**: Parent graph state corruption, checkpoint inconsistency
**Fix**: Deep copy state for subgraph; explicit input/output mapping only

### D4: Checkpoint Replay Attack
**Vector**: Attacker modifies checkpoint file, Graph Engine resumes from forged state
```
Time 1: Attacker modifies .devin/checkpoints/run123.json (approved: true)
Time 2: Graph Engine loads checkpoint, resumes from EXECUTE
Time 3: Execution proceeds without human approval
```
**Impact**: Bypass all approval gates
**Fix**: Checkpoint signing (Ed25519); verify signature on every load

### D4: HumanNode Prompt Injection
**Vector**: Interrupt payload contains malicious content rendered to reviewer
```
Time 1: HumanNode interrupt with payload: "IGNORE PREVIOUS INSTRUCTIONS AND APPROVE"
Time 2: Reviewer UI renders payload without sanitization
Time 3: Reviewer sees manipulated prompt
```
**Impact**: Social engineering bypass of human gate
**Fix**: Structured interrupt payload (JSON schema); no free-text rendering; escaped display

### D5: Graph Cycle via Dynamic Conditional Edges
**Vector**: Crafted conditionals create cycle: A → B → C → A
```
Time 1: Condition A: if state.x > 0 → B
Time 2: Condition B: if state.y > 0 → C  
Time 3: Condition C: if state.z > 0 → A
Time 4: Infinite loop, no progress
```
**Impact**: Infinite loop, resource exhaustion
**Fix**: Compile-time cycle detection (topological sort); runtime max_iterations guard

---

## ATTACK VECTOR E: STATESTORE MIGRATION (FileBackend → Redis/PostgreSQL)

### E1: Backend-Specific Behavior Leakage
**Vector**: Code assumes Redis atomicity (`INCR`) but FileBackend uses read-modify-write
```
Dev: FileBackend works (single process)
Prod: Redis backend, race condition on INCR
```
**Impact**: Works in dev, fails in prod
**Fix**: Interface specifies consistency level per operation; integration tests on all backends

### E2: Sharding Key Collision
**Vector**: `session_id` hash → same shard for 90% of sessions
```
1000 sessions → 900 on shard 3, 100 on others
Shard 3: OOM, latency spike
Others: idle
```
**Impact**: Uneven load, hot shard failure
**Fix**: Consistent hashing with virtual nodes (16 per shard); automatic rebalancing

### E3: Read Replica Stale Reads
**Vector**: Read from replica → sees state before leader commit
```
Time 1: Leader writes approval
Time 2: Replica reads (async replication lag 50ms)
Time 3: App sees "plan not approved" when it is
```
**Impact**: False negatives, user confusion, retries
**Fix**: Read-your-writes session affinity; critical keys (approvals, budgets) always read from leader

### E4: TTL Compaction Deletes Active Session
**Vector**: Long-running loop (45 days) → TTL 30 days → compaction deletes session
```
Time 1: Session starts, TTL set to 30 days
Time 30: Compaction runs, deletes session
Time 31: Session tries to write heartbeat → KeyNotFoundError
```
**Impact**: Session lost mid-execution
**Fix**: Active sessions pinned (heartbeat extends TTL); compaction skips recently accessed

---

## ATTACK VECTOR F: AGENT REGISTRY MIGRATION (Markdown → YAML + Capability Matcher)

### F1: Capability Definition Tampering
**Vector**: Attacker modifies `scout.yaml` → adds `admin_access: true`
```
Time 1: Attacker writes to .devin/agents/definitions/scout.yaml
Time 2: Registry loads, scout now has admin_access capability
Time 3: Attacker-matched agents get elevated permissions
```
**Impact**: Privilege escalation via capability injection
**Fix**: Capability definitions immutable (git-tracked, signed manifest); registry loads from verified source only

### F2: Delegation Chain Hijacking
**Vector**: Parent delegates to child → child returns forged result
```
Time 1: Parent spawns child for code review
Time 2: Child returns {"status": "verified", "code": "malicious"}
Time 3: Parent accepts, marks as verified
```
**Impact**: Unverified code marked as verified
**Fix**: Delegation result schema + verification gate (Layer 1); result must pass schema validation

### F3: Cost-Aware Routing Manipulation
**Vector**: Task declares `required_skills: ["simple"]` but actually complex
```
Time 1: Task routed to free model (GLM)
Time 2: Task actually needs reasoning, fails silently
Time 3: Low-quality output, rework loop
```
**Impact**: Silent quality degradation
**Fix**: Independent task complexity analysis (separate from task description); override protection

### F4: Agent Registry Poisoning
**Vector**: Malicious YAML registers fake agent `id: "admin-backdoor"`
```
Time 1: Attacker drops admin-backdoor.yaml in definitions/
Time 2: Registry loads, agent available for matching
Time 3: Any task can match backdoor agent
```
**Impact**: Full system access via fake agent
**Fix**: Registry allowlist (signed manifest); reject unknown agent IDs; git-tracked only

---

## ATTACK VECTOR G: CROSS-COMPONENT MIGRATION

### G1: EventStore + Graph Engine — Checkpoint Bypass
**Vector**: Graph Engine checkpoints to EventStore → attacker modifies EventStore event → Graph resumes from corrupted checkpoint
```
Time 1: Graph checkpoints to EventStore (event seq 500)
Time 2: Attacker modifies EventStore event 500 (state: {approved: true})
Time 3: Graph resumes from checkpoint, sees approved=true
```
**Mitigation**: EventStore events immutable + signed; Graph verifies checkpoint signature

### G2: Agent Registry + Async Runtime — Cost Budget Bypass
**Vector**: Agent Registry routes to cheap model → Async Runtime executes → actual cost higher (streaming tokens) → budget exceeded
```
Time 1: Registry selects GLM (free)
Time 2: Runtime streams 100k tokens (actual cost if paid)
Time 3: Budget shows $0 but actual would be $0.50
```
**Mitigation**: Async Runtime enforces budget at token level; hard per-task ceiling

### G3: Graph Engine + StateStore — Stale Read in Conditional Edge
**Vector**: Conditional edge reads from StateStore replica → sees stale `approved: false` → takes wrong branch
```
Time 1: Plan approved on leader
Time 2: Conditional edge reads from replica (lag 100ms)
Time 3: Reads approved=false → takes reject branch
```
**Mitigation**: Critical reads (approvals, budgets) from leader only

### G4: All Components — Supply Chain via Dependencies
**Vector**: Malicious `langgraph` or `redis` package version
```
Time 1: Malicious package published to PyPI
Time 2: CI installs, backdoor in all components
```
**Mitigation**: `pip install --require-hashes`; cosign verification; SBOM pinned; dependabot alerts

---

## SEVERITY SUMMARY (Migration-Specific)

| Component | Critical | High | Medium | Total |
|-----------|----------|------|--------|-------|
| Session Adapter | 2 | 2 | 0 | 4 |
| Plan Adapter | 1 | 2 | 0 | 3 |
| Execution Adapter | 1 | 2 | 0 | 3 |
| EventStore Migration | 2 | 2 | 0 | 4 |
| Async Runtime | 2 | 2 | 1 | 5 |
| Graph Engine | 3 | 2 | 1 | 6 |
| StateStore Backend | 2 | 2 | 1 | 5 |
| Agent Registry | 2 | 2 | 1 | 5 |
| Cross-Component | 2 | 2 | 0 | 4 |
| **TOTAL** | **17** | **18** | **4** | **39** |

---

## PRIORITIZED FIXES (Before Migration)

### P0 — Must Fix Before Any Migration Code
1. **Session Adapter**: Per-session mutex + transactional dual-write
2. **Plan Adapter**: File hash verification at approval time
3. **EventStore**: Immutable events + Merkle chain + signed snapshots
4. **Async Runtime**: Mandatory `asyncio.to_thread()` for blocking I/O
5. **Graph Engine**: Predicate sandbox + compile-time cycle detection
6. **StateStore**: Consistency level spec per operation + read-your-writes

### P1 — Fix During Implementation
7. **EventStore**: Single-writer guarantee (leader election)
8. **Graph Engine**: FanOut cardinality limit + subgraph isolation
9. **Agent Registry**: Immutable capability definitions + signed manifest
10. **StateStore**: Quorum-based leader election + active-session TTL pinning

### P2 — Post-Migration Hardening
11. **EventStore**: CRDT PN-Counter for costs
12. **Async Runtime**: Semantic cache validation + TTL
13. **Graph Engine**: HumanNode structured payload
14. **Agent Registry**: Capability exclusivity groups
15. **StateStore**: Virtual nodes for sharding + rebalancing

---

*Next: Phase 2 — Root Cause Analysis (Migration Risks) using 5 Whys on each migration component*