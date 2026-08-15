# MIGRATION EXECUTION COMPONENT MAP — Iteration 4
**Date**: 2026-08-15  
**Scope**: Actual migration execution from Legacy AHD v1.x → Structural Architecture v2.0  
**Strategy**: Strangler Fig (Dual-write → Shadow → Cutover → Cleanup)

---

## CURRENT STATE (Post-Iteration 3)

### READY FOR EXECUTION
| Component | Status | Files |
|-----------|--------|-------|
| **StateStore** | ✅ Implemented | `state_store/interface.py`, `file_backend.py` |
| **EventStore** | ✅ Implemented | `state_machine_v2/event_store.py` (CQRS views, CRDTs, Merkle chain) |
| **Async Runtime** | ✅ Implemented | `runtime/` (AsyncTaskGraph, StreamingExecutor, TokenBudget, StreamAdapter) |
| **Graph Engine** | ✅ Implemented | `graph_engine/` (StateGraph, nodes, edges, checkpointer) |
| **Migration Coordinator** | ✅ Implemented | `adapters/migration_coordinator.py` (Saga orchestrator) |
| **Session Adapter** | ✅ Implemented | `adapters/session_state_adapter.py` (dual-write, mutex) |
| **Plan Adapter** | ✅ Implemented | `adapters/plan_state_adapter.py` (file hash verification, full state upsert) |
| **Execution Adapter** | ✅ Implemented | `adapters/execution_state_adapter.py` (task state, checkpoints) |
| **PlanView Fix** | ✅ Implemented | `state_machine_v2/event_store.py` (LAST_WRITE concurrency) |

### NOT YET EXECUTED (TO BE DONE IN ITERATION 4)
| Migration Task | Status | Priority |
|----------------|--------|----------|
| **EventStore Migration** (Session/Plan/Execution data) | ⏳ PENDING | CRITICAL |
| **Async Runtime Integration** (dag_executor → AsyncTaskGraph) | ⏳ PENDING | CRITICAL |
| **Graph Engine Migration** (Plan FSM → StateGraph) | ⏳ PENDING | CRITICAL |
| **Agent Registry** (YAML definitions + capability matcher) | ⏳ PENDING | HIGH |
| **Redis Backend** (StateStore production backend) | ⏳ PENDING | HIGH |
| **Hook Rewrites** (PlanEnforce, PreToolUse → EventStore) | ⏳ PENDING | MEDIUM |
| **Dual-Write Cutover** (AHD_STATE_V2=1) | ⏳ PENDING | CRITICAL |
| **Shadow Validation** (100% parity check) | ⏳ PENDING | CRITICAL |
| **Legacy Cleanup** (remove v1 stores) | ⏳ PENDING | MEDIUM |

---

## EXECUTION DEPENDENCY ORDER

```
Week 1: Foundation
├── M4-1: Redis Backend Deployment
├── M4-2: EventStore Migration Script Execution
└── M4-3: Dual-Write Adapters Activation (AHD_DUAL_WRITE=1)

Week 2: Execution Layer
├── M4-4: Async Runtime Integration (dag_executor → AsyncTaskGraph)
├── M4-5: StreamAdapter Integration (3 executors)
└── M4-6: Shadow Mode Validation (AHD_SHADOW_MODE=1)

Week 3: Orchestration Layer
├── M4-7: Graph Engine Migration (Plan FSM → StateGraph)
├── M4-8: Plan Orchestrator Rewrite
├── M4-8: State Router Rewrite
└── M4-9: Agent Registry Deployment

Week 4: Cutover
├── M4-10: Dual-Write Parity Verification (100% parity)
├── M4-11: Cutover (AHD_STATE_V2=1, AHD_ASYNC_RUNTIME=1, AHD_GRAPH_ENGINE=1)
├── M4-11: Legacy Code Cleanup
└── M4-12: Production Monitoring (48h)
```

---

## FEATURE FLAGS (Execution Control)

| Flag | Default | Phase | Purpose |
|------|---------|-------|---------|
| `AHD_REDIS_BACKEND=1` | 0 | Week 1 | Enable Redis backend |
| `AHD_DUAL_WRITE=1` | 0 | Week 1 | Enable dual-write adapters |
| `AHD_SHADOW_MODE=1` | 0 | Week 2 | Shadow mode validation |
| `AHD_ASYNC_RUNTIME=1` | 0 | Week 2 | Enable AsyncTaskGraph |
| `AHD_GRAPH_ENGINE=1` | 0 | Week 3 | Enable StateGraph |
| `AHD_STATE_V2=1` | 0 | Week 4 | Cutover to v2 |
| `AHD_AGENT_REGISTRY=1` | 0 | Week 3 | Enable Agent Registry |

---

## LEGACY STORES TO MIGRATE

| Legacy Store | Path | Target | Records Est. |
|--------------|------|--------|--------------|
| Session State | `.devin/session_state/*.json` | EventStore SessionView | ~500 |
| Loop State | `.devin/loop_state/*.md` | EventStore LoopView | ~200 |
| Context Flags | `.devin/context_flags/*.json` | EventStore SessionView | ~100 |
| Plan State | `.devin/plan_state/*.json` | EventStore PlanView | ~100 |
| Checkpoints | `.devin/checkpoints/*.json` | EventStore ExecutionView | ~200 |
| Idempotency | `.devin/idempotency/*.ledger.jsonl` | StateStore (keep) | ~50 |
| Blackboard | `.devin/blackboard/*.json` | EventStore LoopView | ~50 |
| Event Bus | `.devin/event_bus/*.jsonl` | EventStore (native) | ~100 |

---

## ROLLBACK PLAN

| Trigger | Action | Time |
|---------|--------|------|
| Parity check fails | Set `AHD_STATE_V2=0`, `AHD_DUAL_WRITE=0` | <5 min |
| Async Runtime errors | Set `AHD_ASYNC_RUNTIME=0` | <2 min |
| Graph Engine errors | Set `AHD_GRAPH_ENGINE=0` | <2 min |
| Data corruption detected | Restore from EventStore snapshots | <15 min |
| Critical bug in production | Full rollback to v1 tags | <30 min |

---

## SUCCESS CRITERIA (Per Phase)

| Phase | Criteria | Measurement |
|-------|----------|-------------|
| **Foundation** | Redis healthy, EventStore migrated | 0 data loss, <5ms latency |
| **Execution** | Async Runtime parity, streaming works | 0 result diff, streaming tokens |
| **Orchestration** | 15 states mapped, FanOut parallel | 100% state transition parity |
| **Cutover** | Zero downtime, <1% error rate | Monitoring dashboards |

---

*Next: Phase 1 — Red Team on Migration Execution (attack each execution step before running)*