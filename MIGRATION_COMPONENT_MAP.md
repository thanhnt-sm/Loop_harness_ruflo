# MIGRATION COMPONENT MAP — Iteration 3
**Date**: 2026-08-15  
**Scope**: Migration from Legacy AHD v1.x → Structural Architecture v2.0  
**Strategy**: Strangler Fig (Dual-write → Shadow → Cutover → Cleanup)

---

## LEGACY COMPONENTS TO MIGRATE (Source of Truth)

### State Management (8 Fragmented Stores → EventStore)
| Legacy Store | Path | Migration Target | Risk |
|--------------|------|------------------|------|
| Session State | `.devin/session_state/*.json` | EventStore → SessionView | HIGH |
| Loop State | `.devin/loop_state/*.md` | EventStore → LoopView | HIGH |
| Context Flags | `.devin/context_flags/*.json` | EventStore → SessionView | MEDIUM |
| Plan State | `.devin/plan_state/*.json` | EventStore → PlanView | HIGH |
| Checkpoints | `.devin/checkpoints/*.json` | EventStore → ExecutionView | HIGH |
| Idempotency | `.devin/idempotency/*.ledger.jsonl` | StateStore (keep separate) | LOW |
| Blackboard | `.devin/blackboard/*.json` | EventStore → LoopView | MEDIUM |
| Event Bus | `.devin/event_bus/*.jsonl` | EventStore (native) | LOW |

### Execution Engine (ThreadPoolExecutor → Async Runtime)
| Legacy Component | File | Migration Target | Risk |
|------------------|------|------------------|------|
| DAG Executor | `.devin/scripts/dag_executor.py` | AsyncTaskGraph + StreamingExecutor | CRITICAL |
| State Router | `.devin/scripts/state_router.py` | Graph Engine (StateGraph) | HIGH |
| Plan Orchestrator | `.devin/scripts/plan_orchestrator.py` | Graph Engine (15 states → nodes) | HIGH |
| Plan FSM | `.devin/scripts/plan_fsm/state_machine.py` | Graph Engine (StateGraph nodes) | HIGH |

### Enforcement Hooks (Keep + Integrate)
| Hook | File | Integration Point | Risk |
|------|------|-------------------|------|
| Plan Enforce | `.devin/hooks/plan_enforce.py` | EventStore session_state | MEDIUM |
| Pre Tool Use | `.devin/hooks/pre_tool_use.py` | Async Runtime cost/SSRF/encoding | LOW |
| Post Tool Use | `.devin/hooks/post_tool_use.py` | EventStore session heartbeat | LOW |
| Schema Gate | `.devin/hooks/schema_gate.py` | EventStore + StateStore | LOW |
| Coverage Enforce | `.devin/hooks/coverage_enforce.py` | EventStore coverage tracking | MEDIUM |
| Drift Detect | `.devin/hooks/drift_detect.py` | Graph Engine state comparison | MEDIUM |

### Approval Gates (Keep + Crypto)
| Component | File | Migration Target | Risk |
|-----------|------|------------------|------|
| Approval Gate | `.devin/scripts/approval_gate.py` | EventStore PlanView (keep Ed25519) | LOW |
| Plan Quality Check | `.devin/scripts/plan_quality_check.py` | Graph Engine validation | LOW |
| Coverage Matrix | `.devin/scripts/coverage_matrix.py` | EventStore + StateStore hashes | LOW |

### Agents & Skills (Refactor to Registry)
| Component | Current | Migration Target | Risk |
|-----------|---------|------------------|------|
| Commander | `.devin/agents/COMMANDER.md` | Agent Registry (YAML) | HIGH |
| Workers (5) | `.devin/agents/workers/*.md` | Agent Registry (capability YAML) | HIGH |
| Personas (6) | `.devin/agents/personas/*.md` | Agent Registry (capability YAML) | HIGH |
| Executors (3) | `.devin/agents/*-executor/AGENT.md` | Agent Registry + StreamAdapter | MEDIUM |
| Skills (26) | `.devin/skills/*/SKILL.md` | Keep as-is, register in Agent Registry | LOW |

