#!/usr/bin/env python3
"""schema_gate_paths — file path validation gate cho schema_gate.

Tách từ schema_gate.py (monolith 824 lines). Cổng 5: chặn path traversal và
ghi ngoài safe zone cho tool Write/Edit/NotebookEdit. Giữ nguyên logic.
"""
from __future__ import annotations

from pathlib import Path

from schema_gate_config import (
    BLOCKED_ZONES,
    SAFE_ZONES,
    _extract_file_path,
    _normalize_path,
    _resolve_under_root,
)


def _gate_file_path_validation(tool_name: str, tool_input: dict, root: Path) -> dict | None:
    """Cổng 5: File path validation — chặn path traversal và ghi ngoài safe zone.

    Áp dụng cho tool ghi file (Write/Edit/NotebookEdit).
    Trả về dict lỗi nếu vi phạm, None nếu pass (hoặc không áp dụng).
    """
    write_tools = {"Write", "write", "Edit", "edit", "notebook_edit", "NotebookEdit"}
    if tool_name not in write_tools:
        return None
    file_path = _extract_file_path(tool_input)
    if not file_path:
        return None

    # Resolve đường dẫn dưới repo root; tuyệt đối ngoài root -> block
    resolved = _resolve_under_root(file_path, root)
    if resolved is None:
        return {
            "reason": "File path outside repo root is not allowed",
            "details": {"file": file_path},
        }

    try:
        rel = resolved.relative_to(root.resolve())
    except ValueError:
        return {
            "reason": "File path outside repo root is not allowed",
            "details": {"file": file_path},
        }
    norm = _normalize_path(str(rel))

    # Chuẩn hóa lowercase để so khớp zone không phân biệt hoa thường (case-sensitive FS bypass).
    norm_lower = norm.lower()
    # Kiểm tra path traversal: .. trong đường dẫn
    if ".." in norm.split("/"):
        return {
            "reason": "Path traversal blocked: '..' detected in path",
            "details": {"file": file_path, "normalized": norm},
        }
    # Kiểm tra blocked zone: nếu đường dẫn bắt đầu bằng zone cấm -> fail
    for zone in BLOCKED_ZONES:
        zone_norm = zone.replace("\\", "/").lower()
        if norm_lower.startswith(zone_norm) or norm_lower == zone_norm.rstrip("/"):
            return {
                "reason": f"Blocked zone: writing to '{zone}' is not allowed",
                "details": {"file": file_path, "zone": zone},
            }
    # Kiểm tra safe zone: đường dẫn phải nằm trong ít nhất một safe zone
    in_safe = any(norm_lower.startswith(sz.lower()) for sz in SAFE_ZONES)
    if not in_safe:
        return {
            "reason": (
                f"File outside safe zone. Safe zones: {', '.join(SAFE_ZONES)}"
            ),
            "details": {"file": file_path, "safe_zones": list(SAFE_ZONES)},
        }
    return None
