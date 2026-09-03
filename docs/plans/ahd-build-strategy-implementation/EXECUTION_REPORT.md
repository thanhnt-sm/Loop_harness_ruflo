# EXECUTION REPORT — P1-05: Durable step boundaries + resume

> **Ticket**: P1-05 | **REQ ID**: REQ-P1-05 | **Priority**: 🔴 HIGH
> **Date**: 2026-08-27 | **Status**: COMPLETED
> **Plan**: `docs/plans/ahd-build-strategy-implementation/IMPLEMENTATION_PLAN.md`
> **Sub-plan**: `docs/plans/ahd-build-strategy-implementation/P1-05.md`

---

## 1. Summary

Implemented **durable execution layer** for AHD sessions enabling checkpoint/resume, LLM call deduplication, tool receipts with idempotency keys, and human-gated saga for irreversible actions. Based on BUILD_LONG_SESSION_2026.md (L1-L6) patterns: DBOS-style lightweight checkpointing.

---

## 2. Files Changed

| File | Type | Description |
|------|------|-------------|
| `.devin/hooks/ahd_session_durable.py` | **NEW** | Core durable execution module (checkpoint, LLM cache, receipts, saga) |
| `.devin/hooks/ahd_session.py` | **EXTEND** | Exported durable APIs |
| `.devin/hooks/post_tool_engine.py` | **EXTEND** | Integrated receipt emission |
| `.devin/hooks/post_tool_config.py` | **EXTEND** | Added durable execution constants (phases, checkpoint, saga) |
| `tests/test_durable_execution.py` | **NEW** | 24 unit tests covering all acceptance criteria |
| `docs/plans/ahd-build-strategy-implementation/P1-05.md` | **NEW** | Sub-plan with detailed spec |
| `docs/plans/ahd-build-strategy-implementation/IMPLEMENTATION_PLAN.md` | **MODIFIED** | Updated file paths |

---

## 3. Acceptance Criteria Verification

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| **AC-1** | Phase checkpoint: save state after each phase | ✅ PASS | `advance_phase()`, `record_step_completion()` |
| **AC-2** | Resume from checkpoint: loads last phase state | ✅ PASS | `resume_session()` loads checkpoint + LLM cache |
| **AC-3** | LLM call deduplication: cached responses not re-executed | ✅ PASS | `llm_cache_get/put()` with hash-based dedup |
| **AC-4** | Tool receipts with idempotency keys | ✅ PASS | `emit_tool_receipt()`, `check_idempotent()` |
| **AC-5** | Human-gated saga for irreversible actions | ✅ PASS | `saga_begin()`, `saga_request_approval()`, `saga_approve_step()` |
| **AC-6** | Compacted durable state: goal + waits + receipts | ✅ PASS | `get_compact_state()` returns minimal state |

---

## 4. Test Results

```bash
$ python -m pytest tests/test_durable_execution.py -v --no-cov
============================= test session starts =============================
collected 24 items
tests/test_durable_execution.py::TestCheckpointCreation::test_create_initial_checkpoint PASSED
tests/test_durable_execution.py::TestCheckpointCreation::test_save_and_load_checkpoint PASSED
tests/test_durable_execution.py::TestCheckpointCreation::test_load_nonexistent_checkpoint PASSED
tests/test_durable_execution.py::TestPhaseAdvancement::test_advance_phase PASSED
tests/test_durable_execution.py::TestPhaseAdvancement::test_record_step_completion PASSED
tests/test_durable_execution.py::TestLLMCallCache::test_cache_put_and_get PASSED
tests/test_durable_execution.py::TestLLMCallCache::test_cache_miss PASSED
tests/test_durable_execution.py::TestLLMCallCache::test_different_prompts_different_hashes PASSED
tests/test_durable_execution.py::TestLLMCallCache::test_same_prompt_same_hash PASSED
tests/test_durable_execution.py::TestToolReceipts::test_emit_receipt PASSED
tests/test_durable_execution.py::TestToolReceipts::test_check_idempotent PASSED
tests/test_durable_execution.py::TestToolReceipts::test_idempotent_miss PASSED
tests/test_durable_execution.py::TestSaga::test_saga_begin PASSED
tests/test_durable_execution.py::TestSaga::test_saga_execute_step PASSED
tests/test_durable_execution.py::TestSaga::test_saga_human_approval_required PASSED
tests/test_durable_execution.py::TestSaga::test_saga_approve_and_execute PASSED
tests/test_durable_execution.py::TestSaga::test_saga_compensate PASSED
tests/test_durable_execution.py::TestSaga::test_saga_complete PASSED
tests/test_durable_execution.py::TestResume::test_resume_session PASSED
tests/test_durable_execution.py::TestCompactState::test_get_compact_state PASSED
tests/test_durable_execution.py::TestHashFunctions::test_call_hash_deterministic PASSED
tests/test_durable_execution.py::TestHashFunctions::test_call_hash_different PASSED
tests/test_durable_execution.py::TestHashFunctions::test_idempotency_key_deterministic PASSED
tests/test_durable_execution.py::TestHashFunctions::test_idempotency_key_different_args PASSED
=============================== 24 passed in 0.97s ==============================
```

