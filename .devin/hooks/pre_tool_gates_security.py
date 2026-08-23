#!/usr/bin/env python3
"""pre_tool_gates_security.py — Security gates cho pre_tool_use hook."""
import sys
from pathlib import Path

import ahd_session
import json

from pre_tool_common import _entry_mod, _gate_error
from pre_tool_secrets import (
    check_ssrf,
    _extract_urls,
    _log_ssrf_block,
    _ssrf_allowlist,
    _pin_and_verify_url,
    detect_hlk_secret,
)
from pre_tool_encoding import (
    detect_encoding_bypass,
    analyze_shell_structure,
    normalize_command,
)
from reflection_gate import check_reflection as _check_reflection

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

