#!/usr/bin/env python3
"""Kiểm thử Adaptive Compression — T3.2 (REQ-002).

Các ca kiểm thử:
1. Query đơn giản → nén tối thiểu (chỉ bỏ turn rỗng).
2. Query phức tạp → nén sâu (gộp turn liên tiếp cùng role).
3. prefix_stable_hash: prefix ổn định khi turn đầu mỗi role giữ nguyên.
4. prefix_stable_hash: phát hiện prefix bị thay đổi.
5. mode="minimal" / "deep" override auto.
6. Đầu vào không hợp lệ raise lỗi.
7. History rỗng → trả list rỗng.
8. Không thay đổi history đầu vào.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from adaptive_compress import compress, prefix_stable_hash  # noqa: E402
from data_models import Turn  # noqa: E402


def _ts(i: int) -> datetime:
    """Tạo timestamp cố định theo index để test deterministic."""
    return datetime(2026, 1, 1, 0, 0, i, tzinfo=timezone.utc)


def _turn(role: str, content: str, i: int) -> Turn:
    return Turn(role=role, content=content, tokens=max(1, len(content) // 4), timestamp=_ts(i))


def _simple_history() -> list[Turn]:
    return [
        _turn("user", "tôi cần giúp", 0),
        _turn("assistant", "tôi sẽ giúp bạn", 1),
        _turn("user", "viết hàm tính tổng", 2),
        _turn("assistant", "def tong(a,b): return a+b", 3),
    ]


def _complex_history() -> list[Turn]:
    """History có nhiều turn liên tiếp cùng role để test gộp."""
    return [
        _turn("user", "câu hỏi cũ 1", 0),
        _turn("user", "câu hỏi cũ 2", 1),
        _turn("assistant", "trả lời cũ 1", 2),
        _turn("assistant", "trả lời cũ 2", 3),
        _turn("assistant", "trả lời cũ 3", 4),
        _turn("user", "câu hỏi mới nhất", 5),
        _turn("assistant", "trả lời mới nhất", 6),
    ]


def test_simple_query_minimal_compress():
    """Query đơn giản → nén tối thiểu, giữ nguyên history (trừ turn rỗng)."""
    history = _simple_history()
    out = compress(history, "viết hàm", mode="auto")
    # Query đơn giản (2 từ) → minimal → giữ nguyên 4 turn.
    assert len(out) == 4
    assert [t.content for t in out] == [t.content for t in history]


def test_simple_query_drops_empty_turns():
    """Nén tối thiểu bỏ turn có content rỗng."""
    history = [
        _turn("user", "", 0),
        _turn("assistant", "ok", 1),
        _turn("user", "   ", 2),
    ]
    out = compress(history, "hi", mode="auto")
    assert len(out) == 1
    assert out[0].content == "ok"


def test_complex_query_deep_compress():
    """Query phức tạp → nén sâu: gộp turn liên tiếp cùng role."""
    history = _complex_history()
    out = compress(history, "phân tích so sánh đánh giá", mode="auto")
    # 7 turn gốc, gộp nhóm → ít hơn.
    assert len(out) < len(history)
    # Turn cuối mỗi role phải còn nguyên (user mới nhất, assistant mới nhất).
    contents = [t.content for t in out]
    assert "câu hỏi mới nhất" in contents
    assert "trả lời mới nhất" in contents


def test_deep_mode_merges_consecutive_same_role():
    """mode=deep gộp nhóm liên tiếp cùng role thành 1 tóm tắt (trừ last của role)."""
    history = _complex_history()
    out = compress(history, "anything", mode="deep")
    # Nhóm: [u,u] [a,a,a] [u] [a] → u cũ gộp, a cũ gộp, u mới giữ, a mới giữ = 4.
    assert len(out) == 4
    roles = [t.role for t in out]
    # Thứ tự role phải xen kẽ không có 2 role liên tiếp giống nhau.
    for i in range(1, len(roles)):
        assert roles[i] != roles[i - 1]


def test_prefix_stable_hash_stable():
    """prefix_stable_hash True khi turn đầu mỗi role giữ nguyên."""
    before = _complex_history()
    after = compress(before, "phân tích", mode="auto")
    # Turn đầu user ("câu hỏi cũ 1") và đầu assistant ("trả lời cũ 1") —
    # với deep_compress, nhóm [u,u] cũ gộp thành 1 tóm tắt, mất "câu hỏi cũ 1" → không ổn định.
    # Test riêng: tạo after mà giữ nguyên turn đầu mỗi role.
    stable_after = [
        _turn("user", "câu hỏi cũ 1", 0),
        _turn("assistant", "trả lời cũ 1", 2),
        _turn("user", "câu hỏi mới nhất", 5),
        _turn("assistant", "trả lời mới nhất", 6),
    ]
    assert prefix_stable_hash(before, stable_after) is True


def test_prefix_stable_hash_unstable_when_first_role_turn_changed():
    """prefix_stable_hash False khi turn đầu role bị thay đổi."""
    before = [
        _turn("user", "gốc user", 0),
        _turn("assistant", "gốc assistant", 1),
    ]
    after = [
        _turn("user", "ĐÃ THAY ĐỔI", 0),
        _turn("assistant", "gốc assistant", 1),
    ]
    assert prefix_stable_hash(before, after) is False


def test_prefix_stable_hash_false_when_role_lost():
    """prefix_stable_hash False khi role mất trong after."""
    before = [
        _turn("user", "u", 0),
        _turn("assistant", "a", 1),
    ]
    after = [_turn("user", "u", 0)]
    assert prefix_stable_hash(before, after) is False


def test_prefix_stable_hash_empty_before():
    """before rỗng → luôn ổn định."""
    assert prefix_stable_hash([], [_turn("user", "x", 0)]) is True


def test_prefix_stable_hash_empty_after_nonempty_before():
    """after rỗng, before không rỗng → không ổn định."""
    before = [_turn("user", "x", 0)]
    assert prefix_stable_hash(before, []) is False


def test_mode_minimal_override():
    """mode=minimal luôn nén tối thiểu dù query phức tạp."""
    history = _complex_history()
    out = compress(history, "phân tích so sánh", mode="minimal")
    assert len(out) == len(history)  # không có turn rỗng → giữ nguyên


def test_mode_deep_override():
    """mode=deep luôn nén sâu dù query đơn giản."""
    history = _complex_history()
    out = compress(history, "hi", mode="deep")
    assert len(out) < len(history)


def test_invalid_inputs():
    with pytest.raises(TypeError):
        compress("not a list", "q")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        compress([], 123)  # type: ignore[arg-type]


def test_empty_history():
    assert compress([], "q", mode="auto") == []


def test_input_not_mutated():
    """compress không thay đổi history đầu vào."""
    history = _complex_history()
    snapshot = [t.model_dump(by_alias=True) for t in history]
    compress(history, "phân tích", mode="deep")
    after = [t.model_dump(by_alias=True) for t in history]
    assert snapshot == after
