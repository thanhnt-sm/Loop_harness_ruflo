"""Tests cho HLK/scripts/metrics_dashboard.py (Plan 10 phase 7)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
sys.path.insert(0, str(ROOT / "HLK" / "scripts"))
import metrics_dashboard  # noqa: E402


def test_collect_hlk_metrics_keys():
    m = metrics_dashboard.collect_hlk_metrics()
    assert "hlk_chain_modules" in m
    assert "hlk_loaders" in m
    assert "hlk_hlk_wrappers" in m


def test_collect_hlk_modules_count_at_least_17():
    m = metrics_dashboard.collect_hlk_metrics()
    assert m["hlk_chain_modules"] >= 17  # 16 + __init__.py + 1 config


def test_collect_devin_metrics_keys():
    m = metrics_dashboard.collect_devin_metrics()
    assert "devin_shims" in m
    assert m["devin_shims"] >= 1  # Có ít nhất 1 shim file


def test_collect_provider_metrics_keys():
    m = metrics_dashboard.collect_provider_metrics()
    # Có thể có 0 hoặc nhiều providers
    assert isinstance(m, dict)


def test_collect_chain_metrics_combines_all():
    m = metrics_dashboard.collect_chain_metrics()
    assert "hlk" in m
    assert "devin" in m
    assert "providers" in m
    assert "sync_state" in m
    assert "chain_runtime" in m
    assert "collected_at" in m


def test_render_markdown_has_required_sections():
    metrics = {
        "hlk": {"hlk_chain_modules": 18, "hlk_loaders": 1, "hlk_hlk_wrappers": 1},
        "devin": {"devin_shims": 17, "devin_skills_count": 28},
        "providers": {"cmdc_agents": 12, "opencode_commands": 11},
        "sync_state": {"last_sync": "2026-08-27T00:00:00"},
        "chain_runtime": {"total_runs": 0, "pass_count": 0, "pass_rate": 0.0,
                        "last_10_verdicts": []},
        "collected_at": "2026-08-27T00:00:00Z",
    }
    md = metrics_dashboard.render_markdown(metrics)
    assert "# Verify-First Chain Metrics Dashboard" in md
    assert "## HLK Layer" in md
    assert "## .devin Layer" in md
    assert "## Providers" in md
    assert "## Sync State" in md
    assert "## Chain Runtime" in md
    # Tables
    assert "| Metric | Value |" in md
    assert "hlk_chain_modules" in md
    assert "18" in md


def test_main_outputs_markdown(capsys, monkeypatch):
    """Chạy main() in-place (no args) → in markdown ra stdout."""
    monkeypatch.setattr("sys.argv", ["metrics_dashboard.py"])
    rc = metrics_dashboard.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "# Verify-First Chain Metrics Dashboard" in captured.out


def test_main_outputs_json(capsys, monkeypatch):
    """--json mode → in JSON."""
    monkeypatch.setattr("sys.argv", ["metrics_dashboard.py", "--json"])
    rc = metrics_dashboard.main()
    assert rc == 0
    captured = capsys.readouterr()
    # Có thể parse lại JSON
    data = json.loads(captured.out)
    assert "hlk" in data
    assert "collected_at" in data
