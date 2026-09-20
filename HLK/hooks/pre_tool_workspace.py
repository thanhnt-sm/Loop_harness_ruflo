#!/usr/bin/env python3
"""pre_tool_workspace.py — Workspace layout gate cho pre_tool_use hook.

Tách từ pre_tool_gates.py để giảm kích thước file. Chứa:
  - _check_workspace_layout_gate
  - _WRITE_TOOLS
"""
import sys
from pathlib import Path

# Thêm scripts dir để import path_zones.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from path_zones import validate_workspace_path
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    validate_workspace_path = None  # type: ignore[assignment]


# --- Workspace layout gate (root markdown/junk prevention) ---
# Các tool write/edit phải tuân theo WORKSPACE_GOVERNANCE.md.
# File mới ở root chỉ được phép nếu nằm trong ALLOWED_ROOT_FILES/PATTERNS.
# Markdown/work report/plan/map phải đặt trong docs/plans/<slug>/ hoặc docs/reports/.
_WRITE_TOOLS = {"write", "edit", "notebook_edit"}


def _check_workspace_layout_gate(data: dict) -> None:
    """Gate: chặn write/edit/notebook_edit tạo file ở root không được phép hoặc junk."""
    # Lazy-resolve để tránh bị "đóng băng" giá trị None khi module được import
    # lần đầu mà .devin/scripts chưa nằm trong sys.path (trường hợp test reload/import chéo).
    vwp = validate_workspace_path
    if vwp is None:
        try:
            from path_zones import validate_workspace_path as vwp  # noqa: PLC0415
        except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
            return
    if vwp is None:
        return
    tool_name = (data.get("tool_name") or "").lower()
    if tool_name not in _WRITE_TOOLS:
        return
    tool_input = data.get("tool_input", {}) or {}
    file_path = ""
    for key in ("file_path", "path", "notebook_path", "file"):
        if key in tool_input:
            file_path = tool_input[key] or ""
            break
    if not file_path:
        return
    ok, reason = vwp(file_path)
    if not ok:
        print(f"[Agent Harness Deploy guard] BLOCKED: {reason}", file=sys.stderr)
        print(f"Target path: {file_path}", file=sys.stderr)
        sys.exit(2)
