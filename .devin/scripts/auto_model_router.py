#!/usr/bin/env python3
"""Auto Model Router — integrates with config.json _u12_model_routing.

Automatically selects executor based on task type, using routing rules
defined in config.json. Falls back to default executor if no match.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional


def _repo_root() -> Path:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        return Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else Path.cwd()
    except Exception:
        return Path.cwd()


def _load_routing_config(root: Path) -> dict:
    """Load model routing config from config.json."""
    config_path = root / ".devin" / "config.json"
    if not config_path.exists():
        return {}
    
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return config.get("_u12_model_routing", {})
    except Exception:
        return {}


def _match_task_type(task_description: str, task_type_pattern: str) -> bool:
    """Check if task description matches a task type pattern.
    
    Patterns can be:
    - Simple keywords: "simple_edit", "read", "grep", "glob", "ls"
    - Pipe-separated alternatives: "code_generation|refactor|debug"
    - Multiple patterns separated by spaces
    """
    task_lower = task_description.lower()
    patterns = task_type_pattern.split("|")
    
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        # Check if pattern keywords appear in task description
        keywords = pattern.replace("_", " ").split()
        if all(kw in task_lower for kw in keywords):
            return True
        # Also check for single keyword matches
        if pattern in task_lower:
            return True
    
    return False


def select_executor(task_description: str, root: Optional[Path] = None) -> dict:
    """Select executor based on task description and routing rules.
    
    Returns:
        {
            "executor": "glm-executor|kimi-executor|lightning-executor|active-model",
            "reason": str,
            "matched_rule": str,
            "fallback": bool
        }
    """
    root = root or _repo_root()
    routing_config = _load_routing_config(root)
    
    if not routing_config:
        return {
            "executor": "glm-executor",
            "reason": "No routing config found, using default",
            "matched_rule": "default",
            "fallback": True
        }
    
    rules = routing_config.get("routing_rules", [])
    fallback = routing_config.get("fallback", "glm-executor")
    cost_aware = routing_config.get("cost_aware", True)
    
    # Try to match each rule in order
    for rule in rules:
        task_type = rule.get("task_type", "")
        executor = rule.get("executor", "")
        reason = rule.get("reason", "")
        
        if _match_task_type(task_description, task_type):
            return {
                "executor": executor,
                "reason": reason,
                "matched_rule": task_type,
                "fallback": False
            }
    
    # No match - use fallback
    return {
        "executor": fallback,
        "reason": f"No rule matched, using fallback",
        "matched_rule": "fallback",
        "fallback": True
    }


def get_executor_config(executor_name: str, root: Optional[Path] = None) -> dict:
    """Get executor configuration details."""
    root = root or _repo_root()
    routing_config = _load_routing_config(root)
    
    # Default executor configs (from AGENTS.md)
    executor_defaults = {
        "lightning-executor": {
            "model": "SWE-1.7 Lightning",
            "cost_per_mtok": {"input": 2.5, "output": 12.5},
            "speed": "1000 tok/s",
            "use_when": "Speed needed"
        },
        "glm-executor": {
            "model": "GLM-5.2 High",
            "cost_per_mtok": {"input": 0.0, "output": 0.0},
            "speed": "normal",
            "use_when": "Free tier, high reasoning"
        },
        "kimi-executor": {
            "model": "Kimi K2.7",
            "cost_per_mtok": {"input": 0.0, "output": 0.0},
            "speed": "normal",
            "use_when": "Free tier until 2026-07-05, open-source"
        },
        "active-model": {
            "model": "Current active model",
            "cost_per_mtok": {"input": 0.0, "output": 0.0},
            "speed": "normal",
            "use_when": "Planning, reviewing, orchestrating"
        },
    }
    
    return executor_defaults.get(executor_name, executor_defaults["glm-executor"])


def estimate_task_cost(task_description: str, estimated_input_tokens: int = 10000, estimated_output_tokens: int = 5000, root: Optional[Path] = None) -> dict:
    """Estimate cost for a task using the selected executor."""
    selection = select_executor(task_description, root)
    executor_config = get_executor_config(selection["executor"], root)
    
    input_cost = (estimated_input_tokens / 1_000_000) * executor_config["cost_per_mtok"]["input"]
    output_cost = (estimated_output_tokens / 1_000_000) * executor_config["cost_per_mtok"]["output"]
    total_cost = input_cost + output_cost
    
    # Also calculate cost with fallback for comparison
    fallback_config = get_executor_config("lightning-executor", root)
    fallback_input = (estimated_input_tokens / 1_000_000) * fallback_config["cost_per_mtok"]["input"]
    fallback_output = (estimated_output_tokens / 1_000_000) * fallback_config["cost_per_mtok"]["output"]
    fallback_total = fallback_input + fallback_output
    
    savings = fallback_total - total_cost
    savings_pct = (savings / fallback_total * 100) if fallback_total > 0 else 0
    
    return {
        "selected_executor": selection["executor"],
        "selection_reason": selection["reason"],
        "model": executor_config["model"],
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
        "fallback_cost_usd": round(fallback_total, 6),
        "savings_usd": round(savings, 6),
        "savings_pct": round(savings_pct, 1),
        "cost_aware": True
    }


# ---- P1-01: tiered selection wrappers cho test_model_tiering ----

def select_executor_by_role(role: str, task_description: str = "", root: Optional[Path] = None) -> dict:
    """Chon executor theo role (cheap/premium) — test stub."""
    try:
        from router_config import ROLE_TIER_MAP, get_executor_for_role, estimate_cost_for_role

        tier = ROLE_TIER_MAP.get(role, "cheap")
        executor = get_executor_for_role(role)
        return {"executor": executor, "tier": tier, "role": role, "reason": f"role:{role}->{tier}"}
    except Exception:
        # Fallback neu router_config chua co
        return select_executor(task_description or role, root)


def estimate_task_cost_by_role(role: str, task_description: str, input_tokens: int, output_tokens: int, root: Optional[Path] = None) -> dict:
    """Uoc tinh cost theo role."""
    try:
        from router_config import estimate_cost_for_role, MODEL_COST_PER_MTOK, get_executor_for_role

        total = estimate_cost_for_role(role, input_tokens, output_tokens)
        # Baseline = Lightning cost
        lightning_input = (input_tokens / 1_000_000) * 2.5
        lightning_output = (output_tokens / 1_000_000) * 12.5
        baseline = round(lightning_input + lightning_output, 6)
        savings = baseline - total
        savings_pct = round((savings / baseline * 100) if baseline > 0 else 0, 1)
        return {
            "total_cost_usd": total,
            "baseline_cost_usd": baseline,
            "savings_usd": round(savings, 6),
            "savings_pct": savings_pct,
            "role": role,
        }
    except Exception:
        return estimate_task_cost(task_description, input_tokens, output_tokens, root)


def main():
    if len(sys.argv) < 2:
        print("Usage: auto_model_router.py <task_description> [--estimate-cost]", file=sys.stderr)
        sys.exit(1)
    
    task_description = sys.argv[1]
    estimate_cost = "--estimate-cost" in sys.argv
    
    root = _repo_root()
    selection = select_executor(task_description, root)
    
    print(f"Task: {task_description}")
    print(f"Selected Executor: {selection['executor']}")
    print(f"Reason: {selection['reason']}")
    print(f"Matched Rule: {selection['matched_rule']}")
    print(f"Fallback: {selection['fallback']}")
    
    if estimate_cost:
        cost = estimate_task_cost(task_description, root=root)
        print(f"\nCost Estimate:")
        print(f"  Model: {cost['model']}")
        print(f"  Input Cost: ${cost['input_cost_usd']:.6f}")
        print(f"  Output Cost: ${cost['output_cost_usd']:.6f}")
        print(f"  Total Cost: ${cost['total_cost_usd']:.6f}")
        print(f"  Fallback Cost: ${cost['fallback_cost_usd']:.6f}")
        print(f"  Savings: ${cost['savings_usd']:.6f} ({cost['savings_pct']:.1f}%)")


if __name__ == "__main__":
    main()