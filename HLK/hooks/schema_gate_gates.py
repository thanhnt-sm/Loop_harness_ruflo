#!/usr/bin/env python3
"""schema_gate_gates — các cổng kiểm tra deterministic cho schema_gate.

Tách từ schema_gate.py (monolith 824 lines). Giữ nguyên: json_schema,
required_fields, symbol_verification, encoding_bypass và orchestrator _run_gates.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from schema_gate_config import (
    REQUIRED_FIELDS_BY_TOOL,
    _extract_file_path,
    _normalize_path,
)
from schema_gate_secrets import _gate_secret_scan
from schema_gate_paths import _gate_file_path_validation


def _gate_json_schema(tool_output) -> dict | None:
    """Cổng 1: JSON schema validation.

    Nếu output là chuỗi JSON hoặc dict, thử parse và kiểm tra cấu trúc cơ bản.
    Trả về dict lỗi nếu fail, None nếu pass (hoặc không áp dụng).
    """
    # Nếu không phải JSON / dict -> bỏ qua cổng này (không áp dụng)
    if tool_output is None:
        return None
    if isinstance(tool_output, dict):
        # Đã là dict -> coi như pass cổng JSON (cấu trúc hợp lệ)
        return None
    if isinstance(tool_output, str):
        stripped = tool_output.strip()
        if not stripped:
            return None
        # Chỉ kiểm tra nếu bắt đầu bằng { hoặc [ (trông như JSON)
        if stripped[0] not in "{[":
            return None
        try:
            json.loads(stripped)
            return None  # parse thành công -> pass
        except json.JSONDecodeError as e:
            return {
                "reason": f"Invalid JSON: {e}",
                "details": {"position": getattr(e, "pos", -1)},
            }
    return None


def _gate_required_fields(tool_name: str, tool_input: dict, tool_output) -> dict | None:
    """Cổng 2: Required fields check theo loại tool.

    Kiểm tra tool_input có đủ các trường bắt buộc không.
    Trả về dict lỗi nếu thiếu, None nếu pass.
    """
    required = next(
        (v for k, v in REQUIRED_FIELDS_BY_TOOL.items() if k.lower() == tool_name.lower()),
        None,
    )
    if not required:
        return None  # tool không có yêu cầu trường -> pass
    missing = [f for f in required if f not in tool_input or tool_input[f] in (None, "")]
    if missing:
        return {
            "reason": f"Missing required fields: {', '.join(missing)}",
            "details": {"missing_fields": missing, "tool": tool_name},
        }
    return None


def _gate_symbol_verification(tool_name: str, tool_input: dict, root: Path) -> dict | None:
    """Cổng 4: Symbol verification — cho Write/Edit, grep hàm kỳ vọng trong plan.

    Đọc IMPLEMENTATION_PLAN.md (nếu có) để tìm các symbol (hàm/class) kỳ vọng
    cho file đang được ghi. Nếu file mới không chứa symbol -> fail.
    Trả về dict lỗi nếu thiếu symbol, None nếu pass (hoặc không áp dụng).
    """
    if tool_name not in ("Write", "Edit", "write", "edit"):
        return None
    file_path = _extract_file_path(tool_input)
    if not file_path:
        return None
    # Tìm file plan (ưu tiên docs/plans/, sau đó root)
    plan_candidates = [
        root / "docs" / "plans" / "IMPLEMENTATION_PLAN.md",
        root / "IMPLEMENTATION_PLAN.md",
    ]
    plan_path = next((p for p in plan_candidates if p.exists()), None)
    if plan_path is None:
        return None  # không có plan -> bỏ qua cổng
    try:
        plan_text = plan_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        print(f"[schema_gate] unexpected exception: {e}", file=sys.stderr)
        return None
    # Tìm block cho file này: dạng "## <task_id> — <file>: <symbols>"
    # Hoặc "- [ ] <task_id>: <file> (functions: foo, bar)"
    norm_file = _normalize_path(file_path)
    # Pattern 1: dòng chứa đường dẫn file + danh sách hàm trong ngoặc
    expected_symbols: list[str] = []
    for line in plan_text.splitlines():
        if norm_file in line.replace("\\", "/"):
            # Trích tên hàm sau "functions:" hoặc "symbols:"
            m = re.search(r"(?i)(?:functions?|symbols?)\s*[:=]\s*([^\)]+)", line)
            if m:
                syms = [s.strip().strip("`*") for s in m.group(1).split(",") if s.strip()]
                expected_symbols.extend(syms)
    if not expected_symbols:
        return None  # plan không liệt kê symbol cho file này -> pass
    # Đọc nội dung file mới ghi để grep symbol
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if not content:
        return None
    missing_symbols = []
    for sym in expected_symbols:
        # Tìm định nghĩa hàm/class: def sym, function sym, class sym, const sym
        pattern = re.compile(
            rf"\b(def|class|function|const|public|private|protected)\s+{re.escape(sym)}\b",
            re.IGNORECASE,
        )
        if not pattern.search(content):
            missing_symbols.append(sym)
    if missing_symbols:
        return {
            "reason": f"File missing expected symbols from plan: {', '.join(missing_symbols)}",
            "details": {
                "file": file_path,
                "expected_symbols": expected_symbols,
                "missing_symbols": missing_symbols,
                "plan": str(plan_path),
            },
        }
    return None


def detect_encoding_bypass(text: str) -> list[str]:
    """T2.10: Phát hiện các kỹ thuật encoding bypass trong text.

    Trả về danh sách các loại bypass phát hiện được (rỗng nếu sạch).
    """
    if not text:
        return []
    findings: list[str] = []

    if re.search(r'\+[A-Za-z0-9+/]+-', text):
        findings.append("utf7")

    if re.search(r'\bxn--[a-zA-Z0-9-]+\b', text):
        findings.append("punycode")

    if re.search(r'&#[xX]?[0-9a-fA-F]+;', text):
        findings.append("html_entity")

    if re.search(r'\\x[0-9a-fA-F]{2}', text):
        findings.append("hex_escape")

    if re.search(r'\\u[0-9a-fA-F]{4}', text) or re.search(r'\\U[0-9a-fA-F]{8}', text):
        findings.append("unicode_escape")

    if re.search(r'\\[0-7]{1,3}', text):
        findings.append("octal_escape")

    if re.search(r'base64.*[\|<].*(bash|sh|zsh|python|perl)', text, re.IGNORECASE) or \
       re.search(r'base64.*-d.*[\|<]', text, re.IGNORECASE):
        findings.append("base64_pipe")

    return findings


def _gate_encoding_bypass(tool_name: str, tool_input: dict, tool_output) -> dict | None:
    """T2.10: Phát hiện encoding bypass trong output hoặc content đầu vào."""
    sources: list[str] = []

    if isinstance(tool_output, str):
        sources.append(tool_output)
    elif isinstance(tool_output, dict):
        sources.append(json.dumps(tool_output, ensure_ascii=False))

    if isinstance(tool_input, dict):
        for key in ("content", "new_string", "command", "old_string"):
            value = tool_input.get(key)
            if isinstance(value, str):
                sources.append(value)

    for text in sources:
        findings = detect_encoding_bypass(text)
        if findings:
            return {
                "reason": f"Encoding bypass detected: {', '.join(findings)}",
                "details": {"findings": findings, "source": text[:200]},
            }
    return None


def _run_gates(tool_name: str, tool_input: dict, tool_output, root: Path) -> dict:
    """Chạy tuần tự các cổng theo thứ tự ưu tiên.

    Cổng đầu tiên FAIL -> dừng, trả kết quả fail.
    Trả về dict: {"passed": bool, "gate": str, "reason": str, "details": dict}
    """
    # Danh sách cổng theo thứ tự (rẻ nhất trước)
    gates = [
        ("json_schema", lambda: _gate_json_schema(tool_output)),
        ("required_fields", lambda: _gate_required_fields(tool_name, tool_input, tool_output)),
        ("secret_scan", lambda: _gate_secret_scan(tool_output)),
        ("encoding_bypass", lambda: _gate_encoding_bypass(tool_name, tool_input, tool_output)),
        ("symbol_verification", lambda: _gate_symbol_verification(tool_name, tool_input, root)),
        ("file_path_validation", lambda: _gate_file_path_validation(tool_name, tool_input, root)),
    ]
    for gate_name, gate_fn in gates:
        try:
            result = gate_fn()
        except Exception as e:  # noqa: BLE001
            # Lỗi nội bộ cổng -> coi như fail (fail-closed cho an toàn)
            return {
                "passed": False,
                "gate": gate_name,
                "reason": f"Internal error in gate {gate_name}: {e}",
                "details": {"error": str(e)[:200]},
            }
        if result is not None:
            # Cổng fail -> block ngay, không chạy cổng còn lại
            return {
                "passed": False,
                "gate": gate_name,
                "reason": result["reason"],
                "details": result.get("details", {}),
            }
    # Tất cả cổng pass
    return {"passed": True, "gate": "all", "reason": "", "details": {}}
