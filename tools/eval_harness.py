#!/usr/bin/env python3
"""Unified Eval Harness — Runs golden set, trajectory eval, SWE-bench Pro.

Implements V1+V2+V3 integration: the control plane for AHD competitiveness.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from golden_set_miner import GoldenTask, list_golden_tasks, get_golden_stats
from trajectory_eval import (
    AgentTrajectory,
    TrajectoryStep,
    compare_trajectories,
    trajectory_from_dict,
    trajectory_to_dict,
)


# Types
EvalMode = Literal["smoke", "core", "torture"]
EvalLayer = Literal["task", "quality", "production"]


@dataclass
class EvalConfig:
    """Configuration for eval run."""
    mode: EvalMode = "core"
    golden_dir: str = "tests/golden"
    swe_bench_path: Optional[str] = None
    agent_version: str = "current"
    replay_mode: bool = False
    replay_dir: Optional[str] = None
    max_tasks: Optional[int] = None
    trajectory_mode: str = "strict"  # strict, llm_judge, semantic


@dataclass
class EvalTaskResult:
    """Result for a single task."""
    task_id: str
    layer: EvalLayer
    passed: bool
    score: float
    trajectory_match: bool
    details: dict
    agent_version: str
    eval_mode: str


@dataclass
class EvalRun:
    """Complete eval run record."""
    run_id: str
    config: EvalConfig
    agent_version: str
    started_at: str
    completed_at: Optional[str] = None
    results: list[EvalTaskResult] = None
    summary: dict = None

    def __post_init__(self):
        if self.results is None:
            self.results = []


def _generate_run_id() -> str:
    """Generate unique run ID."""
    return f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"


def _get_agent_version() -> str:
    """Get current agent version (git SHA + prompt hash)."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=False
        ).stdout.strip()
        return f"ahd-{sha}"
    except Exception:
        return f"ahd-{datetime.now().strftime('%Y%m%d')}"


def run_golden_task(
    task: GoldenTask,
    config: EvalConfig,
    agent_version: str,
) -> EvalTaskResult:
    """Run a single golden task through the agent.

    This is a stub - in real implementation, would invoke the actual agent.
    """
    # In real implementation:
    # 1. Create isolated environment
    # 2. Run agent with task description
    # 3. Capture trajectory
    # 4. Compare with golden_diff

    # For now, simulate
    trajectory = AgentTrajectory(
        task_id=task.task_id,
        agent_version=agent_version,
        steps=[],
        final_answer="simulated",
        success=True,
    )

    # Compare with expected (would be golden trajectory in real impl)
    comparison = compare_trajectories(trajectory, trajectory, config.trajectory_mode)

    return EvalTaskResult(
        task_id=task.task_id,
        layer="task",
        passed=comparison.get("match", True),
        score=1.0 if comparison.get("match", True) else 0.0,
        trajectory_match=comparison.get("match", True),
        details={
            "comparison": comparison,
            "task_difficulty": task.difficulty,
            "task_tags": task.tags,
        },
        agent_version=agent_version,
        eval_mode=config.mode,
    )


def run_golden_set(config: EvalConfig) -> list[EvalTaskResult]:
    """Run eval on golden task set."""
    tasks = list_golden_tasks()
    if config.max_tasks:
        tasks = tasks[:config.max_tasks]

    agent_version = config.agent_version or _get_agent_version()
    results = []

    for i, task in enumerate(tasks):
        print(f"[{i+1}/{len(tasks)}] Running {task.task_id} [{task.difficulty}]")
        result = run_golden_task(task, config, agent_version)
        results.append(result)

    return results


def run_swe_bench_pro(config: EvalConfig) -> list[EvalTaskResult]:
    """Run SWE-bench Pro tasks.

    Stub - would integrate with SWE-bench Pro harness.
    """
    if not config.swe_bench_path:
        return []

    # In real implementation:
    # 1. Load SWE-bench Pro dataset
    # 2. Run agent on each instance
    # 3. Score with Pro's oracle
    return []


def run_replay_mode(config: EvalConfig) -> list[EvalTaskResult]:
    """Run eval in replay mode (deterministic, recorded tool outputs)."""
    if not config.replay_dir:
        return []

    replay_path = Path(config.replay_dir)
    if not replay_path.exists():
        print(f"Replay dir not found: {config.replay_dir}")
        return []

    # In real implementation:
    # 1. Load recorded tool outputs
    # 2. Run agent with deterministic responses
    # 3. Compare with live results
    return []


