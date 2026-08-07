#!/usr/bin/env python3
"""Kiểm thử Swarm Judge — T4.2 (REQ-004).

Các ca kiểm thử:
1. judge với tất cả success -> Verdict pass=True, không retry.
2. judge với failed -> Verdict pass=False, có retry_orders.
3. judge retry tối đa 2 (max_retry).
4. judge deterministic: cùng input + seed -> cùng output.
5. judge seed khác -> retry order thứ tự khác (nếu có).
6. per_step đúng ok/severity theo status.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from data_models import Order, SwarmSpec, WorkerResult  # noqa: E402
from swarm_judge import judge  # noqa: E402


def _make_spec(order_ids: list[str]) -> SwarmSpec:
    return SwarmSpec(
        run_id="run-test",
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
        orders=[
            Order(id=oid, worker_id=f"w-{oid}", task=oid, idempotency_key=oid)
            for oid in order_ids
        ],
    )


def _result(oid: str, status: str, error: str | None = None) -> WorkerResult:
    return WorkerResult(
        order_id=oid,
        worker_id=f"w-{oid}",
        status=status,
        error=error,
        duration_ms=1,
        cost_usd=0.0,
    )


def test_judge_all_success_pass():
    spec = _make_spec(["a", "b", "c"])
    results = [_result("a", "success"), _result("b", "success"), _result("c", "success")]
    v = judge(results, spec, seed=42)
    assert v.pass_ is True
    assert len(v.retry_orders) == 0
    assert all(s.ok for s in v.per_step)
    assert "PASS" in v.feedback


def test_judge_failed_generates_retry():
    spec = _make_spec(["a", "b"])
    results = [_result("a", "success"), _result("b", "failed", error="boom")]
    v = judge(results, spec, seed=42, max_retry=2)
    assert v.pass_ is False
    assert len(v.retry_orders) == 1
    assert v.retry_orders[0].id == "b-retry"
    # per_step cho b phải ok=False, severity=error
    sb = next(s for s in v.per_step if s.step_id == "b")
    assert sb.ok is False
    assert sb.severity == "error"
    assert "boom" in sb.reason


def test_judge_retry_max():
    spec = _make_spec(["a", "b", "c"])
    results = [
        _result("a", "failed"),
        _result("b", "failed"),
        _result("c", "failed"),
    ]
    v = judge(results, spec, seed=42, max_retry=2)
    assert v.pass_ is False
    # Tối đa 2 retry
    assert len(v.retry_orders) == 2


def test_judge_deterministic_same_seed():
    spec = _make_spec(["a", "b"])
    results = [_result("a", "failed"), _result("b", "failed")]
    v1 = judge(results, spec, seed=42, max_retry=2)
    v2 = judge(results, spec, seed=42, max_retry=2)
    assert v1.model_dump_json() == v2.model_dump_json()
    assert v1.judge_seed == 42


def test_judge_retry_status_also_retried():
    spec = _make_spec(["a"])
    results = [_result("a", "retry", error="transient")]
    v = judge(results, spec, seed=42, max_retry=2)
    assert v.pass_ is False
    assert len(v.retry_orders) == 1
    sa = v.per_step[0]
    assert sa.severity == "warn"


def test_judge_invalid_inputs():
    spec = _make_spec(["a"])
    with pytest.raises(TypeError):
        judge("not a list", spec)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        judge([], "not spec")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        judge([], spec, max_retry=-1)


def test_judge_empty_results_fail():
    spec = _make_spec(["a"])
    v = judge([], spec, seed=42)
    # Không có result -> pass=False (guard len > 0)
    assert v.pass_ is False
