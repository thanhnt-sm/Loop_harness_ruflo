# STRUCTURAL IMPLEMENTATION PLAN — Iteration 2
**Date**: 2026-08-15  
**Scope**: 5 Structural Root Causes (RC-01 through RC-05)  
**Method**: Strangler Fig migration (dual-write → shadow → cutover)

---

## DEPENDENCY ORDER (Must Follow)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. STATE STORE INTERFACE + FILE BACKEND      (RC-05)          │
│     ↓ Foundation for all other components                       │
├─────────────────────────────────────────────────────────────────┤
│  2. EVENT STORE + FILE BACKEND                (RC-01)          │
│     ↓ Uses StateStore; replaces 8 fragmented stores             │
├─────────────────────────────────────────────────────────────────┤
│  3. ASYNC RUNTIME (TaskGraph, StreamingExecutor) (RC-02)       │
│     ↓ Replaces ThreadPoolExecutor in dag_executor               │
├─────────────────────────────────────────────────────────────────┤
│  4. GRAPH ENGINE (LangGraph StateGraph)         (RC-03)        │
│     ↓ Replaces plan_fsm/state_machine.py                        │
├─────────────────────────────────────────────────────────────────┤
│  5. AGENT REGISTRY + CAPABILITY SYSTEM          (RC-04)        │
│     ↓ Uses StateStore; replaces missions.py hardcoded missions  │
├─────────────────────────────────────────────────────────────────┤
│  6. REDIS/POSTGRESQL BACKENDS                 (RC-01, RC-05)   │
│     ↓ Production scaling                                         │
├─────────────────────────────────────────────────────────────────┤
│  7. INTEGRATION & MIGRATION                                           │
│     • Hooks → EventStore                                          │
│     • Graph Engine → Agent Registry                               │
│     • Dual-write migration (v1 → v2)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## MILESTONES & DEFINITION OF DONE

### M1: StateStore Interface + FileBackend (Week 1)
**Target**: `.devin/scripts/state_store/interface.py` + `file_backend.py`

| DoD | Verification |
|-----|--------------|
| `StateStore` ABC with get/set/delete/watch/transaction | Unit tests pass |
| `FileBackend` implements ABC (JSONL + SQLite index) | CRUD + transaction tests pass |
| Consistency levels: strong/eventual documented | Integration test with mock |
| Sharding strategy: session_id → shard | Distribution test (1000 keys) |
| TTL compaction with active-session pinning | Long-running session survives compaction |
| Health check endpoint | `/health` returns latency, lag, errors |

**Files to Create**:
```
.devin/scripts/state_store/
├── interface.py          # StateStore ABC
├── file_backend.py       # JSONL + SQLite
├── transaction.py        # Transaction context manager
├── sharding.py           # Consistent hashing
├── compaction.py         # TTL compaction
└── health.py             # HealthCheck
```

---

### M2: EventStore + FileBackend (Week 1-2)
**Target**: `.devin/scripts/state_machine_v2/event_store.py` + views

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
| Migration script: v1 stores → EventStore | Zero data loss verification |

**Files to Create**:
```
.devin/scripts/state_machine_v2/
├── event_store.py        # EventStore class
├── event.py              # Event dataclass + schema
├── views/
│   ├── session_view.py   # Active sessions, costs, heartbeats
│   ├── plan_view.py      # Plan status, approvals, artifacts
│   ├── execution_view.py # DAG state, task results, checkpoints
│   └── loop_view.py      # Loop iterations, convergence
├── crdt/
│   ├── lww_register.py
│   ├── or_set.py
│   └── pn_counter.py
├── snapshots/
│   └── snapshot_manager.py
├── backends/
│   └── file_backend.py   # Uses StateStore FileBackend
└── migration/
    └── migrate_v1_to_v2.py
```

---

### M3: Async Runtime (Week 2)
**Target**: `.devin/scripts/runtime/` — replaces ThreadPoolExecutor

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

