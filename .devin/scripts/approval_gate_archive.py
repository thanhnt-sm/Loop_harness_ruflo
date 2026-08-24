#!/usr/bin/env python3
"""approval_gate_archive.py — Archive approved plans (CVE-2026-AHD-010)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from approval_gate_constants import ARTIFACTS_DIR_NAME, HASH_CHUNK_SIZE


def _sha256_chunked(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """SHA-256 theo chunk (CVE-2026-AHD-010): không load toàn bộ file lớn."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _plan_file_hashes(plan_path: Path, root: Path) -> dict:
    """CVE-2026-AHD-010: SHA-256 của từng file được plan tham chiếu.

    Key = đường dẫn tương đối (forward slash) như trong plan. File chưa tồn
    tại lúc approval → ghi null (verify sẽ bỏ qua hash, dùng tồn tại-check).
    """
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    file_paths = set(re.findall(r"`([^`]*[/\\][^`]*)`", text))
    hashes: dict[str, str | None] = {}
    for fp in sorted(file_paths):
        rel = fp.replace("\\", "/").lstrip("/")
        if not rel:
            continue
        candidate = root / rel
        if candidate.exists() and candidate.is_file():
            try:
                hashes[rel] = _sha256_chunked(candidate)
            except OSError:
                hashes[rel] = None
        else:
            hashes[rel] = None
    return hashes


def _archive_approved_plan(root: Path, plan_path: Path, phash: str) -> str | None:
    """CVE-2026-AHD-010: lưu bản copy bất biến vào .devin/artifacts/<plan_hash>/.

    Trả đường dẫn tương đối artifact (hoặc None nếu lỗi — không chặn approval).
    """
    try:
        artifact_dir = root / ARTIFACTS_DIR_NAME / phash
        artifact_dir.mkdir(parents=True, exist_ok=True)
        dest = artifact_dir / plan_path.name
        if not dest.exists():
            dest.write_bytes(plan_path.read_bytes())
        return str(dest.relative_to(root))
    except OSError:
        return None