#!/usr/bin/env python3
"""schema_gate_secrets — chunked secret scan cho schema_gate.

Tách từ schema_gate.py (monolith 824 lines). Giữ nguyên logic CVE-2026-AHD-005:
quét TOÀN BỘ output (chunk 64KB + overlap), two-stage trigger, entropy + JWT.
"""
from __future__ import annotations

import json
import re
from typing import Optional, Tuple

from schema_gate_config import (
    ENTROPY_THRESHOLD,
    KEYWORD_PATTERN_IDX,
    SCAN_CHUNK_SIZE,
    SCAN_OVERLAP,
    SECRET_PATTERNS,
    SLOW_PATTERN_IDXS,
    SLOW_URL_IDXS,
    _ENTROPY_TOKEN_RE,
    _ENTROPY_TRIGGER_RE,
    _KEYWORD_PRE,
    _TRIGGER_RE,
    _UPPER_ONLY_RE,
    _find_jwt,
    _shannon_entropy,
)


def _iter_chunks(text: str) -> list[str]:
    """CVE-2026-AHD-005: Chia text thành các chunk có overlap.

    Chunk 64KB + overlap 1KB ở hai đầu để pattern không bị cắt lệch chunk.
    """
    if len(text) <= SCAN_CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + SCAN_CHUNK_SIZE, n)
        # Thêm overlap trước (trừ chunk đầu) và sau (trừ chunk cuối)
        chunk_start = max(0, start - SCAN_OVERLAP) if start > 0 else 0
        chunk_end = min(n, end + SCAN_OVERLAP) if end < n else n
        chunks.append(text[chunk_start:chunk_end])
        start = end
    return chunks


def _scan_chunk_secrets(chunk: str) -> Optional[Tuple[re.Match, int]]:
    """Stage B: scan patterns trên 1 chunk. Trả (match, index) nếu tìm thấy.

    Thứ tự: patterns nhanh (literal prefix) trước; patterns chậm chỉ chạy
    khi pre-check guard khớp (fail-fast trên chunk vô hại).
    """
    for i, p in enumerate(SECRET_PATTERNS):
        if i in SLOW_PATTERN_IDXS or i in SLOW_URL_IDXS or i in KEYWORD_PATTERN_IDX:
            continue
        m = p.search(chunk)
        if m:
            return m, i
    # Patterns chậm với guard riêng
    if "://" in chunk:
        for i in SLOW_URL_IDXS:
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
    if _KEYWORD_PRE.search(chunk):
        for i in KEYWORD_PATTERN_IDX:
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
    for i in list(SLOW_PATTERN_IDXS):
        pat = SECRET_PATTERNS[i].pattern
        if ("sk-" in chunk or "pk-" in chunk) and ("sk-" in pat or "pk-" in pat):
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
        if "eyJ" in chunk and "eyJ" in pat:
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
    return None


def _gate_secret_scan(tool_output) -> Optional[dict]:
    """Cổng 3: Secret scan — quét TOÀN BỘ output (chunked, không truncate).

    CVE-2026-AHD-005 fix:
    - Bỏ giới hạn SCAN_TRUNCATE_CHARS (trước đây bỏ sót secret ở giữa output
      lớn > 400K chars).
    - Quét từng chunk 64KB + overlap; pattern = HLK config ∪ defaults.
    - Bổ sung entropy-based detection cho định dạng secret chưa biết.
    """
    if tool_output is None:
        return None
    # Chuyển output thành chuỗi để quét
    if isinstance(tool_output, dict):
        text = json.dumps(tool_output, ensure_ascii=False)
    elif isinstance(tool_output, str):
        text = tool_output
    else:
        text = str(tool_output)

    for chunk in _iter_chunks(text):
        # Stage A1: trigger cụ thể → full pattern scan
        # Guard [a-z_:.=] rẻ: chunk toàn uppercase không cần chạy _TRIGGER_RE
        # (chỉ AKIA/BEGIN khớp được → _UPPER_ONLY_RE).
        if re.search(r"[a-z_:.=]", chunk) is not None:
            hit = _scan_chunk_secrets(chunk) if _TRIGGER_RE.search(chunk) is not None else None
        elif _UPPER_ONLY_RE.search(chunk) is not None:
            hit = _scan_chunk_secrets(chunk)
        else:
            hit = None
        if hit is not None:
            match, pattern_idx = hit
            pattern = SECRET_PATTERNS[pattern_idx]
            # Che giá trị secret trước khi báo cáo (không log secret thật)
            masked = match.group(0)[:4] + "***" + match.group(0)[-2:]
            return {
                "reason": f"Secret detected in output (masked): {masked}",
                "details": {"pattern": pattern.pattern, "masked_value": masked},
            }
        # Stage A2: run dài 20+ (khả năng secret lạ) → entropy + jwt
        if _ENTROPY_TRIGGER_RE.search(chunk) is None:
            continue
        # 2) JWT-style token — linear split-based check
        if _find_jwt(chunk):
            return {
                "reason": "JWT token detected in output",
                "details": {"pattern": "jwt", "masked_value": "***"},
            }
        # 3) Entropy-based: định dạng secret chưa biết (finditer linear).
        #    Digit check bằng regex C-level (không dùng any() Python — chậm).
        if re.search(r"\d", chunk) is not None:
            for token_match in _ENTROPY_TOKEN_RE.finditer(chunk):
                token = token_match.group(0)
                # Regex {20,} nên len(token) >= 20 luôn; chỉ cần check digit
                if re.search(r"\d", token) is None:
                    continue
                if _shannon_entropy(token) > ENTROPY_THRESHOLD:
                    masked = token[:4] + "***" + token[-2:]
                    return {
                        "reason": f"High-entropy secret-like token detected (masked): {masked}",
                        "details": {"pattern": "entropy", "masked_value": masked,
                                    "entropy": round(_shannon_entropy(token), 2)},
                    }
    return None
