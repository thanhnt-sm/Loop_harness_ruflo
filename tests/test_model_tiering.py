"""Tests for P1-01: Model tiering + per-call budget."""

from __future__ import annotations

import pytest

from router_config import (
    ROLE_TIER_MAP,
    ROLE_BUDGET_BUCKETS,
    BUDGET_ALERT_THRESHOLD_PCT,
    MODEL_COST_PER_MTOK,
    EXECUTOR_CAPS,
    BudgetBucket,
    get_session_budgets,
    get_executor_for_role,
    estimate_cost_for_role,
    get_tier_for_executor,
    validate_budget_config,
    CallSiteRole,
)
from cost_tracker import (
    track_tool_cost_by_role,
    check_role_budget,
    get_role_budget_status,
    get_total_role_spend,
)
from auto_model_router import (
    select_executor_by_role,
    estimate_task_cost_by_role,
)


class TestRoleTierMap:
    """Test role → tier mapping."""

    def test_classifier_is_cheap(self):
        assert ROLE_TIER_MAP["classifier"] == "cheap"

    def test_router_is_cheap(self):
        assert ROLE_TIER_MAP["router"] == "cheap"

    def test_planner_is_premium(self):
        assert ROLE_TIER_MAP["planner"] == "premium"

    def test_synthesizer_is_premium(self):
        assert ROLE_TIER_MAP["synthesizer"] == "premium"

    def test_executor_is_premium(self):
        assert ROLE_TIER_MAP["executor"] == "premium"

    def test_reviewer_is_premium(self):
        assert ROLE_TIER_MAP["reviewer"] == "premium"

    def test_researcher_is_cheap(self):
        assert ROLE_TIER_MAP["researcher"] == "cheap"

    def test_general_is_cheap(self):
        assert ROLE_TIER_MAP["general"] == "cheap"


class TestExecutorSelection:
    """Test executor selection by role."""

    def test_classifier_uses_cheap(self):
        executor = get_executor_for_role("classifier")
        assert executor in ["glm-executor", "kimi-executor"]

    def test_router_uses_cheap(self):
        executor = get_executor_for_role("router")
        assert executor in ["glm-executor", "kimi-executor"]

    def test_planner_uses_premium(self):
        executor = get_executor_for_role("planner")
        assert executor == "lightning-executor"

    def test_synthesizer_uses_premium(self):
        executor = get_executor_for_role("synthesizer")
        assert executor == "lightning-executor"

    def test_executor_uses_premium(self):
        executor = get_executor_for_role("executor")
        assert executor == "lightning-executor"

    def test_reviewer_uses_premium(self):
        executor = get_executor_for_role("reviewer")
        assert executor == "lightning-executor"


class TestBudgetBuckets:
    """Test budget bucket configuration."""

    def test_all_roles_have_buckets(self):
        for role in ROLE_TIER_MAP:
            assert role in ROLE_BUDGET_BUCKETS, f"Role {role} missing budget bucket"

    def test_bucket_values_positive(self):
        for role, limit in ROLE_BUDGET_BUCKETS.items():
            assert limit > 0, f"Role {role} has non-positive budget"

    def test_planner_highest_budget(self):
        assert ROLE_BUDGET_BUCKETS["planner"] == max(ROLE_BUDGET_BUCKETS.values())

    def test_classifier_router_low_budget(self):
        assert ROLE_BUDGET_BUCKETS["classifier"] <= 1.0
        assert ROLE_BUDGET_BUCKETS["router"] <= 1.0


class TestBudgetBucketClass:
    """Test BudgetBucket dataclass."""

    def test_usage_pct(self):
        bucket = BudgetBucket(role="planner", limit_usd=5.0, spent_usd=2.5)
        assert bucket.usage_pct == 50.0

    def test_alert_at_80(self):
        bucket = BudgetBucket(role="planner", limit_usd=5.0, spent_usd=4.0)
        assert bucket.is_alert is True  # 80%

    def test_not_alert_below_80(self):
        bucket = BudgetBucket(role="planner", limit_usd=5.0, spent_usd=3.0)
        assert bucket.is_alert is False  # 60%

    def test_exceeded(self):
        bucket = BudgetBucket(role="planner", limit_usd=5.0, spent_usd=5.5)
        assert bucket.is_exceeded is True

    def test_add_spend(self):
        bucket = BudgetBucket(role="planner", limit_usd=5.0)
        bucket.add_spend(1.0)
        bucket.add_spend(2.0)
        assert bucket.spent_usd == 3.0
        assert bucket.call_count == 2


