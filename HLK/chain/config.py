"""HLK/chain/config.py — Load HLK config cho verify-first chain.

Theo plan: HLK là source of truth duy nhất, config tập trung tại `HLK/config/hlk.config.json`.

Backward compat: nếu HLK config thiếu section, fallback về .devin/config/*.yaml.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
__all__ = [
    "get_verify_first_config",
    "is_hlk_config_complete",
    "load_hlk_config",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


def _find_repo_root() -> Path:
    """Repo root = parent của HLK/."""
    p = Path(__file__).resolve()
    return p.parent.parent.parent  # HLK/chain/config.py → 3 levels up


def load_hlk_config(config_path: Optional[str | Path] = None) -> dict:
    """Load HLK config từ `HLK/config/hlk.config.json`.

    Returns:
        dict (rỗng nếu file không tồn tại hoặc lỗi parse).
    """
    repo = _find_repo_root()
    p = Path(config_path) if config_path else repo / "HLK" / "config" / "hlk.config.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def get_verify_first_config(hlk_config: Optional[dict] = None) -> dict:
    """Trả về section `verify_first` từ HLK config.

    Fallback: nếu HLK config thiếu, merge với defaults + đọc từ .devin/config/.

    Returns:
        dict với đầy đủ keys cần thiết (defensive merge).
    """
    # Defaults: nếu HLK config thiếu section, dùng defaults
    defaults = {
        "enabled": True,
        "chain_path": "HLK/chain/",
        "cli_entry": "HLK/chain/verify_first_cli.py",
        "audit_log": ".devin/state/verify_first_audit.jsonl",
        "rate_limit": {"max_runs_per_day_per_prefix": 1},
        "gates": {
            "coverage_matrix": True,
            "adversarial_consensus": True,
            "llm_judge_rubric": True,
            "fable_judge": True,
        },
        "human_confirm_required_for_live": True,
        "secret_scan_enabled": True,
        "prompt_injection_protection": True,
        "auto_pr_blast_radius": {
            "max_per_day_per_prefix": 1,
            "prefixes": ["verify-first/", "harness-upgrade/"],
        },
    }
    if hlk_config is None:
        hlk_config = load_hlk_config()
    vf = hlk_config.get("verify_first", {})
    if not vf:
        # HLK config thiếu → try fallback .devin/config/
        fallback = _load_devin_fallback()
        if fallback and "fallback" in fallback:
            # Merge fallback với defaults
            merged = {**defaults}
            for k, v in fallback.items():
                if k != "fallback":
                    merged[k] = v
            return merged
        return defaults
    # HLK config có section → merge với defaults (defensive)
    merged = {**defaults, **vf}
    return merged


def _load_devin_fallback() -> dict:
    """Fallback: đọc .devin/config/*.yaml nếu HLK config thiếu section verify_first.

    Trả về dict với key tương thích.
    """
    repo = _find_repo_root()
    result: dict[str, Any] = {}
    # Read llm_judge.yaml
    judge_path = repo / ".devin" / "config" / "llm_judge.yaml"
    if judge_path.exists():
        try:
            import yaml
            data = yaml.safe_load(judge_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result["llm_judge"] = data
        except Exception:
            pass
    # Read auto_pr.yaml
    pr_path = repo / ".devin" / "config" / "auto_pr.yaml"
    if pr_path.exists():
        try:
            import yaml
            data = yaml.safe_load(pr_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result["auto_pr"] = data
        except Exception:
            pass
    result["fallback"] = True  # marker
    return result


def is_hlk_config_complete() -> bool:
    """Check xem HLK config có section verify_first đầy đủ không.

    Returns True nếu HLK config có section verify_first. Nếu thiếu → False
    (nhưng defaults vẫn work via get_verify_first_config()).
    """
    cfg = load_hlk_config()
    vf = cfg.get("verify_first", {})
    return "verify_first" in cfg and isinstance(vf, dict) and len(vf) > 0
