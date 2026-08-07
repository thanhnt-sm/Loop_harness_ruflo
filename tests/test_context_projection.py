#!/usr/bin/env python3
"""Kiểm thử Context Projection Engine — T3.1 (REQ-001).

Các ca kiểm thử:
1. Viewport có tối đa K chunk.
2. Tổng token viewport <= budget_tokens.
3. Substrate gốc không bị thay đổi sau khi project.
4. Chunk liên quan query có điểm cao hơn và được ưu tiên.
5. Budget nhỏ → viewport bị cắt cho vừa.
6. Đầu vào không hợp lệ raise lỗi.
7. Đọc substrate dạng thư mục và dạng file JSON có cấu trúc chunks.
8. Token reduction ≥ 25%: viewport nhỏ hơn ít nhất 25% so với substrate.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from context_projection import project, _estimate_tokens  # noqa: E402
from data_models import Viewport  # noqa: E402


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_viewport_respects_k(tmp_path):
    """Viewport có tối đa K chunk."""
    substrate = tmp_path / "sub.txt"
    # Tạo substrate lớn để chia nhiều chunk.
    _write_text_file(substrate, "nội dung đoạn văn bản số\n" * 2000)
    vp = project(substrate, "đoạn văn bản", k=5, budget_tokens=100000)
    assert isinstance(vp, Viewport)
    assert len(vp.chunks) <= 5


def test_viewport_within_budget(tmp_path):
    """Tổng token viewport <= budget_tokens."""
    substrate = tmp_path / "sub.txt"
    _write_text_file(substrate, "x" * 100000)  # ~25000 token
    vp = project(substrate, "x", k=100, budget_tokens=2000)
    assert vp.tokens <= 2000


def test_substrate_unchanged(tmp_path):
    """Substrate gốc không bị thay đổi sau khi project."""
    substrate = tmp_path / "sub.txt"
    original = "dữ liệu gốc quan trọng\n" * 500
    _write_text_file(substrate, original)
    project(substrate, "gốc", k=3, budget_tokens=1000)
    assert substrate.read_text(encoding="utf-8") == original


def test_relevant_chunks_ranked_higher(tmp_path):
    """Chunk chứa từ query được xếp cao hơn chunk không chứa."""
    substrate = tmp_path / "sub.txt"
    # 2 đoạn: đoạn đầu chứa "alpha", đoạn sau chứa "beta".
    content = ("alpha alpha alpha\n" * 100) + "\n" + ("beta beta beta\n" * 100)
    _write_text_file(substrate, content)
    vp = project(substrate, "alpha", k=2, budget_tokens=100000)
    # Chunk đầu (chứa alpha) phải nằm trong viewport và có điểm cao nhất.
    assert len(vp.chunks) >= 1
    assert "alpha" in vp.chunks[0].content


def test_small_budget_trims_chunks(tmp_path):
    """Budget nhỏ → viewport bị cắt cho vừa, không vượt budget."""
    substrate = tmp_path / "sub.txt"
    _write_text_file(substrate, "chunk dữ liệu số một hai ba\n" * 5000)
    vp = project(substrate, "dữ liệu", k=50, budget_tokens=500)
    assert vp.tokens <= 500
    assert len(vp.chunks) <= 50


def test_invalid_inputs(tmp_path):
    """Đầu vào không hợp lệ raise lỗi."""
    substrate = tmp_path / "sub.txt"
    _write_text_file(substrate, "ok")
    with pytest.raises(ValueError):
        project(substrate, "q", k=0, budget_tokens=1000)
    with pytest.raises(ValueError):
        project(substrate, "q", k=5, budget_tokens=0)
    with pytest.raises(TypeError):
        project(substrate, 123, k=5, budget_tokens=1000)  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        project(tmp_path / "khong_ton_tai.txt", "q", k=5, budget_tokens=1000)


def test_directory_substrate(tmp_path):
    """Đọc substrate dạng thư mục: gộp nhiều file .txt/.md."""
    d = tmp_path / "substrate_dir"
    d.mkdir()
    _write_text_file(d / "a.txt", "alpha nội dung file a\n" * 50)
    _write_text_file(d / "b.md", "beta nội dung file b\n" * 50)
    vp = project(d, "alpha", k=10, budget_tokens=100000)
    assert len(vp.chunks) >= 1
    # Chunk có chứa alpha phải được ưu tiên.
    assert "alpha" in vp.chunks[0].content


def test_json_chunks_substrate(tmp_path):
    """Đọc substrate dạng file JSON có cấu trúc {"chunks":[...]}."""
    substrate = tmp_path / "sub.json"
    payload = {
        "chunks": [
            {"content": "alpha " * 100},
            {"content": "beta " * 100},
        ]
    }
    _write_text_file(substrate, json.dumps(payload, ensure_ascii=False))
    vp = project(substrate, "alpha", k=5, budget_tokens=100000)
    assert len(vp.chunks) >= 1
    assert "alpha" in vp.chunks[0].content


def test_token_reduction_at_least_25_percent(tmp_path):
    """Bench: viewport giảm ít nhất 25% token so với substrate."""
    substrate = tmp_path / "sub.txt"
    # Substrate lớn ~25000 token (100000 ký tự).
    _write_text_file(substrate, "đoạn văn bản dữ liệu số " * 4000)
    substrate_tokens = _estimate_tokens(substrate.read_text(encoding="utf-8"))
    vp = project(substrate, "đoạn văn bản", k=8, budget_tokens=4000)
    reduction = (substrate_tokens - vp.tokens) / substrate_tokens
    assert reduction >= 0.25, f"reduction chỉ {reduction:.2%} (< 25%)"


def test_empty_query_keeps_order(tmp_path):
    """Query rỗng → mọi chunk có điểm 0, giữ thứ tự gốc (id tăng dần)."""
    substrate = tmp_path / "sub.txt"
    _write_text_file(substrate, "đoạn số một hai ba bốn năm sáu\n" * 200)
    vp = project(substrate, "", k=3, budget_tokens=100000)
    assert len(vp.chunks) == 3
    # Thứ tự id phải tăng dần (chunk đầu substrate).
    ids = [c.id for c in vp.chunks]
    assert ids == sorted(ids)
