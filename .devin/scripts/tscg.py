#!/usr/bin/env python3
"""tscg.py — Tool-Schema Compression (T3.3, REQ-003).

Mục đích: nén danh sách tool schema (ToolDef) sao cho tổng token mô tả schema
nằm trong budget (thường 8K–16K token), giữ độ chính xác gọi tool (tool-call
accuracy) cao nhất có thể.

Chiến lược "conservative" (an toàn, không mất thông tin gọi):
  1. Ước lượng token mỗi tool: dựa trên độ dài JSON schema (4 ký tự ~ 1 token).
  2. Nếu tổng token đã <= budget → trả nguyên danh sách (không nén).
  3. Nếu vượt budget → chuyển tool có mô tả dài nhất sang profile "conservative":
     - Cắt description về 80 ký tự.
     - Giữ nguyên name + parameters + required (không cắt để tool vẫn gọi đúng).
  4. Lặp cho đến khi tổng token <= budget hoặc tất cả tool đã conservative.
  5. Nếu vẫn vượt → bỏ dần tool có token lớn nhất (ít liên quan nhất theo heuristic
     độ dài) cho đến khi vừa budget. Giữ tối thiểu 1 tool.

Hàm chính: compress_schema(tools, budget_tokens) -> list[ToolDef].

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from data_models import ToolDef

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = __import__("pathlib").Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# Ước lượng: 4 ký tự ~ 1 token.
_CHARS_PER_TOKEN = 4
# Giới hạn độ dài description ở profile conservative.
_CONSERVATIVE_DESC_MAX = 80
# Budget mặc định (token) — 8K theo SDD §5.5.
DEFAULT_BUDGET_TOKENS = 8192
# Giới hạn budget hợp lệ (8K–16K theo acceptance criteria).
MIN_BUDGET_TOKENS = 1024
MAX_BUDGET_TOKENS = 1_000_000


def _estimate_tool_tokens(tool: ToolDef) -> int:
    """Ước lượng token của một tool dựa trên JSON schema serialization."""
    data = tool.model_dump(by_alias=True, mode="json")
    text = json.dumps(data, ensure_ascii=False)
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


def _total_tokens(tools: list[ToolDef]) -> int:
    """Tổng token ước lượng của danh sách tool."""
    return sum(_estimate_tool_tokens(t) for t in tools)


def _to_conservative(tool: ToolDef) -> ToolDef:
    """Chuyển một tool sang profile conservative: cắt description, giữ params."""
    desc = tool.description
    if len(desc) > _CONSERVATIVE_DESC_MAX:
        desc = desc[: _CONSERVATIVE_DESC_MAX - 1].rstrip() + "…"
    return tool.model_copy(
        update={
            "profile": "conservative",
            "description": desc,
        }
    )


def compress_schema(
    tools: list[ToolDef],
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> list[ToolDef]:
    """T3.3: Nén danh sách tool schema cho vừa budget_tokens.

    Nhận vào:
        tools         — list[ToolDef] cần nén.
        budget_tokens — giới hạn tổng token (mặc định 8192).

    Trả về:
        list[ToolDef] đã nén (có thể ngắn hơn đầu vào). Không thay đổi input.

    Chiến lược (xem module docstring). Giữ tối thiểu 1 tool.
    """
    if not isinstance(tools, list):
        raise TypeError("tools phải là list[ToolDef]")
    if budget_tokens < MIN_BUDGET_TOKENS or budget_tokens > MAX_BUDGET_TOKENS:
        raise ValueError(
            f"budget_tokens phải nằm trong [{MIN_BUDGET_TOKENS}, {MAX_BUDGET_TOKENS}]"
        )

    # Copy nông để không thay đổi input.
    work = list(tools)

    # Bước 1: đã vừa budget → trả nguyên.
    if _total_tokens(work) <= budget_tokens:
        return work

    # Bước 2: chuyển tool có token lớn nhất sang conservative cho đến khi vừa
    # hoặc tất cả đều đã conservative.
    while _total_tokens(work) > budget_tokens:
        # Tìm tool full có token lớn nhất.
        candidates = [
            (i, t) for i, t in enumerate(work) if t.profile != "conservative"
        ]
        if not candidates:
            break
        # Sắp xếp giảm dần theo token, lấy tool lớn nhất.
        candidates.sort(key=lambda kv: -_estimate_tool_tokens(kv[1]))
        idx, tool = candidates[0]
        work[idx] = _to_conservative(tool)

    # Bước 3: nếu vẫn vượt → bỏ dần tool có token lớn nhất, giữ tối thiểu 1.
    while _total_tokens(work) > budget_tokens and len(work) > 1:
        # Tìm tool có token lớn nhất để bỏ (heuristic: mô tả dài = ít quan trọng).
        idx_max = max(range(len(work)), key=lambda i: _estimate_tool_tokens(work[i]))
        work.pop(idx_max)

    return work


def _cli() -> int:
    """CLI stub: đọc list tool JSON từ stdin, in ra list đã nén."""
    import argparse

    ap = argparse.ArgumentParser(description="Tool-Schema Compression (T3.3)")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET_TOKENS)
    args = ap.parse_args()
    data = sys.stdin.read()
    payload = json.loads(data)
    tools = [ToolDef.model_validate(t) for t in payload.get("tools", [])]
    out = compress_schema(tools, budget_tokens=args.budget)
    sys.stdout.write(
        "[" + ",".join(t.model_dump_json(by_alias=True) for t in out) + "]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
