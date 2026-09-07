#!/usr/bin/env python3
"""context_projection.py — Context Projection Engine (T3.1, REQ-001).

Mục đích: chuyển một substrate (kho dữ liệu context thô) thành một viewport
(tập hợp top-K chunk liên quan nhất với query) sao cho:
  - Viewport có tối đa K chunk.
  - Tổng token của viewport nằm trong budget_tokens.
  - Substrate gốc không bị thay đổi (read-only).

Giải thuật (đơn giản, không phụ thuộc thư viện ngoài):
  1. Đọc substrate: hỗ trợ (a) thư mục chứa file .txt/.md/.json, (b) file text đơn,
     (c) chuỗi JSON có dạng {"chunks":[...]} hoặc list[chunk].
  2. Chia substrate thành các chunk (mỗi chunk ~512 token, lấy 4 ký tự = 1 token xấp xỉ).
  3. Tính điểm liên quan (relevance) giữa mỗi chunk và query bằng TF (term frequency)
     của các từ trong query xuất hiện trong chunk — không cần embedding model.
  4. Sắp xếp chunk theo điểm giảm dần, lấy top-K, cắt dần cho đến khi tổng token <= budget.
  5. Trả về Viewport (Pydantic model từ data_models).

Hàm chính: project(substrate_path, query, k, budget_tokens) -> Viewport.

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from data_models import Chunk, Viewport

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# Kích thước chunk mặc định (ký tự). ước lượng 4 ký tự ~ 1 token.
DEFAULT_CHUNK_CHARS = 2048
# Ước lượng token: 1 token ~ 4 ký tự.
_CHARS_PER_TOKEN = 4
# Giới hạn K mặc định.
DEFAULT_K = 8


def _estimate_tokens(text: str) -> int:
    """Ước lượng số token của text: 4 ký tự ~ 1 token, tối thiểu 1 nếu không rỗng."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / _CHARS_PER_TOKEN))


def _hash_content(content: str) -> str:
    """Tính hash SHA-256 rút gọn (16 ký tự đầu) cho content — dùng làm chunk.hash."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


def _tokenize(text: str) -> list[str]:
    """Tách text thành list từ thường (lowercase), bỏ dấu câu."""
    return [w for w in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if w]


def _read_substrate(substrate_path: Path) -> str:
    """Đọc substrate từ đường dẫn.

    Hỗ trợ:
      - Thư mục: gộp nội dung tất cả file .txt/.md/.json (theo thứ tự tên).
      - File .json: nếu có key "chunks" (list) hoặc là list → gộp trường content/text.
      - File text thường: đọc trực tiếp.
    """
    if not substrate_path.exists():
        raise FileNotFoundError(f"substrate không tồn tại: {substrate_path}")

    if substrate_path.is_dir():
        parts: list[str] = []
        for child in sorted(substrate_path.rglob("*")):
            if not child.is_file():
                continue
            if child.suffix.lower() not in {".txt", ".md", ".json"}:
                continue
            try:
                parts.append(_read_single_file(child))
            except OSError:
                continue
        return "\n\n".join(parts)

    return _read_single_file(substrate_path)


def _read_single_file(path: Path) -> str:
    """Đọc một file: nếu JSON có cấu trúc chunks thì gộp content, ngược lại trả text."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
        chunks = _extract_chunks_from_json(data)
        if chunks is not None:
            return "\n\n".join(chunks)
    return text


def _extract_chunks_from_json(data: Any) -> list[str] | None:
    """Trích field content/text từ list chunk trong JSON. Trả None nếu không phải."""
    items: list[Any] = []
    if isinstance(data, dict):
        items = data.get("chunks", []) or []
    elif isinstance(data, list):
        items = data
    else:
        return None
    if not items or not isinstance(items, list):
        return None
    out: list[str] = []
    for it in items:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            c = it.get("content") or it.get("text")
            if isinstance(c, str):
                out.append(c)
    return out or None


def _split_chunks(content: str, chunk_chars: int = DEFAULT_CHUNK_CHARS) -> list[Chunk]:
    """Chia content thành các chunk dài ~chunk_chars ký tự (theo ranh giới dòng khi có thể)."""
    if not content:
        return []
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    n = len(content)
    while start < n:
        end = min(start + chunk_chars, n)
        # Cố gắng cắt tại ranh giới dòng gần nhất để không đứt câu giữa chừng.
        if end < n:
            nl = content.rfind("\n", start, end)
            if nl > start + chunk_chars // 2:
                end = nl + 1
        piece = content[start:end]
        tokens = _estimate_tokens(piece)
        chunks.append(
            Chunk(
                id=f"chunk-{idx:04d}",
                content=piece,
                source="substrate",
                tokens=tokens,
                hash=_hash_content(piece),
                embedding=None,
                metadata={"offset_start": start, "offset_end": end},
            )
        )
        start = end
        idx += 1
    return chunks


def _score_chunk(chunk: Chunk, query_terms: list[str]) -> float:
    """Tính điểm liên quan: tổng tần suất xuất hiện các từ query trong chunk.

    Nếu query rỗng → trả 0 cho mọi chunk (giữ thứ tự gốc khi sort ổn định).
    """
    if not query_terms:
        return 0.0
    chunk_terms = _tokenize(chunk.content)
    if not chunk_terms:
        return 0.0
    counts: dict[str, int] = {}
    for t in chunk_terms:
        counts[t] = counts.get(t, 0) + 1
    total = float(len(chunk_terms))
    score = 0.0
    for q in query_terms:
        score += counts.get(q, 0) / total
    return score


