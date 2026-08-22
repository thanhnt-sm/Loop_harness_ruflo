#!/usr/bin/env python3
"""hardening_flags.py — Feature flags cho tất cả 14 hardening fixes.

T15 fix: Mỗi fix có flag riêng, có thể enable/disable qua config hoặc env.
Default: tất cả enabled. Disable qua AHD_HARDENING_DISABLE_<FLAG>=1.

Flags:
  V01_DAG_SCHEMA          — T01: Shared DAG schema + migration
  V02_QUOTA_FALLBACK      — T02: Subagent quota degraded mode
  V03_PATH_RESOLVER       — T03: Cross-platform path resolver
  V04_HOOK_TIMEOUT        — T04: Hook timeout fail-closed
  V05_BASELINE_VALIDATION — T05: Drift baseline validation
  V06_COVERAGE_ESCALATION — T06: Coverage block mode
  V07_STATE_LOCKING       — T07: Atomic state save
  V08_SLUG_COLLISION      — T08: Slug fingerprint suffix
  V09_CROSS_FAMILY_VERIFY — T09: Cross-family verification hook
  V10_PLAN_SANITIZER      — T10: Multi-layer plan sanitization
  V11_MEMORY_ISOLATION    — T11: Untrusted memory tagging
  V12_DAG_RETRY_BRANCH    — T12: Execute retry/branch state machine
  V13_ADAPTIVE_COST       — T13: Adaptive token cost reduction
  V14_SELF_HEAL_GUARD     — T14: Self-heal recursion guard
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Tất cả flags — default True (enabled)
ALL_FLAGS = {
    "V01_DAG_SCHEMA": True,
    "V02_QUOTA_FALLBACK": True,
    "V03_PATH_RESOLVER": True,
    "V04_HOOK_TIMEOUT": True,
    "V05_BASELINE_VALIDATION": True,
    "V06_COVERAGE_ESCALATION": True,
    "V07_STATE_LOCKING": True,
    "V08_SLUG_COLLISION": True,
    "V09_CROSS_FAMILY_VERIFY": True,
    "V10_PLAN_SANITIZER": True,
    "V11_MEMORY_ISOLATION": True,
    "V12_DAG_RETRY_BRANCH": True,
    "V13_ADAPTIVE_COST": True,
    "V14_SELF_HEAL_GUARD": True,
}

# Đường dẫn config file
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def _load_config() -> dict:
    """Load config từ .devin/config.json."""
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def is_enabled(flag: str) -> bool:
    """Kiểm tra flag có enabled không.

    Priority:
      1. Env var AHD_HARDENING_DISABLE_<FLAG>=1 → disabled
      2. Config file .devin/config.json → hardening_flags.<flag>
      3. Default: True (enabled)
    """
    # 1. Env var override (disable)
    env_key = f"AHD_HARDENING_DISABLE_{flag}"
    if os.environ.get(env_key, "0") == "1":
        return False

    # 2. Config file
    config = _load_config()
    hardening_config = config.get("hardening_flags", {})
    if flag in hardening_config:
        return bool(hardening_config[flag])

    # 3. Default
    return ALL_FLAGS.get(flag, True)


def set_flag(flag: str, enabled: bool) -> None:
    """Set flag trong config file."""
    config = _load_config()
    if "hardening_flags" not in config:
        config["hardening_flags"] = {}
    config["hardening_flags"][flag] = enabled
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def all_flags() -> dict:
    """Trả trạng thái tất cả flags."""
    return {flag: is_enabled(flag) for flag in ALL_FLAGS}


if __name__ == "__main__":
    flags = all_flags()
    for flag, enabled in flags.items():
        status = "ENABLED" if enabled else "DISABLED"
        print(f"  {flag}: {status}")
