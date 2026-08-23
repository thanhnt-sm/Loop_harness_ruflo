#!/usr/bin/env python3
"""loop_memory_state_log.py — Immutable state log (append-only Merkle chain) + Ed25519 signing.

This module handles the Task 3.9 state log functionality:
- Append-only Merkle-chained state log entries
- Ed25519 signing of entries
- Verification of the full chain
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    import ahd_session
except ImportError:  # pragma: no cover
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session

STATE_LOG_NAME = "state_log.jsonl"


def _state_log_path(root: Path) -> Path:
    """Return path to state log file."""
    return ahd_session.get_config_root(root) / "telemetry" / STATE_LOG_NAME


def _telemetry_signing_key(root: Path) -> bytes | None:
    """Key ký telemetry: secrets.env TELEMETRY_SIGN_KEY -> env AHD_TELEMETRY_SIGN_KEY
    -> <config_root>/state/.telemetry_key. Không có key -> None (unsigned)."""
    try:
        secrets_env = Path(__file__).resolve().parent.parent.parent / "HLK" / "config" / "secrets.env"
        if secrets_env.exists():
            for line in secrets_env.read_text(encoding="utf-8").splitlines():
                if line.startswith("TELEMETRY_SIGN_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"')
                    if val:
                        return val.encode("utf-8")
        env_val = os.environ.get("AHD_TELEMETRY_SIGN_KEY", "")
        if env_val:
            return env_val.encode("utf-8")
        key_file = ahd_session.get_config_root(root) / "state" / ".telemetry_key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip().encode("utf-8")
    except OSError:
        pass
    return None


def _sign_entry(entry: dict, key: bytes | None) -> str:
    """Ed25519 sign entry (cryptography lib). Không key -> 'unsigned'."""
    if key is None:
        return "unsigned"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        body = json.dumps({k: v for k, v in entry.items() if k != "sig"},
                          sort_keys=True, ensure_ascii=False).encode("utf-8")
        priv = Ed25519PrivateKey.from_private_bytes(key[:32].ljust(32, b"\0"))
        return priv.sign(body).hex()
    except Exception:
        return "unsigned"


def _verify_entry_sig(entry: dict, key: bytes | None) -> bool:
    """Verify Ed25519 signature of an entry."""
    sig = entry.get("sig", "")
    if not sig or sig == "unsigned":
        return sig == "unsigned"  # unsigned hợp lệ khi không cấu hình key
    if key is None:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        body = json.dumps({k: v for k, v in entry.items() if k != "sig"},
                          sort_keys=True, ensure_ascii=False).encode("utf-8")
        priv = Ed25519PrivateKey.from_private_bytes(key[:32].ljust(32, b"\0"))
        pub = priv.public_key()
        pub.verify(bytes.fromhex(sig), body)
        return True
    except Exception:
        return False


def _chain_hash(prev_hash: str, payload: dict, seq: int) -> str:
    """Compute Merkle chain hash: SHA256(prev_hash | seq | payload)."""
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(f"{prev_hash}|{seq}|".encode() + body).hexdigest()


def append_state_log(root: Path, session_id: str, event: str,
                     payload: dict | None = None, loop_id: str = "") -> dict | None:
    """Append-only Merkle-chained state log entry (Task 3.9).

    Entry: {seq, ts, loop_id, session_id, event, payload, prev_hash, hash, sig}.
    hash = SHA256(prev_hash | seq | payload) — mỗi entry commit toàn bộ lịch sử.
    sig = Ed25519 (nếu key cấu hình). Không bao giờ ghi đè/ghi giữa file.
    """
    try:
        path = _state_log_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        prev_hash = "0" * 64
        seq = 0
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if lines:
                try:
                    last = json.loads(lines[-1])
                    prev_hash = last.get("hash", prev_hash)
                    seq = int(last.get("seq", 0)) + 1
                except (json.JSONDecodeError, TypeError, ValueError):
                    prev_hash = hashlib.sha256(b"corrupt|" + lines[-1].encode()).hexdigest()
                    seq = len(lines)
        entry = {
            "seq": seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "loop_id": loop_id or os.environ.get("AHD_LOOP_ID", ""),
            "session_id": session_id,
            "event": event,
            "payload": payload or {},
        }
        entry["prev_hash"] = prev_hash
        entry["hash"] = _chain_hash(prev_hash, entry["payload"], seq)
        entry["sig"] = _sign_entry(entry, _telemetry_signing_key(root))
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry
    except Exception:
        return None


def verify_state_log(root: Path) -> dict:
    """Verify chuỗi Merkle + chữ ký toàn bộ state log.

    Trả về {total, valid, invalid, unsigned, merkle_ok, key_configured, path}.
    """
    path = _state_log_path(root)
    result = {"total": 0, "valid": 0, "invalid": 0, "unsigned": 0,
              "merkle_ok": True, "key_configured": False, "path": str(path)}
    if not path.exists():
        return result
    key = _telemetry_signing_key(root)
    result["key_configured"] = key is not None
    prev_hash = "0" * 64
    lines = path.read_text(encoding="utf-8").splitlines()
    result["total"] = len(lines)
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            result["invalid"] += 1
            result["merkle_ok"] = False
            continue
        seq = int(entry.get("seq", -1))
        if entry.get("prev_hash", "") != prev_hash:
            result["merkle_ok"] = False
        expected = _chain_hash(prev_hash, entry.get("payload", {}), seq)
        if entry.get("hash", "") != expected:
            result["merkle_ok"] = False
        prev_hash = entry.get("hash", prev_hash)
        if _verify_entry_sig(entry, key):
            if entry.get("sig", "") == "unsigned":
                result["unsigned"] += 1
            else:
                result["valid"] += 1
        else:
            result["invalid"] += 1
    return result