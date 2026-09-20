#!/usr/bin/env python3
"""prompt_sanitizer.py — Sanitize prompt chống prompt injection.

Mục đích: trước khi gửi prompt tới Command Code (CC) provider, strip
control chars, reject prompt injection patterns, truncate ở max length.
Được wire vào `redteam_spawner._run_one_call()`.

Spec: docs/plans/hardening-and-scale.md section 2

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
__all__ = [
    "MAX_PROMPT_LENGTH",
    "is_safe",
    "sanitize",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

MAX_PROMPT_LENGTH = 8000  # CC context window safety

# Patterns indicating prompt injection attempt
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|above)", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|all|above)", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"<\|user\|>", re.IGNORECASE),
    re.compile(r"<\|assistant\|>", re.IGNORECASE),
    re.compile(r"^system\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^assistant\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"###\s*system\s*###", re.IGNORECASE),
    re.compile(r"###\s*instructions?\s*###", re.IGNORECASE),
]

# Control chars to strip (excluding \n, \r, \t which are common)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def is_safe(prompt: str) -> bool:
    """Check nhanh: prompt có chứa injection pattern không? Không modify.

    Returns:
        False nếu prompt là None/empty/non-string, hoặc có injection pattern.
        True nếu sạch.
    """
    if not isinstance(prompt, str):
        return False
    if not prompt.strip():
        return False
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(prompt):
            return False
    return True


def sanitize(prompt: str) -> tuple[str, list[str]]:
    """Sanitize prompt trước khi gửi tới CC provider.

    Returns:
        (cleaned_prompt, warnings). warnings = list of issues found.

    Actions:
    - Strip control chars (giữ \\n, \\r, \\t)
    - Reject (return empty + warning) nếu có injection pattern
    - Truncate ở MAX_PROMPT_LENGTH
    """
    warnings: list[str] = []
    if not isinstance(prompt, str):
        warnings.append("prompt không phải string")
        return "", warnings
    if not prompt.strip():
        warnings.append("prompt rỗng")
        return "", warnings
    # Strip control chars
    cleaned = _CONTROL_CHARS.sub("", prompt)
    if len(cleaned) < len(prompt):
        warnings.append(f"stripped {len(prompt) - len(cleaned)} control chars")
    # Reject injection patterns
    for pattern in _INJECTION_PATTERNS:
        m = pattern.search(cleaned)
        if m:
            warnings.append(f"injection pattern detected: {m.group(0)[:50]!r}")
            return "", warnings
    # Truncate
    if len(cleaned) > MAX_PROMPT_LENGTH:
        warnings.append(f"truncated from {len(cleaned)} to {MAX_PROMPT_LENGTH} chars")
        cleaned = cleaned[:MAX_PROMPT_LENGTH]
    return cleaned, warnings


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: prompt_sanitizer.py <file>")
        _sys.exit(2)
    p = Path(_sys.argv[1])
    if not p.exists():
        print(f"File not found: {p}")
        _sys.exit(2)
    text = p.read_text(encoding="utf-8", errors="ignore")
    cleaned, warnings = sanitize(text)
    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")
    if not cleaned:
        print("REFUSED: prompt is unsafe or empty")
        _sys.exit(1)
    print(f"OK: sanitized prompt ({len(cleaned)} chars)")
    _sys.exit(0)
