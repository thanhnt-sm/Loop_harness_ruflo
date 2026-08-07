#!/usr/bin/env python3
"""Kiểm thử Swarm Director — T4.1 (REQ-004).

Các ca kiểm thử:
1. compile_spec parse plan markdown có bảng task -> SwarmSpec với Order.
2. compile_spec với plan rỗng -> spec có 1 order noop.
3. dispatch song song N worker -> tất cả success.
4. dispatch phát hiện WriteSetConflict khi 2 order ghi cùng file.
5. dispatch tôn trọng depends_on (chạy tuần tự).
6. dispatch worker raise -> WorkerResult failed.
7. max_parallel ngoài phạm vi raise ValueError.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from data_models import Order, SwarmSpec, WorkerResult  # noqa: E402
from swarm_director import (  # noqa: E402
    WriteSetConflict,
    compile_spec,
    dispatch,
)


_PLAN_MD = """# Plan

## Task table

| Task ID | Description | File Path | Function | Acceptance Criteria |
|---------|-------------|-----------|----------|---------------------|
| T4.1 | Swarm Director | `.devin/scripts/swarm_director.py` | `compile_spec` | N=5 parallel |
| T4.2 | Swarm Judge | `.devin/scripts/swarm_judge.py` | `judge` | max 2 retry |
| T4.3 | ABC Checklist | `.devin/scripts/abc_checklist.py` | `evaluate` | gate block |
"""


def test_compile_spec_parses_task_table():
    spec = compile_spec(_PLAN_MD, run_id="run-1", max_parallel=3)
    assert isinstance(spec, SwarmSpec)
    assert spec.run_id == "run-1"
    assert spec.max_parallel == 3
    # 3 task -> 3 order
    assert len(spec.orders) == 3
    ids = [o.id for o in spec.orders]
    assert "t4-1" in ids
    assert "t4-2" in ids
    assert "t4-3" in ids
    # Mỗi order có write_set là đường dẫn file
    o1 = next(o for o in spec.orders if o.id == "t4-1")
    assert any("swarm_director.py" in p for p in o1.write_set)


def test_compile_spec_empty_plan_returns_noop():
    spec = compile_spec("# Empty plan\nNo tasks here.", run_id="r")
    assert len(spec.orders) == 1
    assert spec.orders[0].id == "noop"


def test_compile_spec_invalid_inputs():
    with pytest.raises(TypeError):
        compile_spec(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compile_spec("ok", max_parallel=0)
    with pytest.raises(ValueError):
        compile_spec("ok", max_parallel=99)


def test_dispatch_parallel_all_success():
    spec = compile_spec(_PLAN_MD, run_id="run-dispatch", max_parallel=5)
    results = dispatch(spec)
    assert len(results) == 3
    assert all(r.status == "success" for r in results)
    # Thứ tự kết quả khớp thứ tự order
    assert [r.order_id for r in results] == [o.id for o in spec.orders]


def test_dispatch_write_set_conflict():
    """Hai order ghi cùng file -> WriteSetConflict."""
    from datetime import datetime, timezone

    spec = SwarmSpec(
        run_id="run-conflict",
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
        orders=[
            Order(
                id="a",
                worker_id="w-a",
                task="t-a",
                write_set=["same/file.py"],
                idempotency_key="a",
            ),
            Order(
                id="b",
                worker_id="w-b",
                task="t-b",
                write_set=["same/file.py"],
                idempotency_key="b",
            ),
        ],
    )
    with pytest.raises(WriteSetConflict):
        dispatch(spec)


def test_dispatch_respects_depends_on():
    """Order có depends_on phải chạy sau dependency."""
    from datetime import datetime, timezone

    order_log: list[str] = []

    def worker(o: Order) -> WorkerResult:
        order_log.append(o.id)
        return WorkerResult(
            order_id=o.id,
            worker_id=o.worker_id,
            status="success",
            duration_ms=1,
            cost_usd=0.0,
        )

    spec = SwarmSpec(
        run_id="run-deps",
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
        orders=[
            Order(
                id="child",
                worker_id="w-child",
                task="t-child",
                idempotency_key="child",
                depends_on=["parent"],
            ),
            Order(
                id="parent",
                worker_id="w-parent",
                task="t-parent",
                idempotency_key="parent",
            ),
        ],
    )
    results = dispatch(spec, worker_fn=worker)
    assert all(r.status == "success" for r in results)
    # parent phải xuất hiện trước child trong log
    assert order_log.index("parent") < order_log.index("child")


def test_dispatch_worker_raise_marks_failed():
    from datetime import datetime, timezone

    def bad_worker(o: Order) -> WorkerResult:
        if o.id == "bad":
            raise RuntimeError("boom")
        return WorkerResult(
            order_id=o.id,
            worker_id=o.worker_id,
            status="success",
            duration_ms=1,
            cost_usd=0.0,
        )

    spec = SwarmSpec(
        run_id="run-fail",
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
        orders=[
            Order(id="good", worker_id="w", task="t", idempotency_key="good"),
            Order(id="bad", worker_id="w", task="t", idempotency_key="bad"),
        ],
    )
    results = dispatch(spec, worker_fn=bad_worker)
    statuses = {r.order_id: r.status for r in results}
    assert statuses["good"] == "success"
    assert statuses["bad"] == "failed"
    bad = next(r for r in results if r.order_id == "bad")
    assert "boom" in (bad.error or "")


def test_dispatch_cycle_detected():
    from datetime import datetime, timezone

    spec = SwarmSpec(
        run_id="run-cycle",
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
        orders=[
            Order(id="a", worker_id="w", task="t", idempotency_key="a", depends_on=["b"]),
            Order(id="b", worker_id="w", task="t", idempotency_key="b", depends_on=["a"]),
        ],
    )
    with pytest.raises(ValueError):
        dispatch(spec)


# --- T5.5: Mở rộng coverage ---

def test_parse_task_id_cleaning():
    """_parse_task_id làm sạch task id thành idempotency_key hợp lệ."""
    from swarm_director import _parse_task_id
    assert _parse_task_id("T4.1") == "t4-1"
    assert _parse_task_id("ABC-123") == "abc-123"
    assert _parse_task_id("  T4.1  ") == "t4-1"
    # Ký tự đặc biệt -> "-"
    assert _parse_task_id("T4.1!@#") == "t4-1"
    # Rỗng -> "task"
    assert _parse_task_id("   ") == "task"
    assert _parse_task_id("---") == "task"


def test_extract_file_paths():
    """_extract_file_paths trích đường dẫn .py từ cell."""
    from swarm_director import _extract_file_paths
    paths = _extract_file_paths("foo.py and bar/baz.py and qux.py")
    assert "foo.py" in paths
    assert "bar/baz.py" in paths
    assert "qux.py" in paths
    # Trùng lặp bị loại
    paths2 = _extract_file_paths("a.py a.py")
    assert paths2 == ["a.py"]
    # Không có .py -> rỗng
    assert _extract_file_paths("no files here") == []
    # Backslash được chuẩn hóa thành forward slash
    paths3 = _extract_file_paths("src\\mod.py")
    assert "src/mod.py" in paths3


def test_compile_spec_dedup_ids():
    """Hai task cùng id -> id thứ 2 được thêm suffix."""
    plan = """| T4.1 | desc1 | a.py | f | c |
