#!/usr/bin/env python3
"""Kiểm thử idempotency ledger — T2.5 (REB-004).

Các ca kiểm thử:
1. register tính toán và lưu kết quả.
2. register với key đã tồn tại trả kết quả cache, không gọi op lại.
3. lookup trả kết quả đã cache hoặc None.
4. ledger_path trả đúng đường dẫn.
5. ledger tồn tại trên disk.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


def _counter_op():
    """Op tăng biến toàn cục để kiểm tra có bị gọi lại không."""
    _counter_op.counter += 1
    return _counter_op.counter


_counter_op.counter = 0


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    devin_dir = tmp_path / ".devin"
    devin_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    return tmp_path


def test_ledger_path(patched_root):
    from idempotency import ledger_path
    p = ledger_path("run-123", root=patched_root)
    assert p == patched_root / ".devin" / "idempotency" / "run-123.ledger.jsonl"


def test_register_computes_and_caches(patched_root):
    from idempotency import register, lookup
    _counter_op.counter = 0
    run_id = "run-cache-1"
    key = "step-a"

    result1 = register(key, _counter_op, run_id=run_id)
    assert result1 == 1
    assert _counter_op.counter == 1

    # Gọi lại với cùng key không chạy op nữa
    result2 = register(key, _counter_op, run_id=run_id)
    assert result2 == 1
    assert _counter_op.counter == 1  # vẫn là 1

    # lookup cũng trả kết quả cache
    cached = lookup(key, run_id=run_id)
    assert cached == 1


def test_register_different_keys(patched_root):
    from idempotency import register
    _counter_op.counter = 0
    run_id = "run-cache-2"

    assert register("step-1", _counter_op, run_id=run_id) == 1
    assert register("step-2", _counter_op, run_id=run_id) == 2
    assert _counter_op.counter == 2


def test_lookup_missing(patched_root):
    from idempotency import lookup
    assert lookup("nonexistent", run_id="run-missing") is None


def test_ledger_file_exists(patched_root):
    from idempotency import register, ledger_path
    run_id = "run-file-1"
    register("k1", lambda: {"ok": True, "value": 42}, run_id=run_id)
    p = ledger_path(run_id)
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = __import__("json").loads(lines[0])
    assert entry["key"] == "k1"
    assert entry["result"]["value"] == 42
