#!/usr/bin/env python3
"""secret_scanner.py — Scan text cho secrets (AWS keys, GitHub tokens, etc.).

Mục đích: tránh push secret lên GitHub qua `gh pr create`. Được wire vào
`auto_pr_gh.live_auto_merge()` để scan `pr_diff` trước khi tạo PR.

Spec: docs/plans/fix-p0-and-deferred.md section 4

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
__all__ = [
    "Finding",
    "has_secret",
    "redact",
    "scan",
    "scan_summary",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

SecretType = Literal[
    "aws_access_key",
    "aws_secret_key",
    "github_pat",
    "github_oauth",
    "slack_token",
    "generic_api_key",
    "pem_private_key",
    "stripe_live_key",
]

# 8 patterns theo best practices (vd GitHub secret scanning, trufflehog)
PATTERNS: list[tuple[SecretType, str]] = [
    ("aws_access_key", r"AKIA[0-9A-Z]{16}"),
    ("aws_secret_key", r"(?i)aws[_-]?secret[_-]?(?:access[_-]?)?key[=:\s\"']+([A-Za-z0-9/+=]{40})"),
    ("github_pat", r"ghp_[0-9a-zA-Z]{36}"),
    ("github_oauth", r"gho_[0-9a-zA-Z]{36}"),
    ("slack_token", r"xox[baprs]-[0-9a-zA-Z]{10,}"),
    ("generic_api_key", r"(?i)(api[_-]?key|apikey|secret[_-]?key)[=:\s\"']+([A-Za-z0-9_\-]{16,})"),
    ("pem_private_key", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ("stripe_live_key", r"sk_live_[0-9a-zA-Z]{24}"),
]


@dataclass
class Finding:
    type: SecretType
    line_no: int
    match_preview: str  # 4 ký tự đầu + *** + 4 ký tự cuối


def _mask(match: str) -> str:
    """Mask secret: chỉ show 4 đầu + *** + 4 cuối."""
    if len(match) <= 12:
        return match[:2] + "***" + match[-2:]
    return match[:4] + "***" + match[-4:]


def scan(text: str) -> list[Finding]:
    """Scan text cho tất cả secret patterns. Trả về list Finding (1 per line per type).

    Args:
        text: full content (vd PR diff)
    Returns:
        List Finding sorted by line_no. Empty list = no secret detected.
    """
    findings: list[Finding] = []
    for secret_type, pattern in PATTERNS:
        for m in re.finditer(pattern, text, re.MULTILINE):
            # Tính line_no dựa trên start position
            line_no = text[: m.start()].count("\n") + 1
            match_str = m.group(0)
            findings.append(Finding(
                type=secret_type,
                line_no=line_no,
                match_preview=_mask(match_str),
            ))
    return sorted(findings, key=lambda f: f.line_no)


def has_secret(text: str) -> bool:
    """Check nhanh: text có secret không? Trả về bool."""
    return len(scan(text)) > 0


def scan_summary(text: str) -> str:
    """Trả về summary string cho log/audit."""
    findings = scan(text)
    if not findings:
        return "no secret detected"
    lines = [f"{len(findings)} secret(s) detected:"]
    for f in findings:
        lines.append(f"  - {f.type} at line {f.line_no}: {f.match_preview}")
    return "\n".join(lines)


def redact(text: str) -> str:
    """Replace tất cả secrets bằng [REDACTED:<type>].

    Args:
        text: input text có thể chứa secret
    Returns:
        text với secret bị thay bằng marker
    """
    if not text:
        return text
    result = text
    for secret_type, pattern in PATTERNS:
        # Build marker cho type
        marker = f"[REDACTED:{secret_type}]"
        # Replace match với marker (không giữ secret)
        result = re.sub(pattern, marker, result, flags=re.MULTILINE)
    return result


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: secret_scanner.py <file>")
        _sys.exit(2)
    p = Path(_sys.argv[1])
    if not p.exists():
        print(f"File not found: {p}")
        _sys.exit(2)
    text = p.read_text(encoding="utf-8", errors="ignore")
    findings = scan(text)
    if findings:
        for f in findings:
            print(f"[{f.type}] line {f.line_no}: {f.match_preview}")
        _sys.exit(1)
    else:
        print("OK: no secret detected")
        _sys.exit(0)
