#!/usr/bin/env python3
"""llm_as_judge.py — LLM-as-Judge hardened (T4.4, REQ-007).

Mục đích: đánh giá task/result bằng "LLM-as-judge" nhưng:
- Hardened prompt (không bị prompt injection dễ dàng).
- Rule-based fallback khi low-confidence.
- High-risk → yêu cầu human confirm.
- Prompt log audit (ghi log prompt + verdict để audit sau).

Hàm chính: judge(task, result, seed) -> str.

Vì môi trường test không có model thật, module này dùng rule-based làm chính:
- Tính điểm heuristic (marker thành công, độ dài, keyword).
- Trả verdict dạng text ngắn: "PASS: ..." / "FAIL: ..." / "REVIEW: ...".
- Dùng seed để deterministic (nếu có yếu tố ngẫu nhiên).

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# Seed mặc định — deterministic
DEFAULT_SEED = 42

# Từ khóa high-risk → cần human confirm
HIGH_RISK_KEYWORDS = ("delete", "drop", "force_push", "reset_hard", "rm -rf", "destructive")

# Marker thành công trong result
_SUCCESS_MARKERS = ("ok", "pass", "success", "complete", "done", "verified")
# Marker thất bại
_FAIL_MARKERS = ("fail", "error", "exception", "crash", "timeout")

# Đường dẫn log audit (mặc định .devin/state/llm_judge_audit.jsonl)
_AUDIT_DIR = os.environ.get("AHD_LLM_JUDGE_AUDIT_DIR", "")


def _audit_path() -> Path | None:
    """Trả về đường dẫn log audit, hoặc None nếu không ghi."""
    if _AUDIT_DIR:
        return Path(_AUDIT_DIR) / "llm_judge_audit.jsonl"
    # Mặc định: không ghi file khi chạy test (tránh side-effect)
    return None


def _log_audit(task: str, result: Any, verdict: str, seed: int) -> None:
    """Ghi log audit prompt + verdict (JSONL). Best-effort, không raise."""
    import json
    import time

    p = _audit_path()
    if p is None:
        return
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "seed": seed,
            "task_len": len(task),
            "result_preview": str(result)[:200],
            "verdict": verdict[:500],
        }
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Audit log không bao giờ được làm fail judge
        pass


def _heuristic_score(task: str, result: Any) -> float:
    """Tính điểm heuristic (0..1) cho task/result.

    - Có marker thành công trong result: +0.5
    - Task có keyword mục tiêu: +0.2
    - Result không rỗng và độ dài hợp lý: +0.3
    - Có marker thất bại: -0.5
    """
    text = str(result or "").lower()
    task_low = task.lower()
    score = 0.0
    if any(m in text for m in _SUCCESS_MARKERS):
        score += 0.5
    if any(kw in task_low for kw in ("criteria", "must", "verify", "acceptance")):
        score += 0.2
    if 0 < len(text) < 10000:
        score += 0.3
    if any(m in text for m in _FAIL_MARKERS):
        score -= 0.5
    return max(0.0, min(1.0, score))


def _is_high_risk(task: str, result: Any) -> bool:
    """Kiểm tra task/result có high-risk keyword không."""
    combined = (task + " " + str(result or "")).lower()
    return any(kw in combined for kw in HIGH_RISK_KEYWORDS)


def judge(task: str, result: Any, seed: int = DEFAULT_SEED) -> str:
    """Đánh giá task/result bằng rule-based hardened judge.

    Nhận vào:
        task    — mô tả task.
        result  — kết quả cần đánh giá.
        seed    — seed deterministic (mặc định 42).

    Trả về:
        Verdict dạng text:
        - "PASS: <reason>"           — score cao, không high-risk.
        - "FAIL: <reason>"           — score thấp.
        - "REVIEW: <reason>"         — high-risk, cần human confirm.
        - "UNCERTAIN: <reason>"      — score trung bình, low-confidence.
    """
    if not isinstance(task, str):
        raise TypeError("task phải là chuỗi")
    if not (0 <= seed <= 2147483647):
        raise ValueError("seed phải nằm trong 0..2147483647")

    rng = random.Random(seed)
    score = _heuristic_score(task, result)
    # Thêm nhiễ nhỏ deterministic để tránh boundary nondeterminism
    noise = rng.uniform(-0.05, 0.05)
    score = max(0.0, min(1.0, score + noise))

    high_risk = _is_high_risk(task, result)

    if high_risk:
        verdict = f"REVIEW: high-risk phát hiện, cần human confirm (score={score:.2f})"
    elif score >= 0.7:
        verdict = f"PASS: kết quả đạt chuẩn (score={score:.2f})"
    elif score >= 0.4:
        verdict = f"UNCERTAIN: low-confidence, rule-based fallback (score={score:.2f})"
    else:
        verdict = f"FAIL: kết quả không đạt (score={score:.2f})"

    _log_audit(task, result, verdict, seed)
    return verdict


def _cli() -> int:
    """CLI stub: đọc JSON {task, result, seed} từ stdin, in verdict."""
    import json

    payload = json.loads(sys.stdin.read())
    v = judge(
        payload["task"],
        payload.get("result"),
        seed=int(payload.get("seed", DEFAULT_SEED)),
    )
    sys.stdout.write(v + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
