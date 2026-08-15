# MIGRATION IMPLEMENTATION PLAN — Iteration 3
**Date**: 2026-08-15  
**Scope**: Migration from Legacy AHD v1.x → Structural Architecture v2.0  
**Strategy**: Strangler Fig (Dual-write → Shadow → Cutover → Cleanup)

---

## DEPENDENCY ORDER (Must Follow)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. STATE STORE INTERFACE + FILE BACKEND      (MIG-07)         │
│     ↓ Foundation for all other components                       │
├─────────────────────────────────────────────────────────────────┤
│  2. EVENT STORE + FILE BACKEND                (MIG-01, MIG-03) │
│     ↓ Uses StateStore; replaces 8 fragmented stores             │
├─────────────────────────────────────────────────────────────────┤
│  3. ADAPTER LAYER (Session/Plan/Execution)     (MIG-01, MIG-02) │
│     ↓ Dual-write adapters for legacy stores                     │
├─────────────────────────────────────────────────────────────────┤
│  4. ASYNC RUNTIME (TaskGraph, StreamingExecutor) (MIG-04)      │
│     ↓ Replaces ThreadPoolExecutor in dag_executor               │
├─────────────────────────────────────────────────────────────────┤
│  5. GRAPH ENGINE (LangGraph StateGraph)         (MIG-05, MIG-06)│
│     ↓ Replaces plan_fsm/state_machine.py                        │
├─────────────────────────────────────────────────────────────────┤
│  6. AGENT REGISTRY + CAPABILITY SYSTEM          (MIG-08, MIG-10)│
│     ↓ Uses StateStore; replaces missions.py hardcoded missions  │
├─────────────────────────────────────────────────────────────────┤
│  7. REDIS/POSTGRESQL BACKENDS                 (MIG-07)         │
│     ↓ Production scaling                                         │
├─────────────────────────────────────────────────────────────────┤
│  8. INTEGRATION & MIGRATION                                           │
│     • Hooks → EventStore                                          │
│     • Graph Engine → Agent Registry                               │
│     • Dual-write migration (v1 → v2)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## MILESTONES & DEFINITION OF DONE

### M1: StateStore Interface + FileBackend (Week 1) — MIG-07
**Target**: `.devin/scripts/state_store/interface.py` + `file_backend.py`

| DoD | Verification |
|-----|--------------|
| `StateStore` ABC with get/set/delete/watch/transaction | Unit tests pass |
| `FileBackend` implements ABC (JSONL + SQLite index) | CRUD + transaction tests pass |
| Consistency levels: strong/eventual documented | Integration test with mock |
| Sharding strategy: session_id → shard | Distribution test (1000 keys) |
| TTL compaction with active-session pinning | Long-running session survives compaction |
| Health check endpoint | `/health` returns latency, lag, errors |

**Files to Create/Update**:
```
.devin/scripts/state_store/
├── interface.py          # StateStore ABC (UPDATE ConsistencyLevel enum)
├── file_backend.py       # JSONL + SQLite (DONE)
├── transaction.py        # Transaction context manager
├── sharding.py           # Consistent hashing with virtual nodes
├── compaction.py         # TTL compaction with active-session pinning
├── health.py             # HealthCheck
├── redis_backend.py      # Redis Streams + Redis JSON (Phase 2)
└── pg_backend.py         # PostgreSQL async backend (Phase 2)
```

---

### M2: EventStore + FileBackend (Week 1-2) — MIG-01, MIG-03
**Target**: `.devin/scripts/state_machine_v2/event_store.py`

| DoD | Verification |
|-----|--------------|
| `EventStore.append(event)` <5ms p99 | Benchmark test |
| `EventStore.subscribe(topic)` yields events | Pub/sub test |
| `EventStore.replay(from_seq)` reconstructs state | Replay test from seq 0 |
| Merkle hash chain: each event commits history | Tamper detection test |
| Event schema validation (Pydantic) | Invalid event rejected |
| HMAC per event (Ed25519) | Signature verification test |
| Materialized Views: SessionView, PlanView, ExecutionView, LoopView | View query <2ms |
| CRDT: LWW-Register, OR-Set, PN-Counter | Concurrent merge test |
| Migration Mode: read-only log, reject out-of-order | Migration mode test |
| Migration script: v1 stores → EventStore | Zero data loss verification |

