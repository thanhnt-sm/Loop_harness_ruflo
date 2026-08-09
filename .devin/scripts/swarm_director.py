#!/usr/bin/env python3
"""swarm_director.py — Hierarchical Swarm Director (T4.1, REQ-004).

Mục đích: dịch một implementation plan (markdown) thành SwarmSpec (Pydantic),
sau đó dispatch song song N worker (mặc định N=5) theo DAG phụ thuộc.

Quy ước:
- compile_spec(plan_md) -> SwarmSpec: parse plan markdown, tách task table thành
  các Order. Mỗi Order có write_set (đường dẫn file sẽ ghi) và idempotency_key.
- dispatch(spec) -> list[WorkerResult]: chạy song song các Order không phụ thuộc
  nhau, validate write_set không giao nhau (disjoint), raise WriteSetConflict khi
  hai worker ghi cùng đường dẫn.

Hàm worker mặc định là stub (giả lập) — không gọi model thật — để test deterministic.
Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from data_models import Order, SwarmSpec, WorkerResult  # noqa: E402


class WriteSetConflict(Exception):
    """Hai worker ghi cùng đường dẫn trong write_set — xung đột."""


# Regex đơn giản để nhận diện dòng task table trong plan markdown.
# Hỗ trợ bảng có cột Task ID | Description | File Path | Function | ...
_TASK_ROW_RE = re.compile(
    r"^\|\s*(?P<id>T\d+\.\d+|[A-Z]+-\d+)\s*\|(?P<rest>.*)$",
    re.IGNORECASE,
)
# Tìm đường dẫn file .py trong cell của bảng
_FILE_PATH_RE = re.compile(r"[\w./\\-]+\.py")


def _now() -> datetime:
    """Trả về timestamp UTC hiện tại (giúp test monkeypatch)."""
    return datetime.now(timezone.utc)


def _parse_task_id(raw: str) -> str:
    """Làm sạch task id (vd 'T4.1' -> 't4-1') để dùng làm idempotency_key."""
    cleaned = raw.strip().lower()
    cleaned = re.sub(r"[^a-z0-9_-]", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "task"


def _extract_file_paths(cell: str) -> list[str]:
    """Trích xuất danh sách đường dẫn file .py từ một cell markdown."""
    paths: list[str] = []
    for m in _FILE_PATH_RE.finditer(cell):
        p = m.group(0).replace("\\", "/").strip()
        if p and p not in paths:
            paths.append(p)
    return paths


def compile_spec(
    plan_md: str,
    *,
    run_id: Optional[str] = None,
    max_parallel: int = 5,
) -> SwarmSpec:
    """Biên dịch nội dung plan markdown thành SwarmSpec.

    Nhận vào:
        plan_md     — nội dung IMPLEMENTATION_PLAN.md.
        run_id      — định danh run (mặc định sinh từ timestamp).
        max_parallel — số worker tối đa chạy song song (1..16).

    Trả về:
        SwarmSpec với danh sách Order tương ứng các task trong bảng plan.
        Mỗi Order có write_set là các đường dẫn file .py sẽ được task ghi.
    """
    if not isinstance(plan_md, str):
        raise TypeError("plan_md phải là chuỗi")
    if not (1 <= max_parallel <= 16):
        raise ValueError("max_parallel phải nằm trong 1..16")

    rid = run_id or f"run-{int(_now().timestamp())}"
    orders: list[Order] = []
    seen_ids: set[str] = set()

    for line in plan_md.splitlines():
        m = _TASK_ROW_RE.match(line)
        if not m:
            continue
        task_id_raw = m.group("id")
        rest = m.group("rest")
        # Bỏ qua dòng header (chứa '---' hoặc 'Description')
        if "description" in rest.lower() or set(rest.strip(" |")) <= {"-"}:
            continue

        tid = _parse_task_id(task_id_raw)
        # Đảm bảo id duy nhất
        base = tid
        suffix = 1
        while tid in seen_ids:
            tid = f"{base}-{suffix}"
            suffix += 1
        seen_ids.add(tid)

        file_paths = _extract_file_paths(rest)
        # write_set = các đường dẫn file .py (chính là output của task)
        write_set = file_paths[:50]
        # outputs = cũng là file_paths (artifacts)
        outputs = list(write_set)

        try:
            order = Order(
                id=tid,
                worker_id=f"worker-{tid}",
                task=task_id_raw,
                inputs={},
                outputs=outputs,
                write_set=write_set,
                idempotency_key=tid[:64] if tid else "task",
                depends_on=[],
            )
        except Exception as e:
            print(f"[swarm_director] unexpected exception: {e}", file=sys.stderr)
            # Bỏ qua dòng không parse được thành Order hợp lệ
            continue
        orders.append(order)

    if not orders:
        # Trường hợp plan không có bảng task: tạo 1 order rỗng để spec vẫn hợp lệ
        orders.append(
            Order(
                id="noop",
                worker_id="worker-noop",
                task="noop",
                idempotency_key="noop",
            )
        )

    return SwarmSpec(
        run_id=rid,
        orders=orders[:50],
        max_parallel=max_parallel,
        created_at=_now(),
    )


def _validate_disjoint_write_sets(spec: SwarmSpec) -> None:
    """Kiểm tra write_set của các order không giao nhau.

    Raise WriteSetConflict nếu có đường dẫn bị 2+ order ghi.
    """
    owners: dict[str, str] = {}
    for order in spec.orders:
        for path in order.write_set:
            norm = path.strip().lower()
            if norm in owners and owners[norm] != order.id:
                raise WriteSetConflict(
                    f"write_set xung đột: '{path}' được ghi bởi "
                    f"{owners[norm]} và {order.id}"
                )
            owners[norm] = order.id


def _default_worker(order: Order) -> WorkerResult:
    """Worker stub giả lập: luôn success, không ghi file thật.

    Dùng trong test để kết quả deterministic mà không cần model thật.
    """
    # Giả lập duration nhỏ, cost 0
    return WorkerResult(
        order_id=order.id,
        worker_id=order.worker_id,
        status="success",
        artifacts=list(order.outputs),
        error=None,
        duration_ms=10,
        cost_usd=0.0,
    )


def dispatch(
    spec: SwarmSpec,
    *,
    worker_fn: Optional[Callable[[Order], WorkerResult]] = None,
) -> list[WorkerResult]:
    """Dispatch song song các order trong spec.

    Nhận vào:
        spec      — SwarmSpec chứa danh sách order.
        worker_fn — hàm worker tùy chọn (mặc định dùng stub giả lập).

    Trả về:
        Danh sách WorkerResult theo thứ tự order trong spec.

    Raise:
        WriteSetConflict — khi write_set của 2 order giao nhau.
        ValueError       — khi spec không hợp lệ.
    """
    if not isinstance(spec, SwarmSpec):
        raise TypeError("spec phải là SwarmSpec")
    _validate_disjoint_write_sets(spec)

    fn = worker_fn or _default_worker
    results_by_id: dict[str, WorkerResult] = {}

    # Tính dependency: order.depends_on phải hoàn thành trước
    pending: dict[str, Order] = {o.id: o for o in spec.orders}
    completed: set[str] = set()

    # Vòng lặp theo tầng (wave) — mỗi tầng chạy song song các order sẵn sàng
    max_waves = len(spec.orders) + 1
    while pending:
        ready = [
            o
            for o in pending.values()
            if all(dep in completed for dep in o.depends_on)
        ]
        if not ready:
            # Có cycle hoặc dep thiếu — raise để tránh loop vô hạn
            raise ValueError(
                f"phụ thuộc vòng hoặc thiếu: {list(pending.keys())}"
            )
        n = min(len(ready), spec.max_parallel)
        batch = ready[:n]

        with ThreadPoolExecutor(max_workers=n) as ex:
            future_map = {ex.submit(fn, o): o for o in batch}
            for fut in as_completed(future_map):
                order = future_map[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # worker raise -> mark failed
                    res = WorkerResult(
                        order_id=order.id,
                        worker_id=order.worker_id,
                        status="failed",
                        error=str(exc)[:2000],
                        duration_ms=0,
                        cost_usd=0.0,
                    )
                results_by_id[order.id] = res
                completed.add(order.id)
                pending.pop(order.id, None)

        if max_waves <= 0:
            raise RuntimeError("vượt quá số wave cho phép — có thể cycle")
        max_waves -= 1

    # Trả theo thứ tự order ban đầu
    return [results_by_id[o.id] for o in spec.orders if o.id in results_by_id]


def _cli() -> int:
    """CLI stub: đọc plan từ stdin, in SwarmSpec JSON, dispatch giả lập."""
    plan_md = sys.stdin.read()
    spec = compile_spec(plan_md)
    sys.stdout.write(spec.model_dump_json(indent=2))
    sys.stdout.write("\n")
    results = dispatch(spec)
    for r in results:
        sys.stdout.write(f"{r.order_id}: {r.status}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
