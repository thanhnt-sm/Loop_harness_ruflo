#!/usr/bin/env python3
"""judge_config.py — Load + validate .devin/config/llm_judge.yaml.

Mục đích: cung cấp API đơn giản để mọi script (llm_as_judge, redteam_spawner,
auto_pr_runner) đọc config LLM-as-judge mà không phải parse YAML lặp lại.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 10.3

Usage:
    from judge_config import load_judge_config, get_judge_model
    cfg = load_judge_config()
    model = get_judge_model("unit_rubric")  # str | None
    if cfg.redteam.auto_spawn and confidence < cfg.redteam.confidence_threshold:
        spawn_redteam_round(...)

Behavior: graceful fallback khi thiếu file / thiếu key — luôn trả về
default config in-memory thay vì raise (để caller không bị crash nếu
user chưa tạo file config).

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal, Optional

try:
    import yaml
except ImportError:  # graceful fallback khi thiếu PyYAML
    yaml = None  # type: ignore[assignment]

from pydantic import BaseModel, Field
__all__ = [
    "AgreementPolicy",
    "AuditConfig",
    "DEFAULT_CONFIG_PATH",
    "JudgeConfig",
    "RedteamConfig",
    "get_judge_model",
    "load_judge_config",
    "pick_judge_for_audit_path",
    "should_spawn_redteam",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

DEFAULT_CONFIG_PATH = Path(".devin/config/llm_judge.yaml")

# Model aliases hợp lệ
ModelName = Literal["haiku", "sonnet", "opus"]


class AgreementPolicy(BaseModel):
    unanimous_override: bool = True
    majority_escalate: bool = True
    no_consensus_block: bool = True


class RedteamConfig(BaseModel):
    auto_spawn: bool = True
    personas_per_round: int = Field(default=3, ge=1, le=10)
    pool: list[str] = Field(
        default_factory=lambda: [
            "persona-saboteur",
            "persona-security-auditor",
            "persona-architect",
            "persona-code-reviewer",
            "persona-new-hire",
        ]
    )
    trigger: Literal["low_confidence", "always", "never"] = "low_confidence"
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    parallel: bool = True
    agreement_policy: AgreementPolicy = Field(default_factory=AgreementPolicy)


class AuditConfig(BaseModel):
    enabled: bool = True
    path: str = ".devin/state/llm_judge_audit.jsonl"
    include_prompt: bool = True
    include_verdict: bool = True


class JudgeConfig(BaseModel):
    default: Optional[ModelName] = None
    unit_rubric: Optional[ModelName] = None
    final_gate: Optional[ModelName] = None
    redteam: RedteamConfig = Field(default_factory=RedteamConfig)
    cross_model_requirement: bool = True
    audit: AuditConfig = Field(default_factory=AuditConfig)
    # CC client config (Phase 7 - wire Command Code CLI)
    cc_cli_path: str = "command-code"
    available_models: list[str] = Field(
        default_factory=lambda: ["haiku", "sonnet", "opus"]
    )
    cross_model_strategy: Literal["cheapest", "newest", "rotate"] = "cheapest"
    cc_timeout_seconds: int = 60
    cc_max_retries: int = 3


def _empty_config() -> JudgeConfig:
    """Default config khi file không tồn tại hoặc thiếu key."""
    return JudgeConfig()


def load_judge_config(path: str | Path | None = None) -> JudgeConfig:
    """Load config từ YAML, fallback về default nếu lỗi.

    KHÔNG raise — graceful degradation để caller không crash.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if yaml is None:
        return _empty_config()
    if not config_path.exists():
        return _empty_config()
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return _empty_config()
    if not isinstance(raw, dict):
        return _empty_config()
    llm_judge = raw.get("llm_judge", raw)
    try:
        return JudgeConfig.model_validate(llm_judge)
    except Exception:  # ValidationError hoặc bất kỳ lỗi nào
        return _empty_config()


def get_judge_model(slot: Literal["default", "unit_rubric", "final_gate"]) -> Optional[str]:
    """Trả về model name cho 1 slot, hoặc None (= dùng model hiện tại).

    Có thể override qua env var: AHD_JUDGE_MODEL_<SLOT>=haiku
    """
    env_key = f"AHD_JUDGE_MODEL_{slot.upper()}"
    env_val = os.environ.get(env_key)
    if env_val in ("haiku", "sonnet", "opus"):
        return env_val
    cfg = load_judge_config()
    val = getattr(cfg, slot, None)
    return val  # None nếu không set, = dùng model hiện tại


def should_spawn_redteam(confidence: float, trigger: Optional[str] = None) -> bool:
    """Quyết định có spawn redteam round hay không.

    Args:
        confidence: primary judge confidence (0..1)
        trigger: override trigger mode (nếu None, lấy từ config)
    """
    cfg = load_judge_config()
    mode = trigger or cfg.redteam.trigger
    if mode == "never":
        return False
    if mode == "always":
        return cfg.redteam.auto_spawn
    # low_confidence
    return cfg.redteam.auto_spawn and confidence < cfg.redteam.confidence_threshold


def pick_judge_for_audit_path() -> str:
    """Đường dẫn audit log (cho llm_as_judge.py dùng)."""
    cfg = load_judge_config()
    return cfg.audit.path if cfg.audit.enabled else ""


if __name__ == "__main__":
    import json as _json

    cfg = load_judge_config()
    print(_json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False))
