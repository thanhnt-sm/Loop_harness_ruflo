#!/usr/bin/env python3
"""pre_tool_common.py — Shared helpers cho pre_tool_use gates.

Chứa _entry_mod và _gate_error dùng chung bởi các module gate.
"""
import sys


def _entry_mod():
    """Trả module entry (pre_tool_use hoặc __main__) để đọc constant/monkeypatch.

    Test monkeypatch các attribute trên pre_tool_use (OVERSIZED_*, check_cost_cap...)
    nên gate phải đọc động từ module entry thay vì bind giá trị tĩnh.
    """
    return sys.modules.get("pre_tool_use") or sys.modules.get("__main__")


def _gate_error(gate_name: str, exc: Exception) -> None:
    """Security/resource gates fail closed on internal errors.

    An unexpected exception inside a gate must NOT silently allow the tool call.
    Default: block (exit 2). Opt-in fail-open via AHD_FAIL_OPEN=1 (same convention
    as the U52 timeout handling in main()).
    """
    import os
    print(f"[pre_tool_use] {gate_name} internal error: {exc}", file=sys.stderr)
    if os.environ.get("AHD_FAIL_OPEN", "0") == "1":
        print(
            f"[pre_tool_use] {gate_name} allowing on internal error (AHD_FAIL_OPEN=1).",
            file=sys.stderr,
        )
        return
    print(
        f"[pre_tool_use] {gate_name} FAILED CLOSED: blocked on internal error. "
        f"Set AHD_FAIL_OPEN=1 to allow.",
        file=sys.stderr,
    )
    sys.exit(2)
