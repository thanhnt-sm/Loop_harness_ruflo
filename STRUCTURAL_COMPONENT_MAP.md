# COMPONENT MAP — STRUCTURAL ARCHITECTURE v2.0
**Iteration**: 2  
**Scope**: Redesign 5 Structural Root Causes (RC-01 through RC-05)  
**Date**: 2026-08-15

---

## CURRENT STATE (Fragmented)

| Layer | Current Components | Problems |
|-------|-------------------|----------|
| **State** | `session_state/*.json`, `loop_state/*.md`, `context_flags/*.json`, `plan_state/*.json`, `blackboard/*.json`, `event_bus/*.jsonl`, `checkpoints/*.json`, `idempotency/*.jsonl` | 8 separate stores, no ACID, no transactions, race conditions |
| **Execution** | `dag_executor.py` (ThreadPoolExecutor), `plan_fsm/state_machine.py` (15 hardcoded states) | Sync blocking, no streaming, no dynamic graph |
| **Agents** | `.md` files in `.devin/agents/` (Commander, 5 workers, 6 personas, 3 executors) | Static, no capability registry, no dynamic team formation |
| **Persistence** | Direct `Path.read_text()/write_text()` everywhere | File locks only, single-machine, no horizontal scaling |

---

## TARGET ARCHITECTURE (Unified)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AHD v2.0 ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│  │   CLIENTS    │    │   CLIENTS    │    │   CLIENTS    │             │
│  │  (Hooks,     │    │  (Agents,    │    │  (Tools,     │             │
│  │   Scripts)   │    │   Skills)    │    │   MCP)       │             │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘             │
│         │                   │                   │                      │
│         └───────────────────┼───────────────────┘                      │
│                             ▼                                           │
│              ┌────────────────────────────────┐                        │
│              │      EVENT STORE (RC-01)       │  ◄── Single Source   │
│              │  • Append-only event log       │       of Truth        │
│              │  • Materialized Views          │  ◄── ACID + CRDT      │
│              │  • Snapshots + Compaction      │       (Redis/PG)      │
│              └────────────────┬───────────────┘                        │
│                               │                                        │
│         ┌─────────────────────┼─────────────────────┐                  │
│         ▼                     ▼                     ▼                  │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐          │
│  │  ASYNC      │      │  GRAPH      │      │  AGENT      │          │
│  │  RUNTIME    │      │  ENGINE     │      │  REGISTRY   │          │
│  │  (RC-02)    │      │  (RC-03)    │      │  (RC-04)    │          │
│  │             │      │             │      │             │          │
│  │ • AsyncTask │      │ • StateGraph│      │ • YAML defs │          │
│  │   Graph     │      │   API       │      │ • Capability│          │
│  │ • Streaming │      │ • Conditional│     │   Matcher   │          │
│  │   Executor  │      │   Edges     │      │ • Delegation│          │
│  │ • Cancel    │      │ • FanOut/In │      │   Chains    │          │
│  │   Tokens    │      │ • Interrupts│      │             │          │
│  │ • Backpres- │      │ • Subgraphs │      │             │          │
│  │   sure      │      │             │      │             │          │
│  └──────┬──────┘      └──────┬──────┘      └──────┬──────┘          │
│         │                    │                    │                   │
│         └────────────────────┼────────────────────┘                   │
│                              ▼                                       │
│                 ┌────────────────────────┐                          │
│                 │   STATE STORE (RC-05)  │                          │
│                 │  • Abstract Interface  │                          │
│                 │  • File/Redis/PG/etcd  │                          │
│                 │  • Sharding + Replicas │                          │
│                 │  • TTL Compaction      │                          │
│                 └────────────────────────┘                          │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## DETAILED COMPONENT SPECIFICATIONS

---

### RC-01: EVENT STORE (Unified State Machine)

**Purpose**: Single source of truth for all state — replaces 8 fragmented stores