---

## 5. Governance Verification

```bash
$ python tools/check_governance.py
=== Governance Check — Loop_harness_ruflo ===

[WARNINGS (7)] — nên xử lý:
  ⚠ code thay đổi không nằm trong plan nào: tests/test_hlk_config.py
  ⚠ code thay đổi không nằm trong plan nào: tests/test_hlk_skill_pointer.py
  ⚠ code thay đổi không nằm trong plan nào: tests/test_migration_diff.py
  ⚠ code thay đổi không nằm trong plan nào: tests/test_platform_utils.py
  ⚠ code thay đổi không nằm trong plan nào: tests/test_provider_config.py
  ⚠ code thay đổi không nằm trong plan nào: tests/test_sync_to_mirrors.py
  ⚠ plan thiếu execution report: docs/plans/fix-14-failed-36-errors-pre-existing-tests-test-cost-guard-3/

Kết quả: errors=0, warnings=7
```

✅ **0 errors** — All new files in allowed paths
⚠️ Warnings are pre-existing files from git restore

---

## 6. Key Implementation Details

### Phase-Based Checkpointing (`ahd_session_durable.py`)
```python
SESSION_PHASES = [
    "boot", "plan", "approve_sdd", "approve_plan",
    "execute", "verify", "report", "completed"
]

# Checkpoint structure
DurableCheckpoint:
  - version, session_id, phase, step_index
  - goal, completed_steps, pending_waits
  - receipts, compact_state, llm_call_cache
```

### LLM Call Deduplication
```python
# Hash-based cache key
call_hash = sha256(f"{model}|{prompt}|{json.dumps(kwargs)}")[:32]

# LRU cache with max 1000 entries
# On resume: llm_cache_load() restores cache from disk
```

### Tool Receipts with Idempotency
```python
# Deterministic idempotency key
idempotency_key = sha256(f"{session_id}|{tool}|{json.dumps(args)}")[:32]

# Receipt structure
ToolReceipt:
  - idempotency_key, tool, args, result
  - status, timestamp, session_id, expires_at
```

### Saga for Irreversible Actions
```python
# Human-gated steps
saga_begin(session_id, steps)
saga_request_approval(session_id, "delete_step")
# Human approves via UI/webhook
saga_approve_step(session_id, "delete_step")
saga_execute_step(session_id, "delete_step", delete_fn)

# Compensation on failure
saga_compensate(session_id)  # Runs in reverse order
```

### Integration Points
1. **post_tool_engine.py** — Emits receipt on every successful tool call
2. **ahd_session.py** — Exports all durable APIs
3. **post_tool_config.py** — Defines phase constants and timeouts

---

## 7. Residual Risks

| Risk | Mitigation |
|------|------------|
| Checkpoint file corruption | Atomic write via temp file + replace |
| LLM cache grows unbounded | LRU eviction at 1000 entries |
| Saga timeout | Configurable 5-min timeout for human approval |
| State schema evolution | Version field in checkpoint, migrate on load |

---

## 8. Next Steps

1. **Integrate with approval_gate.py** — Use saga for approval workflow
2. **Add telemetry** — Log checkpoint/resume events for monitoring
3. **Proceed to P1-06** (Private golden set + trajectory eval) or P1-07 (3-layer stack)

---

## 9. Commits

*(To be filled after git commit)*

```
<commit-hash> feat: P1-05 durable execution (checkpoint, LLM cache, receipts, saga)
<commit-hash> test: P1-05 add 24 unit tests for durable execution
<commit-hash> docs: P1-05 sub-plan and execution report
```

---

*Execution report generated 2026-08-27 | P1-05 COMPLETED*