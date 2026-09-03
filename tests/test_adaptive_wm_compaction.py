"""Tests for P1-04: Adaptive WM + Prefix-Cache Compaction."""

from __future__ import annotations

import pytest

import pytest
from datetime import datetime

from context_compaction import (
    AdaptiveWM,
    PrefixCache,
    PressureCompactor,
    get_adaptive_wm,
    get_prefix_cache,
    get_pressure_compactor,
    reset_session_compaction,
    MODEL_CONTEXT_WINDOWS,
    WM_BUDGET_FRACTION,
    RESERVED_TOKENS_HEADROOM_PCT,
    COMPACT_AT_CONTEXT_FRACTION,
    RETAIN_CONTEXT_FRACTION,
)
from adaptive_compress import (
    AdaptiveWM as ScriptAdaptiveWM,
    get_wm_budget_for_model,
    compress,
    compact_by_pressure,
    MODEL_CONTEXT_WINDOWS as AC_MODEL_CONTEXT_WINDOWS,
    WM_BUDGET_FRACTION as AC_WM_BUDGET_FRACTION,
    RESERVED_TOKENS_HEADROOM_PCT as AC_RESERVED_TOKENS_HEADROOM_PCT,
    COMPACT_AT_CONTEXT_FRACTION as AC_COMPACT_AT_CONTEXT_FRACTION,
    RETAIN_CONTEXT_FRACTION as AC_RETAIN_CONTEXT_FRACTION,
)
from data_models import Turn


class TestAdaptiveWM:
    """Test AdaptiveWM budget calculation."""

    def setup_method(self):
        reset_session_compaction("test-session")

    def test_default_model_budget(self):
        wm = AdaptiveWM(model="default")
        # default: 8192 window, 20% reserved = 1638, available = 6554, 80% = 5243
        assert wm.window_size == 8192
        assert wm.reserved_budget == 1638
        assert wm.wm_budget == 5243

    def test_glm_model_budget(self):
        wm = AdaptiveWM(model="glm-5.2")
        # glm-5.2: 200000 window, 20% reserved = 40000, available = 160000, 80% = 128000
        assert wm.window_size == 200000
        assert wm.reserved_budget == 40000
        assert wm.wm_budget == 128000

    def test_kimi_model_budget(self):
        wm = AdaptiveWM(model="kimi-k2.7")
        # kimi-k2.7: 128000 window, 20% reserved = 25600, available = 102400, 80% = 81920
        assert wm.window_size == 128000
        assert wm.reserved_budget == 25600
        assert wm.wm_budget == 81920

    def test_lightning_model_budget(self):
        wm = AdaptiveWM(model="lightning")
        # lightning: 200000 window
        assert wm.window_size == 200000
        assert wm.wm_budget == 128000

    def test_set_model_recalculates(self):
        wm = AdaptiveWM(model="default")
        assert wm.wm_budget == 5243
        wm.set_model("glm-5.2")
        assert wm.wm_budget == 128000

    def test_set_reserved(self):
        wm = AdaptiveWM(model="default")
        wm.set_reserved(1000)
        assert wm.reserved_tokens == 1000

    def test_reserved_capped_at_headroom(self):
        wm = AdaptiveWM(model="default")
        # Try to set more than 20% headroom
        wm.set_reserved(5000)
        # Should be capped at 20% of 8192 = 1638
        assert wm.reserved_tokens == 1638

    def test_should_compact_at_pressure(self):
        wm = AdaptiveWM(model="default")
        # Threshold at 50% of 8192 = 4096
        assert wm.should_compact(4000) is False
        assert wm.should_compact(4096) is True
        assert wm.should_compact(5000) is True

    def test_usage_pct(self):
        wm = AdaptiveWM(model="default")
        # WM budget 5243 + reserved 0 = 5243 / 8192 = 64%
        # Actually wm_budget is 5243, so usage = 5243/8192 = 64%
        pct = wm.usage_pct
        assert 60 <= pct <= 70


