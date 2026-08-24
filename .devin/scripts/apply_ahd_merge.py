#!/usr/bin/env python3
"""
apply_ahd_merge.py — 3-way merge logic cho AHD patch.

Chứa: merge_3way.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def merge_3way(local_text: str, base_text: str, remote_text: str, resolve_theirs: bool = False) -> str | None:
    """Chạy git merge-file 3-way, trả nội dung merge hoặc None nếu conflict.
    Nếu resolve_theirs=True, xung đột sẽ được giải quyết theo phía remote (upstream).
    Temp file luôn được cleanup kể cả khi timeout hoặc exception."""
    temp_paths: list[str] = []
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-local") as lf:
            lf.write(local_text)
            temp_paths.append(lf.name)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-base") as bf:
            bf.write(base_text)
            temp_paths.append(bf.name)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix="-remote") as rf:
            rf.write(remote_text)
            temp_paths.append(rf.name)

        cmd = ["git", "merge-file", "-p"]
        if resolve_theirs:
            cmd.append("--theirs")
        cmd.extend(temp_paths)
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if proc.returncode != 0:
            return None
        return proc.stdout
    except subprocess.TimeoutExpired:
        print("[WARN] git merge-file timeout sau 60s")
        return None
    finally:
        for p in temp_paths:
            try:
                Path(p).unlink()
            except OSError:
                pass