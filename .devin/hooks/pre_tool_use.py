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
import json
import re
import sys
import threading

import ahd_session

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

    return normalized


# Patterns that are always blocked
DANGEROUS_PATTERNS = [
    # rm -rf with broad targets
    (r"\brm\s+(-[a-z]*r[a-z]*f|--recursive\s+--force)\s+(/|/\*|~|\$HOME|\.\.|\*|\.)", "rm -rf with broad target"),
    # git push --force / -f to main/master
    (r"\bgit\s+push\s+(--force|-f)\b.*\b(main|master)\b", "force-push to main/master"),
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

    # Gate 1.5: U28 — Risk contract check for critical file modifications
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    _check_risk_contract(tool_name, tool_input)

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
        except Exception:
            # U52: fail-closed on unexpected error too (was fail-open)
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
