#!/usr/bin/env python3
"""swarm_judge.py — Swarm Judge (T4.2, REQ-004).

Mục đích: tổng hợp WorkerResult từ dispatch thành Verdict (Pydantic).
Judge là agent-as-judge với refine loop: nếu có order failed/retry, sinh
retry_orders (tối đa 2 retry). Dùng fixed seed để kết quả deterministic.

Hàm chính: judge(results, spec) -> Verdict.

Quy ước:
- pass=True khi tất cả order success.
- Mỗi order thành 1 StepVerdict (ok/reason/severity).
- retry_orders chứa các Order cần retry (status failed/retry, tối đa 2).
- judge_seed cố định (mặc định 42) để deterministic.

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from data_models import Order, StepVerdict, SwarmSpec, Verdict, WorkerResult  # noqa: E402


# Số retry tối đa cho judge refine loop
MAX_RETRY = 2
# Seed mặc định — deterministic
DEFAULT_SEED = 42


def _step_verdict_for(result: WorkerResult) -> StepVerdict:
    """Tạo StepVerdict cho một WorkerResult."""
    if result.status == "success":
        return StepVerdict(
            step_id=result.order_id,
            ok=True,
            reason="worker success",
            severity="info",
        )
    if result.status == "retry":
        return StepVerdict(
            step_id=result.order_id,
            ok=False,
            reason=result.error or "worker retry",
            severity="warn",
        )
    # failed
    return StepVerdict(
        step_id=result.order_id,
        ok=False,
        reason=result.error or "worker failed",
        severity="error",
    )


def _retry_orders(
    results: list[WorkerResult],
    spec: SwarmSpec,
    *,
    max_retry: int,
    rng: random.Random,
) -> list[Order]:
    """Sinh retry_orders cho các order failed/retry, tối đa max_retry.

    Dùng rng để chọn thứ tự retry (deterministic theo seed).
    """
    order_by_id = {o.id: o for o in spec.orders}
    failed_ids = [
        r.order_id
        for r in results
        if r.status in ("failed", "retry") and r.order_id in order_by_id
    ]
    # Trộn thứ tự bằng seed để deterministic nhưng không theo thứ tự cố định
    rng.shuffle(failed_ids)
    retry: list[Order] = []
    for oid in failed_ids[:max_retry]:
        original = order_by_id[oid]
        # Tạo order retry với id mới
        retry.append(
            Order(
                id=f"{oid}-retry",
                worker_id=original.worker_id,
                task=original.task,
                inputs=original.inputs,
                outputs=original.outputs,
                write_set=original.write_set,
                idempotency_key=f"{original.idempotency_key}-r"[:64],
                depends_on=original.depends_on,
            )
        )
    return retry


def _build_feedback(results: list[WorkerResult], pass_: bool) -> str:
    """Tạo feedback text tóm tắt verdict."""
    ok = sum(1 for r in results if r.status == "success")
    fail = sum(1 for r in results if r.status == "failed")
    retry = sum(1 for r in results if r.status == "retry")
    head = "PASS" if pass_ else "FAIL"
    return (
        f"{head}: {ok} success, {fail} failed, {retry} retry "
        f"trong {len(results)} order"
    )


def judge(
    results: list[WorkerResult],
    spec: SwarmSpec,
    *,
    seed: int = DEFAULT_SEED,
    max_retry: int = MAX_RETRY,
) -> Verdict:
    """Tổng hợp WorkerResult thành Verdict.

    Nhận vào:
        results    — danh sách WorkerResult từ dispatch.
        spec       — SwarmSpec gốc (để tra order khi cần retry).
        seed       — seed cho RNG (deterministic).
        max_retry  — số retry tối đa (mặc định 2).

    Trả về:
        Verdict với pass_, per_step, feedback, retry_orders, judge_seed.
    """
    if not isinstance(results, list):
        raise TypeError("results phải là list[WorkerResult]")
    if not isinstance(spec, SwarmSpec):
        raise TypeError("spec phải là SwarmSpec")
    if max_retry < 0:
        raise ValueError("max_retry phải >= 0")

    rng = random.Random(seed)
    per_step = [_step_verdict_for(r) for r in results]
    pass_ = all(r.status == "success" for r in results) and len(results) > 0
    feedback = _build_feedback(results, pass_)
    retry = _retry_orders(results, spec, max_retry=max_retry, rng=rng)

    return Verdict(
        pass_=pass_,
        per_step=per_step,
        feedback=feedback,
        retry_orders=retry,
        judge_seed=seed,
    )


def _cli() -> int:
    """CLI stub: đọc JSON results + spec từ stdin, in Verdict JSON.

    Pentest fix: xử lý stdin rỗng/sai JSON (trả 1 thay vì crash).
    """
    import json

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(f"[swarm_judge] lỗi parse JSON stdin: {e}", file=sys.stderr)
        return 1
    if "spec" not in payload:
        print("[swarm_judge] lỗi: thiếu trường 'spec' trong payload", file=sys.stderr)
        return 1
    results = [WorkerResult.model_validate(r) for r in payload.get("results", [])]
    spec = SwarmSpec.model_validate(payload["spec"])
    v = judge(results, spec, seed=int(payload.get("seed", DEFAULT_SEED)))
    sys.stdout.write(v.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
