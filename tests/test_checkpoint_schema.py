#!/usr/bin/env python3
"""Kiểm thử checkpoint schema — T2.6 (REB-005/006/008).

Các ca kiểm thử:
1. save(CheckpointState) -> Path, file tồn tại.
2. load(path) -> CheckpointState round-trip.
3. migrate(old v1) -> v2.
4. _sanitize_step_id chặn path traversal và allowlist.
5. _redact_snapshot che secret.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)


def _make_state(step_id: str, run_id: str = "run-1"):
    from data_models import CheckpointState, Turn
    return CheckpointState(
        version=2,
        run_id=run_id,
        conversation=[
            Turn(role="user", content="hello", tokens=1, timestamp=datetime.now(timezone.utc))
        ],
        side_effects_ledger=[],
        run_metadata={"task": "test"},
        external_handles=[],
        timestamp=datetime.now(timezone.utc),
        step_id=step_id,
    )


def test_save_round_trip(tmp_path):
    from checkpoint import save, load
    state = _make_state("step-ok")
    path = save(state, root=tmp_path)
    assert path.exists()
    loaded = load(path)
    assert loaded.step_id == "step-ok"
    assert loaded.run_id == "run-1"


def test_sanitize_step_id(tmp_path):
    import pytest
    from checkpoint import save, _sanitize_step_id
    # CVE-2026-AHD-004: step_id chứa '..' bị TỪ CHỐI (reject), không sanitize
    with pytest.raises(ValueError):
        _sanitize_step_id("../etc/passwd")
    # ID hợp lệ (không '..') sanitize bình thường
    assert _sanitize_step_id("step-01") == "step-01"


def test_migrate_old_version(tmp_path):
    from checkpoint import migrate, load, _save_json
    old = {
        "version": 1,
        "run_id": "old-run",
        "step_id": "old-step",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    migrated = migrate(old, target_version=2)
    assert migrated["version"] == 2
    assert "conversation" in migrated

    # Lưu migrated dict và load bằng load()
    ckpt_path = tmp_path / "migrated.json"
    _save_json(ckpt_path, migrated)
    loaded = load(ckpt_path)
    assert loaded.run_id == "old-run"
    assert loaded.step_id == "old-step"


def test_redact_snapshot(tmp_path):
    from checkpoint import save, load
    from data_models import CheckpointState
    state = CheckpointState(
        version=2,
        run_id="run-redact",
        conversation=[],
        side_effects_ledger=[],
        run_metadata={"secret_key": "sk-abcdefghijklmnopqrstuvwxyz123456"},
        external_handles=[],
        timestamp=datetime.now(timezone.utc),
        step_id="redact-step",
    )
    path = save(state, root=tmp_path)
    loaded = load(path)
    assert "sk-" not in loaded.run_metadata["secret_key"]
    assert "[REDACTED]" in loaded.run_metadata["secret_key"]
