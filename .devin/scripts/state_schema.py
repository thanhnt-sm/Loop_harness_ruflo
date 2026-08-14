#!/usr/bin/env python3
"""state_schema.py — Schema validation + HMAC integrity cho state router (CVE-2026-AHD-002).

Mục đích:
1. Validate state theo Pydantic model — REJECT unknown fields (fail-closed).
   Trước đây `_normalize_state()` merge bất kỳ dict nào vào DEFAULT_STATE,
   cho phép attacker inject `approved: true`, `all_gates_pass: true`,
   `phase: EXECUTE` để ép FSM chuyển thẳng tới EXECUTE mà không qua approval.

2. HMAC-SHA256 signature cho state transitions:
   - `sign_state()`: ký canonical JSON của state bằng khóa HMAC.
   - `verify_state()`: xác minh chữ ký; state không khớp chữ ký → REJECT.

Khóa HMAC: lấy từ env `AHD_STATE_HMAC_KEY`, nếu không có thì đọc/generate
file `.devin/state/.state_hmac_key` (ngoài git — nằm trong .gitignore).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StrictBool,
    ValidationError,
)


class StateValidationError(ValueError):
    """State không hợp lệ (unknown field / sai type / sai chữ ký)."""


# ---------------------------------------------------------------------------
# Pydantic schema — danh sách field hợp pháp (fail-closed, extra='forbid')
# ---------------------------------------------------------------------------

class StateSchema(BaseModel):
    """Schema chuẩn cho state router.

    extra='forbid': bất kỳ field nào không khai báo ở đây → REJECT.
    Kiểu dữ liệu được kiểm tra nghiêm ngặt (bool không thể là "true" string...).
    """

    model_config = ConfigDict(extra="forbid")

    phase: str = "PLAN"
    step: str = "ANALYZE"
    findings: list[Any] = Field(default_factory=list)
    design: Any = None
    plan: Any = None
    quality_score: float | None = None
    approved: StrictBool = False
    coverage_pct: float | None = None
    drift_detected: StrictBool = False
    error: str | None = None
    # Field bổ sung hợp pháp (các trường router đọc khi định tuyến)
    tasks_dispatched: StrictBool = True
    all_tasks_complete: StrictBool = False
    all_gates_pass: StrictBool = False
    # Field ký hiệu (signature) — quản lý riêng, không phải field Pydantic
    _sig: str | None = PrivateAttr(default=None)


# ---------------------------------------------------------------------------
# Canonical JSON (ổn định cho HMAC)
# ---------------------------------------------------------------------------

def _canonical_json(state: dict) -> bytes:
    """Serialize state thành canonical JSON (sort_keys) để ký/verify."""
    payload = dict(state)
    payload.pop("_sig", None)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------------------
# HMAC key management
# ---------------------------------------------------------------------------

def _state_dir(root: Path | None = None) -> Path:
    """Thư mục lưu khóa HMAC (ngoài git)."""
    if root is None:
        p = Path(__file__).resolve().parent
        root = p.parent.parent
    return root / ".devin" / "state"


def _key_file(root: Path | None = None) -> Path:
    return _state_dir(root) / ".state_hmac_key"


def load_hmac_key(root: Path | None = None) -> bytes | None:
    """Load khóa HMAC từ env hoặc file key. Trả None nếu không cấu hình."""
    env_key = os.environ.get("AHD_STATE_HMAC_KEY", "")
    if env_key:
        return env_key.encode("utf-8")
    kf = _key_file(root)
    try:
        if kf.exists():
            return kf.read_text(encoding="utf-8").strip().encode("utf-8")
    except OSError:
        pass
    return None


def ensure_hmac_key(root: Path | None = None) -> bytes | None:
    """Load hoặc generate khóa HMAC (persist vào .devin/state/.state_hmac_key)."""
    key = load_hmac_key(root)
    if key is not None:
        return key
    try:
        kf = _key_file(root)
        kf.parent.mkdir(parents=True, exist_ok=True)
        new_key = os.urandom(32).hex()
        kf.write_text(new_key + "\n", encoding="utf-8")
        try:  # best-effort: chmod 600
            kf.chmod(0o600)
        except OSError:
            pass
        return new_key.encode("utf-8")
    except OSError:
        return None


def sign_state(state: dict, key: bytes | None = None, root: Path | None = None) -> dict:
    """Ký state bằng HMAC-SHA256. Trả state kèm `_sig`.

    Nếu không có khóa → trả state nguyên (không ký, best-effort).
    """
    if key is None:
        key = load_hmac_key(root)
    if key is None:
        return state
    sig = hmac.new(key, _canonical_json(state), hashlib.sha256).hexdigest()
    out = dict(state)
    out["_sig"] = sig
    return out


def verify_state(state: dict, key: bytes | None = None, root: Path | None = None) -> bool:
    """Xác minh chữ ký HMAC của state.

    Quy tắc (fail closed):
    - Có khóa + state có `_sig` → phải khớp, không khớp → False.
    - Có khóa + state KHÔNG có `_sig` → False (state không được ký = khả nghi).
    - Không có khóa → bỏ qua (không thể verify) → True (chỉ schema gate áp dụng).
    """
    if key is None:
        key = load_hmac_key(root)
    if key is None:
        return True
    sig = state.get("_sig")
    if not sig:
        return False
    expected = hmac.new(key, _canonical_json(state), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


# ---------------------------------------------------------------------------
# Public API — dùng bởi state_router.py
# ---------------------------------------------------------------------------

def validate_state(raw: Any) -> dict:
    """Validate + chuẩn hóa state đầu vào (fail-closed).

    - raw không phải dict → StateValidationError.
    - Unknown field / sai type → StateValidationError (extra='forbid').
    - Sau đó HMAC verify: nếu có khóa cấu hình mà state không khớp → error.
    """
    if not isinstance(raw, dict):
        raise StateValidationError(f"state phải là dict, nhận {type(raw).__name__}")

    # Tách _sig trước khi validate (nó không phải field Pydantic)
    sig = raw.get("_sig")
    payload = {k: v for k, v in raw.items() if k != "_sig"}

    try:
        state = StateSchema.model_validate(payload).model_dump()
    except ValidationError as e:
        raise StateValidationError(f"state schema violation: {e}") from e
    if sig is not None:
        state["_sig"] = sig

    if not verify_state(state):
        raise StateValidationError("state HMAC signature invalid or missing")
    return state


if __name__ == "__main__":
    # CLI smoke test
    raw = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    try:
        out = validate_state(raw)
        print(json.dumps({"valid": True, "state": out}, ensure_ascii=False))
    except StateValidationError as e:
        print(json.dumps({"valid": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)