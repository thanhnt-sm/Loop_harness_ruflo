#!/usr/bin/env python3
"""pre_tool_cli.py — CLI / orchestration cho pre_tool_use hook.

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API: main() (threading timeout wrapper) + _run_main() (gate runner).
"""
import json
import os
import re
import sys
import threading

# T4 fix: Internal timeout — fail-closed thay vì fail-open.
# Config timeout 3s; internal timeout 2.5s (0.5s margin) để exit trước config.
# Nếu timeout → BLOCK + escalate (không force-allow).
HOOK_TIMEOUT_SECONDS = 2.5

from pre_tool_encoding import normalize_command
from pre_tool_dangerous import (
    DANGEROUS_PATTERNS,
    WARN_PATTERNS,
    _check_bash_workspace_layout_gate,
)
from pre_tool_gates import (
    _check_context_oversized_gate,
    _check_cost_cap_gate,
    _check_ssrf_gate,
    _check_encoding_bypass_gate,
    _check_reflection_gate,
    _check_risk_contract,
    _check_workspace_layout_gate,
)
from pre_tool_callgraph import _check_call_graph_gate
from pre_tool_sandbox import _check_sandbox_gate


def _entry_mod():
    """Trả module entry (pre_tool_use) hoặc __main__ — hỗ trợ monkeypatch test."""
    return sys.modules.get("pre_tool_use") or sys.modules.get("__main__")


def _run_main() -> None:
    """Gate runner — logic gốc của main() trước khi có threading wrapper."""
    try:
        data = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
        print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
        # U42: Fail-closed mode — exit 2 on parse error if configured
        fail_closed = os.environ.get("AHD_FAIL_CLOSED", "0") == "1"
        if fail_closed:
            print("[U42 Fail-closed] stdin parse error — blocking.", file=sys.stderr)
            sys.exit(2)
        # Can't parse input — allow (don't block on parse failure)
        sys.exit(0)

    # Gate 1: context-oversized enforcement (all tools)
    _check_context_oversized_gate(data)

    # Gate 1.4: T2.4 — Cost cap enforcement (pre-tool-use)
    # Đọc check_cost_cap động từ entry module (hỗ trợ monkeypatch test trên
    # pre_tool_use.check_cost_cap); guard None giống bản gốc (bỏ qua gate luôn).
    check_cost_cap = getattr(_entry_mod(), "check_cost_cap", globals().get("check_cost_cap"))
    if check_cost_cap is not None:
        _check_cost_cap_gate(data)

    # Gate 1.8: RC-3 — Call-graph enforcement
    _check_call_graph_gate(data)

    # Gate 1.9: RC-4 — Seatbelt sandbox for hooks
    _check_sandbox_gate(data)

    # Gate 1.5: U28 — Risk contract check for critical file modifications
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    _check_risk_contract(tool_name, tool_input)

    # Gate 1.6: T2.9 — SSRF guard
    _check_ssrf_gate(data)

    # Gate 1.7: T2.10 — Encoding bypass guard
    _check_encoding_bypass_gate(data)

    # Gate 1.8: Workspace layout enforcement — prevent root markdown/junk files.
    _check_workspace_layout_gate(data)

    # Gate 2: dangerous-command check (Bash/shell only)
    # tool_name + tool_input already extracted above (Gate 1.5)

    if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
        sys.exit(0)

    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Normalize before pattern matching (U02: fix regex bypass via shell encoding)
    normalized = normalize_command(command)

    # Gate 2.0a: Workspace layout enforcement in shell commands (e.g. `echo > REPORT.md`)
    _check_bash_workspace_layout_gate(normalized)

    # Check dangerous patterns against BOTH raw and normalized command
    # T4 fix: patterns đã pre-compile tại module load — dùng .search() thay re.search()
    for pattern, reason in DANGEROUS_PATTERNS:
        if pattern.search(command) or pattern.search(normalized):
            print(f"[Agent Harness Deploy guard] BLOCKED: {reason}", file=sys.stderr)
            print(f"Command: {command[:200]}", file=sys.stderr)
            print(f"Pattern: {pattern.pattern}", file=sys.stderr)
            sys.exit(2)

    # Gate 2.1: T4.9 — Reflection gate (pre-action reflection, multi-level)
    # Chạy sau dangerous-pattern gate để giữ thông báo quen thuộc cho các lệnh
    # destructive đã được nhận diện; reflection gate bổ sung cho trường hợp còn lại.
    _check_reflection_gate(data)

    # Check warn patterns (allow but note)
    for pattern, reason in WARN_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            print(f"[Agent Harness Deploy guard] NOTE: {reason} — proceed carefully", file=sys.stderr)
            break

    sys.exit(0)


def main() -> None:
    """    U52: Fail-closed default — block on timeout unless AHD_FAIL_OPEN=1.

    Chạy _run_main() trong thread có timeout; nếu vượt quá HOOK_TIMEOUT_SECONDS
    thì fail-closed (exit 2) trừ khi AHD_FAIL_OPEN=1.
    """
    result = {"code": 0}

    def _run():
        try:
            _run_main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception as e:  # noqa: BLE001
            # U52: fail-closed on unexpected error too (was fail-open)
            print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
            fail_open = os.environ.get("AHD_FAIL_OPEN", "0") == "1"
            result["code"] = 0 if fail_open else 2

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        # U52: Timeout — fail closed by default, fail open only if AHD_FAIL_OPEN=1
        fail_open = os.environ.get("AHD_FAIL_OPEN", "0") == "1"
        if fail_open:
            print("[pre_tool_use] U52 timeout — allowing (AHD_FAIL_OPEN=1)", file=sys.stderr)
            sys.exit(0)
        else:
            print("[pre_tool_use] U52 timeout — blocking (fail-closed default)", file=sys.stderr)
            sys.exit(2)
    sys.exit(result["code"])
