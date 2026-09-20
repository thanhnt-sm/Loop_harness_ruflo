#!/usr/bin/env python3
"""pre_tool_gates.py — Resource gates cho pre_tool_use hook (entry point).

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API:
  - _gate_error
  - _check_context_oversized_gate, _check_cost_cap_gate
  - _check_ssrf_gate, _check_encoding_bypass_gate, _check_reflection_gate
  - _check_risk_contract, _check_workspace_layout_gate
  - _WRITE_TOOLS, _check_reflection, validate_workspace_path, is_allowed_root_file,
    is_junk_path, ALLOWED_ROOT_FILES, ALLOWED_ROOT_PATTERNS, check_cost_cap
"""
import json
import os
import sys
from pathlib import Path

import ahd_session

# Thêm scripts dir để import các module external (cost_tracker, path_zones, ...).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from cost_tracker import check_cost_cap  # noqa: F401  (re-export cho pre_tool_use)
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    check_cost_cap = None  # type: ignore[assignment]

try:
    from path_zones import (
        validate_workspace_path,
        is_allowed_root_file,
        is_junk_path,
        ALLOWED_ROOT_FILES,
        ALLOWED_ROOT_PATTERNS,
    )
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    validate_workspace_path = None  # type: ignore[assignment]
    is_allowed_root_file = None  # type: ignore[assignment]
    is_junk_path = None  # type: ignore[assignment]
    ALLOWED_ROOT_FILES = ()  # type: ignore[assignment]
    ALLOWED_ROOT_PATTERNS = ()  # type: ignore[assignment]

try:
    from reflection_gate import check_reflection as _check_reflection
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    _check_reflection = None  # type: ignore[assignment]

from pre_tool_encoding import (
    detect_encoding_bypass,
    analyze_shell_structure,
    normalize_command,
)
from pre_tool_secrets import (
    check_ssrf,
    _extract_urls,
    _log_ssrf_block,
    _ssrf_allowlist,
    _pin_and_verify_url,
    detect_hlk_secret,
)
from pre_tool_common import _entry_mod, _gate_error
from pre_tool_gates_security import (
    _check_ssrf_gate,
    _check_encoding_bypass_gate,
    _check_reflection_gate,
    _check_risk_contract,
)
from pre_tool_workspace import _check_workspace_layout_gate, _WRITE_TOOLS


def _check_token_revocation_gate(data: dict) -> None:
    """Gate: Check token revocation for high-risk tool calls (CHG-001).
    
    Validates delegation token against local token registry.
    Checks revocation list and REVOCATION_BOUND per V5 protocol.
    """
    try:
        from token_registry import check_revocation_gate
        check_revocation_gate(data)
    except ImportError:
        pass  # token_registry not available
    except Exception as e:
        _gate_error("token_revocation", e)


def _check_context_oversized_gate(data: dict) -> None:
    """Gate 1: context-oversized graduated enforcement.

    Checks .devin/context_flags/<session_id>.json for context_oversized flag.
    If set, responds based on how many tool calls have passed without compaction:
      - counter < WARN_THRESHOLD: allow + stderr note
      - WARN_THRESHOLD <= counter < BLOCK_THRESHOLD: allow + stderr warning
      - counter >= BLOCK_THRESHOLD: block non-compaction tools (exit 2)

    Compaction-safe tools (read, grep, write, etc.) are always allowed so the
    agent can actually run the context-compactor skill.
    """
    # Đọc threshold động từ module entry (hỗ trợ monkeypatch test).
    _em = _entry_mod()
    OVERSIZED_WARN_THRESHOLD = getattr(_em, "OVERSIZED_WARN_THRESHOLD", 2)
    OVERSIZED_BLOCK_THRESHOLD = getattr(_em, "OVERSIZED_BLOCK_THRESHOLD", 4)
    OVERSIZED_NOTE_THRESHOLD = getattr(_em, "OVERSIZED_NOTE_THRESHOLD", 0)
    COMPACTION_SAFE_TOOLS = getattr(_em, "COMPACTION_SAFE_TOOLS", frozenset())
    try:
        session_id = ahd_session.get_session_id(data)
        root = ahd_session.get_repo_root()
        flags = ahd_session.read_context_flags(session_id, root)

        if not flags.get("context_oversized"):
            return  # no flag -> no gate

        counter = flags.get("oversized_tool_calls_since_flag", 0)
        tool_name = data.get("tool_name", "")

        # Always allow compaction-safe tools — agent needs them to compact
        if tool_name in COMPACTION_SAFE_TOOLS:
            if counter >= OVERSIZED_WARN_THRESHOLD:
                print(
                    f"[Agent Harness Deploy] context_oversized: {counter} tool calls "
                    f"without compaction. You are using a compaction-safe tool — good. "
                    f"Continue compacting, then clear the flag.",
                    file=sys.stderr,
                )
            return

        # Non-compaction tool — graduated response
        if counter >= OVERSIZED_BLOCK_THRESHOLD:
            # Block: force the agent to compact before doing more work
            print(
                f"[Agent Harness Deploy] BLOCKED: context_oversized for {counter}+ tool calls "
                f"without compaction. Run the context-compactor skill first: "
                f"(1) offload large outputs to .devin/tmp/, keep head+tail+path. "
                f"(2) lower caveman_level to compact or ultra. "
                f"(3) clear context_oversized flag in "
                f".devin/context_flags/{session_id}.json. "
                f"Then retry this tool call.",
                file=sys.stderr,
            )
            sys.exit(2)
        elif counter >= OVERSIZED_WARN_THRESHOLD:
            print(
                f"[Agent Harness Deploy] WARNING: context_oversized for {counter} tool calls. "
                f"Compact NOW — run context-compactor skill before the next non-essential tool call. "
                f"At {OVERSIZED_BLOCK_THRESHOLD}+ calls, non-compaction tools will be BLOCKED.",
                file=sys.stderr,
            )
        else:
            print(
                f"[Agent Harness Deploy] NOTE: context_oversized detected. "
                f"Run context-compactor skill soon to offload large outputs.",
                file=sys.stderr,
            )
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        _gate_error("context_oversized", e)


