#!/usr/bin/env python3
"""blackboard_cli.py — CLI interface for blackboard.

argparse, _read_value_file, main() entry point.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Import core functions
from blackboard_core import (
    read_value,
    write_value,
    list_keys,
    list_regions,
)


def _read_value_file(path: str) -> tuple[Any, str]:
    """Đọc file JSON chứa giá trị + agent.

    File có dạng: {"value": ..., "agent": "..."} hoặc giá trị đơn.
    Trả về (value, agent).
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[blackboard] Không đọc được file giá trị {path}: {exc}",
              file=sys.stderr)
        return None, "unknown"
    if isinstance(data, dict) and "value" in data:
        return data.get("value"), data.get("agent", "unknown")
    return data, "unknown"


def _build_arg_parser() -> argparse.ArgumentParser:
    """Xây dựng trình phân tích tham số dòng lệnh."""
    ap = argparse.ArgumentParser(
        description="Phase D: Bảng đen bộ nhớ dùng chung (shared blackboard)"
    )
    ap.add_argument("--read", nargs=2, metavar=("region", "key"),
                    help="Đọc giá trị từ region")
    ap.add_argument("--write", nargs=3, metavar=("region", "key", "value.json"),
                    help="Ghi giá trị vào region (kèm giải quyết xung đột)")
    ap.add_argument("--list", metavar="region",
                    help="Liệt kê tất cả key trong region")
    ap.add_argument("--regions", action="store_true",
                    help="Liệt kê tất cả region")
    return ap


def main(argv: list[str] | None = None) -> int:
    """Hàm chính: phân tích tham số, thực thi, in kết quả JSON."""
    ap = _build_arg_parser()
    args = ap.parse_args(argv)

    if not any([args.read, args.write, args.list, args.regions]):
        ap.print_help(sys.stderr)
        return 1

    if args.read:
        region, key = args.read
        result = read_value(region, key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.write:
        region, key, val_path = args.write
        value, agent = _read_value_file(val_path)
        if value is None and val_path:
            # value None có thể hợp lệ (ghi None), nhưng nếu đọc file lỗi
            # thì đã in lỗi. Kiểm tra file tồn tại.
            if not Path(val_path).exists():
                return 1
        result = write_value(region, key, value, agent)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("written") else 1

    if args.list:
        result = list_keys(args.list)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.regions:
        result = list_regions()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 0


# Export public API
__all__ = [
    "main",
    "_read_value_file",
    "_build_arg_parser",
]