**Files to Create/Update**:
```
.devin/scripts/state_machine_v2/
├── event_store.py        # EventStore class (DONE)
├── event.py              # Event dataclass + schema (DONE)
├── views/
│   ├── session_view.py   # Active sessions, costs, heartbeats (DONE)
│   ├── plan_view.py      # Plan status, approvals, artifacts (DONE)
│   ├── execution_view.py # DAG state, task results, checkpoints (DONE)
│   └── loop_view.py      # Loop iterations, convergence metrics (DONE)
├── crdt/
│   ├── lww_register.py   # Last-Writer-Wins Register (DONE)
│   ├── or_set.py         # Observed-Remove Set (DONE)
│   └── pn_counter.py     # Positive-Negative Counter (DONE)
├── snapshots/
│   └── snapshot_manager.py
├── backends/
│   └── file_backend.py   # Uses StateStore FileBackend
├── migration/
│   └── migrate_v1_to_v2.py  # Migration script
└── factory.py            # EventStoreFactory
```

---

### M3: Adapter Layer — Dual-Write (Week 2) — MIG-01, MIG-02
**Target**: `.devin/scripts/adapters/` (NEW)

| DoD | Verification |
|-----|--------------|
| SessionStateAdapter: per-session mutex + transactional dual-write | Concurrent write test: no divergence |
| PlanStateAdapter: file hash verification at approval | File swap after approval → rejected |
| ExecutionStateAdapter: checkpoint HMAC verification | Corrupted checkpoint → rejected |
| All adapters: saga pattern compensating transactions | Failure injection: rollback verified |
| Shadow mode: EventStore reads, compare with legacy | Diff alert on mismatch |
| Feature flag: `AHD_STATE_V2=1` enables adapters | Flag test |

**Files to Create**:
```
.devin/scripts/adapters/
├── __init__.py
├── session_state_adapter.py    # SessionState ↔ EventStore SessionView
├── plan_state_adapter.py       # PlanState ↔ EventStore PlanView
├── execution_state_adapter.py  # ExecutionState ↔ EventStore ExecutionView
├── migration_coordinator.py    # Saga orchestrator for dual-write
└── dual_write.py              # Transactional dual-write base
```

---

### M4: Async Runtime (Week 2-3) — MIG-04
**Target**: `.devin/scripts/runtime/` (DONE — integrate into dag_executor)

| DoD | Verification |
|-----|--------------|
| `AsyncTaskGraph.execute()` returns async iterator | Streaming test |
| `StreamingExecutor` yields progress events | Token streaming test |
| `CancellationToken` propagates to all nodes | Cancel mid-execution test |
| `BackpressureQueue(maxsize=N)` pauses producer | Queue full → producer waits |
| `StreamAdapter` for SWE-1.7/GLM/Kimi streaming | All 3 executors stream tokens |
| `TokenBudget` per session/task/agent | Budget exceeded → block |
| `CostOptimizer` routes to cheapest capable model | Routing test with mock models |
| Atomic budget reservation (check-then-act) | Concurrent test: no overrun |
| Integration: `dag_executor.py` uses AsyncRuntime | E2E DAG execution test |

**Files to Update**:
```
.devin/scripts/dag_executor.py    # REPLACE ThreadPoolExecutor with AsyncTaskGraph
.devin/scripts/runtime/__init__.py  # Export new classes (DONE)
```

---

### M5: Graph Engine (Week 3-4) — MIG-05, MIG-06
**Target**: `.devin/scripts/graph_engine/` (DONE — integrate into plan_orchestrator)

| DoD | Verification |
|-----|--------------|
| `StateGraph.add_node()`, `add_edge()`, `add_conditional_edge()` | API compatibility test |
| 15 FSM states → StateGraph nodes mapping complete | All states reachable |
| FanOut: 8 SCOUTs execute truly parallel | Parallel execution test (wall time) |
| Conditional edges: sandboxed predicates | Predicate injection test |
| HumanNode: `interrupt()` + structured payload | Human approval test |
| SubGraph: nested planning graph | Subgraph isolation test |
| Checkpointer: MemorySaver (dev) + RedisSaver (prod) | Resume from checkpoint test |
| Visualizer: `to_mermaid()` renders correctly | Mermaid output test |
| Compile-time cycle detection | Cyclic graph rejected |
| Migration: `plan_orchestrator.py` uses StateGraph | E2E Plan Phase test |

