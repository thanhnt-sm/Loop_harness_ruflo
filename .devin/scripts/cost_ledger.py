#!/usr/bin/env python3
"""cost_ledger.py — CVE-2026-AHD-013: append-only cost ledger (JSONL + HMAC).

Mỗi tool call ghi 1 entry bất biến:
  {session_id, tool, cost, cumulative, timestamp, hmac}

- Append-only: luôn mở mode 'a' — không bao giờ ghi đè/truncate.
- HMAC-SHA256 ký mỗi entry (key từ HLK vault, không nằm trong repo).
- Key sources (ưu tiên cao -> thấp):
    1. HLK/config/secrets.env  →  COST_LEDGER_KEY=...
    2. env AHD_COST_LEDGER_KEY
    3. .devin/state/.cost_ledger_key (gitignored)
- Không có key → entry vẫn append nhưng hmac="unsigned" (read sẽ báo).
- cumulative_from_ledger / global_cumulative chỉ tính entry có HMAC hợp lệ
  (hoặc toàn bộ nếu không cấu hình key — best effort).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class LedgerError(RuntimeError):
    pass


def _config_root(root: Path) -> Path:
    """Cùng quy ước ahd_session.get_config_root: source repo -> root/.agents."""
    try:
        import ahd_session
        return ahd_session.get_config_root(root)
    except Exception:
        return root / ".devin"


def _repo_root(root: Path | None = None) -> Path:
    if root is not None:
        return root
    try:
        import ahd_session
        return ahd_session.get_repo_root()
    except Exception:
        return Path.cwd()


def ledger_path(root: Path | None = None) -> Path:
    """Đường dẫn ledger: <config_root>/telemetry/cost_ledger.jsonl."""
    root = _repo_root(root)
    return _config_root(root) / "telemetry" / "cost_ledger.jsonl"


def _load_hmac_key(root: Path) -> bytes | None:
    """HMAC key từ HLK vault (secrets.env) hoặc env/state file."""
    # 1. HLK vault: HLK/config/secrets.env
    try:
        env_file = _repo_root(root) / "HLK" / "config" / "secrets.env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("COST_LEDGER_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val.encode("utf-8")
    except OSError:
        pass
    # 2. Env override
    val = os.environ.get("AHD_COST_LEDGER_KEY", "")
    if val:
        return val.encode("utf-8")
    # 3. State key file (gitignored)
    try:
        key_file = _config_root(_repo_root(root)) / "state" / ".cost_ledger_key"
        if key_file.exists():
            val = key_file.read_text(encoding="utf-8").strip()
            if val:
                return val.encode("utf-8")
    except OSError:
        pass
    return None


def _sign(entry_json: bytes, key: bytes) -> str:
    return hmac.new(key, entry_json, hashlib.sha256).hexdigest()


def _verify(entry: dict, key: bytes) -> bool:
    sig = entry.get("hmac", "")
    if not sig:
        return False
    body = json.dumps({k: v for k, v in entry.items() if k != "hmac"},
                      sort_keys=True, ensure_ascii=False).encode("utf-8")
    expected = _sign(body, key)
    return hmac.compare_digest(sig, expected)


def append_entry(root: Path | None, session_id: str, tool: str, cost: float, cumulative: float) -> dict:
    """Append 1 entry có HMAC vào ledger. Trả entry đã ghi (kèm hmac)."""
    if not session_id:
        raise LedgerError("cost_ledger: no session_id")
    cost = max(0.0, float(cost or 0.0))
    cumulative = max(0.0, float(cumulative or 0.0))

    entry = {
        "session_id": session_id,
        "tool": tool,
        "cost": round(cost, 6),
        "cumulative": round(cumulative, 6),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
    key = _load_hmac_key(root)
    entry["hmac"] = _sign(body, key) if key else "unsigned"

    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_ledger(root: Path | None = None) -> list[dict]:
    """Đọc toàn bộ entries (giữ nguyên thứ tự append)."""
    path = ledger_path(root)
    if not path.exists():
        return []
    entries: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if isinstance(entry, dict):
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return entries


def _verified_entries(root: Path | None, entries: list[dict] | None = None) -> tuple[list[dict], bool]:
    """(entries hợp lệ, có_key). Không có key -> chấp nhận mọi entry (best effort)."""
    if entries is None:
        entries = read_ledger(root)
    key = _load_hmac_key(root)
    if key is None:
        return entries, False
    verified = []
    for entry in entries:
        if _verify(dict(entry), key):
            verified.append(entry)
    return verified, True


def cumulative_from_ledger(root: Path | None, session_id: str) -> float | None:
    """Tổng cost đã verify cho session. Trả None nếu không thể verify (thiếu key)."""
    verified, has_key = _verified_entries(root)
    if not has_key:
        return None
    return round(sum(float(e.get("cost", 0.0)) for e in verified
                     if e.get("session_id") == session_id), 6)


def global_cumulative(root: Path | None = None) -> float | None:
    """Tổng cost đã verify trên MỌI session (org/repo aggregate).

    Trả None nếu không thể verify (thiếu key).
    """
    verified, has_key = _verified_entries(root)
    if not has_key:
        return None
    return round(sum(float(e.get("cost", 0.0)) for e in verified), 6)


def verify_integrity(root: Path | None = None) -> dict:
    """Quét ledger: đếm entry hợp lệ / thiếu HMAC / HMAC sai."""
    entries = read_ledger(root)
    key = _load_hmac_key(root)
    valid = invalid = unsigned = 0
    for entry in entries:
        if not entry.get("hmac") or entry["hmac"] == "unsigned":
            unsigned += 1
        elif key is not None and _verify(dict(entry), key):
            valid += 1
        elif key is not None:
            invalid += 1
        else:
            valid += 1  # không có key — không thể verify, đếm best-effort
    return {
        "total": len(entries),
        "valid": valid,
        "invalid": invalid,
        "unsigned": unsigned,
        "key_configured": key is not None,
        "path": str(ledger_path(root)),
    }


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if mode == "verify":
        print(json.dumps(verify_integrity(), indent=2))
    elif mode == "global":
        print(json.dumps({"global_cumulative": global_cumulative()}, indent=2))
    else:
        print("Usage: cost_ledger.py [verify|global]", file=sys.stderr)
        sys.exit(2)