class TestSessionBudgets:
    """Test session budget management."""

    def setup_method(self):
        # Clear global state
        import router_config
        router_config._SESSION_BUDGETS.clear()

    def test_get_session_budgets_creates_all(self):
        budgets = get_session_budgets("test-session")
        assert len(budgets) == len(ROLE_BUDGET_BUCKETS)
        for role in ROLE_BUDGET_BUCKETS:
            assert role in budgets
            assert budgets[role].limit_usd == ROLE_BUDGET_BUCKETS[role]

    def test_session_isolation(self):
        budgets1 = get_session_budgets("session-1")
        budgets2 = get_session_budgets("session-2")

        budgets1["planner"].add_spend(2.0)
        assert budgets1["planner"].spent_usd == 2.0
        assert budgets2["planner"].spent_usd == 0.0


class TestCostEstimation:
    """Test cost estimation by role."""

    def test_cheap_role_zero_cost(self):
        # GLM/Kimi are free
        cost = estimate_cost_for_role("classifier", 1000, 500)
        assert cost == 0.0

    def test_premium_role_has_cost(self):
        cost = estimate_cost_for_role("planner", 10000, 5000)
        # Lightning: input $2.5/MTok, output $12.5/MTok
        # 10K input = $0.025, 5K output = $0.0625
        assert cost > 0
        expected = round((10000/1_000_000)*2.5 + (5000/1_000_000)*12.5, 6)
        assert cost == expected


class TestAutoModelRouterTiered:
    """Test auto_model_router tiered selection."""

    def test_classifier_role_selects_cheap(self):
        result = select_executor_by_role("classifier", "classify this task")
        assert result["executor"] in ["glm-executor", "kimi-executor"]
        assert result["tier"] == "cheap"

    def test_router_role_selects_cheap(self):
        result = select_executor_by_role("router", "route this task")
        assert result["executor"] in ["glm-executor", "kimi-executor"]
        assert result["tier"] == "cheap"

    def test_planner_role_selects_premium(self):
        result = select_executor_by_role("planner", "plan this project")
        assert result["executor"] == "lightning-executor"
        assert result["tier"] == "premium"

    def test_synthesizer_role_selects_premium(self):
        result = select_executor_by_role("synthesizer", "synthesize results")
        assert result["executor"] == "lightning-executor"
        assert result["tier"] == "premium"

    def test_unknown_role_falls_back_to_task_type(self):
        result = select_executor_by_role("unknown_role", "simple_edit file.txt")
        assert result["executor"] == "glm-executor"  # From config routing rule


class TestCostEstimationByRole:
    """Test cost estimation with role-based selection."""

    def test_classifier_saves_vs_premium(self):
        result = estimate_task_cost_by_role(
            "classifier", "classify task", 10000, 5000
        )
        # Classifier uses cheap (free) → should save 100% vs Lightning
        assert result["savings_pct"] >= 99.0
        assert result["total_cost_usd"] == 0.0

    def test_planner_costs_same_as_premium(self):
        result = estimate_task_cost_by_role(
            "planner", "plan project", 10000, 5000
        )
        # Planner uses premium (Lightning) → same as baseline
        assert result["savings_pct"] == 0.0
        assert result["total_cost_usd"] == result["baseline_cost_usd"]

    def test_mixed_roles_different_costs(self):
        classifier_cost = estimate_task_cost_by_role("classifier", "task", 10000, 5000)
        planner_cost = estimate_task_cost_by_role("planner", "task", 10000, 5000)

        assert classifier_cost["total_cost_usd"] < planner_cost["total_cost_usd"]


class TestCostTrackerPerRole:
    """Test per-role cost tracking (mock session)."""

    def setup_method(self):
        # We can't easily test without ahd_session, so test the logic
        pass

    def test_estimate_cost_cheap_role(self):
        # Test the cost estimation logic directly
        from router_config import estimate_cost_for_role
        cost = estimate_cost_for_role("classifier", 500, 300)
        assert cost == 0.0  # Free tier


class TestValidateConfig:
    """Test budget config validation."""

    def test_no_warnings(self):
        warnings = validate_budget_config()
        # Should have no warnings with default config
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])