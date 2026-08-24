#!/usr/bin/env python3
"""pre_tool_dangerous.py — Dangerous-command patterns + bash workspace-layout gate.

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API: DANGEROUS_PATTERNS, WARN_PATTERNS, _check_bash_workspace_layout_gate.
"""
import re
import sys
from pathlib import Path

# T4 fix: Pre-compile regex patterns at module load (cached at startup)
# để tránh re-compile mỗi lần check — giảm latency, tránh timeout.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from path_zones import (
        validate_workspace_path,
        is_allowed_root_file,
    )
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    validate_workspace_path = None  # type: ignore[assignment]
    is_allowed_root_file = None  # type: ignore[assignment]


# Patterns that are always blocked
# T4 fix: Pre-compile regex patterns at module load (cached at startup)
# để tránh re-compile mỗi lần check — giảm latency, tránh timeout.
_DANGEROUS_PATTERNS_RAW = [
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
    # S-04: Disk partition / LVM / crypto destructive ops (bypass via fdisk/parted)
    (r"\b(fdisk|sfdisk|gdisk|parted|mkpart)\b", "disk partition tool"),
    (r"\b(lvremove|vgremove|pvremove|lvreduce|vgreduce)\b", "LVM destructive op"),
    (r"\b(cryptsetup\s+(luksFormat|luksRemoveKey|erase|remove|reformat))\b", "cryptsetup destructive op"),
    (r"\b(swapoff)\b", "swapoff"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "host power control"),
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
    # SQL destructive ops
    (r"\bDELETE\s+FROM\b", "SQL DELETE FROM — data loss"),
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b", "SQL DROP — schema destruction"),
    (r"\bTRUNCATE\s+TABLE\b", "SQL TRUNCATE — data loss"),
    # File shredding / secure delete
    (r"\bshred\b", "shred — secure file deletion"),
    # Windows format command
    (r"\bformat\s+[a-z]:\b", "Windows format drive"),
]

# T4 fix: Pre-compile tại module load — patterns cached at startup
DANGEROUS_PATTERNS = [
    (re.compile(pat, re.IGNORECASE), reason)
    for pat, reason in _DANGEROUS_PATTERNS_RAW
]

# Patterns that are warned but allowed (exit 0 with stderr note)
WARN_PATTERNS = [
    (r"\bgit\s+push\b(?!.*--force)", "git push (not force)"),
    (r"\bnpm\s+publish\b", "npm publish"),
    (r"\bpip\s+install\b", "pip install"),
]


def _check_bash_workspace_layout_gate(command: str) -> None:
    """Gate: chặn bash tạo file .md/junk trực tiếp ở root (vd. `echo > REPORT.md`)."""
    if validate_workspace_path is None or is_allowed_root_file is None:
        return
    # Chỉ xét bare filename (không chứa /) sau redirection, touch, cp, mv.
    patterns = [
        r"(?:^|[\s;|&])[>]{1,2}\s*[\"']?([A-Za-z0-9_\-\.]+\.[A-Za-z0-9]+)[\"']?(?=[\s;|&]|$)",
        r"(?:^|[\s;|&])touch\s+[\"']?([A-Za-z0-9_\-\.]+\.[A-Za-z0-9]+)[\"']?(?=[\s;|&]|$)",
        r"(?:^|[\s;|&])(?:cp|mv)\s+\S+\s+[\"']?([A-Za-z0-9_\-\.]+\.[A-Za-z0-9]+)[\"']?(?=[\s;|&]|$)",
    ]
    candidates = []
    for pat in patterns:
        for m in re.finditer(pat, command, re.IGNORECASE):
            filename = m.group(1)
            if "/" not in filename and ".\\" not in filename:
                candidates.append(filename)
    for filename in candidates:
        ok, reason = validate_workspace_path(filename)
        if not ok:
            print(f"[Agent Harness Deploy guard] BLOCKED: {reason}", file=sys.stderr)
            print(f"Shell command would create disallowed file: {filename}", file=sys.stderr)
            print(f"Command: {command[:200]}", file=sys.stderr)
            sys.exit(2)