**FSM → Graph Mapping**:
| FSM State | Graph Node | Type |
|-----------|------------|------|
| INIT | START | Entry |
| CLASSIFY | ClassifyNode | Conditional → BRAINSTORM \| SKIP |
| BRAINSTORM | BrainstormNode | FanOut (6 perspectives) |
| ANALYZE | AnalyzeNode | Wait (8 SCOUTs) |
| DESIGN | ArchitectNode | LLM |
| REVIEW | ReviewNode | FanOut (6 personas) |
| REVISION | RevisionNode | Loop → ARCHITECT |
| SDD_APPROVAL | HumanNode | Interrupt (approve/reject) |
| PLAN | PlannerNode | Decompose → DAG |
| GAP_SCAN | GapScanNode | FanOut |
| QC | QCNode | Parallel (10 dimensions) |
| PLAN_ENHANCE | EnhanceNode | FanOut (5 skills) |
| PLAN_APPROVAL | HumanNode | Interrupt (approve/reject) |
| WRITE_STATE | StateWriterNode | Activate enforcement |
| DONE | END | Terminal |

**Files to Update**:
```
.devin/scripts/plan_orchestrator.py     # REPLACE plan_fsm with Graph Engine
.devin/scripts/plan_fsm/state_machine.py  # KEEP for reference
.devin/scripts/plan_fsm/missions.py       # REFACTOR for Graph Engine nodes
```

---

### M6: Agent Registry + Capability System (Week 4) — MIG-08, MIG-10
**Target**: `.devin/agents/definitions/` + `.devin/scripts/agents/registry.py` (NEW)

| DoD | Verification |
|-----|--------------|
| `AgentRegistry.match(task_requirements) → List[AgentCapability]` | Matching test |
| YAML definitions for 3 executors + 6 personas | All load without error |
| Capability matcher: vector search + skill filter | Semantic + exact test |
| DynamicTeam forms different compositions (S/M/L/XL) | Team composition test |
| DelegationChain: parent→child + result aggregation | Delegation test |
| Delegation verification gate (Layer 1) | Unverified result rejected |
| Cost-aware routing: TokenBudget + CostOptimizer | Routing test |
| Immutable definitions: signed manifest allowlist | Unknown agent rejected |
| Capability exclusivity groups (no duplicate roles) | Conflict resolution test |

**AgentCard YAML Schema**:
```yaml
# .devin/agents/definitions/scout.yaml
id: scout
version: "1.0"
capabilities:
  - code_search
  - web_search
  - dependency_analysis
  - test_coverage_analysis
  - constraint_analysis
model: "auto"
cost_per_token: 0.000002
tools:
  - grep
  - glob
  - read
  - web_search
  - webfetch
max_parallel: 8
```

**Files to Create**:
```
.devin/agents/
├── registry.py             # AgentRegistry
├── capabilities.py         # Capability dataclass
├── dynamic_team.py         # DynamicTeam formation
├── delegation.py           # DelegationChain
├── definitions/
│   ├── scout.yaml
│   ├── architect.yaml
│   ├── reviewer.yaml
│   ├── builder.yaml
│   ├── verifier.yaml
│   ├── executor/
│   │   ├── lightning.yaml
│   │   ├── glm.yaml
│   │   └── kimi.yaml
│   └── manifest.yaml       # Signed allowlist (cosign)
└── base.py                 # BaseAgent
```

---

### M7: Redis/PostgreSQL Backends (Week 4-5) — MIG-07
**Target**: `.devin/scripts/state_store/backends/`

| DoD | Verification |
|-----|--------------|
| `RedisBackend` implements StateStore ABC | All interface tests pass |
| `PgBackend` implements StateStore ABC | All interface tests pass |
| Optimistic locking: ETags + `first_write` | Concurrent update test |
| Transactions: multi-key atomic | Transaction test |
| Sharding: consistent hashing + virtual nodes | 1000 sessions → uniform |
| Read replicas: read-your-writes for critical keys | Stale read test |
| TTL compaction: active sessions pinned | Long session survives |
| Leader election: Redis Sentinel / etcd | Failover <5s, zero data loss |
| Health check: latency, lag, errors | Monitoring test |

**Files to Create**:
```
.devin/scripts/state_store/backends/
├── redis_backend.py        # Redis Streams + Redis JSON
├── pg_backend.py           # PostgreSQL (asyncpg)
├── etcd_backend.py         # etcd (optional)
└── factory.py              # BackendFactory (config-driven)
```

