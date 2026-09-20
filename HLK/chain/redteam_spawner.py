#!/usr/bin/env python3
"""redteam_spawner.py — Auto-spawn expert sub-agent khi judge confidence thấp.

Mục đích: khi `llm_as_judge` trả về confidence < threshold, tự động spawn
N sub-agent chuyên gia từ persona pool chấm lại độc lập, aggregate
bằng median + inter-rater agreement. Quyết định cuối cùng theo
agreement_policy trong config.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 10.3

Design notes:
- Spawn ở đây là **conceptual**: trả về RedteamRound spec (list of agent calls)
  chứ không trực tiếp tạo sub-agent. Caller (verify layer) sẽ dùng spec này
  để dispatch vào plan_orchestrator / agent_spawn. Tách I/O để dễ test.
- Inter-rater agreement: fraction of agents agreeing with final verdict.
- Chi phí: 1 round = N sub-agent. Logged cho cost tracking.

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from judge_config import load_judge_config, should_spawn_redteam  # noqa: E402
__all__ = [
    "AgentCall",
    "AggregateResult",
    "RedteamRound",
    "aggregate_verdicts",
    "build_redteam_round",
    "run_redteam_round",
]



Verdict = Literal["PASS", "FAIL", "REVIEW"]


def _run_one_call(call: "AgentCall") -> Verdict:
    """Gọi 1 sub-agent qua CC client, parse verdict.

    MVP: dùng command_code_client.chat() thật; fallback rule-based khi fail.
    Trả về verdict chuẩn hoá (PASS/FAIL/REVIEW).

    Phase 1 hardening: sanitize prompt trước khi gửi (chống prompt injection).
    """
    # Sanitize prompt chống injection (P2 từ adversarial review)
    try:
        from prompt_sanitizer import is_safe, sanitize
        if not is_safe(call.task_prompt):
            import sys as _sys
            print(f"[redteam_spawner] WARNING: refusing to call CC with unsafe prompt (persona={call.persona})", file=_sys.stderr)
            return "REVIEW"
        cleaned_prompt, _warnings = sanitize(call.task_prompt)
        if not cleaned_prompt:
            print(f"[redteam_spawner] WARNING: sanitize() returned empty prompt", file=_sys.stderr)
            return "REVIEW"
        prompt_to_send = cleaned_prompt
    except ImportError:
        prompt_to_send = call.task_prompt

    try:
        from command_code_client import chat as cc_chat
        resp = cc_chat(prompt_to_send, model=call.model)
        content_low = resp.content.lower()
        if "pass" in content_low and "fail" not in content_low:
            return "PASS"
        if "fail" in content_low:
            return "FAIL"
        return "REVIEW"
    except ImportError:
        # command_code_client không có → fallback rule
        low = prompt_to_send.lower()
        if "fail" in low:
            return "FAIL"
        if "pass" in low:
            return "PASS"
        return "REVIEW"


def run_redteam_round(round_spec: "RedteamRound") -> list[Verdict]:
    """Chạy 1 round redteam: gọi song song tất cả calls, trả về list verdict.

    Dùng ThreadPoolExecutor để parallel. Timeout 60s/call qua CC client config.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    verdicts: list[Verdict] = []
    with ThreadPoolExecutor(max_workers=len(round_spec.calls) or 1) as ex:
        futures = {ex.submit(_run_one_call, call): call for call in round_spec.calls}
        for fut in as_completed(futures):
            try:
                verdicts.append(fut.result())
            except Exception:
                verdicts.append("REVIEW")
    return verdicts


@dataclass
class AgentCall:
    """Một sub-agent sẽ được dispatch để chấm lại."""

    persona: str  # vd "persona-saboteur"
    model: str    # "haiku" | "sonnet" | "opus"
    task_prompt: str  # prompt sẽ gửi cho sub-agent
    rationale_required: bool = True  # bắt buộc kèm lý do


@dataclass
class RedteamRound:
    """Một round redteam (1-N sub-agent song song)."""

    trigger: str  # "low_confidence" | "always" | "never"
    primary_confidence: float
    primary_verdict: Verdict
    calls: list[AgentCall] = field(default_factory=list)
    parallel: bool = True
    reason: str = ""  # giải thích tại sao spawn


@dataclass
class AggregateResult:
    """Kết quả aggregate sau khi sub-agent chấm xong."""

    final_verdict: Verdict
    agreement_score: float  # 0..1, fraction agreeing with final
    escalate_human: bool
    block: bool
    individual_verdicts: list[Verdict] = field(default_factory=list)
    aggregation_method: str = "majority"


