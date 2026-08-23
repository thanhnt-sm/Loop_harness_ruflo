#!/usr/bin/env python3
"""pre_tool_gates.py — Các security/resource gates cho pre_tool_use hook.

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API:
  - _gate_error
  - _check_context_oversized_gate, _check_cost_cap_gate, _check_ssrf_gate
  - _check_encoding_bypass_gate, _check_reflection_gate, _check_risk_contract
  - _check_workspace_layout_gate
  - _WRITE_TOOLS, _check_reflection, validate_workspace_path, is_allowed_root_file,
    is_junk_path, ALLOWED_ROOT_FILES, ALLOWED_ROOT_PATTERNS, check_cost_cap
"""
import json
import os
import re
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


def _check_ssrf_gate(data: dict) -> None:
    """T2.9: Kiểm tra SSRF trong command hoặc các trường URL rõ ràng.

    - Trích URL từ command (Bash/Shell) và các trường URL rõ ràng (url, endpoint, host).
    - Bỏ qua content/new_string/old_string của Write/Edit để tránh false positive.
    - URL private/loopback/link-local -> block (exit 2) + ghi OTel log.
    """
    # Đọc helper động từ module entry (hỗ trợ monkeypatch test trên pre_tool_use.*)
    # Dùng globals()[name] làm default để tránh UnboundLocalError (tên local trùng).
    check_ssrf = getattr(_entry_mod(), "check_ssrf", globals()["check_ssrf"])
    _extract_urls = getattr(_entry_mod(), "_extract_urls", globals()["_extract_urls"])
    _pin_and_verify_url = getattr(_entry_mod(), "_pin_and_verify_url", globals()["_pin_and_verify_url"])
    _log_ssrf_block = getattr(_entry_mod(), "_log_ssrf_block", globals()["_log_ssrf_block"])
    _ssrf_allowlist = getattr(_entry_mod(), "_ssrf_allowlist", globals()["_ssrf_allowlist"])
    try:
        session_id = ahd_session.get_session_id(data)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}

        # Pentest fix: chỉ quét nguồn có khả năng chứa URL đích thực sự.
        sources: list[str] = []
        command = tool_input.get("command", "")
        if command:
            sources.append(command)
        # Các trường URL rõ ràng
        for url_field in ("url", "endpoint", "host", "base_url", "api_url"):
            value = tool_input.get(url_field, "")
            if isinstance(value, str) and value and value not in sources:
                sources.append(value)

        allowlist = _ssrf_allowlist()
        seen: set[str] = set()
        for text in sources:
            for url in _extract_urls(text):
                if url in seen:
                    continue
                seen.add(url)
                status = check_ssrf(url, allowlist)
                if status == 2:
                    print(
                        f"[U43/T2.9 SSRF guard] BLOCKED: {url} resolves to private/loopback/link-local.",
                        file=sys.stderr,
                    )
                    _log_ssrf_block(url, "private_or_internal_host", session_id)
                    sys.exit(2)
                # CVE-2026-AHD-008: DNS pinning — resolve + verify rebinding
                pin_status, reason = _pin_and_verify_url(url)
                if pin_status == 2:
                    print(
                        f"[CVE-2026-AHD-008 SSRF DNS pinning] BLOCKED: {url} ({reason}).",
                        file=sys.stderr,
                    )
                    _log_ssrf_block(url, reason, session_id)
                    sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        _gate_error("ssrf", e)


def _check_encoding_bypass_gate(data: dict) -> None:
    """T2.10 + CVE-2026-AHD-007: Phát hiện encoding bypass trong lệnh shell.

    CVE-2026-AHD-007 fix — detection order:
    1. Chạy detect_encoding_bypass TRÊN normalize_command() trước (payload
       decode-revealed như UTF-7 ẩn trong \\xNN bị lộ sau khi decode).
    2. Chạy tiếp trên command raw (escape gốc vẫn bị flag).
    3. analyze_shell_structure() bằng shlex: unbalanced quotes / quote
       breakout / control chars.
    4. HLK sanitizer patterns (redact_patterns) quét secret trong command.

    Block (exit 2) nếu BẤT KỲ detection nào có finding.
    """
    # Đọc helper động từ module entry (hỗ trợ monkeypatch test trên pre_tool_use.*)
    # Dùng globals()[name] làm default để tránh UnboundLocalError (tên local trùng).
    detect_encoding_bypass = getattr(_entry_mod(), "detect_encoding_bypass", globals()["detect_encoding_bypass"])
    analyze_shell_structure = getattr(_entry_mod(), "analyze_shell_structure", globals()["analyze_shell_structure"])
    normalize_command = getattr(_entry_mod(), "normalize_command", globals()["normalize_command"])
    detect_hlk_secret = getattr(_entry_mod(), "detect_hlk_secret", globals()["detect_hlk_secret"])
    try:
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
            return

        command = tool_input.get("command", "")
        if not command:
            return

        # CVE-2026-AHD-007: ưu tiên phát hiện trên command ĐÃ normalize
        normalized = normalize_command(command)
        findings = detect_encoding_bypass(normalized)
        if not findings:
            findings = detect_encoding_bypass(command)

        # Phân tích cấu trúc shell (shlex)
        findings += analyze_shell_structure(command)

        # HLK sanitizer patterns — secret trong command
        hlk_hits = detect_hlk_secret(command)
        if findings or hlk_hits:
            detail = ", ".join(findings) if findings else ""
            if hlk_hits:
                detail = f"{detail}; hlk_secret({len(hlk_hits)} pattern)" if detail else f"hlk_secret({len(hlk_hits)} pattern)"
            print(
                f"[T2.10 Encoding bypass] BLOCKED: detected {detail}",
                file=sys.stderr,
            )
            sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        _gate_error("encoding_bypass", e)