### Config & Canon (Consolidate)
| Component | Current | Migration Target | Risk |
|-----------|---------|------------------|------|
| AHD Config | `.devin/config.json` | Keep, add StateStore/EventStore config | LOW |
| Tool Registry | `.devin/tool_registry.json` | Keep | LOW |
| Risk Contract | `.devin/risk_contract.json` | Keep | LOW |
| Hook Hashes | `.devin/hook_hashes.json` | Keep | LOW |
| Canon (15) | `.devin/canon/*.md` | Keep as reference docs | LOW |

### HLK Security Layer (Keep)
| Component | Current | Migration Target | Risk |
|-----------|---------|------------------|------|
| Sanitizer | `HLK/security/sanitizer.js` | Keep (EventStore uses patterns) | LOW |
| Vault Bridge | `HLK/security/vault-bridge.js` | Keep (Async Runtime uses) | LOW |
| Config | `HLK/config/hlk.config.json` | Keep | LOW |

---

## NEW STRUCTURAL COMPONENTS (Target Architecture)

| Component | Files | Status | Integration Points |
|-----------|-------|--------|-------------------|
| **StateStore** | `state_store/interface.py`, `file_backend.py` | ✅ Implemented | All legacy stores |
| **EventStore** | `state_machine_v2/event_store.py` | ✅ Implemented | Session/Plan/Execution/Loop views |
| **Async Runtime** | `runtime/` (6 files) | ✅ Implemented | DAG Executor, Plan Orchestrator |
| **Graph Engine** | `graph_engine/` (8 files) | ✅ Implemented | Plan FSM, State Router |
| **Agent Registry** | `agents/definitions/` (planned) | 📋 Designed | Commander, Workers, Skills |

---

## MIGRATION DEPENDENCY GRAPH

```
                    ┌─────────────────────┐
                    │  1. StateStore      │  ← Foundation (FileBackend done)
                    │  (interface + impl) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │ 2. EventStore   │  │ 3. Async Runtime │  │ 4. Graph Engine │
       │ (on StateStore) │  │ (uses StateStore)  │  │ (uses StateStore) │
       └──────┬────────┘  └──────┬────────┘  └──────┬────────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 ▼
                    ┌─────────────────────┐
                    │ 5. Migration Layer  │
                    │ (Adapters + Dual-write) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │ Session     │  │ Plan        │  │ Execution   │
       │ State       │  │ State       │  │ State       │
       │ Adapter     │  │ Adapter     │  │ Adapter     │
       └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ 6. Legacy Hook/     │
                    │ Executor Rewrites   │
                    └─────────────────────┘
```

---

## MIGRATION RISK MATRIX

| Migration | Risk | Impact | Mitigation |
|-----------|------|--------|------------|
| **Session State → EventStore** | HIGH | All sessions break | Dual-write + validation |
| **Plan State → EventStore** | HIGH | Plan approvals lost | Immutable artifacts + signatures |
| **DAG Executor → Async Runtime** | CRITICAL | All execution fails | Shadow mode + feature flag |
| **Plan FSM → Graph Engine** | HIGH | Planning breaks | 15-state mapping verified |
| **State Router → Graph Engine** | HIGH | Routing fails | Conditional edges tested |
| **Hook Rewrites** | MEDIUM | Enforcement gaps | Dual-write enforcement |
| **Agent Registry Migration** | HIGH | Workers fail | Gradual rollout |
| **Async Hook Integration** | MEDIUM | Blocking calls | Thread pool for blocking I/O |

---

## ADAPTER SPECIFICATIONS (Migration Layer)

