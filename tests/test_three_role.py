#!/usr/bin/env python3
"""Kiểm thử three_role.py — T4.7 (REQ-010).

Các ca kiểm thử:
1. run trả Result đầy đủ các trường.
2. Viewport ≤ budget của model.
3. Corrector sửa ≥1 lỗi nếu main có lỗi.
4. Không role bleed: summarizer chỉ thấy task, main thấy task+summary, corrector thấy main.
5. Role split chuẩn hóa tổng = 1.0.
6. Đầu vào không hợp lệ raise lỗi.
7. Small-model fixture: budget nhỏ vẫn chạy được.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from data_models import ModelProfile  # noqa: E402
from three_role import run, Result, DEFAULT_ROLE_SPLIT  # noqa: E402


def _profile(budget: int = 4096, split: dict | None = None) -> ModelProfile:
    return ModelProfile(
        name="test-small",
        context_budget=budget,
        role_split=split or dict(DEFAULT_ROLE_SPLIT),
        tool_profile="conservative",
        k_chunks=4,
    )


def test_run_returns_result():
    """run trả về đối tượng Result đầy đủ trường."""
    result = run("Phân tích bài toán X. Tìm giải pháp.", _profile())
    assert isinstance(result, Result)
    assert result.summary
    assert result.main_answer
    assert result.corrected_answer
    assert result.budget_tokens == 4096
    assert result.viewport_tokens > 0


def test_viewport_within_budget():
    """Viewport tokens phải ≤ budget của model."""
    budget = 2048
    result = run("Bài toán cần giải. Có nhiều bước.", _profile(budget=budget))
    assert result.viewport_tokens <= budget


def test_corrector_fixes_at_least_one_error_when_main_has_errors():
    """Khi main_answer có lỗi (mơ hồ/TBD), corrector phải sửa ≥1."""
    # Task chứa từ mơ hồ để main dễ bắt chước -> corrector phải sửa
    result = run("Maybe cần làm TBD.  Có   nhiều   khoảng   trắng.", _profile())
    # corrector phát hiện ≥1 lỗi
    assert result.corrections >= 1
    assert len(result.errors_found) >= 1


def test_no_role_bleed_isolated_context():
    """Mỗi role chỉ thấy output role trước cần thiết — kiểm tra qua nội dung."""
    task = "Bài toán độc lập XYZ."
    result = run(task, _profile())
    # Summary phải chứa "Tóm tắt" (chỉ từ summarizer)
    assert "Tóm tắt" in result.summary
    # Main phải chứa "Phân tích" (chỉ từ main)
    assert "Phân tích" in result.main_answer
    # Corrected phải kết thúc bằng dấu câu (corrector đã chuẩn hóa)
    assert result.corrected_answer.rstrip().endswith(('.', '!', '?'))


def test_role_split_normalizes_to_one():
    """Role split không hợp lệ vẫn được chuẩn hóa tổng = 1.0."""
    # Split lệch (main 90%, còn lại 5% mỗi role)
    bad_split = {"summarizer": 0.05, "main": 0.90, "corrector": 0.05}
    result = run("Task test.", _profile(split=bad_split))
    total = sum(result.role_split.values())
    assert abs(total - 1.0) < 1e-6
    assert set(result.role_split.keys()) == {"summarizer", "main", "corrector"}


def test_role_split_empty_uses_default():
    """Profile không có role_split -> dùng default."""
    profile = ModelProfile(name="empty", context_budget=2048)
    result = run("Task test.", profile)
    assert set(result.role_split.keys()) == {"summarizer", "main", "corrector"}


def test_invalid_inputs_raise():
    """Đầu vào không hợp lệ raise lỗi."""
    with pytest.raises(ValueError):
        run("", _profile())
    with pytest.raises(ValueError):
        run("   ", _profile())
    with pytest.raises(TypeError):
        run("task", "not-a-profile")  # type: ignore[arg-type]


def test_small_model_fixture_runs():
    """Small-model fixture: budget nhỏ (1024 — minimum của ModelProfile) vẫn chạy được."""
    result = run("Task nhỏ.", _profile(budget=1024))
    assert result.viewport_tokens <= 1024
    assert result.budget_tokens == 1024


def test_corrector_no_errors_when_main_clean():
    """Khi main_answer sạch (không pattern lỗi), corrections = 0."""
    # Task ngắn, không chứa pattern lỗi -> main_answer sạch
    result = run("Tính tổng 2+2.", _profile())
    # corrector có thể không phát hiện lỗi -> corrections có thể = 0
    # Đảm bảo không crash, corrected_answer vẫn hợp lệ
    assert result.corrected_answer
    assert isinstance(result.corrections, int)
    assert result.corrections >= 0


# --- T5.5: Mở rộng coverage ---

def test_normalize_role_split_zero_total_uses_default():
    """role_split có tổng = 0 -> dùng default."""
    from three_role import _normalize_role_split
    profile = ModelProfile(
        name="zero",
        context_budget=2048,
        role_split={"summarizer": 0.0, "main": 0.0, "corrector": 0.0},
    )
    split = _normalize_role_split(profile)
    assert split == {"summarizer": 0.2, "main": 0.6, "corrector": 0.2}


def test_normalize_role_split_partial_uses_default_for_missing():
    """role_split thiếu 1 role -> role đó dùng default, rồi chuẩn hóa."""
    from three_role import _normalize_role_split
    profile = ModelProfile(
        name="partial",
        context_budget=2048,
        role_split={"summarizer": 0.3, "main": 0.7},  # thiếu corrector
    )
    split = _normalize_role_split(profile)
    assert "corrector" in split
    total = sum(split.values())
    assert abs(total - 1.0) < 1e-6


def test_normalize_role_split_no_dict_uses_default():
    """Profile không có role_split (None) -> dùng default."""
    from three_role import _normalize_role_split
    profile = ModelProfile(name="none", context_budget=2048)
    split = _normalize_role_split(profile)
    assert split == {"summarizer": 0.2, "main": 0.6, "corrector": 0.2}


def test_summarizer_short_task():
    """_summarizer với task ngắn vẫn trả tóm tắt."""
    from three_role import _summarizer
    summary = _summarizer("Task ngắn.", 1024)
    assert "Tóm tắt" in summary
    assert summary.rstrip().endswith(".")


def test_summarizer_empty_sentences():
    """_summarizer với task không có câu hoàn chỉnh vẫn trả kết quả."""
    from three_role import _summarizer
    summary = _summarizer("no punctuation here", 1024)
    assert "Tóm tắt" in summary


def test_summarizer_truncates_to_budget():
    """_summarizer không vượt quá char budget."""
    from three_role import _summarizer
    long_task = ". ".join(f"sentence {i}" for i in range(100))
    summary = _summarizer(long_task, 256)
    # char_budget = 256 * 0.25 * 4 = 256
    assert len(summary) < 500  # không quá dài


def test_main_truncates_to_budget():
    """_main không vượt quá char budget."""
    from three_role import _main
    long_task = "x" * 5000
    answer = _main(long_task, "summary", 256)
    # char_budget = 256 * 0.6 * 4 = ~614
    assert len(answer) <= 700


def test_corrector_fixes_first_person_pronouns():
    """_corrector sửa đại từ ngôi thứ nhất."""
    from three_role import _corrector
    corrected, errors = _corrector("Tôi nghĩ maybe đúng.", 4096)
    assert any("đại từ" in e for e in errors)
    assert "tôi" not in corrected.lower()


def test_corrector_fixes_vague_words():
    """_corrector sửa từ mơ hồ."""
    from three_role import _corrector
    corrected, errors = _corrector("maybe có lẽ đúng.", 4096)
    assert any("mơ hồ" in e for e in errors)
    assert "maybe" not in corrected.lower()


def test_corrector_fixes_tbd_todo():
    """_corrector sửa TBD/TODO."""
    from three_role import _corrector
    corrected, errors = _corrector("Phần này TBD.", 4096)
    assert any("TBD" in e for e in errors)
    assert "TBD" not in corrected


def test_corrector_fixes_extra_whitespace():
    """_corrector sửa khoảng trắng dư."""
    from three_role import _corrector
    corrected, errors = _corrector("Có   nhiều   khoảng   trắng.", 4096)
    assert any("khoảng trắng" in e for e in errors)
    assert "   " not in corrected


def test_corrector_fixes_ellipsis():
    """_corrector phát hiện dấu ba chấm lạm dụng."""
    from three_role import _corrector
    corrected, errors = _corrector("Thiếu chi tiết...", 4096)
    # Pattern được phát hiện (reason chứa "ba chấm")
    assert any("ba chấm" in e for e in errors)


def test_corrector_adds_ending_punctuation():
    """_corrector thêm dấu câu cuối nếu thiếu."""
    from three_role import _corrector
    corrected, _ = _corrector("Câu không có dấu kết", 4096)
    assert corrected.rstrip().endswith((".", "!", "?"))


def test_corrector_truncates_to_budget():
    """_corrector không vượt quá char budget."""
    from three_role import _corrector
    long_answer = "x" * 5000
    corrected, _ = _corrector(long_answer, 256)
    # char_budget = 256 * 0.2 * 4 = ~204
    assert len(corrected) <= 250


def test_run_with_custom_role_split():
    """run với role_split tùy chỉnh vẫn chạy."""
    result = run("Task test.", _profile(split={"summarizer": 0.3, "main": 0.5, "corrector": 0.2}))
    assert result.budget_tokens == 4096
    total = sum(result.role_split.values())
    assert abs(total - 1.0) < 1e-6


def test_cli_runs_with_args(capsys, monkeypatch):
    """CLI stub chạy với task từ argv."""
    import three_role
    monkeypatch.setattr(sys, "argv", ["three_role.py", "Test task from argv"])
    code = three_role._cli()
    assert code == 0
    captured = capsys.readouterr()
    assert "summary" in captured.out


def test_cli_error_on_empty(capsys, monkeypatch):
    """CLI stub lỗi khi task rỗng."""
    import three_role
    monkeypatch.setattr(sys, "argv", ["three_role.py", ""])
    code = three_role._cli()
    assert code == 1


def test_result_model_validation():
    """Result model validate các trường."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Result(
            summary="s", main_answer="m", corrected_answer="c",
            corrections=-1,  # ge=0
            role_split={}, viewport_tokens=0, budget_tokens=1,
        )
    with pytest.raises(ValidationError):
        Result(
            summary="s", main_answer="m", corrected_answer="c",
            corrections=0, role_split={}, viewport_tokens=0,
            budget_tokens=0,  # ge=1
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
