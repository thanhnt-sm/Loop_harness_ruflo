#!/usr/bin/env python3
"""Kiểm tra migrate_config.py theo T1.4 / REQ-014."""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import migrate_config  # noqa: E402


def test_migrate_config_replaces_paths_and_writes_env(tmp_path: Path):
    config = tmp_path / "config.json"
    config.write_text(
        '{"log_dir": "/var/log/ahd", "data_dir": "/var/data/ahd"}',
        encoding="utf-8",
    )
    mapping = {
        "/var/log/ahd": "LOG_DIR",
        "/var/data/ahd": "DATA_DIR",
    }
    result = migrate_config.migrate(config, mapping)

    assert result == config
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["log_dir"] == "${LOG_DIR}"
    assert data["data_dir"] == "${DATA_DIR}"

    env_template = tmp_path / ".env.template"
    assert env_template.exists()
    text = env_template.read_text(encoding="utf-8")
    assert "LOG_DIR=/var/log/ahd" in text
    assert "DATA_DIR=/var/data/ahd" in text


def test_migrate_config_idempotent(tmp_path: Path):
    config = tmp_path / "config.json"
    config.write_text(
        '{"log_dir": "${LOG_DIR}"}',
        encoding="utf-8",
    )
    mapping = {"/var/log/ahd": "LOG_DIR"}
    migrate_config.migrate(config, mapping)

    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["log_dir"] == "${LOG_DIR}"
