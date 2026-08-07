#!/usr/bin/env python3
"""Kiểm thử cot_synthesis.py — T4.8 (REQ-011).

Các ca kiểm thử:
1. synthesize trả CoT với steps không rỗng.
2. CoT token ≤ model budget.
3. critique trả CRVScore với reasoning_load, coherence, pass.
4. CoT mạch lạc (có "Bước N:") -> pass=True.
5. CoT rỗng/kém -> pass=False.
6. Đầu vào không hợp lệ raise lỗi.
7. Budget nhỏ vẫn fit được.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from data_models import CoT, CRVScore, ModelProfile  # noqa: E402
from cot_synthesis import synthesize, critique  # noqa: E402


def _profile(budget: int = 2048) -> ModelProfile:
    return ModelProfile(
        name="test-small",
        context_budget=budget,
        tool_profile="conservative",
        k_chunks=4,
    )


def test_synthesize_returns_cot_with_steps():
    """synthesize trả CoT có steps không rỗng."""
    cot = synthesize("Bài toán A. Cần giải. Có ràng buộc.", _profile())
    assert isinstance(cot, CoT)
    assert len(cot.steps) > 0
    assert cot.tokens > 0
    assert cot.model_profile == "test-small"


def test_cot_tokens_within_budget():
    """Tổng token của CoT phải ≤ context_budget."""
    budget = 1024
    cot = synthesize("Bài toán dài. Nhiều bước. Nhiều ràng buộc. Cần giải cẩn thận.", _profile(budget=budget))
    assert cot.tokens <= budget


def test_critique_returns_crvscore():
    """critique trả CRVScore đầy đủ trường."""
    cot = synthesize("Bài toán A. Cần giải.", _profile())
    score = critique(cot)
    assert isinstance(score, CRVScore)
    assert 0.0 <= score.reasoning_load <= 1.0
    assert 0.0 <= score.coherence <= 1.0
    assert isinstance(score.critique, str)
    assert isinstance(score.pass_, bool)


def test_well_structured_cot_passes():
    """CoT có 'Bước N:' và từ reasoning -> pass=True."""
    cot = CoT(
        problem="test",
        steps=[
            "Bước 1: Phân tích bài toán",
            "Bước 2: Áp dụng phương pháp",
            "Bước 3: Kiểm tra kết quả",
        ],
        tokens=30,
        model_profile="test",
    )
    score = critique(cot)
    assert score.pass_ is True
    assert score.reasoning_load >= 0.5
    assert score.coherence >= 0.5


def test_empty_cot_fails():
    """CoT rỗng -> pass=False."""
    cot = CoT(problem="test", steps=[], tokens=0, model_profile="test")
    score = critique(cot)
    assert score.pass_ is False
    assert "rỗng" in score.critique.lower() or "không đạt" in score.critique.lower()


def test_unstructured_cot_low_coherence():
    """CoT không có 'Bước N:' -> coherence thấp, pass=False."""
    cot = CoT(
        problem="test",
        steps=["làm gì đó", "làm tiếp", "xong"],
        tokens=10,
        model_profile="test",
    )
    score = critique(cot)
    assert score.coherence < 0.5
    assert score.pass_ is False


def test_invalid_inputs_raise():
    """Đầu vào không hợp lệ raise lỗi."""
    with pytest.raises(ValueError):
        synthesize("", _profile())
    with pytest.raises(ValueError):
        synthesize("   ", _profile())
    with pytest.raises(TypeError):
        synthesize("task", "not-a-profile")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        critique("not-a-cot")  # type: ignore[arg-type]


def test_small_budget_fits():
    """Budget nhỏ (minimum 1024) vẫn synthesize được."""
    cot = synthesize("Task ngắn.", _profile(budget=1024))
    assert cot.tokens <= 1024
    assert len(cot.steps) >= 1


def test_single_sentence_problem():
    """Problem 1 câu vẫn tạo được các bước generic."""
    cot = synthesize("Tính tổng 2+2.", _profile())
    assert len(cot.steps) >= 3  # generic steps


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
