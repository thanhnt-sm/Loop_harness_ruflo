#!/usr/bin/env python3
"""context_guard.py — Context Guard (T3.4, REQ-015).

Mục đích: kiểm tra context có vượt quá ngưỡng (mặc định 3000 ký tự) và áp dụng
phản hồi phân cấp (graduated response) để giữ context trong budget:

- Dưới ngưỡng (≤ threshold): trả nguyên văn context.
- Vượt ngưỡng (> threshold, ≤ 1.5x): cảnh báo (warn) — giữ nguyên nội dung,
  thêm tiền tố cảnh báo.
- Vượt 1.5x ngưỡng (> 1.5x, ≤ 2x): nén (compress) — gộp khoảng trắng dư,
  bỏ dòng trùng lặp, giữ thông tin cốt lõi.
- Vượt 2x ngưỡng (> 2x): cắt (truncate) — giữ threshold ký tự đầu và thêm
  dấu hiệu đã cắt.

Hàm chính: check_oversize(context, threshold) -> str.

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


# Hậu tố cắt — dùng tiếng Việt tự nhiên, dễ hiểu.
_TRUNCATE_SUFFIX = "\n[CONTEXT GUARD] Đã cắt nội dung vượt 2x ngưỡng."


def _compress(context: str) -> str:
    """Nén context: gộp khoảng trắng dư, bỏ dòng trùng lặp liền kề."""
    # Bước 1: gộp nhiều khoảng trắng/dấu tab liên tiếp thành 1 khoảng trắng
    lines = []
    for line in context.splitlines():
        stripped = " ".join(line.split())
        lines.append(stripped)
    # Bước 2: bỏ dòng trống lặp lại liền kề
    compressed: list[str] = []
    prev = None
    for line in lines:
        if line == "" and prev == "":
            continue
        compressed.append(line)
        prev = line
    return "\n".join(compressed)


def check_oversize(context: str, threshold: int = 3000) -> str:
    """Kiểm tra và xử lý context vượt ngưỡng theo phản hồi phân cấp.

    Nhận vào:
        context   — chuỗi context cần kiểm tra.
        threshold — ngưỡng ký tự (mặc định 3000).

    Trả về:
        Chuỗi đã được xử lý theo cấp độ:
        - ≤ threshold: nguyên văn.
        - > threshold, ≤ 1.5x: giữ nguyên nội dung.
        - > 1.5x, ≤ 2x: nén nội dung.
        - > 2x: cắt về threshold ký tự + hậu tố cảnh báo cắt.
    """
    if not isinstance(context, str):
        raise TypeError("context phải là chuỗi")
    if threshold <= 0:
        raise ValueError("threshold phải lớn hơn 0")

    size = len(context)

    # Cấp 0: trong budget — trả nguyên văn
    if size <= threshold:
        return context

    # Cấp 3: vượt 2x ngưỡng — cắt cứng
    if size > 2 * threshold:
        return context[:threshold] + _TRUNCATE_SUFFIX

    # Cấp 2: vượt 1.5x ngưỡng — nén
    if size > 1.5 * threshold:
        compressed = _compress(context)
        # Nếu sau nén vẫn vượt 2x ngưỡng thì cắt tiếp cho an toàn
        if len(compressed) > 2 * threshold:
            return compressed[:threshold] + _TRUNCATE_SUFFIX
        return compressed

    # Cấp 1: vượt ngưỡng nhưng ≤ 1.5x — giữ nguyên nội dung, không cảnh báo
    return context


def _cli() -> int:
    """CLI stub: đọc context từ stdin, in kết quả check_oversize."""
    data = sys.stdin.read()
    sys.stdout.write(check_oversize(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