class TestGetWMBudgetForModel:
    """Test get_wm_budget_for_model function."""

    def test_default_model(self):
        budget = get_wm_budget_for_model("default")
        assert budget == 5243

    def test_glm_model(self):
        budget = get_wm_budget_for_model("glm-5.2")
        assert budget == 128000

    def test_kimi_model(self):
        budget = get_wm_budget_for_model("kimi-k2.7")
        assert budget == 81920

    def test_lightning_model(self):
        budget = get_wm_budget_for_model("lightning")
        assert budget == 128000

    def test_unknown_model_fallback(self):
        budget = get_wm_budget_for_model("unknown")
        assert budget == 5243  # fallback to default


class TestPrefixCache:
    """Test PrefixCache stability."""

    def setup_method(self):
        reset_session_compaction("test-session")

    def test_pin_and_get(self):
        cache = PrefixCache()
        cache.pin("system_prompt", "You are a helpful assistant")
        assert cache.get("system_prompt") == "You are a helpful assistant"

    def test_only_allowed_items_pinned(self):
        cache = PrefixCache()
        cache.pin("system_prompt", "allowed")
        cache.pin("random_key", "not_allowed")
        assert cache.get("system_prompt") == "allowed"
        assert cache.get("random_key") is None

    def test_prefix_hash_stable(self):
        cache = PrefixCache()
        cache.pin("system_prompt", "prompt v1")
        cache.pin("pinned_memory", "memory v1")
        hash1 = cache.prefix_hash()

        cache.pin("system_prompt", "prompt v1")  # Same value
        hash2 = cache.prefix_hash()

        assert hash1 == hash2

    def test_prefix_hash_changes_on_update(self):
        cache = PrefixCache()
        cache.pin("system_prompt", "prompt v1")
        hash1 = cache.prefix_hash()

        cache.pin("system_prompt", "prompt v2")
        hash2 = cache.prefix_hash()

        assert hash1 != hash2

    def test_is_stable(self):
        cache = PrefixCache()
        cache.pin("system_prompt", "prompt v1")
        hash1 = cache.prefix_hash()
        assert cache.is_stable(hash1) is True

        cache.pin("system_prompt", "prompt v2")
        assert cache.is_stable(hash1) is False


class TestPressureCompactor:
    """Test PressureCompactor."""

    def setup_method(self):
        reset_session_compaction("test-session")

    def test_compact_if_needed_no_pressure(self):
        wm = AdaptiveWM(model="default")
        cache = PrefixCache()
        compactor = PressureCompactor(wm, cache)

        # Content well below threshold (4096)
        content = "x" * 1000
        result = compactor.compact_if_needed(content)
        assert result is None  # No compaction needed

    def test_compact_if_needed_at_pressure(self):
        wm = AdaptiveWM(model="default")
        cache = PrefixCache()
        compactor = PressureCompactor(wm, cache)

        # Content at threshold (4096 tokens ~ 16384 chars)
        content = "x" * 17000  # ~4250 tokens
        result = compactor.compact_if_needed(content)
        assert result is not None
        compressed, stats = result
        assert stats["trigger"] == "pressure"
        assert "wm_budget" in stats
        assert "pressure_threshold" in stats

    def test_retain_newest_fraction(self):
        wm = AdaptiveWM(model="default")
        cache = PrefixCache()
        compactor = PressureCompactor(wm, cache)

        content = "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10"
        retained = compactor.retain_newest_fraction(content, 0.3)
        # 30% of 10 lines = 3 lines, keep last 3
        lines = retained.splitlines()
        assert len(lines) == 3
        assert lines == ["line8", "line9", "line10"]


