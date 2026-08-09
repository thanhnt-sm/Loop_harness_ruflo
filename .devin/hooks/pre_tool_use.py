#!/usr/bin/env python3
"""Pre-tool-use hook — guards against dangerous operations + enforces context compaction.

Called by the AI tool before executing any tool. Receives JSON on stdin:
  {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "session_id": "..."}

Exit codes:
  0 = allow the tool call
  2 = block the tool call (stderr shown to user)
  other non-zero = error (tool decides; usually allow)

Two gates:
  1. Context-oversized gate — if context_oversized flag is set, graduated response:
     - counter < 2: allow + stderr note (compact soon)
     - counter 2-3: allow + stderr warning (compact NOW)
     - counter >= 4: block non-compaction tools (force agent to compact)
     Compaction tools (read, grep, glob, write, edit, notebook_*, todo_write, skill)
     are always allowed so the agent can actually run context-compactor.

  2. Dangerous-command gate — blocks rm -rf, force-push, etc. (Bash/shell only)

This is a safety net, not a replacement for the canon's red lines. The agent
should already know not to do these things; this hook catches it if the agent
doesn't.
"""
import ipaddress
import json
import os
import re
import sys
import threading
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import ahd_session

# T2.4: Import cost_tracker từ .devin/scripts.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from cost_tracker import check_cost_cap
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    check_cost_cap = None  # type: ignore[assignment]

# T4.9: Import reflection_gate từ .devin/scripts.
except Exception as e:
    print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
    check_cost_cap = None  # type: ignore[assignment]

# T4.9: Import reflection_gate từ .devin/scripts.
try:
    from reflection_gate import check_reflection as _check_reflection
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    _check_reflection = None  # type: ignore[assignment]

# U15: Internal timeout — if hook runs longer than this, force-allow (fail open).
# Config timeout is 3s; this is a safety net at 2s (1s margin) to exit before config kills us.
except Exception as e:
    print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
    _check_reflection = None  # type: ignore[assignment]

# U15: Internal timeout — if hook runs longer than this, force-allow (fail open).
# Config timeout is 3s; this is a safety net at 2s (1s margin) to exit before config kills us.
HOOK_TIMEOUT_SECONDS = 2.0

# --- Context-oversized gate config ---
OVERSIZED_NOTE_THRESHOLD = 0   # counter >= this -> note
OVERSIZED_WARN_THRESHOLD = 2   # counter >= this -> warning
OVERSIZED_BLOCK_THRESHOLD = 4  # counter >= this -> block non-compaction tools

# Tools that are always allowed even during compaction block (needed to actually compact)
COMPACTION_SAFE_TOOLS = frozenset({
    "read", "Read", "grep", "Grep", "glob", "Glob", "find_file_by_name",
    "write", "Write", "edit", "Edit",
    "notebook_read", "notebook_edit",
    "todo_write", "TodoWrite",
    "skill", "Skill",
})


def detect_encoding_bypass(text: str) -> list[str]:
    """T2.10: Phát hiện các kỹ thuật encoding bypass trong text.

    Trả về danh sách các loại bypass phát hiện được (rỗng nếu sạch).
    Các loại: utf7, punycode, html_entity, hex_escape, unicode_escape,
    octal_escape, base64_pipe.
    """
    if not text:
        return []
    findings: list[str] = []

    # UTF-7: +AGY- hay +Base64-
    if re.search(r'\+[A-Za-z0-9+/]+-', text):
        findings.append("utf7")

    # Punycode: xn-- prefix
    if re.search(r'\bxn--[a-zA-Z0-9-]+\b', text):
        findings.append("punycode")

    # HTML entities: &#65; hoặc &#x41;
    if re.search(r'&#[xX]?[0-9a-fA-F]+;', text):
        findings.append("html_entity")

    # Hex escapes \xNN
    if re.search(r'\\x[0-9a-fA-F]{2}', text):
        findings.append("hex_escape")

    # Unicode escapes \uNNNN, \UNNNNNNNN
    if re.search(r'\\u[0-9a-fA-F]{4}', text) or re.search(r'\\U[0-9a-fA-F]{8}', text):
        findings.append("unicode_escape")

    # Octal escapes \NNN
    if re.search(r'\\[0-7]{1,3}', text):
        findings.append("octal_escape")

    # Base64 pipe-to-shell (U02, U51 already detect but reinforce here)
    if re.search(r'base64.*[\|<].*(bash|sh|zsh|python|perl)', text, re.IGNORECASE) or \
       re.search(r'base64.*-d.*[\|<]', text, re.IGNORECASE):
        findings.append("base64_pipe")

    return findings