def project(
    substrate_path: str | Path,
    query: str,
    k: int = DEFAULT_K,
    budget_tokens: int = 8192,
) -> Viewport:
    """T3.1: Chiếu substrate thành viewport liên quan với query.

    Nhận vào:
        substrate_path — đường dẫn tới substrate (file hoặc thư mục).
        query          — câu truy vấn (để tính relevance).
        k              — số chunk tối đa trong viewport.
        budget_tokens  — giới hạn tổng token của viewport.

    Trả về:
        Viewport (Pydantic) chứa tối đa K chunk, tổng token <= budget_tokens.

    Quy trình:
        1. Đọc substrate (không thay đổi gốc).
        2. Chia thành chunk.
        3. Tính điểm relevance với query.
        4. Sắp xếp giảm dần, lấy top-K.
        5. Cắt dần chunk thấp điểm nhất cho đến khi tổng token <= budget.
    """
    if k <= 0:
        raise ValueError("k phải lớn hơn 0")
    if budget_tokens <= 0:
        raise ValueError("budget_tokens phải lớn hơn 0")
    if not isinstance(query, str):
        raise TypeError("query phải là chuỗi")

    path = Path(substrate_path)
    content = _read_substrate(path)
    chunks = _split_chunks(content)
    query_terms = _tokenize(query)

    # Bước 3+4: tính điểm và sắp xếp giảm dần (ổn định theo id để cùng điểm giữ thứ tự).
    scored = sorted(
        chunks,
        key=lambda c: (-_score_chunk(c, query_terms), c.id),
    )
    top = scored[:k]

    # Bước 5: cắt dần chunk cuối (điểm thấp nhất) cho đến khi tổng token <= budget.
    while top and sum(c.tokens for c in top) > budget_tokens:
        top.pop()

    total_tokens = sum(c.tokens for c in top)
    source_hashes = [c.hash for c in top]

    return Viewport(
        chunks=top,
        tokens=total_tokens,
        source_hashes=source_hashes,
        budget_tokens=budget_tokens,
        query=query,
    )


def _cli() -> int:
    """CLI: project substrate hoặc report baseline metrics."""
    import argparse

    ap = argparse.ArgumentParser(description="Context Projection Engine (T3.1)")
    ap.add_argument("substrate", nargs="?", help="Đường dẫn substrate (file hoặc thư mục)")
    ap.add_argument("--query", default="", help="Query để tính relevance")
    ap.add_argument("--k", type=int, default=DEFAULT_K, help="Số chunk tối đa")
    ap.add_argument("--budget", type=int, default=8192, help="Giới hạn token viewport")
    ap.add_argument("--report", action="store_true", help="In baseline metrics (token counts) cho verification")
    args = ap.parse_args()

    if args.report:
        root = Path(".").resolve()
        # BOOT_PROTOCOL.md: Only these load at BOOT (always-on)
        # All other canon = ON-DEMAND ONLY
        targets = [
            root / "AGENTS.md",
            root / ".devin" / "canon" / "CORE_CANON.md",
            root / ".devin" / "canon" / "REDLINES.md",
            root / ".devin" / "canon" / "BOOT_PROTOCOL.md",
        ]
        import os
        total_chars = 0
        print("  ALWAYS-ON (BOOT):")
        for t in targets:
            if t.exists():
                chars = t.stat().st_size
                total_chars += chars
                print(f"    {t.relative_to(root)}: {chars} chars (~{chars//4} tokens)")
        print(f"  BOOT TOTAL: {total_chars} chars (~{total_chars//4} tokens)")
        
        # On-demand canon (not counted in boot payload)
        ondemand = [
            root / ".devin" / "canon" / "VERIFICATION_PROTOCOL.md",
            root / ".devin" / "canon" / "HARNESS_ENGINEERING.md",
            root / ".devin" / "canon" / "MEMORY_PROTOCOL.md",
            root / ".devin" / "canon" / "LOOP_PROTOCOL.md",
            root / ".devin" / "canon" / "CAVEMAN_PROTOCOL.md",
            root / ".devin" / "canon" / "DAEMON_PROTOCOL.md",
            root / ".devin" / "canon" / "HANDOFF_LETTER.md",
            root / ".devin" / "canon" / "JUDGMENT_RUBRICS.md",
            root / ".devin" / "canon" / "LOOP_GOAL_BASED.md",
            root / ".devin" / "canon" / "LOOP_PROACTIVE.md",
            root / ".devin" / "canon" / "LOOP_TIME_BASED.md",
            root / ".devin" / "canon" / "LOOP_TURN_BASED.md",
        ]
        ondemand_chars = 0
        print("  ON-DEMAND (lazy-load):")
        for t in ondemand:
            if t.exists():
                chars = t.stat().st_size
                ondemand_chars += chars
                print(f"    {t.relative_to(root)}: {chars} chars (~{chars//4} tokens)")
        print(f"  ON-DEMAND TOTAL: {ondemand_chars} chars (~{ondemand_chars//4} tokens)")
        print(f"  GRAND TOTAL: {total_chars + ondemand_chars} chars (~{(total_chars + ondemand_chars)//4} tokens)")
        return 0

    if not args.substrate:
        ap.error("substrate required unless --report")

    vp = project(args.substrate, args.query, k=args.k, budget_tokens=args.budget)
    sys.stdout.write(vp.model_dump_json(by_alias=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
