#!/usr/bin/env python3
"""Kiểm tra resource constraints của data_models.py theo §5.5.1 (T1.1)."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from data_models import Chunk, Viewport, Turn, ToolDef, Order, SwarmSpec, CheckpointState, ModelProfile, Action  # noqa: E402


def test_chunk_content_max_length():
    with pytest.raises(ValidationError):
        Chunk(
            id="1", content="x" * 10001, source="src", tokens=10, hash="h",
            metadata={}
        )


def test_chunk_embedding_max_length():
    with pytest.raises(ValidationError):
        Chunk(
            id="1", content="ok", source="src", tokens=10, hash="h",
            embedding=[0.0] * 3073
        )


def test_viewport_chunks_max_length():
    chunks = [Chunk(id=f"c{i}", content="x", source="s", tokens=1, hash="h") for i in range(101)]
    with pytest.raises(ValidationError):
        Viewport(chunks=chunks, tokens=10, source_hashes=[], budget_tokens=10, query="q")


def test_viewport_tokens_out_of_range():
    with pytest.raises(ValidationError):
        Viewport(chunks=[], tokens=-1, source_hashes=[], budget_tokens=10, query="q")


def test_turn_content_max_length():
    from datetime import datetime
    with pytest.raises(ValidationError):
        Turn(role="user", content="x" * 20001, tokens=10, timestamp=datetime.now())


def test_tooldef_parameters_too_many_keys():
    params = {f"p{i}": "v" for i in range(65)}
    with pytest.raises(ValidationError):
        ToolDef(name="t", description="d", parameters=params)


def test_order_inputs_too_many_keys():
    inputs = {f"k{i}": "v" for i in range(65)}
    with pytest.raises(ValidationError):
        Order(id="o", worker_id="w", task="t", inputs=inputs, idempotency_key="ok-1")


def test_swarmspec_orders_max_length():
    from datetime import datetime
    orders = [
        Order(id=f"o{i}", worker_id="w", task="t", inputs={}, idempotency_key=f"ok-{i}")
        for i in range(51)
    ]
    with pytest.raises(ValidationError):
        SwarmSpec(run_id="r", orders=orders, created_at=datetime.now())


def test_checkpoint_metadata_too_many_keys():
    from datetime import datetime
    meta = {f"k{i}": "v" for i in range(65)}
    with pytest.raises(ValidationError):
        CheckpointState(
            version=2, run_id="r", conversation=[], side_effects_ledger=[],
            run_metadata=meta, external_handles=[], timestamp=datetime.now(),
            step_id="step-1"
        )


def test_model_profile_role_split_too_many_keys():
    with pytest.raises(ValidationError):
        ModelProfile(
            name="m", context_budget=8192,
            role_split={"summarizer": 0.2, "main": 0.5, "corrector": 0.2, "extra": 0.1}
        )


def test_action_args_string_value_too_long():
    with pytest.raises(ValidationError):
        Action(id="a", category="read", target="t", args={"k": "x" * 10001})