def normalize_command(command: str) -> str:
    """Normalize shell command before pattern matching (U02: fix regex bypass).

    Strips backslash escaping, quotes, and expands simple $(echo X) substitutions.
    Also flags base64-piped-to-shell patterns that can hide destructive commands.

    U51: Expanded encoding bypass protection:
    - Hex escape decode (\\xNN)
    - Octal escape decode (\\NNN)
    - Unicode escape decode (\\uNNNN, \\UNNNNNNNN)
    - Shell variable expansion simulation ($VAR, ${VAR})
    - Broader base64 detection (all shell variants, redirect, heredoc)
    """
    # U51-3. Decode hex escapes \xNN -> char (BEFORE backslash strip)
    normalized = re.sub(
        r'\\x([0-9a-fA-F]{2})',
        lambda m: chr(int(m.group(1), 16)),
        command,
    )

    # U51-4. Decode octal escapes \NNN (1-3 digits) -> char (BEFORE backslash strip)
    normalized = re.sub(
        r'\\([0-7]{1,3})',
        lambda m: chr(int(m.group(1), 8)),
        normalized,
    )

    # U51-5. Decode unicode escapes \uNNNN, \UNNNNNNNN -> char (BEFORE backslash strip)
    normalized = re.sub(
        r'\\U([0-9a-fA-F]{8})',
        lambda m: chr(int(m.group(1), 16)),
        normalized,
    )
    normalized = re.sub(
        r'\\u([0-9a-fA-F]{4})',
        lambda m: chr(int(m.group(1), 16)),
        normalized,
    )

    # 1. Remove backslash escaping (r\m -> rm) — after hex/octal/unicode decode
    normalized = re.sub(r'\\(.)', r'\1', normalized)

    # 2. Remove quote characters (r''m -> rm, r""m -> rm)
    normalized = re.sub(r"['\"]", "", normalized)

    # 6. Expand simple $(echo X) command substitutions
    normalized = re.sub(
        r'\$\(echo\s+(\S+)\)',
        lambda m: m.group(1),
        normalized,
    )

    # 7. Expand backtick `echo X` substitutions
    normalized = re.sub(
        r'`echo\s+(\S+)`',
        lambda m: m.group(1),
        normalized,
    )

    # U51-8. Simulate shell variable expansion — flag any $VAR / ${VAR} usage
    # We can't know the value, so we flag it as EXPANDED_VAR for pattern matching
    normalized = re.sub(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}', 'EXPANDED_VAR', normalized)
    normalized = re.sub(r'\$[A-Za-z_][A-Za-z0-9_]*', 'EXPANDED_VAR', normalized)

    # U51-9. Broader base64 detection — all shell variants, redirects, heredocs
    # Covers: base64 -d | sh, base64 -d|bash, base64<d|bash, <<<$(base64...), etc.
    if re.search(r'base64.*[\|<].*(bash|sh|zsh|python|perl)', normalized, re.IGNORECASE):
        normalized += " BASE64_PIPE_TO_SHELL_DETECTED"
    if re.search(r'base64.*-d.*[\|<]', normalized, re.IGNORECASE):
        normalized += " BASE64_PIPE_TO_SHELL_DETECTED"
    if re.search(r'<<<\$\(base64', normalized, re.IGNORECASE):
        normalized += " BASE64_PIPE_TO_SHELL_DETECTED"

    # Pentest fix: gộp split short flags của rm thành một flag duy nhất theo thứ tự chuẩn.
    # "rm -r -f /" -> "rm -rf /", "rm -f -r /" -> "rm -rf /", "rm -fr /" -> "rm -rf /".
    # Tránh bypass khi -r và -f nằm ở hai flag group riêng (rm -r -f /).
    def _merge_rm_flags(match: "re.Match[str]") -> str:
        # match.group(1) = chuỗi các flag riêng "-r -f -v" ...
        flags = re.findall(r'-([a-zA-Z])', match.group(1))
        unique = []
        for f in flags:
            if f not in unique:
                unique.append(f)
        # Sắp xếp: r trước f (chuẩn -rf), các flag khác giữ nguyên phía sau
        ordered = sorted(unique, key=lambda c: ({'r': 0, 'f': 1}.get(c, 2), c))
        return 'rm -' + ''.join(ordered) + ' '

    normalized = re.sub(
        r'\brm\s+((?:-[a-zA-Z]\s+){2,})',
        _merge_rm_flags,
        normalized,
    )

    return normalized


