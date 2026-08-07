#!/usr/bin/env python3
"""reward_shaping.py — Reward Shaping (T4.5, REQ-008).

Mục đích: áp dụng reward shaping theo ADOPS/LaRes/ARES:
- Phạt cost vượt budget.
- Phạt security events (reward hack, exploit).
- Bonus chất lượng (hoàn thành đúng).
- Phát hiện reward hack trong trace (detect_hack).

Hàm chính:
- shape(base_score, actions, cost, security_events) -> float
- detect_hack(trace) -> list[Exploit]

Quy ước:
- base_score trong [-100, 100].
- cost > budget → penalty tỷ lệ thuận.
- security_events: list dict {type, severity} → penalty.
- detect_hack: quét trace tìm pattern reward hack (padding, shortcut, metric_gaming).

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from data_models import Exploit  # noqa: E402

# Ngưỡng cost budget mặc định (USD)
DEFAULT_COST_BUDGET = 10.0
# Hệ số penalty cost (mỗi USD vượt budget trừ điểm)
COST_PENALTY_PER_UNIT = 2.0
# Hệ số penalty security event theo severity
_SECURITY_PENALTY = {"info": 0.0, "warn": 5.0, "error": 20.0, "critical": 50.0}
# Bonus chất lượng tối đa
QUALITY_BONUS_MAX = 10.0
# Score giới hạn
SCORE_MIN = -100.0
SCORE_MAX = 100.0

# Pattern reward hack trong trace text
_HACK_PATTERNS: list[tuple[str, str]] = [
    # padding: lặp lại cùng token để kéo dài output mà không thêm giá trị
    # Dùng capturing group để backreference \1 hoạt động
    (r"([.xa\s])\1{50,}", "padding"),
    # shortcut: bỏ qua bước verify / test
    (r"\b(skip|bypass|ignore)\b.*\b(test|verify|check|validation)\b", "shortcut"),
    # metric_gaming: hardcode kết quả để qua metric
    (r"\bhardcoded?\b.*\b(result|output|answer|metric)\b", "metric_gaming"),
    # reward_hack: ghi trực tiếp điểm cao
    (r"\b(set|assign|write)\b.*\b(score|reward)\b.*\b(100|high|pass)\b", "reward_hack"),
]


def shape(
    base_score: float,
    actions: list[dict[str, Any]],
    cost: float,
    security_events: list[dict[str, Any]],
    *,
    cost_budget: float = DEFAULT_COST_BUDGET,
) -> float:
    """Tính shaped score từ base_score + penalty + bonus.

    Nhận vào:
        base_score       — điểm gốc (trước shaping), [-100, 100].
        actions          — danh sách action đã thực hiện (đếm cho bonus).
        cost             — tổng cost (USD).
        security_events  — list dict {type, severity} (vd security violation).
        cost_budget      — ngưỡng cost cho phép.

    Trả về:
        Shaped score trong [-100, 100].
    """
    if not (-100.0 <= base_score <= 100.0):
        raise ValueError("base_score phải nằm trong [-100, 100]")
    if cost < 0:
        raise ValueError("cost phải >= 0")
    if not isinstance(actions, list):
        raise TypeError("actions phải là list")
    if not isinstance(security_events, list):
        raise TypeError("security_events phải là list")

    score = float(base_score)

    # Penalty cost: chỉ phạt phần vượt budget
    if cost > cost_budget:
        score -= (cost - cost_budget) * COST_PENALTY_PER_UNIT

    # Penalty security events
    for ev in security_events:
        if not isinstance(ev, dict):
            continue
        sev = str(ev.get("severity", "warn")).lower()
        score -= _SECURITY_PENALTY.get(sev, _SECURITY_PENALTY["warn"])

    # Bonus chất lượng: mỗi action thành công +1, tối đa QUALITY_BONUS_MAX
    ok_actions = sum(
        1
        for a in actions
        if isinstance(a, dict) and str(a.get("status", "")).lower() == "success"
    )
    score += min(ok_actions, QUALITY_BONUS_MAX)

    # Clamp về [-100, 100]
    return max(SCORE_MIN, min(SCORE_MAX, score))


def detect_hack(trace: list[dict[str, Any]]) -> list[Exploit]:
    """Quét trace tìm pattern reward hack, trả danh sách Exploit.

    Nhận vào:
        trace — list dict, mỗi item có thể có 'text', 'output', 'action'...

    Trả về:
        list[Exploit] với detected=True cho mỗi pattern tìm thấy.
    """
    if not isinstance(trace, list):
        raise TypeError("trace phải là list")

    exploits: list[Exploit] = []
    seen: set[str] = set()

    for idx, item in enumerate(trace):
        if not isinstance(item, dict):
            continue
        # Gom text từ các field phổ biến
        parts = []
        for key in ("text", "output", "action", "content", "command"):
            v = item.get(key)
            if v is not None:
                parts.append(str(v))
        text = "\n".join(parts)
        if not text:
            continue
        low = text.lower()

        for pattern, etype in _HACK_PATTERNS:
            if re.search(pattern, low):
                key = f"{etype}-{idx}"
                if key in seen:
                    continue
                seen.add(key)
                # Penalty theo loại
                penalty_map = {
                    "padding": -5.0,
                    "shortcut": -15.0,
                    "metric_gaming": -25.0,
                    "reward_hack": -50.0,
                }
                exploits.append(
                    Exploit(
                        exploit_type=etype,  # type: ignore[arg-type]
                        description=f"phát hiện {etype} tại trace[{idx}]",
                        detected=True,
                        penalty=penalty_map.get(etype, -10.0),
                        evidence=text[:4000],
                    )
                )
    return exploits


def _cli() -> int:
    """CLI stub: đọc JSON {base_score, actions, cost, security_events} từ stdin.

    Pentest fix: xử lý stdin rỗng/sai JSON (trả 1 thay vì crash).
    """
    import json

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(f"[reward_shaping] lỗi parse JSON stdin: {e}", file=sys.stderr)
        return 1
    if "base_score" not in payload:
        print("[reward_shaping] lỗi: thiếu trường 'base_score' trong payload", file=sys.stderr)
        return 1
    score = shape(
        float(payload["base_score"]),
        payload.get("actions", []),
        float(payload.get("cost", 0.0)),
        payload.get("security_events", []),
        cost_budget=float(payload.get("cost_budget", DEFAULT_COST_BUDGET)),
    )
    sys.stdout.write(f"{score}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
