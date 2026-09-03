"""Tests for P1-05: Durable step boundaries + resume."""

from __future__ import annotations

import pytest

from ahd_session_durable import (
    SessionPhase,
    LLMCallCacheEntry,
    ToolReceipt,
    SagaStep,
    DurableCheckpoint,
    create_initial_checkpoint,
    advance_phase,
    record_step_completion,
    save_checkpoint,
    load_checkpoint,
    resume_session,
    get_compact_state,
    llm_cache_get,
    llm_cache_put,
    llm_cache_persist,
    llm_cache_load,
    emit_tool_receipt,
    check_idempotent,
    saga_begin,
    saga_execute_step,
    saga_request_approval,
    saga_approve_step,
    saga_compensate,
    saga_complete,
    _compute_call_hash,
    _compute_idempotency_key,
    _LLM_CALL_CACHES,
    _ACTIVE_SAGAS,
)


class TestCheckpointCreation:
    """Test checkpoint creation and loading."""

    def test_create_initial_checkpoint(self, tmp_path):
        checkpoint = create_initial_checkpoint(tmp_path, "test-session", "Test goal")

        assert checkpoint.version == 1
        assert checkpoint.session_id == "test-session"
        assert checkpoint.phase == SessionPhase.BOOT.value
        assert checkpoint.goal == "Test goal"
        assert checkpoint.step_index == 0
        assert checkpoint.completed_steps == []

    def test_save_and_load_checkpoint(self, tmp_path):
        checkpoint = create_initial_checkpoint(tmp_path, "test-session", "Test goal")
        checkpoint.phase = SessionPhase.PLAN.value

        assert save_checkpoint(tmp_path, "test-session", checkpoint)

        loaded = load_checkpoint(tmp_path, "test-session")
        assert loaded is not None
        assert loaded.session_id == "test-session"
        assert loaded.phase == SessionPhase.PLAN.value
        assert loaded.goal == "Test goal"

    def test_load_nonexistent_checkpoint(self, tmp_path):
        loaded = load_checkpoint(tmp_path, "nonexistent")
        assert loaded is None


class TestPhaseAdvancement:
    """Test phase advancement."""

    def test_advance_phase(self, tmp_path):
        create_initial_checkpoint(tmp_path, "test-session", "Test goal")

        assert advance_phase(tmp_path, "test-session", SessionPhase.PLAN)

        loaded = load_checkpoint(tmp_path, "test-session")
        assert loaded.phase == SessionPhase.PLAN.value

    def test_record_step_completion(self, tmp_path):
        create_initial_checkpoint(tmp_path, "test-session", "Test goal")
        advance_phase(tmp_path, "test-session", SessionPhase.PLAN)

        assert record_step_completion(
            tmp_path, "test-session", SessionPhase.PLAN, "step_1",
            llm_calls_cached=2, receipts=[{"tool": "test"}]
        )

        loaded = load_checkpoint(tmp_path, "test-session")
        assert len(loaded.completed_steps) == 1
        assert loaded.completed_steps[0]["step"] == "step_1"
        assert loaded.completed_steps[0]["llm_calls_cached"] == 2


class TestLLMCallCache:
    """Test LLM call deduplication cache."""

    def setup_method(self):
        # Clear global cache
        _LLM_CALL_CACHES.clear()

    def test_cache_put_and_get(self):
        session_id = "test-session"
        model = "test-model"
        prompt = "Test prompt"
        response = {"text": "Test response"}
        tokens_in = 100
        tokens_out = 50
        cost_usd = 0.001

        call_hash = llm_cache_put(
            session_id, model, prompt, response, tokens_in, tokens_out, cost_usd
        )

        cached = llm_cache_get(session_id, model, prompt)
        assert cached is not None
        assert cached["cached"] is True
        assert cached["response"] == response
        assert cached["tokens_saved"] == tokens_in + tokens_out
        assert cached["cost_saved_usd"] == cost_usd

    def test_cache_miss(self):
        session_id = "test-session"
        cached = llm_cache_get(session_id, "model", "different prompt")
        assert cached is None

    def test_different_prompts_different_hashes(self):
        session_id = "test-session"
        model = "test-model"

        h1 = llm_cache_put(session_id, model, "prompt 1", {"r": 1})
        h2 = llm_cache_put(session_id, model, "prompt 2", {"r": 2})

        assert h1 != h2

    def test_same_prompt_same_hash(self):
        session_id = "test-session"
        model = "test-model"
        prompt = "same prompt"

        h1 = llm_cache_put(session_id, model, prompt, {"r": 1})
        h2 = llm_cache_put(session_id, model, prompt, {"r": 2})

        assert h1 == h2


class TestToolReceipts:
    """Test tool receipt emission and idempotency."""

    def test_emit_receipt(self, tmp_path):
        idempotency_key = emit_tool_receipt(
            tmp_path, "test-session", "Read", {"path": "file.txt"}, {"content": "hello"}, "success"
        )

        assert idempotency_key is not None
        assert len(idempotency_key) == 32

    def test_check_idempotent(self, tmp_path):
        emit_tool_receipt(
            tmp_path, "test-session", "Read", {"path": "file.txt"}, {"content": "hello"}, "success"
        )

        result = check_idempotent(tmp_path, "test-session", "Read", {"path": "file.txt"})
        assert result is not None
        assert result["content"] == "hello"

    def test_idempotent_miss(self, tmp_path):
        result = check_idempotent(tmp_path, "test-session", "Read", {"path": "other.txt"})
        assert result is None