# Patterns that are always blocked
DANGEROUS_PATTERNS = [
    # rm -rf with broad targets
    # Pentest fix: thêm EXPANDED_VAR (sau khi $HOME được normalize) và
    # chấp nhận cả -fr (f trước r) vì normalize_command đã gộp split flags.
    (r"\brm\s+(-[a-z]*r[a-z]*f|--recursive\s+--force)\s+(/|/\*|~|\$HOME|EXPANDED_VAR|\.\.|\*|\.|\.git|\.git/)", "rm -rf with broad target"),
    # Pentest fix: rm -fr (f trước r, gộp trong một flag) cũng phải block
    (r"\brm\s+-[a-z]*f[a-z]*r[a-z]*\s+(/|/\*|~|\$HOME|EXPANDED_VAR|\.\.|\*|\.|\.git|\.git/)", "rm -fr with broad target"),
    # git push --force / -f to any branch
    (r"\bgit\s+push\s+(--force|-f)\b", "force-push"),
    # git reset --hard to remote
    (r"\bgit\s+reset\s+--hard\b.*\b(origin|upstream)\b", "hard reset to remote"),
    # curl/wget pipe to shell
    (r"\b(curl|wget)\b.*\|\s*(bash|sh|zsh)\b", "pipe-to-shell from URL"),
    # chmod -R 777
    (r"\bchmod\s+-R\s+777\b", "chmod 777 recursive"),
    # dd to disk device
    (r"\bdd\b.*\bof=/dev/(sd|nvme|hd)", "dd to disk device"),
    # mkfs
    (r"\bmkfs\b", "filesystem format"),
    # GitHub token / API key in command
    (r"\b(ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{48}|AKIA[A-Z0-9]{16})\b", "secret in command"),
    # base64 decoded piped to shell (U02: prevent encoding bypass)
    (r"base64\s+-d\s*\|\s*(bash|sh|zsh)", "base64 decoded piped to shell"),
    # BASE64_PIPE_TO_SHELL_DETECTED flag from normalize_command
    (r"BASE64_PIPE_TO_SHELL_DETECTED", "base64 encoded command piped to shell"),
    # U43: Network egress to known-bad domains
    (r"\b(curl|wget)\b.*\b(malicious|evil|attacker|hack|exploit)\.(com|net|org|io)\b", "network egress to suspicious domain"),
    # U43: Exfiltration patterns — curl/wget with data upload
    (r"\b(curl|wget)\b.*\b(--upload-file|-T\s|--data|-d\s|--post-data)\b.*\b(http|ftp)\b", "potential data exfiltration"),
]

# T2.9: SSRF URL extraction regex
URL_RE = re.compile(r'https?://[^\s\'"<>\)\]\}]+', re.IGNORECASE)

# T2.9: Default allowlist for outbound URLs (expandable via env AHD_SSRF_ALLOWLIST)
DEFAULT_SSRF_ALLOWLIST = {"example.com", "api.github.com", "api.openai.com"}


def _ssrf_allowlist() -> set[str]:
    """Trả về tập allowlist từ env hoặc default."""
    env = os.environ.get("AHD_SSRF_ALLOWLIST", "")
    if not env:
        return set(DEFAULT_SSRF_ALLOWLIST)
    return set(item.strip() for item in env.split(",") if item.strip())


def check_ssrf(url: str, allowlist: set[str] | None = None) -> int:
    """T2.9: Kiểm tra URL có dẫn đến SSRF không.

    Trả về:
      0 — URL an toàn hoặc nằm trong allowlist.
      2 — URL trỏ tới private/loopback/link-local -> block.
    """
    if not url:
        return 0

    if allowlist is None:
        allowlist = _ssrf_allowlist()

    try:
        parsed = urllib.parse.urlparse(url)
    except (ValueError, TypeError):
        return 0

    except Exception as e:
        print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
        return 0

    host = (parsed.hostname or "").lower().strip()
    if not host:
        return 0

    # Allowlist: khớp chính xác hoặc subdomain
    for allowed in allowlist:
        allowed = allowed.lower().strip()
        if not allowed:
            continue
        if host == allowed or host.endswith(f".{allowed}"):
            return 0

    # Block localhost / loopback names
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return 2
    if host.endswith(".local") or host.endswith(".localhost"):
        return 2
    if "metadata" in host and ".internal" in host:
        return 2

    # IP literal check
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return 2
    except ValueError:
        pass

    # Optional: DNS resolution to private IP would go here; disabled to keep hook fast.
    return 0


def _extract_urls(text: str) -> list[str]:
    """Trích các URL http/https từ chuỗi."""
    if not text:
        return []
    return URL_RE.findall(text)


