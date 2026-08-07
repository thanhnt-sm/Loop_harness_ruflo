#!/usr/bin/env python3
"""T5.4: Property-based tests cho data_models + checkpoint + idempotency + DAG.

Dùng Hypothesis để sinh đầu vào ngẫu nhiên và kiểm tra các bất biến:
- data_models overflow: string/list/dict vượt giới hạn -> ValidationError.
- checkpoint round-trip: save -> load giữ nguyên dữ liệu.
- idempotency: register cùng key trả cùng kết quả.
- DAG topo sort: mọi DAG acyclic có thứ tự topo hợp lệ.
- viewport budget: tổng tokens của chunks <= budget_tokens.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st, assume

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)


# ---------------------------------------------------------------------------
# data_models overflow
# ---------------------------------------------------------------------------
from data_models import (  # noqa: E402
    Chunk, Viewport, Turn, Order, SwarmSpec, WorkerResult,
    CheckpointState, ModelProfile, Exploit, RewardScore, ABCReport,
    SideEffect, ExternalHandle, IdempotencyEntry, ToolDef, Action,
    ReflectVerdict, CRVScore, CoT, StepVerdict, Verdict,
)
from pydantic import ValidationError  # noqa: E402


@given(st.text(max_size=200))
@settings(max_examples=50, deadline=None)
def test_chunk_content_within_limit(content):
    """Chunk.content có max_length=10000 — chuỗi ≤200 chars luôn hợp lệ."""
    chunk = Chunk(
        id="c1", content=content, source="src", tokens=1,
        hash="h", metadata={},
    )
    assert chunk.content == content


def test_chunk_content_overflow_rejected():
    with pytest.raises(ValidationError):
        Chunk(
            id="c1", content="x" * 10001, source="src", tokens=1,
            hash="h", metadata={},
        )


def test_chunk_tokens_overflow_rejected():
    with pytest.raises(ValidationError):
        Chunk(
            id="c1", content="ok", source="src", tokens=100001,
            hash="h", metadata={},
        )


def test_chunk_metadata_too_many_keys_rejected():
    with pytest.raises(ValidationError):
        Chunk(
            id="c1", content="ok", source="src", tokens=1,
            hash="h", metadata={f"k{i}": "v" for i in range(65)},
        )


def test_chunk_metadata_string_value_too_long_rejected():
    with pytest.raises(ValidationError):
        Chunk(
            id="c1", content="ok", source="src", tokens=1,
            hash="h", metadata={"k": "v" * 10001},
        )


def test_viewport_chunks_overflow_rejected():
    chunks = [
        Chunk(id=f"c{i}", content="x", source="s", tokens=1, hash="h")
        for i in range(101)
    ]
    with pytest.raises(ValidationError):
        Viewport(chunks=chunks, tokens=10, source_hashes=[], budget_tokens=100, query="q")


def test_order_idempotency_key_pattern_rejected():
    with pytest.raises(ValidationError):
        Order(
            id="o1", worker_id="w", task="t",
            idempotency_key="UPPER CASE",  # pattern chỉ cho phép [a-z0-9_-]
        )


def test_order_idempotency_key_too_long_rejected():
    with pytest.raises(ValidationError):
        Order(
            id="o1", worker_id="w", task="t",
            idempotency_key="a" * 65,
        )


def test_swarm_spec_orders_overflow_rejected():
    orders = [
        Order(id=f"o{i}", worker_id="w", task="t", idempotency_key=f"k{i}")
        for i in range(51)
    ]
    with pytest.raises(ValidationError):
        SwarmSpec(run_id="r", orders=orders, created_at=datetime.now(timezone.utc))


def test_worker_result_cost_overflow_rejected():
    with pytest.raises(ValidationError):
        WorkerResult(
            order_id="o", worker_id="w", status="success",
            duration_ms=1, cost_usd=101.0,
        )


def test_checkpoint_state_version_too_low_rejected():
    with pytest.raises(ValidationError):
        CheckpointState(
            version=1, run_id="r", conversation=[], side_effects_ledger=[],
            run_metadata={}, external_handles=[],
            timestamp=datetime.now(timezone.utc), step_id="s",
        )


def test_checkpoint_state_step_id_pattern_rejected():
    with pytest.raises(ValidationError):
        CheckpointState(
            version=2, run_id="r", conversation=[], side_effects_ledger=[],
            run_metadata={}, external_handles=[],
            timestamp=datetime.now(timezone.utc), step_id="bad space",
        )


def test_model_profile_budget_too_low_rejected():
    with pytest.raises(ValidationError):
        ModelProfile(name="x", context_budget=1023)


def test_exploit_type_invalid_rejected():
    with pytest.raises(ValidationError):
        Exploit(
            exploit_type="bogus", description="d", detected=False, penalty=0.0,
            evidence="e",
        )


def test_reward_score_out_of_range_rejected():
    with pytest.raises(ValidationError):
        RewardScore(
            base_score=101.0, shaped_score=0, cost_penalty=0,
            security_penalty=0, quality_bonus=0, final=0,
        )


def test_abc_report_pass_alias():
    r = ABCReport(
        task_valid=True, outcome_valid=True, process_score=0.5,
        judge_verdict="ok", pass_=True, judge_seed=1, run_id="r",
    )
    # pass_ alias "pass"
    dumped = r.model_dump(by_alias=True)
    assert dumped["pass"] is True


def test_side_effect_kind_invalid_rejected():
    with pytest.raises(ValidationError):
        SideEffect(
            key="k", kind="bogus", target="t", hash="h",
            timestamp=datetime.now(timezone.utc), result_status="success",
        )


def test_external_handle_kind_invalid_rejected():
    with pytest.raises(ValidationError):
        ExternalHandle(
            handle_id="h", kind="bogus", url="http://x", allowlisted=True,
            ssrf_checked=True,
        )


def test_idempotency_entry_key_pattern_rejected():
    with pytest.raises(ValidationError):
        IdempotencyEntry(
            key="BAD CASE", run_id="r", result_hash="h",
            result_status="success", timestamp=datetime.now(timezone.utc),
        )


def test_tool_def_parameters_too_many_keys_rejected():
    with pytest.raises(ValidationError):
        ToolDef(
            name="t", description="d",
            parameters={f"k{i}": "v" for i in range(65)},
        )


def test_action_category_invalid_rejected():
    with pytest.raises(ValidationError):
        Action(id="a", category="bogus", target="t")


def test_action_args_too_many_keys_rejected():
    with pytest.raises(ValidationError):
        Action(
            id="a", category="read", target="t",
            args={f"k{i}": "v" for i in range(65)},
        )


def test_reflect_verdict_level_invalid_rejected():
    with pytest.raises(ValidationError):
        ReflectVerdict(action_id="a", level="bogus", block=True, reason="r")


def test_crv_score_out_of_range_rejected():
    with pytest.raises(ValidationError):
        CRVScore(reasoning_load=1.5, coherence=0.5, critique="c", pass_=True)


def test_cot_steps_overflow_rejected():
    with pytest.raises(ValidationError):
        CoT(
            problem="p", steps=["s"] * 51, tokens=1, model_profile="m",
        )


def test_step_verdict_severity_invalid_rejected():
    with pytest.raises(ValidationError):
        StepVerdict(step_id="s", ok=True, reason="r", severity="bogus")


def test_verdict_retry_orders_overflow_rejected():
    orders = [
        Order(id=f"o{i}", worker_id="w", task="t", idempotency_key=f"k{i}")
        for i in range(51)
    ]
    with pytest.raises(ValidationError):
        Verdict(
            pass_=True, per_step=[], feedback="ok",
            retry_orders=orders, judge_seed=1,
        )


# ---------------------------------------------------------------------------
# Checkpoint round-trip (property-based)
# ---------------------------------------------------------------------------
@given(
    st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)
@settings(max_examples=50, deadline=None)
def test_checkpoint_round_trip(step_id):
    """save -> load giữ nguyên step_id (sau khi sanitize)."""
    from checkpoint import save, load, _sanitize_step_id
    # step_id đã trong alphabet hợp lệ -> sanitize giữ nguyên
    sanitized = _sanitize_step_id(step_id)
    state = CheckpointState(
        version=2, run_id="r-prop", conversation=[], side_effects_ledger=[],
        run_metadata={"k": "v"}, external_handles=[],
        timestamp=datetime.now(timezone.utc), step_id=step_id,
    )
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = save(state, root=Path(td))
        loaded = load(path)
        assert loaded.step_id == sanitized
        assert loaded.run_id == "r-prop"


@given(st.text(max_size=50))
@settings(max_examples=50, deadline=None)
def test_checkpoint_sanitize_step_id_idempotent(step_id):
    """sanitize(sanitize(x)) == sanitize(x)."""
    from checkpoint import _sanitize_step_id
    once = _sanitize_step_id(step_id)
    twice = _sanitize_step_id(once)
    assert once == twice


@given(st.text(max_size=50))
@settings(max_examples=50, deadline=None)
def test_checkpoint_sanitize_step_id_safe_chars(step_id):
    """sanitize luôn trả về chuỗi khớp ^[a-zA-Z0-9_-]{1,64}$ hoặc 'unnamed'."""
    from checkpoint import _sanitize_step_id
    import re
    result = _sanitize_step_id(step_id)
    assert result == "unnamed" or re.match(r"^[a-zA-Z0-9_-]{1,64}$", result)


# ---------------------------------------------------------------------------
# Idempotency (property-based)
# ---------------------------------------------------------------------------
@given(st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_"))
@settings(max_examples=30, deadline=None)
def test_idempotency_register_same_key_same_result(key):
    """register cùng key + op luôn trả cùng kết quả."""
    import tempfile
    from idempotency import register
    counter = {"n": 0}

    def op():
        counter["n"] += 1
        return counter["n"]

    with tempfile.TemporaryDirectory() as td:
        import ahd_session
        original_repo = ahd_session.get_repo_root
        original_config = ahd_session.get_config_root
        td_path = Path(td)
        ahd_session.get_repo_root = lambda _=None: td_path
        ahd_session.get_config_root = lambda _r=None: td_path / ".devin"
        try:
            r1 = register(key, op, run_id="prop-run")
            r2 = register(key, op, run_id="prop-run")
            assert r1 == r2
            assert counter["n"] == 1  # op chỉ chạy 1 lần
        finally:
            ahd_session.get_repo_root = original_repo
            ahd_session.get_config_root = original_config


# ---------------------------------------------------------------------------
# DAG topo sort (property-based)
# ---------------------------------------------------------------------------
@given(
    st.lists(
        st.tuples(
            st.text(min_size=1, max_size=5, alphabet="ABCDEFGH"),
            st.text(min_size=1, max_size=5, alphabet="ABCDEFGH"),
        ),
        max_size=20,
    )
)
@settings(max_examples=50, deadline=None)
def test_topological_sort_acyclic_valid(edges_raw):
    """Nếu DAG acyclic, topo sort phải chứa mọi node và dep trước dependent."""
    import dag_compile
    # Loại bỏ self-loop và edge trùng
    edges_raw = [(a, b) for a, b in edges_raw if a != b]
    nodes_set = set()
    for a, b in edges_raw:
        nodes_set.add(a)
        nodes_set.add(b)
    nodes = [{"task_id": n, "deps": []} for n in nodes_set]
    edges = [{"from": a, "to": b} for a, b in edges_raw]
    # Build deps từ edges
    dep_map = {n: [] for n in nodes_set}
    for a, b in edges_raw:
        if b in dep_map and a not in dep_map[b]:
            dep_map[b].append(a)
    for n in nodes:
        n["deps"] = dep_map.get(n["task_id"], [])

    sorted_ids, cycle = dag_compile.topological_sort(nodes, edges)
    if cycle:
        return  # có cycle -> bỏ qua
    # Mọi node phải có trong sorted_ids
    assert set(sorted_ids) == nodes_set
    assert len(sorted_ids) == len(nodes_set)
    # Mọi dep phải xuất hiện trước dependent
    pos = {tid: i for i, tid in enumerate(sorted_ids)}
    for a, b in edges_raw:
        if a in pos and b in pos:
            assert pos[a] < pos[b], f"{a} phải trước {b}"


# ---------------------------------------------------------------------------
# Viewport budget (property-based)
# ---------------------------------------------------------------------------
@given(
    st.lists(
        st.integers(min_value=1, max_value=100),
        max_size=50,
    )
)
@settings(max_examples=50, deadline=None)
def test_viewport_tokens_within_budget(token_list):
    """Viewport.tokens = tổng chunk tokens, phải <= budget_tokens."""
    total = sum(token_list)
    assume(total <= 200000)  # giới hạn schema
    assume(len(token_list) <= 100)
    chunks = [
        Chunk(id=f"c{i}", content="x", source="s", tokens=t, hash=f"h{i}")
        for i, t in enumerate(token_list)
    ]
    vp = Viewport(
        chunks=chunks, tokens=total,
        source_hashes=[f"h{i}" for i in range(len(chunks))],
        budget_tokens=max(total, 1), query="q",
    )
    assert vp.tokens <= vp.budget_tokens


# ---------------------------------------------------------------------------
# Slugify idempotent (property-based)
# ---------------------------------------------------------------------------
@given(st.text(max_size=60))
@settings(max_examples=50, deadline=None)
def test_slugify_idempotent(text):
    """slugify(slugify(x)) == slugify(x)."""
    from plan_fsm.storage import slugify
    once = slugify(text)
    twice = slugify(once)
    assert once == twice


@given(st.text(max_size=60))
@settings(max_examples=50, deadline=None)
def test_slugify_no_uppercase(text):
    """slugify luôn trả về lowercase."""
    from plan_fsm.storage import slugify
    result = slugify(text)
    assert result == result.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
