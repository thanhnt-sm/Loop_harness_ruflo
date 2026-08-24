#!/usr/bin/env python3
"""checkpoint_redact.py — Redact and migrate helpers for checkpoint data.

T2.6: Checkpoint schema + sanitize + redact.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone

from data_models import CheckpointState


def _default_redact_patterns() -> list[str]:
    """Tải patterns redact từ HLK config nếu có, nếu không dùng danh sách mặc định."""
    default_patterns = [
        r"sk-[a-zA-Z0-9]{32,}",
        r"ghp_[a-zA-Z0-9]{36}",
        # Pentest fix: bổ sung các pattern secret còn thiếu (gho_, AIza, Bearer, xox).
        r"gho_[a-zA-Z0-9]{36}",
        r"ghs_[a-zA-Z0-9]{36}",
        r"ghu_[a-zA-Z0-9]{36}",
        r"AKIA[A-Z0-9]{16}",
        r"AIza[A-Za-z0-9_-]{35}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"(?i)Bearer\s+[A-Za-z0-9_-]{20,}",
        r"(?i)password\s*=\s*['\"]?[^'\"\s]+",
        r"(?i)api[_-]?key\s*=\s*['\"]?[^'\"\s]+",
        r"(?i)secret\s*[:=]\s*['\"]?[^'\"\s]+",
        r"(?i)token\s*[:=]\s*['\"]?[^'\"\s]+",
    ]
    try:
        from checkpoint import _repo_root
        hlk_path = _repo_root() / "HLK" / "config" / "hlk.config.json"
        if hlk_path.exists():
            hlk = json.loads(hlk_path.read_text(encoding="utf-8"))
            hlk_patterns = hlk.get("security_rules", {}).get("redact_patterns", [])
            # Pentest fix: merge HLK patterns vào default (union) thay vì thay thế.
            # Tránh trường hợp HLK config thiếu pattern (vd gho_) -> secret leak.
            # Default patterns luôn áp dụng; HLK chỉ bổ sung thêm pattern chuyên biệt.
            merged = list(default_patterns)
            for p in hlk_patterns:
                if p not in merged:
                    merged.append(p)
            return merged
    except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError):
        pass
    return default_patterns


def _redact_snapshot(state: CheckpointState) -> CheckpointState:
    """T2.6: Redact secret khỏi state trước khi lưu.

    Quét đệ quy các string trong state và thay thế pattern secret bằng [REDACTED].
    """
    patterns = _default_redact_patterns()
    compiled = [re.compile(p) for p in patterns]
    replacement = "[REDACTED]"

    def _redact_value(value):
        if isinstance(value, str):
            for pat in compiled:
                value = pat.sub(replacement, value)
            return value
        if isinstance(value, dict):
            return {k: _redact_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_redact_value(item) for item in value]
        return value

    data = state.model_dump(by_alias=True, mode="json")
    redacted = _redact_value(data)
    return CheckpointState.model_validate(redacted)


def migrate(old: dict, target_version: int = 2) -> dict:
    """T2.6: Migrate old checkpoint dict lên target_version.

    Thêm các field mặc định còn thiếu, giữ nguyên dữ liệu cũ.
    """
    if not isinstance(old, dict):
        old = {}
    new = copy.deepcopy(old)
    current = new.get("version", 0)

    if current < 2:
        new.setdefault("run_id", new.get("run_id", "default"))
        new.setdefault("conversation", [])
        new.setdefault("side_effects_ledger", [])
        new.setdefault("run_metadata", {})
        new.setdefault("external_handles", [])
        new.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        new.setdefault("step_id", new.get("step_id", "unknown"))

    new["version"] = target_version
    return new