**Files to Create**:
```
.devin/scripts/runtime/
├── async_task_graph.py     # AsyncTaskGraph (DAG with async nodes)
├── streaming_executor.py   # StreamingExecutor (yields progress)
├── cancellation.py         # CancellationToken
├── backpressure.py         # BackpressureQueue
├── llm_stream.py           # StreamAdapter (SWE-1.7/GLM/Kimi)
├── token_budget.py         # TokenBudget (per session/task/agent)
├── cost_optimizer.py       # CostOptimizer (model routing)
└── cache_layer.py          # CacheLayer (semantic cache)
```

**Migration**: Update `dag_executor.py` to use `AsyncRuntime` instead of `ThreadPoolExecutor`

---

### M4: Graph Engine (Week 2-3)
**Target**: LangGraph StateGraph integration — replaces `plan_fsm/state_machine.py`

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

**Files to Create**:
```
.devin/scripts/graph_engine/
├── state_graph.py          # StateGraph (LangGraph-compatible API)
├── compiled_graph.py       # CompiledGraph (optimized execution)
├── nodes/
│   ├── base.py             # BaseNode
│   ├── llm_node.py         # LLMNode (streaming)
│   ├── tool_node.py        # ToolNode (with retries)
│   ├── human_node.py       # HumanNode (interrupt + resume)
│   └── subgraph_node.py    # SubGraphNode
├── edges/
│   ├── direct.py           # DirectEdge
│   ├── conditional.py      # ConditionalEdge (sandboxed)
│   ├── fanout.py           # FanOutEdge
│   └── fanin.py            # FanInEdge (with reducer)
├── checkpointer/
│   ├── base.py             # BaseCheckpointer
│   ├── memory.py           # MemorySaver
│   ├── redis.py            # RedisSaver
│   └── pg.py               # PostgresSaver
├── interrupts/
│   └── interrupt.py        # Interrupt + resume callback
├── visualizer/
│   ├── mermaid.py          # to_mermaid()
│   └── dot.py              # to_dot()
└── migration/
    └── fsm_to_graph.py     # 15-state FSM → StateGraph
```

---

### M5: Agent Registry + Capability System (Week 3)
**Target**: `.devin/agents/registry.py` + YAML definitions

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
│   └── manifest.yaml       # Signed allowlist
└── base.py                 # BaseAgent
```

---

### M6: Redis/PostgreSQL Backends (Week 3-4)
**Target**: Production-ready backends

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

### M7: Integration & Migration (Week 4)
**Target**: End-to-end working system with dual-write migration

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

**Migration Strategy** (Strangler Fig):
```
Phase 1 (Week 4a): Adapter reads v1, writes v2 (dual-write)
    → verify v2 state == v1 state after each operation

Phase 2 (Week 4b): Shadow mode — v2 reads, compare with v1
    → alert on any diff, but v1 still authoritative

Phase 3 (Week 4c): Cutover — v2 authoritative, v1 deprecated
    → feature flag `AHD_STATE_V2=1`

Phase 4 (Week 4d): Cleanup — remove v1 store code
    → delete session_state/, loop_state/, etc. direct access
```

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

## SUCCESS METRICS (Iteration 2)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Planning Latency** (P95) | <10s | E2E trace: task → approved plan |
| **Execution Throughput** | 50 tasks/min | Prometheus: `tasks_completed_total` |
| **Hook Latency** (P99) | <20ms | OTel: `hook_duration_seconds` |
| **Cost per Task** | $0.15 | CostTracker: cumulative / tasks |
| **MTTR** | <5min | Incident log |
| **Horizontal Scale** | 10+ instances | Load test |
| **Agent Dynamic Score** | 9/10 | Capability matrix |

---

## SIGN-OFF REQUIREMENTS

| Phase | Reviewer | Criteria |
|-------|----------|----------|
| M1-M2 (StateStore + EventStore) | Platform Lead | All DoD verified, zero data loss |
| M3 (Async Runtime) | Platform Lead | Streaming works, cancellation propagates |
| M4 (Graph Engine) | Architecture Lead | 15 states mapped, FanOut parallel |
| M5 (Agent Registry) | Architecture Lead | Dynamic teams, delegation verified |
| M6 (Backends) | Platform Lead | Redis/PG pass interface tests |
| M7 (Integration) | All Leads | E2E green, performance targets met |

---

*Next: Phase 5 — Implementation begins with M1 (StateStore Interface + FileBackend)*