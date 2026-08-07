#!/usr/bin/env python3
"""cot_synthesis.py — CoT Synthesis + CRV critique (T4.8, REQ-011).

Mục đích: tổng hợp Chain-of-Thought (CoT) cho model nhỏ, đảm bảo token ≤ budget
của model; sau đó critique bằng CRV (Cognitive load / Reasoning Validation) để
đánh giá reasoning_load, coherence và pass/fail.

Hàm chính:
  - synthesize(problem, model_profile) -> CoT
  - critique(cot) -> CRVScore

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
File < 500 dòng, typed interface (Pydantic).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from data_models import CoT, CRVScore, ModelProfile  # noqa: E402


# Ước lượng token: ~4 ký tự/token (xấp xỉ cho text tiếng Anh/Việt)
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Ước lượng số token của text (xấp xỉ 4 ký tự/token)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _split_problem(problem: str) -> list[str]:
    """Tách problem thành các ý/câu thành phần."""
    sentences = re.split(r'[.!?]\s+', problem.strip())
    return [s.strip() for s in sentences if s.strip()]


def _build_steps(problem: str, max_steps: int = 20) -> list[str]:
    """Xây dựng các bước suy luận (reasoning steps) từ problem.

    Mô phỏng small-model fixture: tách problem thành ý, mỗi ý thành 1 bước.
    Nếu problem chỉ có 1 câu, tạo các bước generic (phân tích → giải → kết luận).
    """
    parts = _split_problem(problem)
    steps: list[str] = []

    if len(parts) <= 1:
        # Problem đơn câu -> tạo 3 bước generic
        steps.append(f"Bước 1: Hiểu bài toán — {problem[:80]}")
        steps.append("Bước 2: Xác định dữ liệu đầu vào và ràng buộc")
        steps.append("Bước 3: Áp dụng phương pháp giải phù hợp")
        steps.append("Bước 4: Kiểm tra kết quả và kết luận")
        return steps[:max_steps]

    # Problem nhiều câu -> mỗi câu thành 1 bước phân tích
    for i, part in enumerate(parts, start=1):
        if len(steps) >= max_steps:
            break
        steps.append(f"Bước {i}: Phân tích — {part[:100]}")
    # Thêm bước kết luận
    if len(steps) < max_steps:
        steps.append(f"Bước {len(steps) + 1}: Tổng hợp và kết luận")
    return steps


def _fit_to_budget(steps: list[str], budget_tokens: int) -> list[str]:
    """Cắt bớt steps cho tới khi tổng token ≤ budget.

    Giữ tối đa số bước có thể, ưu tiên bước đầu và bước cuối (kết luận).
    """
    if not steps:
        return []
    total_tokens = sum(_estimate_tokens(s) for s in steps)
    if total_tokens <= budget_tokens:
        return steps

    # Cắt từ giữa: giữ bước đầu + bước cuối, bỏ bước giữa nếu cần
    fitted: list[str] = [steps[0]]
    remaining_budget = budget_tokens - _estimate_tokens(steps[0])
    # Thêm bước cuối nếu còn budget
    if len(steps) > 1:
        last_tokens = _estimate_tokens(steps[-1])
        if remaining_budget > last_tokens:
            fitted.append(steps[-1])
            remaining_budget -= last_tokens
    # Thêm các bước giữa theo thứ tự cho tới khi hết budget
    for s in steps[1:-1]:
        t = _estimate_tokens(s)
        if t > remaining_budget:
            break
        fitted.insert(-1 if len(fitted) > 1 else len(fitted), s)
        remaining_budget -= t
    return fitted


def synthesize(problem: str, model_profile: ModelProfile) -> CoT:
    """Tổng hợp Chain-of-Thought cho model nhỏ.

    Nhận vào:
        problem        — bài toán cần suy luận.
        model_profile  — profile năng lực và ngân sách model.

    Trả về CoT với:
      - steps: các bước suy luận.
      - tokens: tổng token của các bước (≤ context_budget của profile).
      - model_profile: tên model.
    """
    if not problem or not problem.strip():
        raise ValueError("problem phải không rỗng")
    if not isinstance(model_profile, ModelProfile):
        raise TypeError("model_profile phải là ModelProfile")

    budget = model_profile.context_budget
    # Dành ~80% budget cho steps, 20% cho overhead
    steps_budget = int(budget * 0.8)

    raw_steps = _build_steps(problem)
    fitted = _fit_to_budget(raw_steps, steps_budget)

    total_tokens = sum(_estimate_tokens(s) for s in fitted)
    # Đảm bảo total_tokens ≤ budget (an toàn)
    while fitted and total_tokens > budget:
        fitted.pop(len(fitted) // 2)  # bỏ bước giữa
        total_tokens = sum(_estimate_tokens(s) for s in fitted)

    return CoT(
        problem=problem[:4000],
        steps=fitted,
        tokens=total_tokens,
        model_profile=model_profile.name,
    )


def _reasoning_load(steps: list[str]) -> float:
    """Tính reasoning_load (0..1): tỷ lệ bước có nội dung suy luận thực sự.

    Bước có chứa từ chỉ suy luận (phân tích, kết luận, kiểm tra, áp dụng...)
    được tính là bước có tải reasoning.
    """
    if not steps:
        return 0.0
    reasoning_keywords = re.compile(
        r'\b(phân tích|kết luận|kiểm tra|áp dụng|tổng hợp|xác định|hiểu|giải)\b',
        re.IGNORECASE,
    )
    reasoning_count = sum(1 for s in steps if reasoning_keywords.search(s))
    return reasoning_count / len(steps)


def _coherence(steps: list[str]) -> float:
    """Tính coherence (0..1): các bước có thứ tự logic (Bước 1, 2, 3...).

    Tỷ lệ bước có prefix "Bước N:" với N tăng dần.
    """
    if not steps:
        return 0.0
    step_pattern = re.compile(r'Bước\s+(\d+)\s*:', re.IGNORECASE)
    expected = 1
    coherent = 0
    for s in steps:
        m = step_pattern.search(s)
        if m and int(m.group(1)) == expected:
            coherent += 1
            expected += 1
        else:
            # Bước không có số thứ tự nhưng vẫn có nội dung -> vẫn tính mờ
            if step_pattern.search(s):
                coherent += 0.5
    return min(1.0, coherent / len(steps))


def critique(cot: CoT) -> CRVScore:
    """Critique CoT bằng CRV (Cognitive load / Reasoning Validation).

    Nhận vào:
        cot — CoT cần đánh giá.

    Trả về CRVScore với:
      - reasoning_load: tải reasoning (0..1).
      - coherence: tính mạch lạc (0..1).
      - critique: nhận xét dạng text.
      - pass: True nếu reasoning_load ≥ 0.5 và coherence ≥ 0.5.
    """
    if not isinstance(cot, CoT):
        raise TypeError("cot phải là CoT")

    rload = _reasoning_load(cot.steps)
    coh = _coherence(cot.steps)

    # Pass nếu cả reasoning_load và coherence ≥ 0.5
    passed = rload >= 0.5 and coh >= 0.5

    # Xây critique text
    issues: list[str] = []
    if rload < 0.5:
        issues.append("tải reasoning thấp — các bước thiếu từ chỉ suy luận")
    if coh < 0.5:
        issues.append("mạch lạc thấp — các bước thiếu thứ tự logic")
    if not cot.steps:
        issues.append("không có bước suy luận nào")
    if cot.tokens == 0:
        issues.append("CoT rỗng (0 token)")

    critique_text = (
        f"Đánh giá CoT ({len(cot.steps)} bước, {cot.tokens} token): "
        + ("đạt." if passed else "không đạt — " + "; ".join(issues) + ".")
    )

    return CRVScore(
        reasoning_load=rload,
        coherence=coh,
        critique=critique_text,
        pass_=passed,
    )


def _cli() -> int:
    """CLI stub: đọc problem từ argv, in CoT + CRVScore dạng JSON."""
    import json
    problem = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    profile = ModelProfile(
        name="small-fixture",
        context_budget=2048,
        tool_profile="conservative",
        k_chunks=4,
    )
    try:
        cot = synthesize(problem, profile)
        score = critique(cot)
        out = {
            "cot": cot.model_dump(),
            "crv": score.model_dump(by_alias=True),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(f"[cot_synthesis] lỗi: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
