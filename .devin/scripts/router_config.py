"""Router config — P1-01 Model tiering + per-call budget.

Mapping role -> tier + budget buckets + cost estimation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

# Role -> tier mapping
ROLE_TIER_MAP: Dict[str, str] = {
    "classifier": "cheap",
    "router": "cheap",
    "planner": "premium",
    "synthesizer": "premium",
    "executor": "premium",
    "reviewer": "premium",
    "researcher": "cheap",
    "general": "cheap",
}

# Budget buckets per role (USD per session)
ROLE_BUDGET_BUCKETS: Dict[str, float] = {
    "classifier": 0.50,
    "router": 0.50,
    "planner": 5.00,
    "synthesizer": 2.00,
    "executor": 3.00,
    "reviewer": 2.00,
    "researcher": 1.00,
    "general": 1.00,
}

BUDGET_ALERT_THRESHOLD_PCT = 80

MODEL_COST_PER_MTOK: Dict[str, Dict[str, float]] = {
    "lightning-executor": {"input": 2.5, "output": 12.5},
    "glm-executor": {"input": 0.0, "output": 0.0},
    "kimi-executor": {"input": 0.0, "output": 0.0},
    "active-model": {"input": 0.0, "output": 0.0},
}

EXECUTOR_CAPS: Dict[str, int] = {
    "cheap": 10,
    "premium": 5,
    "free": 10,
}

# CallSiteRole type alias
CallSiteRole = str


@dataclass
class BudgetBucket:
    role: str
    limit_usd: float
    spent_usd: float = 0.0
    call_count: int = 0

    @property
    def usage_pct(self) -> float:
        if self.limit_usd == 0:
            return 0.0
        return (self.spent_usd / self.limit_usd) * 100.0

    @property
    def is_alert(self) -> bool:
        return self.usage_pct >= BUDGET_ALERT_THRESHOLD_PCT

    @property
    def is_exceeded(self) -> bool:
        return self.spent_usd > self.limit_usd or self.spent_usd >= self.limit_usd

    def add_spend(self, amount: float) -> None:
        self.spent_usd += amount
        self.call_count += 1


_SESSION_BUDGETS: Dict[str, Dict[str, BudgetBucket]] = {}


def get_session_budgets(session_id: str) -> Dict[str, BudgetBucket]:
    """Lay hoac tao budget buckets cho session."""
    if session_id not in _SESSION_BUDGETS:
        _SESSION_BUDGETS[session_id] = {
            role: BudgetBucket(role=role, limit_usd=limit)
            for role, limit in ROLE_BUDGET_BUCKETS.items()
        }
    return _SESSION_BUDGETS[session_id]


def get_executor_for_role(role: str) -> str:
    tier = ROLE_TIER_MAP.get(role, "cheap")
    if tier == "cheap":
        return "glm-executor"
    if tier == "premium":
        return "lightning-executor"
    return "glm-executor"


def get_tier_for_executor(executor: str) -> str:
    if executor in ("glm-executor", "kimi-executor"):
        return "cheap"
    if executor == "lightning-executor":
        return "premium"
    return "cheap"


def estimate_cost_for_role(role: str, input_tokens: int, output_tokens: int) -> float:
    tier = ROLE_TIER_MAP.get(role, "cheap")
    if tier == "cheap":
        return 0.0
    executor = get_executor_for_role(role)
    costs = MODEL_COST_PER_MTOK.get(executor, {"input": 2.5, "output": 12.5})
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


def validate_budget_config() -> list:
    """Kiem tra config, tra ve warnings."""
    warnings = []
    for role, tier in ROLE_TIER_MAP.items():
        if role not in ROLE_BUDGET_BUCKETS:
            warnings.append(f"Role {role} missing budget bucket")
        if tier not in ("cheap", "premium", "free"):
            warnings.append(f"Role {role} has invalid tier {tier}")
    return warnings