### Session State Adapter
```python
# Reads from EventStore SessionView, writes to both
class SessionStateAdapter:
    async def get(self, session_id: str) -> dict:
        # Read from EventStore (primary)
        data = await event_store.sessions.get(session_id)
        if data: return data
        # Fallback to legacy file
        return await legacy_read(session_id)
    
    async def set(self, session_id: str, data: dict) -> None:
        # Dual-write
        await event_store.sessions.upsert(session_id, data)
        await legacy_write(session_id, data)  # During migration only
```

### Plan State Adapter
```python
class PlanStateAdapter:
    async def get_approval(self, plan_id: str) -> dict:
        return await event_store.plans.get(plan_id) or legacy_read(plan_id)
    
    async def set_approval(self, plan_id: str, data: dict) -> None:
        await event_store.plans.approve(...)  # or reject
        await legacy_write(plan_id, data)
```

### Execution State Adapter
```python
class ExecutionStateAdapter:
    async def get_task(self, run_id: str, task_id: str) -> dict:
        return await event_store.executions.get_task(run_id, task_id)
    
    async def checkpoint(self, run_id: str, state: dict) -> None:
        await event_store.executions.checkpoint(run_id, state)
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

---

## MIGRATION SEQUENCE (4-Week Plan)

### Week 1: Foundation (StateStore + EventStore)
- [ ] Deploy StateStore FileBackend to production
- [ ] Deploy EventStore with dual-write adapters
- [ ] Migrate session_state via adapter (validate 100% parity)
- [ ] Migrate plan_state via adapter (validate approvals)
- [ ] Enable `AHD_STATE_V2=1` for internal testing

### Week 2: Execution Layer (Async Runtime)
- [ ] Integrate AsyncTaskGraph into dag_executor (feature flag)
- [ ] Implement StreamAdapter for 3 executors
- [ ] Shadow mode: run Async Runtime alongside ThreadPoolExecutor
- [ ] Compare results, fix discrepancies
- [ ] Enable `AHD_ASYNC_RUNTIME=1` for internal testing

### Week 3: Orchestration Layer (Graph Engine)
- [ ] Map 15 FSM states → StateGraph nodes
- [ ] Implement Plan Orchestrator on Graph Engine
- [ ] Implement State Router on Graph Engine
- [ ] Shadow mode: run Graph Engine alongside Plan FSM
- [ ] Enable `AHD_GRAPH_ENGINE=1` for internal testing

### Week 4: Integration & Cutover
- [ ] Full dual-write across all adapters
- [ ] Shadow validation: 100% parity for 100 sessions
- [ ] Enable all feature flags: `AHD_STATE_V2=1 AHD_ASYNC_RUNTIME=1 AHD_GRAPH_ENGINE=1`
- [ ] Monitor for 48 hours
- [ ] Disable legacy code paths
- [ ] Remove legacy stores (cleanup)

---

## PARITY-GAPS TO RESOLVE DURING MIGRATION

| Gap | Resolution |
|-----|------------|
| MCP server internals opaque | EventStore captures all MCP calls as events |
| External model APIs opaque | StreamAdapter normalizes SWE-1.7/GLM/Kimi |
| HLK Node.js not visible | HLK sanitizer patterns → EventStore → schema_gate |
| Human approval undefined | HumanNode in Graph Engine with crypto attestation |
| Cost model estimated | TokenBudget + CostOptimizer with real provider pricing |
| Git worktree boundaries | StateStore isolates per-worktree session_id |

---

## SUCCESS CRITERIA (Per Migration Phase)

| Phase | Criteria | Measurement |
|-------|----------|-------------|
| **StateStore/EventStore** | 100% parity with legacy stores | Automated diff tool: 0 differences |
| **Async Runtime** | Same results, streaming support | Shadow mode: 0 result differences |
| **Graph Engine** | 15 states mapped, FanOut works | 100% state transition parity |
| **Full Integration** | All hooks/enforcement work | E2E tests pass, 0 regressions |
| **Production Cutover** | Zero downtime, <1% error rate | Monitoring dashboards |

---

*Next: Phase 1 — Red Team on Migration Designs (attack each adapter/integration point)*