def _check_reflection_gate(data: dict) -> None:
    """T4.9: Reflection gate — đánh giá action trước khi thực hiện.

    Phát hiện action destructive (delete, force_push, drop, reset_hard) qua
    reflection_gate.check_reflection. Nếu block -> exit 2 + yêu cầu human confirm.
    Không thực hiện destructive op — chỉ cảnh báo/block.
    """
    # Đọc _check_reflection động từ module entry (hỗ trợ monkeypatch test).
    _check_reflection = getattr(_entry_mod(), "_check_reflection", globals()["_check_reflection"])
    if _check_reflection is None:
        return
    try:
        tool_input = data.get("tool_input", {}) or {}
        # Xây action input từ tool_input: category suy ra từ tool_name + command pattern
        tool_name = data.get("tool_name", "")
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

        # Chỉ áp dụng cho Bash/shell (nơi có thể có destructive op)
        if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
            return
        if not command:
            return

        # Suy ra category từ command pattern (dùng normalized command để phát hiện đúng cờ).
        category = "read"
        destructive = False
        cmd_lower = normalize_command(command).lower()
        # Chỉ coi là delete nguy hiểm khi rm có cả -r và -f hoặc các dạng tương đương.
        if "rm -rf" in cmd_lower or "rm -fr" in cmd_lower or "del /f" in cmd_lower or "rmdir" in cmd_lower:
            category = "delete"
            destructive = True
        elif "git push --force" in cmd_lower or "git push -f" in cmd_lower:
            category = "force_push"
            destructive = True
        elif "drop table" in cmd_lower or "drop database" in cmd_lower or "drop schema" in cmd_lower:
            category = "drop"
            destructive = True
        elif "delete from" in cmd_lower or "truncate table" in cmd_lower:
            category = "delete"
            destructive = True
        elif "shred" in cmd_lower or "format " in cmd_lower:
            category = "delete"
            destructive = True
        elif "git reset --hard" in cmd_lower:
            category = "reset_hard"
            destructive = True
        elif command.strip().startswith(("curl", "wget")):
            category = "external_call"
        elif command.strip().startswith(("write", "edit")) or " > " in command or " >> " in command:
            category = "write"
        else:
            # Không phải action cần reflection -> skip
            return

        action_input = {
            "id": f"pre_tool_{tool_name}",
            "category": category,
            "target": command[:512],
            "args": {},
            "destructive": destructive,
        }
        # CVE-2026-AHD-014: verdict theo schema chuẩn + input đã sanitize
        try:
            from reflection_gate import verdict_to_dict, sanitize_action_input
            action_input = sanitize_action_input(action_input)
        except (ImportError, ModuleNotFoundError):
            pass
        verdict = _check_reflection(action_input)
        if verdict is None:
            return
        if verdict.block:
            print(
                f"[T4.9 Reflection gate] BLOCKED: {verdict.reason}",
                file=sys.stderr,
            )
            if verdict.human_confirm_required:
                print(
                    "[T4.9 Reflection gate] Human confirm required before executing.",
                    file=sys.stderr,
                )
            sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        _gate_error("reflection", e)


def _check_risk_contract(tool_name: str, tool_input: dict) -> None:
    """U28: Warn on critical file modifications per risk_contract.json.

    Non-blocking — only logs warning to stderr. Does not deny the tool call.
    """
    write_tools = {"Write", "write", "Edit", "edit", "notebook_edit", "NotebookEdit"}
    if tool_name not in write_tools:
        return

    file_path = ""
    for key in ("file_path", "path", "notebook_path", "file"):
        if key in tool_input:
            file_path = tool_input[key]
            break
    if not file_path:
        return

    try:
        root = ahd_session.get_repo_root()
        contract_path = root / ".devin" / "risk_contract.json"
        if not contract_path.exists():
            return

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        critical_files = contract.get("critical_files", {})

        # Normalize path for matching
        norm_path = str(file_path).replace("\\", "/")
        for pattern, rules in critical_files.items():
            norm_pattern = pattern.replace("\\", "/")
            if norm_pattern in norm_path or norm_path.endswith(norm_pattern):
                risk = rules.get("risk", "unknown")
                review = rules.get("required_review", "self")
                print(
                    f"[U28 Risk Contract] WARNING: Modifying critical file "
                    f"{file_path} (risk: {risk}, review: {review})",
                    file=sys.stderr,
                )
                return
    except Exception as e:  # noqa: BLE001
        print(f"[pre_tool_use] unexpected exception in _check_risk_contract: {e}", file=sys.stderr)
        # Non-blocking warning-only gate — never denies the tool call.


# --- Workspace layout gate (root markdown/junk prevention) ---
# Các tool write/edit phải tuân theo WORKSPACE_GOVERNANCE.md.
# File mới ở root chỉ được phép nếu nằm trong ALLOWED_ROOT_FILES/PATTERNS.
# Markdown/work report/plan/map phải đặt trong docs/plans/<slug>/ hoặc docs/reports/.
_WRITE_TOOLS = {"write", "edit", "notebook_edit"}


def _check_workspace_layout_gate(data: dict) -> None:
    """Gate: chặn write/edit/notebook_edit tạo file ở root không được phép hoặc junk."""
    if validate_workspace_path is None:
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
    ok, reason = validate_workspace_path(file_path)
    if not ok:
        print(f"[Agent Harness Deploy guard] BLOCKED: {reason}", file=sys.stderr)
        print(f"Target path: {file_path}", file=sys.stderr)
        sys.exit(2)
