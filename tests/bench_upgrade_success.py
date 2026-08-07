#!/usr/bin/env python3
"""T5.8 — Bench script: đo lường nâng cấp loop-harness (REQ-025).

Đo 5 chỉ số critical (metrics) và assert đạt ngưỡng:
  M1. token_reduction   >= 25%  — context_projection + adaptive_compress giảm token.
  M2. parallel_workers  >= 5    — swarm_director dispatch song song 5 worker.
  M3. crash_survive     == True — kill mid-run -> resume, không mất completed work.
  M4. large_model_ok    == True — three_role với budget lớn (32K) chạy OK.
  M5. small_model_ok    == True — three_role với budget nhỏ (2K) chạy OK, viewport <= budget.

Output: báo cáo JSON (in ra stdout khi chạy trực tiếp, hoặc ghi file qua --output).

Chạy như test pytest: pytest tests/bench_upgrade_success.py -q
Chạy như script:   python tests/bench_upgrade_success.py [--output report.json]

Tuân thủ safe zone (tests/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


# ===========================================================================
# Helper: ước lượng token (≈4 chars/token)
# ===========================================================================

def _estimate_tokens(text: str) -> int:
    """Ước lượng số token từ text (≈4 ký tự/token)."""
    return max(1, len(text) // 4)


# ===========================================================================
# M1: Token reduction >= 25%
# ===========================================================================

def _measure_token_reduction(tmp_path: Path) -> dict:
    """Đo tỷ lệ giảm token khi dùng context_projection + adaptive_compress."""
    import adaptive_compress
    import context_projection
    from data_models import Turn

    # Tạo substrate lớn (10KB) chứa nhiều chunk, chỉ một vài liên quan query.
    substrate_path = tmp_path / "substrate.txt"
    lines = []
    for i in range(200):
        if i % 50 == 0:
            lines.append(f"Section {i}: context projection engine relevance scoring viewport budget")
        else:
            lines.append(f"Line {i}: lorem ipsum dolor sit amet consectetur adipiscing elit")
    substrate_path.write_text("\n".join(lines), encoding="utf-8")
    substrate_tokens = _estimate_tokens(substrate_path.read_text(encoding="utf-8"))

    # Project xuống viewport budget nhỏ (1024 tokens).
    viewport = context_projection.project(
        substrate_path, query="context projection relevance viewport budget",
        k=8, budget_tokens=1024,
    )
    viewport_tokens = viewport.tokens

    # Adaptive compress history dài.
    history = [
        Turn(role="user", content=f"question {i} " + "x" * 100, tokens=30,
             timestamp=datetime.now(timezone.utc))
        for i in range(20)
    ]
    compressed = adaptive_compress.compress(
        history, query="analyze context projection trade-offs", mode="auto"
    )
    history_tokens = sum(t.tokens for t in history)
    compressed_tokens = sum(t.tokens for t in compressed)

    # Tỷ lệ giảm: so sánh substrate vs viewport (chính), bonus compress.
    reduction_pct = max(
        0.0,
        (1.0 - viewport_tokens / max(1, substrate_tokens)) * 100.0,
    )
    compress_reduction = max(
        0.0,
        (1.0 - compressed_tokens / max(1, history_tokens)) * 100.0,
    )

    return {
        "substrate_tokens": substrate_tokens,
        "viewport_tokens": viewport_tokens,
        "reduction_pct": round(reduction_pct, 2),
        "history_tokens": history_tokens,
        "compressed_tokens": compressed_tokens,
        "compress_reduction_pct": round(compress_reduction, 2),
        "pass": reduction_pct >= 25.0,
    }


# ===========================================================================
# M2: Parallel workers >= 5
# ===========================================================================

def _measure_parallel_workers() -> dict:
    """Đo số worker song song swarm_director có thể dispatch."""
    import swarm_director
    from data_models import Order, SwarmSpec

    # Tạo 5 order không phụ thuộc, write_set disjoint.
    orders = [
        Order(
            id=f"task-{i}", worker_id=f"w-{i}", task=f"t-{i}",
            write_set=[f"src/module_{i}.py"], idempotency_key=f"k-{i}",
        )
        for i in range(5)
    ]
    spec = SwarmSpec(
        run_id="bench-parallel",
        orders=orders,
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
    )
    results = swarm_director.dispatch(spec)
    success_count = sum(1 for r in results if r.status == "success")
    return {
        "workers_dispatched": len(results),
        "success_count": success_count,
        "max_parallel": 5,
        "pass": success_count >= 5,
    }


# ===========================================================================
# M3: Crash survive
# ===========================================================================

def _measure_crash_survive(tmp_path: Path, monkeypatch) -> dict:
    """Đo khả năng chịu crash: kill mid-run -> resume không mất completed work."""
    import dag_executor

    devin_dir = tmp_path / ".devin"
    for sub in ("plan_state", "checkpoints", "idempotency"):
        (devin_dir / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _=None: devin_dir)
    monkeypatch.setattr(dag_executor, "_repo_root", lambda: tmp_path)
    monkeypatch.delenv("AHD_RUN_ID", raising=False)

    tasks = [
        {"id": f"t{i}", "goal": f"g{i}", "dependencies": [f"t{i-1}"] if i > 1 else []}
        for i in range(1, 7)
    ]
    wf = {"workflow_id": "bench-crash", "tasks": tasks}

    call_counts: dict[str, int] = {}

    def killable_runner(task_id: str, goal: str):
        call_counts[task_id] = call_counts.get(task_id, 0) + 1
        if task_id == "t3" and call_counts.get("t3", 0) == 1:
            raise KeyboardInterrupt("bench crash")
        return {"ok": True, "task_id": task_id}

    crashed = False
    try:
        dag_executor.execute(wf, batch_size=2, runner=killable_runner, max_retries=0)
    except KeyboardInterrupt:
        crashed = True

    # Resume.
    result = dag_executor.resume("bench-crash", runner=killable_runner, max_retries=0)
    return {
        "crash_simulated": crashed,
        "resumed_success": result.success,
        "all_complete": result.status.get("all_complete", False),
        "total_tasks": result.status.get("total_tasks", 0),
        "pass": crashed and result.success and result.status.get("all_complete", False),
    }


# ===========================================================================
# M4 + M5: Large + small model
# ===========================================================================

def _measure_model(budget: int) -> dict:
    """Đo three_role chạy với budget cho trước."""
    import three_role
    from data_models import ModelProfile

    profile = ModelProfile(
        name=f"bench-model-{budget}",
        context_budget=budget,
        role_split={"summarizer": 0.2, "main": 0.6, "corrector": 0.2},
        tool_profile="conservative",
        k_chunks=4,
    )
    task = "Analyze context projection trade-offs. Acceptance criteria: must explain viewport budget."
    result = three_role.run(task, profile)
    return {
        "budget_tokens": budget,
        "viewport_tokens": result.viewport_tokens,
        "viewport_within_budget": result.viewport_tokens <= budget,
        "corrections": result.corrections,
        "pass": result.viewport_tokens <= budget and bool(result.corrected_answer),
    }


def _measure_large_model() -> dict:
    return {"label": "large_model", **_measure_model(32768)}


def _measure_small_model() -> dict:
    return {"label": "small_model", **_measure_model(2048)}


# ===========================================================================
# Run all metrics + build report
# ===========================================================================

def run_bench(tmp_path: Path, monkeypatch=None) -> dict:
    """Chạy toàn bộ 5 metric, trả báo cáo dict."""
    metrics = {}
    metrics["M1_token_reduction"] = _measure_token_reduction(tmp_path)
    metrics["M2_parallel_workers"] = _measure_parallel_workers()
    metrics["M3_crash_survive"] = _measure_crash_survive(tmp_path, monkeypatch)
    metrics["M4_large_model"] = _measure_large_model()
    metrics["M5_small_model"] = _measure_small_model()

    all_pass = all(m["pass"] for m in metrics.values())
    critical_coverage = sum(1 for m in metrics.values() if "pass" in m)
    return {
        "bench_id": "bench-upgrade-success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "critical_metrics_total": 5,
        "critical_metrics_covered": critical_coverage,
        "critical_metrics_coverage_pct": round(critical_coverage / 5 * 100, 1),
        "all_pass": all_pass,
    }


# ===========================================================================
# CLI entry point (chạy như script)
# ===========================================================================

def _cli() -> int:
    import argparse
    import tempfile

    ap = argparse.ArgumentParser(description="T5.8: Bench upgrade success metrics")
    ap.add_argument("--output", help="Ghi báo cáo JSON ra file (mặc định in stdout)")
    ap.add_argument("--tmp", help="Thư mục tạm (mặc định tự tạo)")
    args = ap.parse_args()

    tmp = Path(args.tmp) if args.tmp else Path(tempfile.mkdtemp(prefix="bench-"))
    tmp.mkdir(parents=True, exist_ok=True)

    class _NullMonkey:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)
        def delenv(self, name, raising=True):
            import os
            os.environ.pop(name, None)

    report = run_bench(tmp, _NullMonkey())
    out = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"[bench] Report written to {args.output}", file=sys.stderr)
    else:
        print(out)
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(_cli())


# ===========================================================================
# Pytest tests (chạy như test suite)
# ===========================================================================

@pytest.fixture
def bench_env(tmp_path, monkeypatch):
    """Môi trường bench: tmp_path + monkeypatch cho repo root."""
    return tmp_path, monkeypatch


def test_M1_token_reduction_at_least_25_percent(bench_env):
    tmp_path, _ = bench_env
    m = _measure_token_reduction(tmp_path)
    assert m["pass"], f"Token reduction chỉ {m['reduction_pct']}% < 25%"
    assert m["reduction_pct"] >= 25.0


def test_M2_parallel_workers_at_least_5(bench_env):
    m = _measure_parallel_workers()
    assert m["pass"], f"Chỉ {m['success_count']} worker success < 5"
    assert m["success_count"] >= 5


def test_M3_crash_survive_resume_completes(bench_env):
    tmp_path, monkeypatch = bench_env
    m = _measure_crash_survive(tmp_path, monkeypatch)
    assert m["pass"], "Crash -> resume không hoàn thành"
    assert m["crash_simulated"] is True
    assert m["all_complete"] is True


def test_M4_large_model_ok(bench_env):
    m = _measure_large_model()
    assert m["pass"], f"Large model viewport {m['viewport_tokens']} > budget {m['budget_tokens']}"
    assert m["viewport_within_budget"] is True


def test_M5_small_model_ok(bench_env):
    m = _measure_small_model()
    assert m["pass"], f"Small model viewport {m['viewport_tokens']} > budget {m['budget_tokens']}"
    assert m["viewport_within_budget"] is True


def test_bench_all_5_critical_metrics_covered(bench_env):
    """100% coverage của 5 critical metrics + all_pass."""
    tmp_path, monkeypatch = bench_env
    report = run_bench(tmp_path, monkeypatch)
    assert report["critical_metrics_total"] == 5
    assert report["critical_metrics_covered"] == 5
    assert report["critical_metrics_coverage_pct"] == 100.0
    assert report["all_pass"] is True


def test_bench_report_is_valid_json(bench_env):
    """Báo cáo JSON phải serialize/deserialize round-trip."""
    tmp_path, monkeypatch = bench_env
    report = run_bench(tmp_path, monkeypatch)
    serialized = json.dumps(report, ensure_ascii=False)
    restored = json.loads(serialized)
    assert restored["bench_id"] == "bench-upgrade-success"
    assert len(restored["metrics"]) == 5