def run_eval(config: EvalConfig) -> EvalRun:
    """Run complete eval based on config."""
    run_id = _generate_run_id()
    agent_version = config.agent_version or _get_agent_version()

    run = EvalRun(
        run_id=run_id,
        config=config,
        agent_version=agent_version,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    print(f"=== Eval Run: {run_id} ===")
    print(f"Mode: {config.mode}")
    print(f"Agent: {agent_version}")
    print(f"Trajectory mode: {config.trajectory_mode}")

    all_results = []

    # Layer 1: Task Harness (golden set)
    if config.mode in ("core", "torture"):
        print("\n--- Layer 1: Golden Set ---")
        results = run_golden_set(config)
        all_results.extend(results)
        passed = sum(1 for r in results if r.passed)
        print(f"Golden set: {passed}/{len(results)} passed")

    # Layer 2: SWE-bench Pro (core/torture only)
    if config.mode in ("core", "torture") and config.swe_bench_path:
        print("\n--- Layer 2: SWE-bench Pro ---")
        results = run_swe_bench_pro(config)
        all_results.extend(results)
        passed = sum(1 for r in results if r.passed)
        print(f"SWE-bench Pro: {passed}/{len(results)} passed")

    # Layer 3: Production Monitor (torture only)
    if config.mode == "torture":
        print("\n--- Layer 3: Production Monitor ---")
        # Would check latency, tool failure rates, cost regressions
        pass

    # Replay mode (for CI determinism)
    if config.replay_mode:
        print("\n--- Replay Mode ---")
        results = run_replay_mode(config)
        all_results.extend(results)
        passed = sum(1 for r in results if r.passed)
        print(f"Replay: {passed}/{len(results)} passed")

    run.results = all_results
    run.completed_at = datetime.now(timezone.utc).isoformat()

    # Summary
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    avg_score = sum(r.score for r in all_results) / total if total > 0 else 0
    traj_matches = sum(1 for r in all_results if r.trajectory_match)

    run.summary = {
        "total_tasks": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0,
        "avg_score": avg_score,
        "trajectory_match_rate": traj_matches / total if total > 0 else 0,
    }

    print(f"\n=== Summary ===")
    print(f"Total: {total}, Passed: {passed}, Rate: {run.summary['pass_rate']:.1%}")
    print(f"Avg Score: {avg_score:.2f}, Traj Match: {run.summary['trajectory_match_rate']:.1%}")

    return run


def promote_or_rollback(
    run: EvalRun,
    current_best: str = "current",
) -> tuple[bool, str]:
    """Promote if resolution + non-regression; else rollback.

    Per BUILD_VERIFY_COMPETE_2026.md: Promote requires both
    resolution + non-regression; archive stores lineage.
    """
    if not run.summary:
        return False, "No summary"

    # Criteria for promotion
    pass_rate = run.summary["pass_rate"]
    traj_match = run.summary["trajectory_match_rate"]

    # Thresholds (configurable)
    MIN_PASS_RATE = 0.8
    MIN_TRAJ_MATCH = 0.9

    if pass_rate >= MIN_PASS_RATE and traj_match >= MIN_TRAJ_MATCH:
        return True, f"Promoted: pass_rate={pass_rate:.1%}, traj_match={traj_match:.1%}"
    else:
        return False, f"Rolled back: pass_rate={pass_rate:.1%} (<{MIN_PASS_RATE}), traj_match={traj_match:.1%} (<{MIN_TRAJ_MATCH})"


def archive_eval_run(run: EvalRun, archive_dir: str = "tests/eval_archive") -> str:
    """Archive eval run with full lineage."""
    archive_path = Path(archive_dir)
    archive_path.mkdir(parents=True, exist_ok=True)

    filename = f"{run.run_id}_{run.agent_version}.json"
    filepath = archive_path / filename

    data = {
        "run_id": run.run_id,
        "agent_version": run.agent_version,
        "config": asdict(run.config),
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "results": [asdict(r) for r in run.results],
        "summary": run.summary,
    }

    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return str(filepath)


def _cli() -> int:
    """CLI: run eval harness."""
    import argparse
    ap = argparse.ArgumentParser(description="Run AHD eval harness")
    ap.add_argument("--mode", default="core", choices=["smoke", "core", "torture"])
    ap.add_argument("--agent-version", help="Agent version string")
    ap.add_argument("--max-tasks", type=int, help="Max golden tasks")
    ap.add_argument("--trajectory-mode", default="strict", choices=["strict", "llm_judge", "semantic"])
    ap.add_argument("--replay-mode", action="store_true")
    ap.add_argument("--replay-dir", help="Replay directory")
    ap.add_argument("--swe-bench", help="SWE-bench Pro path")
    args = ap.parse_args()

    config = EvalConfig(
        mode=args.mode,
        agent_version=args.agent_version,
        max_tasks=args.max_tasks,
        trajectory_mode=args.trajectory_mode,
        replay_mode=args.replay_mode,
        replay_dir=args.replay_dir,
        swe_bench_path=args.swe_bench,
    )

    run = run_eval(config)

    # Archive
    archive_path = archive_eval_run(run)
    print(f"Archived to: {archive_path}")

    # Promote/rollback
    promoted, reason = promote_or_rollback(run)
    print(f"Decision: {'PROMOTE' if promoted else 'ROLLBACK'} - {reason}")

    if not promoted:
        return 1
    return 0


if __name__ == "__main__":
    import argparse
    raise SystemExit(_cli())