"""Tests cho judge_config.py — load + validate llm_judge.yaml config."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from judge_config import (  # noqa: E402
    get_judge_model,
    load_judge_config,
    should_spawn_redteam,
)


def test_load_default_config_when_missing(tmp_path):
    """Khi file config không tồn tại → trả về default, không crash."""
    cfg = load_judge_config(tmp_path / "nonexistent.yaml")
    assert cfg.default is None
    assert cfg.redteam.auto_spawn is True
    assert cfg.cross_model_requirement is True


def test_load_actual_config():
    """Load file config thật từ .devin/config/llm_judge.yaml."""
    cfg = load_judge_config()
    assert cfg.redteam.auto_spawn is True
    assert cfg.redteam.personas_per_round == 3
    assert "persona-saboteur" in cfg.redteam.pool
    assert cfg.cross_model_requirement is True


def test_should_spawn_redteam_low_confidence():
    """Confidence < threshold → spawn."""
    assert should_spawn_redteam(0.5) is True
    assert should_spawn_redteam(0.69) is True


def test_should_spawn_redteam_high_confidence():
    """Confidence >= threshold → không spawn."""
    assert should_spawn_redteam(0.8) is False
    assert should_spawn_redteam(1.0) is False


def test_should_spawn_redteam_trigger_never():
    """trigger='never' override → không spawn bất kể confidence."""
    assert should_spawn_redteam(0.1, trigger="never") is False
    assert should_spawn_redteam(0.9, trigger="never") is False


def test_should_spawn_redteam_trigger_always():
    """trigger='always' → spawn nếu auto_spawn=True (default)."""
    assert should_spawn_redteam(0.9, trigger="always") is True
    assert should_spawn_redteam(0.1, trigger="always") is True


def test_get_judge_model_returns_none_by_default():
    """default slot → None (= dùng model hiện tại)."""
    assert get_judge_model("default") is None
    assert get_judge_model("unit_rubric") is None
    assert get_judge_model("final_gate") is None