**Config** (`.devin/config.json`):
```json
{
  "state_store": {
    "backend": "file",  // "file" | "redis" | "postgresql" | "etcd"
    "redis": {"host": "localhost", "port": 6379, "db": 0},
    "postgresql": {"dsn": "postgresql://user:pass@localhost/dapr"},
    "shards": 10,
    "replicas": 2,
    "ttl_seconds": 2592000
  }
}
```

---

### M8: Integration & Migration (Week 5-6) — ALL

| DoD | Verification |
|-----|--------------|
| Hooks (pre/post) write to EventStore | Hook integration test |
| Graph Engine uses Agent Registry for team formation | E2E Plan→Execute test |
| Dual-write: v1 stores + EventStore | State equality check |
| Shadow mode: EventStore reads, compare with v1 | Diff alert on mismatch |
| Cutover: v1 deprecated, EventStore primary | Zero downtime |
| Cleanup: v1 store code removed | No v1 imports remain |
| All existing tests pass | CI green |
| Performance: Planning <10s, Execution 50 tasks/min | Load test |

---

## MIGRATION STRATEGY (Strangler Fig)

```
Phase 1 (Week 1-2): Adapter reads v1, writes v2 (dual-write)
    → verify v2 state == v1 state after each operation

Phase 2 (Week 3-4): Shadow mode — v2 reads, compare with v1
    → alert on any diff, but v1 still authoritative

Phase 3 (Week 5): Cutover — v2 authoritative, v1 deprecated
    → feature flag `AHD_STATE_V2=1`

Phase 4 (Week 6): Cleanup — remove v1 store code
    → delete session_state/, loop_state/, etc. direct access
```

---

## FEATURE FLAGS (Migration Control)

| Flag | Default | Controls |
|------|---------|----------|
| `AHD_STATE_V2=1` | 0 | Enable EventStore as primary |
| `AHD_ASYNC_RUNTIME=1` | 0 | Use AsyncTaskGraph instead of ThreadPoolExecutor |
| `AHD_GRAPH_ENGINE=1` | 0 | Use StateGraph instead of Plan FSM |
| `AHD_DUAL_WRITE=1` | 0 | Write to both legacy + new |
| `AHD_SHADOW_MODE=1` | 0 | Read from new, compare with legacy |
| `AHD_AGENT_REGISTRY=1` | 0 | Use Agent Registry for dispatch |
| `AHD_REDIS_BACKEND=1` | 0 | Use Redis backend for StateStore |

---

## RISK MITIGATION

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LangGraph API changes | Medium | High | Pin version, vendor interfaces only |
| Redis/PostgreSQL not available in CI | High | Medium | FileBackend as default, Redis optional |
| EventStore migration data loss | Low | Critical | Dual-write verification, rollback plan |
| Graph Engine predicate sandbox escape | Low | Critical | Allowlist-only, no `__builtins__` |
| Agent Registry YAML tampering | Medium | High | Signed manifest, git-tracked only |
| CostOptimizer routes to wrong model | Medium | Medium | Hard per-task ceiling, audit log |
| TTL compaction deletes active session | Low | High | Heartbeat extends TTL, pin active |

---

## SUCCESS METRICS (Iteration 3)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Planning Latency** (P95) | <10s | E2E trace: task → approved plan |
| **Execution Throughput** | 50 tasks/min | Prometheus: `tasks_completed_total` |
| **Hook Latency** (P99) | <20ms | OTel: `hook_duration_seconds` |
| **Cost per Task** | $0.15 | CostTracker: cumulative / tasks |
| **MTTR** | <5min | Incident log |
| **Horizontal Scale** | 10+ instances | Load test |
| **Agent Dynamic Score** | 9/10 | Capability matrix: task → agents |
| **Migration Parity** | 100% | Automated diff tool: 0 differences |

---

## SIGN-OFF REQUIREMENTS

| Phase | Reviewer | Criteria |
|-------|----------|----------|
| M1-M2 (StateStore + EventStore) | Platform Lead | All DoD verified, zero data loss |
| M3 (Adapters) | Platform Lead | Dual-write parity, saga rollback works |
| M4 (Async Runtime) | Platform Lead | Streaming works, cancellation propagates |
| M5 (Graph Engine) | Architecture Lead | 15 states mapped, FanOut parallel |
| M6 (Agent Registry) | Architecture Lead | Dynamic teams, delegation verified |
| M7 (Backends) | Platform Lead | Redis/PG pass interface tests |
| M8 (Integration) | All Leads | E2E green, performance targets met |

---

*Next: Phase 5 — Implementation begins with M1 (StateStore Interface + FileBackend)*