def _log_ssrf_block(url: str, reason: str, session_id: str) -> None:
    """T2.9: Ghi OTel-style log khi SSRF bị block."""
    try:
        root = ahd_session.get_repo_root()
        tel_dir = ahd_session.get_config_root(root) / "telemetry"
        tel_dir.mkdir(parents=True, exist_ok=True)
        log_path = tel_dir / "ssrf_blocks.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event.name": "ssrf.block",
            "url": url,
            "reason": reason,
            "session_id": session_id,
        }
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass


# Patterns that are warned but allowed (exit 0 with stderr note)
WARN_PATTERNS = [
    (r"\bgit\s+push\b(?!.*--force)", "git push (not force)"),
    (r"\bnpm\s+publish\b", "npm publish"),
    (r"\bpip\s+install\b", "pip install"),
]


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
    except Exception:
        pass  # don't block on internal errors


def _check_cost_cap_gate(data: dict) -> None:
    """T2.4: Kiểm tra cost cap trước khi gọi tool.

    - Dưới 80%: cho phép.
    - Từ 80% đến dưới 100%: in cảnh báo stderr, vẫn cho phép.
    - Đạt/vượt 100%: block (exit 2), set flag cost_cap_exceeded.
    """
    try:
        session_id = ahd_session.get_session_id(data)
        if not session_id:
            return

        root = ahd_session.get_repo_root()
        state = ahd_session.read_session_state(session_id, root)
        status = check_cost_cap(state)
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
    except Exception:
        pass


def _check_ssrf_gate(data: dict) -> None:
    """T2.9: Kiểm tra SSRF trong command hoặc các trường URL rõ ràng.

    - Trích URL từ command (Bash/Shell) và các trường URL rõ ràng (url, endpoint, host).
    - Bỏ qua content/new_string/old_string của Write/Edit để tránh false positive.
    - URL private/loopback/link-local -> block (exit 2) + ghi OTel log.
    """
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
    except SystemExit:
        raise
    except Exception:
        pass


def _check_encoding_bypass_gate(data: dict) -> None:
    """T2.10: Phát hiện encoding bypass trong lệnh shell.

    Nếu command chứa UTF-7, Punycode, HTML entity, hex/unicode/octal escape,
    hoặc base64 pipe-to-shell, block (exit 2).
    """
    try:
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
            return

        command = tool_input.get("command", "")
        if not command:
            return

        findings = detect_encoding_bypass(command)
        if findings:
            print(
                f"[T2.10 Encoding bypass] BLOCKED: detected {', '.join(findings)}",
                file=sys.stderr,
            )
            sys.exit(2)
    except SystemExit:
        raise
    except Exception:
        pass


def _check_reflection_gate(data: dict) -> None:
    """T4.9: Reflection gate — đánh giá action trước khi thực hiện.

    Phát hiện action destructive (delete, force_push, drop, reset_hard) qua
    reflection_gate.check_reflection. Nếu block -> exit 2 + yêu cầu human confirm.
    Không thực hiện destructive op — chỉ cảnh báo/block.
    """
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
    except Exception:
        pass  # don't block on internal errors


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
    except Exception:
        pass  # non-blocking


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
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
    if check_cost_cap is not None:
        _check_cost_cap_gate(data)

    # Gate 1.5: U28 — Risk contract check for critical file modifications
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    _check_risk_contract(tool_name, tool_input)

    # Gate 1.6: T2.9 — SSRF guard
    _check_ssrf_gate(data)

    # Gate 1.7: T2.10 — Encoding bypass guard
    _check_encoding_bypass_gate(data)

    # Gate 2: dangerous-command check (Bash/shell only)
    # tool_name + tool_input already extracted above (Gate 1.5)

    if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
        sys.exit(0)

    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Normalize before pattern matching (U02: fix regex bypass via shell encoding)
    normalized = normalize_command(command)

    # Check dangerous patterns against BOTH raw and normalized command
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE) or \
           re.search(pattern, normalized, re.IGNORECASE):
            print(f"[Agent Harness Deploy guard] BLOCKED: {reason}", file=sys.stderr)
            print(f"Command: {command[:200]}", file=sys.stderr)
            print(f"Pattern: {pattern}", file=sys.stderr)
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


if __name__ == "__main__":
    # U52: Fail-closed default — block on timeout unless AHD_FAIL_OPEN=1.
    # Previous behavior (U15): fail open. New default: fail closed for security.
    # Set env AHD_FAIL_OPEN=1 to restore old fail-open behavior.
    result = {"code": 0}

    def _run():
        try:
            main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception as e:
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
