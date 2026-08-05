#!/usr/bin/env python3
"""nuwa_roi.py — U25: Nuwa ROI measurement.

Tracks Nuwa cognitive verification metrics in session_state and
computes ROI (Return on Investment) for Nuwa-audited tasks vs
standard-audited tasks.

Metrics tracked:
- nuwa_runs: Number of Nuwa verification runs
- nuwa_bugs_caught: Bugs caught by Nuwa that standard review missed
- nuwa_token_cost: Token cost of Nuwa runs
- standard_bugs_caught: Bugs caught by standard review
- standard_token_cost: Token cost of standard review

ROI formula:
- bugs_per_10k_tokens = bugs_caught / (token_cost / 10000)
- nuwa_roi = nuwa_bugs_per_10k / standard_bugs_per_10k
- If nuwa_roi < threshold (default 1.5) → reduce Nuwa to high-stakes only

Usage (inline):
    from nuwa_roi import record_nuwa_run, compute_roi, get_recommendation
    record_nuwa_run(session_id, root, bugs_caught=3, token_cost=5000)
    roi = compute_roi(session_id, root)
    rec = get_recommendation(roi)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import ahd_session
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session


# U25: ROI threshold — if Nuwa ROI below this, reduce to high-stakes only
NUWA_ROI_THRESHOLD = 1.5
# U25: Minimum runs before ROI is meaningful (avoid small sample noise)
MIN_RUNS_FOR_ROI = 5


def record_nuwa_run(
    session_id: str,
    root: Path,
    bugs_caught: int = 0,
    token_cost: int = 0,
) -> None:
    """U25: Record a Nuwa verification run in session_state.

    Args:
        session_id: Session ID
        root: Repo root
        bugs_caught: Bugs caught by Nuwa that standard review missed
        token_cost: Token cost of this Nuwa run
    """
    if not session_id:
        return

    try:
        state = ahd_session.read_session_state(session_id, root)
        nuwa_metrics = state.get("nuwa_metrics", {})

        nuwa_metrics["nuwa_runs"] = nuwa_metrics.get("nuwa_runs", 0) + 1
        nuwa_metrics["nuwa_bugs_caught"] = nuwa_metrics.get("nuwa_bugs_caught", 0) + bugs_caught
        nuwa_metrics["nuwa_token_cost"] = nuwa_metrics.get("nuwa_token_cost", 0) + token_cost
        nuwa_metrics["last_nuwa_run"] = ahd_session.now_utc()

        ahd_session.update_session_state(session_id, {"nuwa_metrics": nuwa_metrics}, root)
    except Exception:
        pass


def record_standard_run(
    session_id: str,
    root: Path,
    bugs_caught: int = 0,
    token_cost: int = 0,
) -> None:
    """U25: Record a standard (non-Nuwa) verification run in session_state.

    Args:
        session_id: Session ID
        root: Repo root
        bugs_caught: Bugs caught by standard review
        token_cost: Token cost of this standard run
    """
    if not session_id:
        return

    try:
        state = ahd_session.read_session_state(session_id, root)
        nuwa_metrics = state.get("nuwa_metrics", {})

        nuwa_metrics["standard_runs"] = nuwa_metrics.get("standard_runs", 0) + 1
        nuwa_metrics["standard_bugs_caught"] = nuwa_metrics.get("standard_bugs_caught", 0) + bugs_caught
        nuwa_metrics["standard_token_cost"] = nuwa_metrics.get("standard_token_cost", 0) + token_cost
        nuwa_metrics["last_standard_run"] = ahd_session.now_utc()

        ahd_session.update_session_state(session_id, {"nuwa_metrics": nuwa_metrics}, root)
    except Exception:
        pass


def compute_roi(session_id: str, root: Path) -> dict[str, Any]:
    """U25: Compute Nuwa ROI from session_state metrics.

    Returns dict with:
        nuwa_bugs_per_10k: Bugs per 10K tokens for Nuwa
        standard_bugs_per_10k: Bugs per 10K tokens for standard
        roi: Nuwa ROI ratio (nuwa / standard)
        recommendation: "continue" | "reduce" | "insufficient_data"
    """
    try:
        state = ahd_session.read_session_state(session_id, root)
        m = state.get("nuwa_metrics", {})
    except Exception:
        m = {}

    nuwa_runs = m.get("nuwa_runs", 0)
    nuwa_bugs = m.get("nuwa_bugs_caught", 0)
    nuwa_tokens = m.get("nuwa_token_cost", 0)

    std_runs = m.get("standard_runs", 0)
    std_bugs = m.get("standard_bugs_caught", 0)
    std_tokens = m.get("standard_token_cost", 0)

    # Compute bugs per 10K tokens
    nuwa_bugs_per_10k = (nuwa_bugs / (nuwa_tokens / 10000)) if nuwa_tokens > 0 else 0.0
    std_bugs_per_10k = (std_bugs / (std_tokens / 10000)) if std_tokens > 0 else 0.0

    # Compute ROI ratio
    roi = (nuwa_bugs_per_10k / std_bugs_per_10k) if std_bugs_per_10k > 0 else 0.0

    # Recommendation
    total_runs = nuwa_runs + std_runs
    if total_runs < MIN_RUNS_FOR_ROI:
        recommendation = "insufficient_data"
    elif roi < NUWA_ROI_THRESHOLD:
        recommendation = "reduce"
    else:
        recommendation = "continue"

    return {
        "nuwa_runs": nuwa_runs,
        "nuwa_bugs_caught": nuwa_bugs,
        "nuwa_token_cost": nuwa_tokens,
        "nuwa_bugs_per_10k": round(nuwa_bugs_per_10k, 4),
        "standard_runs": std_runs,
        "standard_bugs_caught": std_bugs,
        "standard_token_cost": std_tokens,
        "standard_bugs_per_10k": round(std_bugs_per_10k, 4),
        "roi": round(roi, 4),
        "threshold": NUWA_ROI_THRESHOLD,
        "recommendation": recommendation,
    }


def get_recommendation(roi_result: dict[str, Any]) -> str:
    """U25: Get human-readable recommendation from ROI result."""
    rec = roi_result.get("recommendation", "insufficient_data")

    if rec == "insufficient_data":
        total = roi_result.get("nuwa_runs", 0) + roi_result.get("standard_runs", 0)
        return (
            f"Insufficient data: {total} runs (need {MIN_RUNS_FOR_ROI}). "
            f"Continue collecting metrics before adjusting Nuwa usage."
        )
    elif rec == "reduce":
        return (
            f"Nuwa ROI {roi_result['roi']} < threshold {NUWA_ROI_THRESHOLD}. "
            f"Reduce Nuwa to high-stakes tasks only (security, financial, "
            f"production-critical). Use standard review for routine tasks."
        )
    else:
        return (
            f"Nuwa ROI {roi_result['roi']} >= threshold {NUWA_ROI_THRESHOLD}. "
            f"Continue using Nuwa for verification. ROI is positive."
        )


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="U25: Nuwa ROI measurement")
    ap.add_argument("--session", required=True, help="Session ID")
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--record-nuwa", action="store_true", help="Record a Nuwa run")
    ap.add_argument("--record-standard", action="store_true", help="Record a standard run")
    ap.add_argument("--bugs", type=int, default=0, help="Bugs caught")
    ap.add_argument("--tokens", type=int, default=0, help="Token cost")
    ap.add_argument("--report", action="store_true", help="Print ROI report")

    args = ap.parse_args()
    root = Path(args.root).resolve()

    if args.record_nuwa:
        record_nuwa_run(args.session, root, args.bugs, args.tokens)
        print(f"Recorded Nuwa run: {args.bugs} bugs, {args.tokens} tokens")

    if args.record_standard:
        record_standard_run(args.session, root, args.bugs, args.tokens)
        print(f"Recorded standard run: {args.bugs} bugs, {args.tokens} tokens")

    if args.report or not (args.record_nuwa or args.record_standard):
        roi = compute_roi(args.session, root)
        print(json.dumps(roi, indent=2))
        print()
        print(get_recommendation(roi))