| Aspect | Current | Target |
|--------|---------|--------|
| **Storage** | 8 independent JSON/JSONL files | Append-only event log (JSONL) + SQLite/Redis index |
| **Consistency** | None (race conditions) | Event-sourced: linearizable writes, snapshot isolation reads |
| **Queries** | Direct file reads | Materialized views (session, plan, execution, loop) |
| **Distribution** | Single machine | CRDT for multi-agent, Redis/PostgreSQL backend |
| **History** | Lost on overwrite | Full replay, time-travel debugging |

**Core Components**:
```
.devin/scripts/state_machine_v2/
├── event_store.py          # EventStore class: append, subscribe, replay
├── event.py                # Event dataclass: {seq, ts, type, payload, hash, sig}
├── views/
│   ├── session_view.py     # Active sessions, heartbeats, costs
│   ├── plan_view.py        # Plan status, approvals, artifacts
│   ├── execution_view.py   # DAG state, task results, checkpoints
│   └── loop_view.py        # Loop iterations, convergence metrics
├── crdt/
│   ├── lww_register.py     # Last-writer-wins for config
│   ├── or_set.py           # Observed-remove set for agent registry
│   └── counter.py          # G-counter for costs/iterations
├── snapshots/
│   └── snapshot_manager.py # Periodic snapshots, incremental recovery
└── backends/
    ├── file_backend.py     # Local development (JSONL + SQLite)
    ├── redis_backend.py    # Production (Redis Streams + Redis JSON)
    └── pg_backend.py       # Audit/analytics (PostgreSQL)
```

**Migration Strategy** (Strangler Fig):
```
Phase 1: Adapter reads v1 stores, writes v2 EventStore (dual-write)
Phase 2: Shadow mode — v2 reads, compare with v1, alert on diff
Phase 3: Cutover — v1 deprecated, v2 primary
Phase 4: Cleanup — remove v1 store code
```

**Definition of Done**:
- [ ] `EventStore.append(event)` <5ms p99
- [ ] `SessionView.get(session_id)` <2ms
- [ ] CRDT convergence verified under network partition
- [ ] Migration script: v1 → v2 with zero data loss
- [ ] Dual-write verification: v1 state == v2 view

---

### RC-02: ASYNC RUNTIME (Streaming Execution)

**Purpose**: Replace ThreadPoolExecutor with async/await, streaming, cancellation

| Aspect | Current | Target |
|--------|---------|--------|
| **Model** | Sync ThreadPoolExecutor | Async TaskGraph + StreamingExecutor |
| **LLM Streaming** | Not supported | Async generators, token-by-token |
| **Cancellation** | Not supported | CancellationToken propagation |
| **Backpressure** | None | Bounded async queues |
| **Progress** | Blocking until done | Real-time callbacks |

**Core Components**:
```
.devin/scripts/runtime/
├── async_task_graph.py     # AsyncTaskGraph: DAG with async node execution
├── streaming_executor.py   # StreamingExecutor: yields progress events
├── cancellation.py         # CancellationToken: propagate cancel across DAG
├── backpressure.py         # BackpressureQueue: bounded async queue
├── llm_stream.py           # StreamAdapter: unified SWE-1.7/GLM/Kimi streaming
├── token_budget.py         # TokenBudget: per-session/task/agent limits
├── cost_optimizer.py       # CostOptimizer: route to cheapest capable model
└── cache_layer.py          # CacheLayer: semantic cache for repeated prompts
```

**API**:
```python
# Execute DAG with streaming
async for progress in StreamingExecutor.execute(graph, initial_state):
    # progress: {type: "node_start|node_complete|token|checkpoint", ...}
    ui.update(progress)

# Cancel mid-execution
token = CancellationToken()
asyncio.create_task(StreamingExecutor.execute(graph, state, cancel_token=token))
# Later: token.cancel() → propagates to all running nodes
```

**Definition of Done**:
- [ ] `StreamingExecutor` yields tokens from all 3 executors
- [ ] Cancellation stops all nodes within 100ms
- [ ] Backpressure: queue full → producer pauses (not OOM)
- [ ] 100% async — no `ThreadPoolExecutor` in hot path
- [ ] Cost optimizer routes correctly (test with mock models)

