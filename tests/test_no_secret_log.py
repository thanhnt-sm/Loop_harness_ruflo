#!/usr/bin/env python3
"""Kiểm thử secret không bị ghi thẳng vào checkpoint — T2.6.

Các ca kiểm thử:
1. API key trong run_metadata bị redact.
2. Token trong conversation content bị redact.
3. File checkpoint trên disk không chứa secret.
"""
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


def _make_state_with_secret(secret: str):
    from data_models import CheckpointState, Turn
    return CheckpointState(
        version=2,
        run_id="run-secret",
        conversation=[
            Turn(role="user", content=f"my key is {secret}", tokens=10, timestamp=datetime.now(timezone.utc))
        ],
        side_effects_ledger=[],
        run_metadata={"api_key": secret},
        external_handles=[],
        timestamp=datetime.now(timezone.utc),
        step_id="secret-step",
    )


def test_checkpoint_on_disk_no_secret(tmp_path):
    from checkpoint import save
    secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
    state = _make_state_with_secret(secret)
    path = save(state, root=tmp_path)
    raw = path.read_text(encoding="utf-8")
    assert secret not in raw
    assert "[REDACTED]" in raw


def test_checkpoint_secret_in_metadata(tmp_path):
    from checkpoint import save, load
    secret = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    state = _make_state_with_secret(secret)
    path = save(state, root=tmp_path)
    loaded = load(path)
    assert secret not in loaded.run_metadata["api_key"]
    assert "[REDACTED]" in loaded.run_metadata["api_key"]
    assert secret not in loaded.conversation[0].content
