#!/usr/bin/env python3
"""abc_checklist.py — Agentic Benchmark Checklist (T4.3, REQ-007).

Mục đích: đánh giá một task + result + trace theo 3 trục:
- Task valid   : task có rõ ràng, measurable (đo lường được) không.
- Outcome valid: result có đạt chuẩn acceptance criteria không.
- Process score: chất lượng quá trình thực hiện (0..1).
- Judge verdict: LLM-as-judge deterministic (fixed seed) — gọi llm_as_judge.

Hàm chính: evaluate(task, result, trace) -> ABCReport.

Quy ước:
- task_valid: kiểm tra task có chứa từ khóa mục tiêu + acceptance criteria.
- outcome_valid: result chứa marker thành công (vd 'OK', 'PASS', 'success').
- process_score: tỷ lệ bước trace thành công / tổng bước.
- pass = task_valid AND outcome_valid AND process_score >= 0.6.
- judge_seed cố định (mặc định 42) để deterministic.

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

from data_models import ABCReport  # noqa: E402
from llm_as_judge import judge as llm_judge  # noqa: E402

# Ngưỡng process score tối thiểu để pass
PROCESS_SCORE_MIN = 0.6
DEFAULT_SEED = 42

# Từ khóa chỉ ra task có acceptance criteria rõ ràng
_CRITERIA_KEYWORDS = ("acceptance", "criteria", "must", "should", "pass", "verify")


def _check_task_valid(task: str) -> bool:
    """Task hợp lệ khi có mô tả + ít nhất 1 từ khóa acceptance criteria."""
    if not isinstance(task, str) or len(task.strip()) < 10:
        return False
    low = task.lower()
    return any(kw in low for kw in _CRITERIA_KEYWORDS)


def _check_outcome_valid(result: Any) -> bool:
    """Outcome hợp lệ khi result chứa marker thành công."""
    if result is None:
        return False
    text = str(result).lower()
    markers = ("ok", "pass", "success", "complete", "done", "verified")
    # Pentest fix: dùng word boundary để tránh false positive.
    # "incomplete" chứa "complete" nhưng không phải marker thành công.
    return any(re.search(r"\b" + re.escape(m) + r"\b", text) for m in markers)


def _compute_process_score(trace: list[dict[str, Any]]) -> float:
    """Tính tỷ lệ bước thành công trong trace (0..1).

    Mỗi item trace có thể có key 'status' hoặc 'ok'.
    Trace rỗng -> 0.0.
    """
    if not trace:
        return 0.0
    ok = 0
    for item in trace:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).lower()
        ok_flag = item.get("ok")
        if status == "success" or ok_flag is True or status == "ok":
            ok += 1
    return ok / len(trace)


def evaluate(
    task: str,
    result: Any,
    trace: list[dict[str, Any]],
    *,
    run_id: str = "abc-run",
    seed: int = DEFAULT_SEED,
) -> ABCReport:
    """Đánh giá task/result/trace theo ABC checklist.

    Nhận vào:
        task    — mô tả task (string).
        result  — kết quả (bất kỳ, sẽ str() để kiểm tra marker).
        trace   — danh sách bước thực hiện (list[dict]).
        run_id  — định danh run.
        seed    — seed cho LLM-as-judge (deterministic).

    Trả về:
        ABCReport với task_valid, outcome_valid, process_score, judge_verdict, pass.
    """
    if not isinstance(task, str):
        raise TypeError("task phải là chuỗi")
    if not isinstance(trace, list):
        raise TypeError("trace phải là list")

    task_valid = _check_task_valid(task)
    outcome_valid = _check_outcome_valid(result)
    process_score = _compute_process_score(trace)
    # Clamp về [0, 1]
    process_score = max(0.0, min(1.0, process_score))

    # LLM-as-judge deterministic — gọi module llm_as_judge
    judge_verdict = llm_judge(task, result, seed=seed)

    pass_ = task_valid and outcome_valid and process_score >= PROCESS_SCORE_MIN

    return ABCReport(
        task_valid=task_valid,
        outcome_valid=outcome_valid,
        process_score=process_score,
        judge_verdict=judge_verdict[:4000],
        pass_=pass_,
        judge_seed=seed,
        run_id=run_id[:128],
    )


def _cli() -> int:
    """CLI stub: đọc JSON {task, result, trace} từ stdin, in ABCReport JSON."""
    import json

    payload = json.loads(sys.stdin.read())
    report = evaluate(
        payload["task"],
        payload.get("result"),
        payload.get("trace", []),
        run_id=payload.get("run_id", "abc-run"),
        seed=int(payload.get("seed", DEFAULT_SEED)),
    )
    sys.stdout.write(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