---

### RC-03: DYNAMIC GRAPH ENGINE (LangGraph-Compatible)

**Purpose**: Replace 15-state hardcoded FSM with dynamic StateGraph

| Aspect | Current | Target |
|--------|---------|--------|
| **Structure** | 15 hardcoded states, fixed edges | Dynamic nodes/edges, conditional routing |
| **Parallelism** | Sequential (with some parallel SCOUTs) | FanOut/FanIn, subgraphs, true parallelism |
| **Checkpointing** | Only at phase boundaries | At any node |
| **Human-in-loop** | Fixed approval gates | Interrupt nodes at arbitrary points |
| **Sub-workflows** | Not supported | SubGraph composition |

**Core Components**:
```
.devin/scripts/graph_engine/
├── state_graph.py          # StateGraph: add_node, add_edge, add_conditional_edge
├── compiled_graph.py       # CompiledGraph: optimized execution plan
├── nodes/
│   ├── base.py             # BaseNode: async execute(state) -> state_update
│   ├── llm_node.py         # LLMNode: streaming LLM call
│   ├── tool_node.py        # ToolNode: tool execution with retries
│   ├── human_node.py       # HumanNode: interrupt + resume
│   └── subgraph_node.py    # SubGraphNode: nested graph execution
├── edges/
│   ├── direct.py           # DirectEdge: fixed transition
│   ├── conditional.py      # ConditionalEdge: runtime predicate
│   ├── fanout.py           # FanOutEdge: parallel branch
│   └── fanin.py            # FanInEdge: join with reducer
├── checkpointer/
│   ├── base.py             # BaseCheckpointer
│   ├── memory.py           # MemorySaver (dev)
│   ├── redis.py            # RedisSaver (prod)
│   └── pg.py               # PostgresSaver (audit)
├── interrupts/
│   └── interrupt.py        # Interrupt: payload + resume callback
└── visualizer/
    ├── mermaid.py          # to_mermaid()
    └── dot.py              # to_dot()
```

**FSM → Graph Mapping** (15 states → nodes):
```
OLD FSM                    NEW GRAPH NODES
─────────────────────────────────────────────────────
INIT              →        START (entry)
CLASSIFY          →        ClassifyNode (conditional → BRAINSTORM | SKIP)
BRAINSTORM        →        BrainstormNode (FanOut: 6 perspectives)
ANALYZE           →        AnalyzeNode (Wait: 8 SCOUTs)
DESIGN            →        ArchitectNode (LLM)
REVIEW            →        ReviewNode (FanOut: 6 personas)
REVISION          →        RevisionNode (loop back to ARCHITECT)
SDD_APPROVAL      →        HumanNode (interrupt: approve/reject)
PLAN              →        PlannerNode (decompose → DAG)
GAP_SCAN          →        GapScanNode (FanOut)
QC                →        QCNode (parallel 10 dimensions)
PLAN_ENHANCE      →        EnhanceNode (FanOut: 5 skills)
PLAN_APPROVAL     →        HumanNode (interrupt: approve/reject)
WRITE_STATE       →        StateWriterNode (activate enforcement)
DONE              →        END (terminal)
```

**Definition of Done**:
- [ ] `StateGraph` API matches LangGraph (`add_node`, `add_edge`, `add_conditional_edge`)
- [ ] `graph.compile()` produces `CompiledGraph` with optimized plan
- [ ] FanOut/FanIn executes 8 SCOUTs truly parallel (not sequential)
- [ ] Checkpoint at any node: resume from exact state
- [ ] HumanNode: interrupt → pause → resume with user input
- [ ] SubGraph: nested planning graph for complex tasks
- [ ] Visualizer: `graph.to_mermaid()` renders correctly

---

### RC-04: AGENT REGISTRY + CAPABILITY SYSTEM

**Purpose**: Dynamic team formation from task requirements