class TestSaga:
    """Test saga for irreversible actions."""

    def setup_method(self):
        _ACTIVE_SAGAS.clear()

    def test_saga_begin(self):
        steps = [
            SagaStep(step_id="step1", action="tool_call", tool="Write", args={"path": "x"}),
            SagaStep(step_id="step2", action="human_approval", requires_human_approval=True),
        ]

        assert saga_begin("test-session", steps)
        assert not saga_begin("test-session", steps)  # Second fails

    def test_saga_execute_step(self):
        executed = []

        def executor():
            executed.append("step1")
            return "ok"

        steps = [SagaStep(step_id="step1", action="tool_call", tool="Write")]
        saga_begin("test-session", steps)

        success, result = saga_execute_step("test-session", "step1", executor)
        assert success
        assert result == "ok"
        assert executed == ["step1"]

    def test_saga_human_approval_required(self):
        steps = [
            SagaStep(step_id="step1", action="tool_call", tool="Delete"),
            SagaStep(step_id="step2", action="human_approval", requires_human_approval=True),
        ]
        saga_begin("test-session", steps)

        saga_request_approval("test-session", "step2")

        def executor():
            return "ok"

        success, result = saga_execute_step("test-session", "step2", executor)
        assert not success
        assert "human approval" in result.lower()

    def test_saga_approve_and_execute(self):
        steps = [
            SagaStep(step_id="step1", action="tool_call", tool="Write"),
            SagaStep(step_id="step2", action="human_approval", requires_human_approval=True),
        ]
        saga_begin("test-session", steps)

        saga_request_approval("test-session", "step2")
        saga_approve_step("test-session", "step2")

        success, result = saga_execute_step("test-session", "step2", lambda: "approved")
        assert success
        assert result == "approved"

    def test_saga_compensate(self):
        steps = [
            SagaStep(step_id="step1", action="tool_call", tool="Write", compensation="delete file"),
            SagaStep(step_id="step2", action="tool_call", tool="Create", compensation="remove"),
        ]
        saga_begin("test-session", steps)

        saga_execute_step("test-session", "step1", lambda: None)
        saga_execute_step("test-session", "step2", lambda: None)

        results = saga_compensate("test-session")
        assert len(results) == 2
        assert "step2" in results[0]
        assert "step1" in results[1]
        assert "Compensated" in results[0]
        assert "Compensated" in results[1]

    def test_saga_complete(self):
        steps = [SagaStep(step_id="step1", action="tool_call")]
        saga_begin("test-session", steps)

        assert saga_complete("test-session")
        assert "test-session" not in _ACTIVE_SAGAS


class TestResume:
    """Test session resume from checkpoint."""

    def test_resume_session(self, tmp_path):
        checkpoint = create_initial_checkpoint(tmp_path, "test-session", "Test goal")
        advance_phase(tmp_path, "test-session", SessionPhase.PLAN)

        # Simulate new process
        import ahd_session
        ahd_session.update_session_state("test-session", {
            "goal": "Test goal",
            "cost_cap": 20.0,
        }, tmp_path)

        checkpoint = resume_session(tmp_path, "test-session")
        assert checkpoint is not None
        assert checkpoint.phase == SessionPhase.PLAN.value


class TestCompactState:
    """Test compacted durable state."""

    def test_get_compact_state(self, tmp_path):
        checkpoint = create_initial_checkpoint(tmp_path, "test-session", "Test goal")
        advance_phase(tmp_path, "test-session", SessionPhase.PLAN)
        record_step_completion(tmp_path, "test-session", SessionPhase.PLAN, "step1")

        compact = get_compact_state(load_checkpoint(tmp_path, "test-session"))

        assert compact["session_id"] == "test-session"
        assert compact["goal"] == "Test goal"
        assert compact["current_phase"] == SessionPhase.PLAN.value
        assert compact["completed_steps"] == 1


class TestHashFunctions:
    """Test deterministic hash functions."""

    def test_call_hash_deterministic(self):
        h1 = _compute_call_hash("model", "prompt", temp=0.7)
        h2 = _compute_call_hash("model", "prompt", temp=0.7)
        assert h1 == h2

    def test_call_hash_different(self):
        h1 = _compute_call_hash("model", "prompt 1")
        h2 = _compute_call_hash("model", "prompt 2")
        assert h1 != h2

    def test_idempotency_key_deterministic(self):
        k1 = _compute_idempotency_key("session", "Read", {"path": "file.txt"})
        k2 = _compute_idempotency_key("session", "Read", {"path": "file.txt"})
        assert k1 == k2

    def test_idempotency_key_different_args(self):
        k1 = _compute_idempotency_key("session", "Read", {"path": "file1.txt"})
        k2 = _compute_idempotency_key("session", "Read", {"path": "file2.txt"})
        assert k1 != k2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])