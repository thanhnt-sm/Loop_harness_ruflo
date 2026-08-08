#!/usr/bin/env python3
"""Kiểm thử Context Guard — T3.4 (REQ-015).

Các ca kiểm thử:
1. Context dưới ngưỡng → trả nguyên văn.
2. Context vượt ngưỡng (≤ 1.5x) → thêm cảnh báo, giữ nội dung.
3. Context vượt 1.5x ngưỡng (≤ 2x) → nén (giảm khoảng trắng/dòng trùng).
4. Context vượt 2x ngưỡng → cắt về threshold + hậu tố cảnh báo.
5. Ngưỡng tùy chỉnh hoạt động đúng.
6. Đầu vào không hợp lệ raise lỗi.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from context_guard import check_oversize, _TRUNCATE_SUFFIX  # noqa: E402


def test_under_threshold_returns_unchanged():
    """Cấp 0: trong budget → nguyên văn."""
    ctx = "a" * 1000
    assert check_oversize(ctx, threshold=3000) == ctx


def test_at_threshold_returns_unchanged():
    """Đúng bằng ngưỡng → vẫn nguyên văn (điều kiện ≤ threshold)."""
    ctx = "b" * 3000
    assert check_oversize(ctx, threshold=3000) == ctx


def test_warn_over_threshold():
    """Cấp 1: vượt ngưỡng nhưng ≤ 1.5x → giữ nguyên nội dung, không cảnh báo."""
    threshold = 3000
    ctx = "c" * 3500  # > 3000, < 4500 (1.5x)
    result = check_oversize(ctx, threshold=threshold)
    assert result == ctx


def test_compress_over_1_5x():
    """Cấp 2: vượt 1.5x ngưỡng (≤ 2x) → nén, giảm kích thước."""
    threshold = 2000
    # Tạo context có nhiều khoảng trắng/dòng trùng để nén có tác dụng
    ctx = ("line one   with   spaces\n\n\nline two\n\n\nline three   \n") * 60
    # Đảm bảo vượt 1.5x (3000) nhưng ≤ 2x (4000)
    assert len(ctx) > 1.5 * threshold
    assert len(ctx) <= 2 * threshold
    result = check_oversize(ctx, threshold=threshold)
    # Không chứa hậu tố cắt (vì chưa đến mức cắt)
    assert _TRUNCATE_SUFFIX not in result
    # Kết quả nén phải ngắn hơn hoặc bằng gốc
    assert len(result) <= len(ctx)


def test_truncate_over_2x():
    """Cấp 3: vượt 2x ngưỡng → cắt về threshold + hậu tố cảnh báo."""
    threshold = 3000
    ctx = "d" * 7000  # > 6000 (2x)
    result = check_oversize(ctx, threshold=threshold)
    assert result.endswith(_TRUNCATE_SUFFIX)
    # Phần đầu đúng là threshold ký tự đầu của context
    assert result[:threshold] == ctx[:threshold]


def test_custom_threshold():
    """Ngưỡng tùy chỉnh hoạt động đúng ở cả 3 cấp."""
    threshold = 500
    # Dưới ngưỡng
    assert check_oversize("x" * 400, threshold=threshold) == "x" * 400
    # Vượt ngưỡng (giữ nguyên, không cảnh báo)
    r_warn = check_oversize("y" * 600, threshold=threshold)
    assert r_warn == "y" * 600
    # Vượt 2x (truncate)
    r_trunc = check_oversize("z" * 1200, threshold=threshold)
    assert r_trunc.endswith(_TRUNCATE_SUFFIX)
    assert r_trunc[:threshold] == "z" * threshold


def test_invalid_inputs():
    """Đầu vào không hợp lệ raise lỗi."""
    with pytest.raises(TypeError):
        check_oversize(123, threshold=3000)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        check_oversize("ok", threshold=0)
    with pytest.raises(ValueError):
        check_oversize("ok", threshold=-1)


def test_compress_collapses_whitespace():
    """Nén gộp nhiều khoảng trắng thành 1."""
    threshold = 150
    # Mỗi khối ~28 ký tự, lặp 10 lần = ~280 ký tự → trong band nén (225, 300]
    ctx = "a    b    c\n\n\n\n   d   e   f\n" * 10
    assert len(ctx) > 1.5 * threshold
    assert len(ctx) <= 2 * threshold
    result = check_oversize(ctx, threshold=threshold)
    # Nhiều khoảng trắng đã bị gộp
    assert "    " not in result
    # Nhiều dòng trống liền kề bị gộp
    assert "\n\n\n" not in result


def test_compress_then_truncate_if_still_oversize():
    """Nếu sau nén vẫn vượt 2x → cắt tiếp cho an toàn."""
    threshold = 100
    # Context không có khoảng trắng dư → nén không giảm được
    ctx = "k" * 400  # > 2x threshold (200)
    result = check_oversize(ctx, threshold=threshold)
    assert result.endswith(_TRUNCATE_SUFFIX)
    assert len(result[:threshold]) == threshold