| Aspect | Current | Target |
|--------|---------|--------|
| **Definition** | Markdown files (`.md`) | YAML + Python class |
| **Discovery** | Hardcoded missions | Capability matcher: task → required agents |
| **Team Formation** | Fixed (8 SCOUTs, 6 reviewers) | Dynamic: task complexity → agent count/skills |
| **Delegation** | None | Parent→child with accountability |
| **Cost Model** | None | Per-agent cost_per_token, budget-aware routing |

**Core Components**:
```
.devin/agents/
├── registry.py             # AgentRegistry: discover, match, instantiate
├── capabilities.py         # Capability: skills, tools, model, cost_per_token
├── dynamic_team.py         # DynamicTeam: form from requirements
├── delegation.py           # DelegationChain: parent→child with result agg
├── definitions/
│   ├── scout.yaml          # Capability: code_search, web_search, analysis
│   ├── architect.yaml      # Capability: design, architecture, tradeoffs
│   ├── reviewer.yaml       # Capability: security, correctness, maintainability
│   ├── builder.yaml        # Capability: implement, test, debug
│   ├── verifier.yaml       # Capability: audit, coverage, traceability
│   └── executor/
│       ├── lightning.yaml  # SWE-1.7, fast, paid
│       ├── glm.yaml        # GLM-5.2, free, reasoning
│       └── kimi.yaml       # Kimi K2.7, free, open-source
└── base.py                 # BaseAgent: execute(task, context) -> result
```

**Capability Schema** (YAML):
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
model: "auto"  # or specific executor
cost_per_token: 0.000002  # estimated
tools:
  - grep
  - glob
  - read
  - web_search
  - webfetch
max_parallel: 8
```

**Definition of Done**:
- [ ] `AgentRegistry.match(task) → List[AgentCapability]` returns optimal team
- [ ] DynamicTeam forms different compositions for S/M/L/XL tasks
- [ ] DelegationChain: parent spawns child, aggregates results, accountability logged
- [ ] Cost-aware routing: task → cheapest capable executor
- [ ] All 3 executors + 6 personas registered with capabilities
- [ ] YAML definitions replace markdown (backward compat: parser reads both)

---

### RC-05: PLUGGABLE STATE STORE

**Purpose**: Horizontal scaling, HA, multi-backend persistence

| Aspect | Current | Target |
|--------|---------|--------|
| **Backend** | Local files only | File / Redis / PostgreSQL / etcd |
| **Scaling** | Single instance | Sharded by session_id, read replicas |
| **HA** | None | Leader election, automatic failover |
| **Compaction** | None | TTL-based, incremental snapshots |
| **Queries** | Direct file reads | Materialized views, indexes |

**Core Components**:
```
.devin/scripts/state_store/
├── interface.py            # StateStore ABC: get, set, delete, watch, transaction
├── transaction.py          # Transaction: atomic multi-key ops
├── sharding.py             # ShardingStrategy: session_id → shard
├── replication.py          # Replication: leader + replicas
├── compaction.py           # TTLCompactor: expire old events
├── backends/
│   ├── file_backend.py     # Local dev (JSONL + SQLite indexes)
│   ├── redis_backend.py    # Redis Cluster (streams + JSON)
│   ├── pg_backend.py       # PostgreSQL (ACID + analytics)
│   └── etcd_backend.py     # etcd (coordination + config)
├── migration/
│   └── migrator.py         # v1 → v2, backend ↔ backend
└── health.py               # HealthCheck: latency, lag, errors
```

**Interface** (Abstract Base Class):
```python
class StateStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]: ...
    
    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> None: ...
    
    @abstractmethod
    async def delete(self, key: str) -> None: ...
    
    @abstractmethod
    async def watch(self, prefix: str) -> AsyncIterator[Event]: ...
    
    @abstractmethod
    async def transaction(self) -> Transaction: ...
    
    @abstractmethod
    async def health_check(self) -> HealthStatus: ...

class Transaction(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]: ...
    @abstractmethod
    async def set(self, key: str, value: bytes) -> None: ...
    @abstractmethod
    async def commit(self) -> None: ...
    @abstractmethod
    async def rollback(self) -> None: ...