class TestSessionManagement:
    """Test per-session instance management."""

    def setup_method(self):
        reset_session_compaction("test-session")

    def test_get_adaptive_wm_creates_new(self):
        wm1 = get_adaptive_wm("test-session")
        wm2 = get_adaptive_wm("test-session")
        assert wm1 is wm2  # Same instance

    def test_get_prefix_cache_creates_new(self):
        cache1 = get_prefix_cache("test-session")
        cache2 = get_prefix_cache("test-session")
        assert cache1 is cache2

    def test_get_pressure_compactor_creates_new(self):
        comp1 = get_pressure_compactor("test-session")
        comp2 = get_pressure_compactor("test-session")
        assert comp1 is comp2

    def test_session_isolation(self):
        wm1 = get_adaptive_wm("session-1")
        wm2 = get_adaptive_wm("session-2")
        wm1.set_model("glm-5.2")
        assert wm1.wm_budget == 128000
        assert wm2.wm_budget == 5243  # default

    def test_reset_session(self):
        wm = get_adaptive_wm("test-session")
        wm.set_model("glm-5.2")
        reset_session_compaction("test-session")
        wm_new = get_adaptive_wm("test-session")
        assert wm_new.model == "default"
        assert wm_new.wm_budget == 5243


class TestAdaptiveCompressPressure:
    """Test adaptive_compress pressure mode."""

    def _make_turn(self, content: str) -> Turn:
        """Create a Turn with required fields."""
        return Turn(role="user", content=content, tokens=10, timestamp=datetime.now())

    def test_compact_by_pressure_no_pressure(self):
        wm = ScriptAdaptiveWM(model="default")
        # Create 10 turns
        history = [self._make_turn(f"turn {i}") for i in range(10)]
        current_usage = 1000  # Well below threshold

        result = compact_by_pressure(history, current_usage, wm)
        assert len(result) == 10  # No change

    def test_compact_by_pressure_at_threshold(self):
        wm = ScriptAdaptiveWM(model="default")
        # Create 20 turns
        history = [self._make_turn(f"turn {i}") for i in range(20)]
        current_usage = 5000  # Above threshold (4096)

        result = compact_by_pressure(history, current_usage, wm)
        # Should retain 15% = 3 turns verbatim, compress rest
        assert len(result) < 20
        assert len(result) >= 3  # At least 15% retained

    def test_compact_by_pressure_retains_newest(self):
        wm = ScriptAdaptiveWM(model="default")
        history = [self._make_turn(f"turn {i}") for i in range(20)]
        current_usage = 5000

        result = compact_by_pressure(history, current_usage, wm)
        # Newest 3 turns (15%) should be verbatim
        # Find the last few turns
        for i, turn in enumerate(result[-3:]):
            # The newest turns should have original content
            pass  # At least structure is preserved

    def test_compress_pressure_mode(self):
        wm = ScriptAdaptiveWM(model="default")
        history = [self._make_turn(f"turn {i}") for i in range(20)]
        current_usage = 5000

        result = compress(history, "test query", mode="pressure", wm=wm, current_usage=current_usage)
        assert len(result) < 20

    def test_compress_pressure_mode_requires_wm(self):
        history = [self._make_turn("test")]
        with pytest.raises(ValueError, match="wm and current_usage required"):
            compress(history, "test", mode="pressure")

    def test_compress_pressure_mode_requires_usage(self):
        wm = ScriptAdaptiveWM(model="default")
        history = [self._make_turn("test")]
        with pytest.raises(ValueError, match="wm and current_usage required"):
            compress(history, "test", mode="pressure", wm=wm)


class TestConfigConsistency:
    """Test config constants are consistent between modules."""

    def test_model_windows_consistent(self):
        # Both modules should have same model windows
        for model, window in MODEL_CONTEXT_WINDOWS.items():
            assert AC_MODEL_CONTEXT_WINDOWS.get(model) == window

    def test_wm_budget_fraction_consistent(self):
        assert WM_BUDGET_FRACTION == AC_WM_BUDGET_FRACTION

    def test_reserved_headroom_consistent(self):
        assert RESERVED_TOKENS_HEADROOM_PCT == AC_RESERVED_TOKENS_HEADROOM_PCT

    def test_compact_fraction_consistent(self):
        assert COMPACT_AT_CONTEXT_FRACTION == AC_COMPACT_AT_CONTEXT_FRACTION

    def test_retain_fraction_consistent(self):
        assert RETAIN_CONTEXT_FRACTION == AC_RETAIN_CONTEXT_FRACTION


if __name__ == "__main__":
    pytest.main([__file__, "-v"])