def build_redteam_round(
    primary_verdict: Verdict,
    primary_confidence: float,
    task: str,
    context: str = "",
) -> RedteamRound | None:
    """Quyết định có spawn redteam không, nếu có thì build spec.

    Trả về None nếu không nên spawn (theo config trigger).
    """
    cfg = load_judge_config()
    if not should_spawn_redteam(primary_confidence):
        return None

    # Pick N personas từ pool (round-robin nếu pool > N)
    pool = cfg.redteam.pool
    n = min(cfg.redteam.personas_per_round, len(pool))
    selected_personas = pool[:n]

    # Pick model cho mỗi agent (ưu tiên model rẻ nhất, override bằng env nếu có)
    # Cross-model requirement: judge phải khác model với builder
    default_model = cfg.unit_rubric or cfg.default or "haiku"

    task_prompt = (
        f"Bạn là expert reviewer. Đánh giá task sau và cho verdict PASS/FAIL/REVIEW "
        f"cùng lý do rõ ràng.\n\n"
        f"## Task\n{task}\n\n"
        f"## Context\n{context or '(none)'}\n\n"
        f"## Primary verdict (để tham khảo)\n"
        f"- Verdict: {primary_verdict}\n- Confidence: {primary_confidence}\n\n"
        f"Cho verdict ĐỘC LẬP, không bị ảnh hưởng bởi primary verdict."
    )

    calls = [
        AgentCall(
            persona=p,
            model=default_model,
            task_prompt=task_prompt,
            rationale_required=True,
        )
        for p in selected_personas
    ]

    reason = (
        f"primary confidence {primary_confidence:.2f} < threshold "
        f"{cfg.redteam.confidence_threshold:.2f}, "
        f"spawning {n} expert(s) for independent review"
    )
    return RedteamRound(
        trigger=cfg.redteam.trigger,
        primary_confidence=primary_confidence,
        primary_verdict=primary_verdict,
        calls=calls,
        parallel=cfg.redteam.parallel,
        reason=reason,
    )


def aggregate_verdicts(
    individual_verdicts: list[Verdict],
    primary_verdict: Verdict,
) -> AggregateResult:
    """Aggregate N sub-agent verdicts theo agreement_policy.

    Quy tắc:
    - unanimous (N/N agree) → override primary
    - majority (≥ ceil(N/2) agree) → escalate human (không auto-merge)
    - no consensus (< majority agree) → block
    """
    cfg = load_judge_config()
    pol = cfg.redteam.agreement_policy

    n = len(individual_verdicts)
    if n == 0:
        return AggregateResult(
            final_verdict=primary_verdict,
            agreement_score=0.0,
            escalate_human=True,
            block=True,
            aggregation_method="no_data",
        )

    # Tìm verdict phổ biến nhất
    counts: dict[Verdict, int] = {"PASS": 0, "FAIL": 0, "REVIEW": 0}
    for v in individual_verdicts:
        counts[v] = counts.get(v, 0) + 1
    majority_verdict = max(counts, key=counts.get)  # type: ignore[arg-type]
    agreement_score = counts[majority_verdict] / n

    unanimous = agreement_score == 1.0
    is_majority = counts[majority_verdict] >= (n + 1) // 2

    if unanimous and pol.unanimous_override:
        return AggregateResult(
            final_verdict=majority_verdict,
            agreement_score=agreement_score,
            escalate_human=False,
            block=False,
            individual_verdicts=individual_verdicts,
            aggregation_method="unanimous_override",
        )
    if is_majority and pol.majority_escalate:
        return AggregateResult(
            final_verdict=majority_verdict,
            agreement_score=agreement_score,
            escalate_human=True,
            block=False,
            individual_verdicts=individual_verdicts,
            aggregation_method="majority_escalate",
        )
    if pol.no_consensus_block:
        return AggregateResult(
            final_verdict="REVIEW",
            agreement_score=agreement_score,
            escalate_human=True,
            block=True,
            individual_verdicts=individual_verdicts,
            aggregation_method="no_consensus_block",
        )
    # Fallback
    return AggregateResult(
        final_verdict=primary_verdict,
        agreement_score=agreement_score,
        escalate_human=True,
        block=True,
        individual_verdicts=individual_verdicts,
        aggregation_method="fallback",
    )


if __name__ == "__main__":
    # Demo: spawn 3 agents, giả lập verdicts, aggregate
    round_spec = build_redteam_round(
        primary_verdict="PASS",
        primary_confidence=0.5,
        task="Demo task: validate BRD has all required fields",
    )
    if round_spec is None:
        print("Redteam NOT triggered (confidence OK)")
    else:
        print(f"Reason: {round_spec.reason}")
        print(f"Calls: {[(c.persona, c.model) for c in round_spec.calls]}")
        # Demo verdicts
        demo_verdicts: list[Verdict] = ["PASS", "PASS", "FAIL"]
        result = aggregate_verdicts(demo_verdicts, round_spec.primary_verdict)
        print(f"Aggregate: {result}")