```

**Definition of Done**:
- [ ] `FileBackend` passes all interface tests (local dev)
- [ ] `RedisBackend` passes all interface tests (CI with Redis)
- [ ] Sharding: 1000 sessions → 10 shards, uniform distribution
- [ ] Read replicas: write to leader, read from replica <5ms
- [ ] TTL compaction: 30-day events auto-expired
- [ ] Failover: leader death → new leader <5s, zero data loss
- [ ] Migration: `FileBackend` → `RedisBackend` zero-downtime

---

## INTEGRATION POINTS

| From | To | Contract |
|------|-----|----------|
| **Hooks** (pre/post) | EventStore | `event_store.append(Event(type="tool_call", ...))` |
| **Graph Engine** | Async Runtime | `await StreamingExecutor.execute(compiled_graph, state)` |
| **Graph Engine** | Agent Registry | `agents = registry.match(task_requirements)` |
| **Agent Registry** | State Store | `await store.set(f"agent:{id}", yaml)` |
| **Async Runtime** | State Store | Checkpoints: `await store.set(f"checkpoint:{run_id}", state)` |
| **Event Store** | State Store | Materialized views backed by StateStore |

---

## IMPLEMENTATION ORDER (Dependency Order)

```
1. StateStore Interface + FileBackend          (RC-05 foundation)
   ↓
2. EventStore + FileBackend                    (RC-01 on StateStore)
   ↓
3. Async Runtime (TaskGraph, StreamingExecutor) (RC-02)
   ↓
4. Graph Engine (StateGraph, CompiledGraph)    (RC-03 on Async Runtime)
   ↓
5. Agent Registry + Capability System          (RC-04 on StateStore)
   ↓
6. Redis/PostgreSQL Backends                   (RC-05 production)
   ↓
7. CRDT Layer (multi-agent coordination)       (RC-01 distributed)
   ↓
8. Integration: Hooks → EventStore, Graph → Agents
   ↓
9. Migration: v1 → v2 dual-write → cutover
```

---

## PARITY-GAPS TO RESOLVE IN THIS ITERATION

| Gap | Resolution |
|-----|------------|
| MCP server internals opaque | EventStore captures all MCP calls as events |
| External model APIs opaque | LLMStream adapter normalizes SWE-1.7/GLM/Kimi |
| HLK Node.js not visible | HLK sanitizer patterns → EventStore → schema_gate |
| Human approval undefined | HumanNode in Graph Engine with crypto attestation |
| Cost model estimated | TokenBudget + CostOptimizer with real provider pricing |
| Git worktree boundaries | StateStore isolates per-worktree session_id |

---

## SUCCESS METRICS (Iteration 2)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Planning Latency** (P95) | <10s | E2E trace: task → approved plan |
| **Execution Throughput** | 50 tasks/min | Prometheus: tasks_completed_total |
| **Hook Latency** (P99) | <20ms | OTel: hook_duration_seconds |
| **Cost per Task** | $0.15 | CostTracker: cumulative / tasks |
| **MTTR** | <5min | Incident log: detect → resolve |
| **Horizontal Scale** | 10+ instances | Load test: concurrent sessions |
| **Agent Dynamic Score** | 9/10 | Capability matrix: task → agents |

---

## OPEN QUESTIONS

1. **EventStore Backend for MVP**: File (SQLite) or Redis? → Start File, Redis in Phase 6
2. **LangGraph Dependency**: Vendored or external? → External (pip install langgraph), vendor only interfaces
3. **CRDT Library**: Automerge, Yjs, or custom? → Custom minimal (LWW-Register, OR-Set, G-Counter)
4. **Agent YAML Location**: `.devin/agents/definitions/` or `.devin/agents/registry/`? → `definitions/`
5. **StateStore Sharding Key**: `session_id` or `loop_id`? → `session_id` (higher cardinality)

---

*Next: Phase 1 — Red Team on Structural Designs (attack each component design before implementation)*