| T4.1 | desc2 | b.py | f | c |
"""
    spec = compile_spec(plan, run_id="r")
    ids = [o.id for o in spec.orders]
    assert "t4-1" in ids
    # id thứ 2 phải khác
    assert len(set(ids)) == 2


def test_compile_spec_skips_header_rows():
    """Dòng header (chứa 'Description' hoặc '---') bị bỏ qua."""
    plan = """| Task ID | Description | File | Func | Crit |
|---------|-------------|------|------|------|
| T4.1 | real task | a.py | f | c |
"""
    spec = compile_spec(plan, run_id="r")
    assert len(spec.orders) == 1
    assert spec.orders[0].id == "t4-1"


def test_compile_spec_skips_separator_row():
    """Dòng chỉ chứa '---' bị bỏ qua."""
    plan = """| T4.1 | task | a.py | f | c |
| --- | --- | --- | --- | --- |
| T4.2 | task2 | b.py | f | c |
"""
    spec = compile_spec(plan, run_id="r")
    ids = [o.id for o in spec.orders]
    assert "t4-1" in ids
    assert "t4-2" in ids


def test_compile_spec_caps_50_orders():
    """Plan có >50 task -> chỉ lấy 50 order đầu."""
    rows = "\n".join(f"| T4.{i} | task{i} | f{i}.py | func | crit |" for i in range(1, 60))
    spec = compile_spec(rows, run_id="r")
    assert len(spec.orders) <= 50


def test_compile_spec_auto_run_id():
    """Không truyền run_id -> tự sinh từ timestamp."""
    spec = compile_spec("# plan", run_id=None)
    assert spec.run_id.startswith("run-")


def test_compile_spec_write_set_capped_50():
    """write_set có >50 file -> chỉ lấy 50."""
    # Một cell với nhiều file .py
    files = " ".join(f"f{i}.py" for i in range(60))
    plan = f"| T4.1 | task | {files} | func | crit |"
    spec = compile_spec(plan, run_id="r")
    assert len(spec.orders[0].write_set) <= 50


def test_validate_disjoint_write_sets_same_owner_ok():
    """Cùng order ghi nhiều file trong write_set -> OK (không conflict)."""
    from datetime import datetime, timezone
    spec = SwarmSpec(
        run_id="r",
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
        orders=[
            Order(
                id="a", worker_id="w", task="t",
                write_set=["x.py", "y.py", "x.py"],  # x.py lặp trong cùng order
                idempotency_key="a",
            ),
        ],
    )
    # Không raise — cùng owner
    results = dispatch(spec)
    assert all(r.status == "success" for r in results)


def test_dispatch_type_error_on_non_spec():
    """dispatch với non-SwarmSpec -> TypeError."""
    with pytest.raises(TypeError):
        dispatch("not a spec")  # type: ignore[arg-type]


def test_dispatch_missing_dependency():
    """Order phụ thuộc vào id không tồn tại -> ValueError."""
    from datetime import datetime, timezone
    spec = SwarmSpec(
        run_id="r",
        max_parallel=5,
        created_at=datetime.now(timezone.utc),
        orders=[
            Order(id="a", worker_id="w", task="t", idempotency_key="a", depends_on=["missing"]),
        ],
    )
    with pytest.raises(ValueError):
        dispatch(spec)


def test_default_worker_returns_success():
    """_default_worker stub luôn trả success."""
    from swarm_director import _default_worker
    order = Order(id="o", worker_id="w", task="t", idempotency_key="o", outputs=["a.py"])
    result = _default_worker(order)
    assert result.status == "success"
    assert result.order_id == "o"
    assert result.artifacts == ["a.py"]


def test_cli_runs_end_to_end(capsys, monkeypatch):
    """CLI stub đọc plan từ stdin, in spec JSON + dispatch results."""
    import io
    from swarm_director import _cli
    monkeypatch.setattr(sys, "stdin", io.StringIO(_PLAN_MD))
    code = _cli()
    assert code == 0
    captured = capsys.readouterr()
    # Output chứa JSON spec + kết quả dispatch
    assert "run_id" in captured.out
    assert "success" in captured.out


def test_compile_spec_case_insensitive_task_id():
    """Task id lowercase vẫn parse được."""
    plan = "| t4.1 | task | a.py | f | c |"
    spec = compile_spec(plan, run_id="r")
    assert len(spec.orders) == 1


def test_compile_spec_alpha_numeric_task_id():
    """Task id dạng ABC-123 cũng parse được."""
    plan = "| ABC-123 | task | a.py | f | c |"
    spec = compile_spec(plan, run_id="r")
    assert len(spec.orders) == 1
    assert spec.orders[0].id == "abc-123"
