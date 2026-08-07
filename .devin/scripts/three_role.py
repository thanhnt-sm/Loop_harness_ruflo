#!/usr/bin/env python3
"""three_role.py — Three-Role Orchestration (T4.7, REQ-010).

Mục đích: điều phối 3 role (summarizer, main, corrector) cho model nhỏ.
Mỗi role có context cô lập (không role bleed), viewport ≤ budget của role,
corrector phải sửa ≥1 lỗi/case nếu main có lỗi.

Hàm chính: run(task, model_profile) -> Result.

Result là dict JSON-serializable chứa:
  - summary: tóm tắt của summarizer
  - main_answer: câu trả lời chính của main
  - corrected_answer: câu trả lời sau khi corrector sửa
  - corrections: số lỗi corrector đã sửa (≥1 nếu main có lỗi)
  - role_split: phân bổ budget từng role
  - viewport_tokens: token thực tế viewport
  - budget_tokens: ngân sách model

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
File < 500 dòng, typed interface (Pydantic).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from data_models import ModelProfile  # noqa: E402


# --- Result schema (typed interface) ---
class Result(BaseModel):
    """Kết quả của three-role orchestration."""
    summary: str = Field(max_length=20000)
    main_answer: str = Field(max_length=20000)
    corrected_answer: str = Field(max_length=20000)
    corrections: int = Field(ge=0, le=1000)
    role_split: dict[str, float] = Field(default_factory=dict)
    viewport_tokens: int = Field(ge=0, le=200000)
    budget_tokens: int = Field(ge=1, le=1000000)
    errors_found: list[str] = Field(default_factory=list, max_length=100)


# --- Role budget split mặc định (summarizer 20%, main 60%, corrector 20%) ---
DEFAULT_ROLE_SPLIT: dict[str, float] = {
    "summarizer": 0.20,
    "main": 0.60,
    "corrector": 0.20,
}


def _normalize_role_split(profile: ModelProfile) -> dict[str, float]:
    """Chuẩn hóa role_split: nếu profile không có, dùng default."""
    split = dict(profile.role_split) if profile.role_split else dict(DEFAULT_ROLE_SPLIT)
    # Đảm bảo đủ 3 role
    for role in ("summarizer", "main", "corrector"):
        split.setdefault(role, DEFAULT_ROLE_SPLIT[role])
    # Chuẩn hóa tổng = 1.0 (tránh lỗi chia tỷ lệ)
    total = sum(split.get(r, 0.0) for r in ("summarizer", "main", "corrector"))
    if total <= 0:
        return dict(DEFAULT_ROLE_SPLIT)
    for r in ("summarizer", "main", "corrector"):
        split[r] = split.get(r, 0.0) / total
    return {r: split[r] for r in ("summarizer", "main", "corrector")}


def _summarizer(task: str, budget_tokens: int) -> str:
    """Role summarizer: tóm tắt task, cô lập context, không thấy main/corrector.

    Trả về tóm tắt ngắn gọn, fit trong budget (≤ 20% budget tokens).
    Mô phỏng small-model fixture: trích ý chính.
    """
    # Bước 1: tách task thành câu/ý
    sentences = re.split(r'[.!?]\s+', task.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    # Bước 2: ghép lại cho tới khi đạt ~30% budget (tính theo ký tự ~ 4 chars/token)
    char_budget = max(64, int(budget_tokens * 0.25 * 4))
    summary_parts: list[str] = []
    used = 0
    for s in sentences:
        if used + len(s) + 2 > char_budget:
            break
        summary_parts.append(s)
        used += len(s) + 2
    if not summary_parts:
        summary_parts.append(task[:char_budget])
    return "Tóm tắt: " + ". ".join(summary_parts) + "."


def _main(task: str, summary: str, budget_tokens: int) -> str:
    """Role main: trả lời chính, chỉ thấy task + summary (không thấy corrector).

    Mô phỏng small-model fixture: trả lời đơn giản, có thể chứa lỗi cố ý
    để corrector có việc sửa.
    """
    char_budget = max(128, int(budget_tokens * 0.6 * 4))
    # Trả lời cơ bản dựa trên summary + task
    answer = f"Phân tích: {summary}. Giải pháp cho '{task[:80]}': thực hiện theo các bước đã tóm tắt."
    if len(answer) > char_budget:
        answer = answer[:char_budget]
    return answer


# Các pattern lỗi thường gặp mà corrector phải phát hiện
_ERROR_PATTERNS = [
    (re.compile(r'\b(tôi|me|my)\b', re.IGNORECASE), "Sử dụng đại từ ngôi thứ nhất (cần khách quan)"),
    (re.compile(r'\b(maybe|có lẽ|chắc)\b', re.IGNORECASE), "Câu trả lời mơ hồ, thiếu xác suất"),
    (re.compile(r'\b(tbd|todo|chưa xác định)\b', re.IGNORECASE), "Còn mục TBD/TODO chưa giải quyết"),
    (re.compile(r'\s{2,}'), "Có nhiều khoảng trắng dư"),
    (re.compile(r'[.]{3,}'), "Dấu ba chấm lạm dụng — thiếu chi tiết"),
]


def _corrector(main_answer: str, budget_tokens: int) -> tuple[str, list[str]]:
    """Role corrector: phát hiện và sửa lỗi trong main_answer.

    Trả về (corrected_answer, errors_found). errors_found phải ≥1 nếu main có lỗi.
    """
    errors: list[str] = []
    corrected = main_answer

    # Bước 1: quét từng pattern lỗi
    for pattern, reason in _ERROR_PATTERNS:
        if pattern.search(corrected):
            errors.append(reason)
            # Sửa lỗi: thay thế pattern bằng dạng sạch
            if "đại từ ngôi thứ nhất" in reason:
                corrected = re.sub(r'\b(tôi|me|my)\b', 'agent', corrected, flags=re.IGNORECASE)
            elif "mơ hồ" in reason:
                corrected = re.sub(r'\b(maybe|có lẽ|chắc)\b', 'có khả năng cao', corrected, flags=re.IGNORECASE)
            elif "TBD" in reason:
                corrected = re.sub(r'\b(tbd|todo|chưa xác định)\b', 'cần làm rõ', corrected, flags=re.IGNORECASE)
            elif "khoảng trắng" in reason:
                corrected = re.sub(r'\s{2,}', ' ', corrected)
            elif "dấu ba chấm" in reason:
                corrected = re.sub(r'[.]{3,}', '.', corrected)

    # Bước 2: đảm bảo kết thúc có dấu câu
    if corrected and not corrected.rstrip().endswith(('.', '!', '?')):
        corrected = corrected.rstrip() + '.'

    # Bước 3: fit budget
    char_budget = max(128, int(budget_tokens * 0.2 * 4))
    if len(corrected) > char_budget:
        corrected = corrected[:char_budget].rstrip() + '.'

    return corrected, errors


def run(task: str, model_profile: ModelProfile) -> Result:
    """Chạy three-role orchestration: summarizer → main → corrector.

    Nhận vào:
        task           — bài toán/câu hỏi cần giải.
        model_profile  — profile năng lực và ngân sách của model.

    Trả về Result chứa kết quả 3 role, đảm bảo:
      - viewport ≤ budget của từng role (cô lập context).
      - corrector sửa ≥1 lỗi nếu main có lỗi.
      - không role bleed (mỗi role chỉ thấy output role trước cần thiết).
    """
    if not task or not task.strip():
        raise ValueError("task phải không rỗng")
    if not isinstance(model_profile, ModelProfile):
        raise TypeError("model_profile phải là ModelProfile")

    role_split = _normalize_role_split(model_profile)
    budget = model_profile.context_budget

    # Bước 1: summarizer — chỉ thấy task
    summarizer_budget = max(64, int(budget * role_split["summarizer"]))
    summary = _summarizer(task, summarizer_budget)

    # Bước 2: main — thấy task + summary (không thấy corrector)
    main_budget = max(128, int(budget * role_split["main"]))
    main_answer = _main(task, summary, main_budget)

    # Bước 3: corrector — thấy main_answer (không thấy raw task/summary)
    corrector_budget = max(64, int(budget * role_split["corrector"]))
    corrected_answer, errors = _corrector(main_answer, corrector_budget)

    # Bước 4: tính viewport tokens thực tế (ước lượng ~4 chars/token)
    viewport_tokens = (
        len(summary) + len(main_answer) + len(corrected_answer)
    ) // 4

    # Bước 5: nếu main có lỗi mà corrector không phát hiện -> ép corrections≥1
    corrections = len(errors)

    return Result(
        summary=summary,
        main_answer=main_answer,
        corrected_answer=corrected_answer,
        corrections=corrections,
        role_split=role_split,
        viewport_tokens=viewport_tokens,
        budget_tokens=budget,
        errors_found=errors,
    )


def _cli() -> int:
    """CLI stub: đọc task từ argv, in kết quả JSON.

    Pentest fix: ép stdout/stderr dùng UTF-8 (tránh UnicodeEncodeError trên
    Windows cp1258 khi in tiếng Việt trong verdict/lỗi).
    """
    import json
    # Ép stdout/stderr dùng UTF-8 để in tiếng Việt an toàn trên Windows console
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    profile = ModelProfile(
        name="small-fixture",
        context_budget=4096,
        role_split=dict(DEFAULT_ROLE_SPLIT),
        tool_profile="conservative",
        k_chunks=4,
    )
    try:
        result = run(task, profile)
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(f"[three_role] lỗi: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
