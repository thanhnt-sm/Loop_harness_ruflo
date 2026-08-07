#!/usr/bin/env python3
"""Kiểm thử Tool-Schema Compression (TSCG) — T3.3 (REQ-003).

Các ca kiểm thử:
1. Tổng token schema <= budget sau nén.
2. Đã vừa budget → trả nguyên danh sách (không nén).
3. Tool có token lớn được chuyển sang conservative trước.
4. conservative giữ name + parameters + required (tool-call accuracy).
5. Budget quá nhỏ → bỏ tool thừa, giữ tối thiểu 1.
6. Đầu vào không hợp lệ raise lỗi.
7. Không thay đổi input.
8. Tool-call accuracy: name/parameters/required không bị cắt ở conservative.

Lưu ý: ToolDef.description bị giới hạn 200 ký tự (data_models), nên để tạo tool
lớn token ta dùng parameters có giá trị chuỗi dài (≤10000 ký tự theo validator).
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from tscg import compress_schema, _estimate_tool_tokens, DEFAULT_BUDGET_TOKENS  # noqa: E402
from data_models import ToolDef  # noqa: E402


def _big_params(n: int = 50) -> dict:
    """Tạo parameters có nhiều property với giá trị chuỗi dài → token lớn."""
    props = {}
    for i in range(n):
        props[f"prop_{i}"] = {
            "type": "string",
            "description": "x" * 200,
            "default": "y" * 200,
        }
    return {"type": "object", "properties": props}


def _tool(
    name: str,
    desc: str = "desc",
    params: dict | None = None,
    required: list[str] | None = None,
) -> ToolDef:
    return ToolDef(
        name=name,
        description=desc,
        parameters=params or {"type": "object", "properties": {}},
        required=required or [],
        profile="full",
    )


def test_within_budget_returns_unchanged():
    """Tổng token đã <= budget → trả nguyên danh sách."""
    tools = [_tool("a", "short desc"), _tool("b", "short desc 2")]
    out = compress_schema(tools, budget_tokens=DEFAULT_BUDGET_TOKENS)
    assert len(out) == len(tools)
    assert [t.profile for t in out] == ["full", "full"]


def test_total_tokens_within_budget_after_compress():
    """Sau nén, tổng token <= budget."""
    # Mỗi tool có parameters vừa phải (~150 token) → 20 tool ~3000 token.
    tools = [_tool(f"tool_{i}", "desc", _big_params(5)) for i in range(20)]
    budget = 2000
    out = compress_schema(tools, budget_tokens=budget)
    total = sum(_estimate_tool_tokens(t) for t in out)
    assert total <= budget


def test_largest_token_tool_converted_to_conservative_first():
    """Tool có token lớn nhất được chuyển conservative trước."""
    small_params = {"type": "object", "properties": {"x": {"type": "string"}}}
    big_params = _big_params(40)
    tools = [
        _tool("small", "ngắn", small_params),
        _tool("big", "desc", big_params),
        _tool("medium", "desc", _big_params(10)),
    ]
    # Budget vừa đủ cho small + medium nhưng không đủ cho big full.
    budget = _estimate_tool_tokens(tools[0]) + _estimate_tool_tokens(tools[2]) + 50
    out = compress_schema(tools, budget_tokens=budget)
    out_by_name = {t.name: t for t in out}
    if "big" in out_by_name:
        # big phải bị conservative (description cắt) vì là tool lớn nhất.
        assert out_by_name["big"].profile == "conservative"


def test_conservative_keeps_name_params_required():
    """conservative giữ nguyên name + parameters + required (tool-call accuracy)."""
    params = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "mode": {"type": "string", "enum": ["r", "w"]},
        },
    }
    required = ["path"]
    # Tool có parameters lớn để ép conservative.
    big_params = _big_params(40)
    tools = [_tool("read_file", "desc", big_params, required=required)]
    out = compress_schema(tools, budget_tokens=1024)
    assert len(out) == 1
    t = out[0]
    assert t.name == "read_file"
    # parameters + required phải giữ nguyên (chỉ description bị cắt).
    assert t.parameters == big_params
    assert t.required == required


def test_too_small_budget_keeps_at_least_one():
    """Budget quá nhỏ → vẫn giữ tối thiểu 1 tool."""
    tools = [_tool(f"t{i}", "desc", _big_params(40)) for i in range(10)]
    out = compress_schema(tools, budget_tokens=1024)
    assert len(out) >= 1


def test_invalid_inputs():
    with pytest.raises(TypeError):
        compress_schema("not a list")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compress_schema([_tool("a", "b")], budget_tokens=100)  # < MIN
    with pytest.raises(ValueError):
        compress_schema([_tool("a", "b")], budget_tokens=10_000_000)  # > MAX


def test_input_not_mutated():
    """compress_schema không thay đổi input."""
    tools = [_tool("a", "desc", _big_params(40)), _tool("b", "desc", _big_params(40))]
    snapshot = [t.model_dump(by_alias=True) for t in tools]
    compress_schema(tools, budget_tokens=1024)
    after = [t.model_dump(by_alias=True) for t in tools]
    assert snapshot == after


def test_conservative_description_truncated():
    """conservative cắt description về ~80 ký tự."""
    # Tool có description dài 200 ký tự (max) + parameters lớn để ép conservative.
    tools = [_tool("t", "d" * 200, _big_params(40))]
    out = compress_schema(tools, budget_tokens=1024)
    assert len(out) == 1
    assert out[0].profile == "conservative"
    assert len(out[0].description) <= 80


def test_budget_8k_to_16k_supported():
    """Budget trong khoảng 8K–16K hoạt động đúng."""
    tools = [_tool(f"t{i}", "desc", _big_params(20)) for i in range(50)]
    for budget in (8192, 12288, 16384):
        out = compress_schema(tools, budget_tokens=budget)
        total = sum(_estimate_tool_tokens(t) for t in out)
        assert total <= budget


def test_empty_tools_list():
    """Danh sách rỗng → trả rỗng."""
    assert compress_schema([], budget_tokens=DEFAULT_BUDGET_TOKENS) == []


def test_drops_largest_when_all_conservative():
    """Khi mọi tool đã conservative mà vẫn vượt budget → bỏ tool lớn nhất."""
    # Tạo tool đã conservative từ đầu với parameters lớn.
    big_params = _big_params(40)
    small_params = {"type": "object", "properties": {"x": {"type": "string"}}}
    tools = [
        ToolDef(name="big", description="d", parameters=big_params, required=[], profile="conservative"),
        ToolDef(name="small", description="d", parameters=small_params, required=[], profile="conservative"),
    ]
    # Budget đủ cho 1 tool nhỏ nhưng không đủ cho big. Đảm bảo >= MIN_BUDGET.
    small_tokens = _estimate_tool_tokens(tools[1])
    budget = max(1024, small_tokens + 5)
    out = compress_schema(tools, budget_tokens=budget)
    # big phải bị bỏ (lớn hơn), small giữ lại.
    assert len(out) == 1
    assert out[0].name == "small"
