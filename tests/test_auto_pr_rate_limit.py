"""Tests for rate limit and metrics (Plan 10 phase 6)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
sys.path.insert(0, str(ROOT / "HLK"))
from chain import auto_pr_runner as chain  # noqa: E402


@pytest.fixture
def mock_live_counter(tmp_path, monkeypatch):
    counter_file = tmp_path / "live_counter.json"
    monkeypatch.setattr(chain, "LIVE_COUNTER_PATH", counter_file)
    return counter_file


def test_check_live_daily_limit_first_run(mock_live_counter):
    ok, msg = chain.check_live_daily_limit()
    assert ok is True
    assert "0/1" in msg


def test_increment_live_counter(mock_live_counter):
    chain.increment_live_counter()
    ok, msg = chain.check_live_daily_limit()
    assert ok is False
    assert "max 1" in msg.lower() or "1/1" in msg


def test_increment_writes_to_file(mock_live_counter):
    chain.increment_live_counter()
    assert mock_live_counter.exists()
    data = json.loads(mock_live_counter.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert len(data) >= 1


def test_metrics_no_audit_log(tmp_path, monkeypatch):
    fake_log = tmp_path / "nonexistent.jsonl"
    monkeypatch.setattr(chain, "AUDIT_LOG_PATH", fake_log)
    m = chain.get_metrics()
    assert m["total_runs"] == 0
    assert m["pass_count"] == 0
    assert m["pass_rate"] == 0.0
    assert m["last_10_verdicts"] == []


def test_metrics_with_entries(tmp_path, monkeypatch):
    fake_log = tmp_path / "audit.jsonl"
    entries = [
        {"gates_failed": []},
        {"gates_failed": []},
        {"gates_failed": ["coverage_matrix"]},
    ]
    fake_log.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    monkeypatch.setattr(chain, "AUDIT_LOG_PATH", fake_log)
    m = chain.get_metrics()
    assert m["total_runs"] == 3
    assert m["pass_count"] == 2
    assert m["fail_count"] == 1
    assert abs(m["pass_rate"] - 2/3) < 0.01