def _check_dependency_pins_gate(data: dict) -> None:
    """Gate: Intercept pip/uv commands that could install unpinned dependencies.
    
    Runs check_deps.py logic to validate filelock <3.13, pydantic-core coupling,
    and SBOM consistency before allowing dependency modifications.
    """
    tool_name = data.get("tool_name", "")
    if tool_name != "bash":
        return
    
    command = data.get("tool_input", {}).get("command", "")
    if not command:
        return
    
    # Check for pip/uv install/add/upgrade commands
    dep_commands = [
        "pip install", "pip add", "pip upgrade",
        "uv add", "uv install", "uv sync", "uv pip install",
        "uv pip sync", "uv lock"
    ]
    
    is_dep_command = any(cmd in command.lower() for cmd in dep_commands)
    if not is_dep_command:
        return
    
    # Run check_deps.py
    try:
        import subprocess
        root = ahd_session.get_repo_root()
        result = subprocess.run(
            [sys.executable, "tools/check_deps.py"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(
                f"[Agent Harness Deploy] BLOCKED: Dependency pin check failed.\n"
                f"Command: {command}\n"
                f"filelock must be <3.13; pydantic-core must match pydantic; SBOM must match lock.\n"
                f"Details:\n{result.stderr}",
                file=sys.stderr,
            )
            sys.exit(2)
    except subprocess.TimeoutExpired:
        print(
            "[Agent Harness Deploy] BLOCKED: Dependency pin check timed out (30s).",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:  # noqa: BLE001
        _gate_error("dependency_pins", e)


def _check_cost_cap_gate(data: dict) -> None:
    """T2.4: Kiểm tra cost cap trước khi gọi tool.

    - Dưới 80%: cho phép.
    - Từ 80% đến dưới 100%: in cảnh báo stderr, vẫn cho phép.
    - Đạt/vượt 100%: block (exit 2), set flag cost_cap_exceeded.

    CVE-2026-AHD-013: cumulative cost đọc từ append-only LEDGER
    (cost_ledger.py, HMAC-signed) — KHÔNG fallback session state.
    Ledger bắt buộc phải có HMAC key cấu hình.
    """
    # Đọc check_cost_cap động từ module entry (hỗ trợ monkeypatch test).
    check_cost_cap_fn = getattr(_entry_mod(), "check_cost_cap", None)
    try:
        session_id = ahd_session.get_session_id(data)
        if not session_id:
            return

        root = ahd_session.get_repo_root()

        # CVE-2026-AHD-013: BẮT BUỘC ledger đã verify (HMAC)
        try:
            from cost_ledger import cumulative_from_ledger
            ledger_cum = cumulative_from_ledger(root, session_id)
            if ledger_cum is None:
                # Không có key hoặc ledger không verify được -> FAIL CLOSED
                print(
                    "[U17 COST CAP] BLOCKED: Cost ledger unavailable or HMAC key not configured. "
                    "Cannot verify cumulative cost (CVE-2026-AHD-013 fail-closed).",
                    file=sys.stderr,
                )
                sys.exit(2)
        except (ImportError, ModuleNotFoundError) as e:
            print(
                f"[U17 COST CAP] BLOCKED: cost_ledger module unavailable: {e}",
                file=sys.stderr,
            )
            sys.exit(2)

        state = ahd_session.read_session_state(session_id, root)
        state["cumulative_cost"] = ledger_cum

        if check_cost_cap_fn is None:
            return

        status = check_cost_cap_fn(state)
        if status == 0:
            return

        cumulative = float(state.get("cumulative_cost", 0.0))
        cost_cap = float(state.get("cost_cap", 5.0))
        pct = (cumulative / cost_cap * 100) if cost_cap > 0 else 0

        if status == 2:
            print(
                f"[U17 COST CAP] BLOCKED: ${cumulative:.4f} >= ${cost_cap:.4f} cap "
                f"({pct:.0f}%). Stop escalation.",
                file=sys.stderr,
            )
            ahd_session.update_session_state(session_id, {
                "cost_cap_exceeded": True,
            }, root)
            sys.exit(2)

        # status == 1
        print(
            f"[U17 COST CAP] WARNING: ${cumulative:.4f} is {pct:.0f}% of ${cost_cap:.4f} cap.",
            file=sys.stderr,
        )
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        _gate_error("cost_cap", e)
