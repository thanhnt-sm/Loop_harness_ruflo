#!/usr/bin/env python3
"""approval_gate_crypto.py — Ed25519 signature verification (CVE-2026-AHD-006)."""

from __future__ import annotations

import base64
import hashlib
import os
import json
from pathlib import Path
from typing import TYPE_CHECKING

from approval_gate_constants import (
    HLK_CONFIG_PATH,
    REVIEWER_KEYS_ENV,
    CRYPTO_AVAILABLE as _CONST_CRYPTO_AVAILABLE,
)

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
        Ed25519PrivateKey,
    )
    from cryptography.exceptions import InvalidSignature

# CVE-2026-AHD-006: Ed25519 — bắt buộc khi reviewer_keys được cấu hình.
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover - phụ thuộc môi trường
    Ed25519PrivateKey = None  # type: ignore
    Ed25519PublicKey = None  # type: ignore
    InvalidSignature = Exception  # type: ignore
    CRYPTO_AVAILABLE = False


def plan_hash(plan_path: Path) -> str:
    """SHA-256 của nội dung plan/SDD file — được ký bởi reviewer."""
    content = plan_path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def load_reviewer_keys(root: Path) -> list[str]:
    """Load reviewer public keys (base64 Ed25519) từ HLK config.

    Source of truth: HLK/config/hlk.config.json -> security_rules.reviewer_keys.
    Override cho test/ops: env AHD_REVIEWER_KEYS (comma-separated base64).
    """
    env_keys = os.environ.get(REVIEWER_KEYS_ENV, "")
    if env_keys.strip():
        return [k.strip() for k in env_keys.split(",") if k.strip()]
    try:
        cfg_path = root / HLK_CONFIG_PATH
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            keys = cfg.get("security_rules", {}).get("reviewer_keys", []) or []
            return [str(k) for k in keys if k]
    except (OSError, json.JSONDecodeError):
        pass
    return []


def signature_required(root: Path) -> bool:
    """Signature bắt buộc khi có reviewer_keys được cấu hình.

    Nếu HLK config bật approval_signature_required, bắt buộc kể cả khi
    chưa có key (fail closed — không approve thiếu chữ ký).
    """
    if load_reviewer_keys(root):
        return True
    try:
        cfg_path = root / HLK_CONFIG_PATH
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            return bool(cfg.get("security_rules", {}).get("approval_signature_required", False))
    except (OSError, json.JSONDecodeError):
        pass
    return False


def _sig_message(plan_hash_hex: str, reviewer: str, ts: str) -> bytes:
    """Message được ký: plan_hash|reviewer|timestamp (deterministic)."""
    return f"{plan_hash_hex}|{reviewer}|{ts}".encode("utf-8")


def verify_signature(message: bytes, signature_b64: str, reviewer_keys: list[str]) -> bool:
    """Verify Ed25519 signature với bất kỳ key nào trong allowlist.

    Fail closed: không có cryptography / key rỗng / sig rỗng → False.
    """
    if not CRYPTO_AVAILABLE or not signature_b64 or not reviewer_keys:
        return False
    try:
        raw_sig = base64.b64decode(signature_b64)
    except (ValueError, TypeError):
        return False
    for key_b64 in reviewer_keys:
        try:
            raw_key = base64.b64decode(key_b64)
            pub = Ed25519PublicKey.from_public_bytes(raw_key)
            pub.verify(raw_sig, message)
            return True
        except (InvalidSignature, ValueError, TypeError):
            continue
    return False