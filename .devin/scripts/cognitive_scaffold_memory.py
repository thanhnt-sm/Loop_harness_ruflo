#!/usr/bin/env python3
"""cognitive_scaffold_memory.py — Cognitive Scaffold Memory (T4.10, REQ-010).

Mục đích: lưu trữ transcript theo từng role (summarizer/main/corrector) cô lập,
redact HLK secret trước khi ghi, enforce retention 7 ngày (xóa transcript cũ).

Hàm chính:
  - record(role, transcript) -> Path  : ghi transcript của role, trả đường dẫn.
  - recall(run_id) -> list            : đọc lại transcript theo run_id.

Quy tắc:
  - Mỗi role có thư mục riêng (cô lập context, không role bleed).
  - Redact secret (HLK patterns) trước khi ghi ra disk.
  - Retention 7 ngày: file cũ hơn 7 ngày bị xóa khi record/recall chạy.
  - File < 500 dòng, typed interface (Pydantic).

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


# --- Retention config ---
RETENTION_DAYS = 7
RETENTION_SECONDS = RETENTION_DAYS * 86400

# --- Vị trí lưu transcript ---
_SCAFFOLD_DIR = "scaffold_memory"

# --- Role hợp lệ ---
VALID_ROLES = frozenset({"summarizer", "main", "corrector"})


# --- Transcript entry schema ---
class TranscriptEntry(BaseModel):
    """Một bản ghi transcript của role."""
    role: str = Field(max_length=64)
    run_id: str = Field(max_length=128)
    content: str = Field(max_length=20000)
    timestamp: float = Field(ge=0.0)


# --- Redact patterns (HLK secret) ---
_REDACT_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"gho_[a-zA-Z0-9]{36}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"AIza[A-Za-z0-9_-]{35}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)\b(token|password|passwd|api_key|apikey|secret|private_key)\s*[:=]\s*['\"]?[^\s'\"&;|]{8,}"),
]
_REDACT_REPLACEMENT = "[REDACTED]"


def _redact_text(text: str) -> str:
    """Redact secret trong text trước khi ghi ra disk."""
    if not text:
        return text
    for pat in _REDACT_PATTERNS:
        text = pat.sub(_REDACT_REPLACEMENT, text)
    return text


def _repo_root() -> Path:
    """Trả về repo root, ưu tiên ahd_session.get_repo_root()."""
    try:
        import ahd_session
        return ahd_session.get_repo_root()
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
        p = Path(__file__).resolve().parent
        for parent in [p, *p.parents]:
            if (parent / ".devin").is_dir():
                return parent
        return p


def _config_root(root: Path) -> Path:
    """Trả về config root (thường là .devin)."""
    try:
        import ahd_session
        return ahd_session.get_config_root(root)
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
        return root / ".devin"


def _scaffold_root(root: Path | None = None) -> Path:
    """Trả về đường dẫn thư mục scaffold memory."""
    root = root or _repo_root()
    return _config_root(root) / _SCAFFOLD_DIR


def _role_dir(role: str, root: Path | None = None) -> Path:
    """Trả về thư mục transcript của role."""
    if role not in VALID_ROLES:
        raise ValueError(f"role phải là một trong {VALID_ROLES}, nhận '{role}'")
    return _scaffold_root(root) / role


def _run_id() -> str:
    """Lấy run_id từ env hoặc mặc định."""
    return os.environ.get("AHD_RUN_ID", f"run-{int(time.time())}")


def _enforce_retention(root: Path | None = None) -> int:
    """Xóa transcript cũ hơn RETENTION_DAYS. Trả về số file đã xóa."""
    scaffold = _scaffold_root(root)
    if not scaffold.exists():
        return 0
    now = time.time()
    cutoff = now - RETENTION_SECONDS
    deleted = 0
    for f in scaffold.rglob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError:
            pass
    return deleted


def record(
    role: str,
    transcript: str,
    run_id: str | None = None,
    root: Path | None = None,
) -> Path:
    """Ghi transcript của role ra disk (đã redact secret).

    Nhận vào:
        role        — tên role (summarizer/main/corrector).
        transcript  — nội dung transcript cần ghi.
        run_id      — định danh run (mặc định từ env).
        root        — repo root (mặc định tự phát hiện).

    Trả về đường dẫn file transcript đã ghi.

    Side-effect: enforce retention 7 ngày (xóa file cũ).
    """
    if role not in VALID_ROLES:
        raise ValueError(f"role phải là một trong {VALID_ROLES}, nhận '{role}'")
    if not transcript:
        raise ValueError("transcript phải không rỗng")
    if run_id is None:
        run_id = _run_id()

    # Bước 1: enforce retention trước khi ghi (dọn dẹp file cũ)
    _enforce_retention(root)

    # Bước 2: redact secret khỏi transcript
    safe_content = _redact_text(transcript)

    # Bước 3: xây entry và ghi ra file theo role (cô lập)
    entry = TranscriptEntry(
        role=role,
        run_id=run_id,
        content=safe_content,
        timestamp=time.time(),
    )
    role_directory = _role_dir(role, root)
    role_directory.mkdir(parents=True, exist_ok=True)
    # Tên file: <run_id>_<timestamp>.json (tránh collision)
    safe_run = re.sub(r"[^a-zA-Z0-9_-]", "_", run_id)[:64]
    file_path = role_directory / f"{safe_run}_{int(entry.timestamp)}.json"
    file_path.write_text(
        entry.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return file_path


def recall(run_id: str, root: Path | None = None) -> list[dict[str, Any]]:
    """Đọc lại transcript theo run_id (tất cả role).

    Nhận vào:
        run_id — định danh run cần đọc.
        root   — repo root (mặc định tự phát hiện).

    Trả về list dict, mỗi dict có: role, run_id, content, timestamp, path.
    Sắp xếp theo timestamp tăng dần.
    """
    if not run_id:
        raise ValueError("run_id phải không rỗng")

    # Bước 1: enforce retention trước khi đọc
    _enforce_retention(root)

    scaffold = _scaffold_root(root)
    if not scaffold.exists():
        return []

    safe_run = re.sub(r"[^a-zA-Z0-9_-]", "_", run_id)[:64]
    results: list[dict[str, Any]] = []
    for role in VALID_ROLES:
        role_directory = scaffold / role
        if not role_directory.exists():
            continue
        for f in role_directory.glob(f"{safe_run}_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data["path"] = str(f)
                results.append(data)
            except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError):
                continue
    # Sắp xếp theo timestamp
    results.sort(key=lambda x: x.get("timestamp", 0.0))
    return results


def _cli() -> int:
    """CLI stub:
    - record <role> <transcript>: ghi transcript.
    - recall <run_id>: đọc transcript.
    """
    if len(sys.argv) < 2:
        print("Usage: cognitive_scaffold_memory.py [record <role> <text> | recall <run_id>]", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    if cmd == "record":
        if len(sys.argv) < 4:
            print("Usage: record <role> <transcript>", file=sys.stderr)
            return 1
        path = record(sys.argv[2], sys.argv[3])
        print(str(path))
        return 0
    if cmd == "recall":
        if len(sys.argv) < 3:
            print("Usage: recall <run_id>", file=sys.stderr)
            return 1
        entries = recall(sys.argv[2])
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
