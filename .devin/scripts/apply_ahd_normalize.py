#!/usr/bin/env python3
"""
apply_ahd_normalize.py — Text normalization sau khi merge AHD patch.

Chứa: _text_replacements, normalize_text_after_merge, _normalize_json, _normalize_py.
"""

from __future__ import annotations
import update_common

import ast
import json
import re
from pathlib import Path
from typing import Any

from apply_ahd_map import PATH_MAP


def _text_replacements() -> list[tuple[str, str]]:
    """Bảng thay thế text cho normalizer."""
    repl = []
    for up, loc in PATH_MAP.items():
        # Chỉ thay thế text references, không thay code logic
        repl.append((up, loc))
    # Bổ sung các thay thế rõ ràng
    repl.append(("scripts/verify.py", "tools/verify-workspace.ps1"))
    repl.append(("scripts/detect.py", ".devin/scripts/plan_dispatch.py"))
    return repl


def _normalize_json(data: Any, repl: list[tuple[str, str]]) -> Any:
    """Đệ quy normalize JSON values."""
    if isinstance(data, dict):
        return {k: _normalize_json(v, repl) for k, v in data.items()}
    if isinstance(data, list):
        return [_normalize_json(v, repl) for v in data]
    if isinstance(data, str):
        for old, new in repl:
            data = data.replace(old, new)
    return data


def _normalize_py(text: str, repl: list[tuple[str, str]]) -> str:
    """Chỉ thay thế comments/docstrings, không thay tên biến/hàm."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expr, ast.Assign)) and isinstance(getattr(node, "value", None), ast.Constant):
            c = node.value
            if isinstance(c.value, str):
                new_val = c.value
                for old, new in repl:
                    new_val = new_val.replace(old, new)
                if new_val != c.value:
                    # Thay thế trong source đơn giản
                    text = text.replace(c.value, new_val, 1)
    return text


def normalize_text_after_merge(paths: list[str]) -> None:
    """Chuẩn hóa text references trong các file vừa patch."""
    repl = _text_replacements()
    for p in paths:
        f = update_common.REPO_ROOT / p
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        ext = f.suffix
        if ext == ".md":
            new_text = text
            for old, new in repl:
                # Tránh thay thế bên trong code block
                parts = re.split(r"(```[\s\S]*?```|`[^`]*`)", new_text)
                for i in range(len(parts)):
                    if not parts[i].startswith("`"):
                        parts[i] = parts[i].replace(old, new)
                new_text = "".join(parts)
            if new_text != text:
                f.write_text(new_text, encoding="utf-8")
        elif ext == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            data = _normalize_json(data, repl)
            new_text = json.dumps(data, ensure_ascii=False, indent=2)
            if new_text != text:
                f.write_text(new_text + "\n", encoding="utf-8")
        elif ext == ".py":
            new_text = _normalize_py(text, repl)
            if new_text != text:
                f.write_text(new_text, encoding="utf-8")