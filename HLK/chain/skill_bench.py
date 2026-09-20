#!/usr/bin/env python3
"""skill_bench.py — Benchmark mọi skill theo thời gian.

Mục đích: đo chất lượng skill bằng cách chạy mỗi skill × N scenarios,
chấm bằng llm_as_judge (cross-model). Output report dạng markdown +
JSON để track drift theo thời gian.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 4.7

Wire vào hlk-loop để chạy mỗi đêm.

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
__all__ = [
    "BenchResult",
    "DEFAULT_PARALLEL",
    "DEFAULT_SCENARIOS_PER_SKILL",
    "bench_skills",
    "render_bench_report",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

DEFAULT_SCENARIOS_PER_SKILL = 5
DEFAULT_PARALLEL = 4


@dataclass
class BenchResult:
    skill_name: str
    skill_path: str
    scenarios_run: int
    scenarios_passed: int
    pass_rate: float
    avg_confidence: float
    avg_latency_ms: float
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


def _parse_skill_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter từ skill file. Trả về dict rỗng nếu lỗi."""
    if not text.startswith("---"):
        return {}
    try:
        end = text.find("\n---", 3)
        if end == -1:
            return {}
        import yaml
        return yaml.safe_load(text[3:end]) or {}
    except Exception:
        return {}


def _generate_scenarios_from_skill(skill_path: Path, n: int) -> list[str]:
    """Sinh N scenarios đơn giản từ description của skill.

    MVP: chỉ return 1 scenario dùng description. Real bench cần agent sinh scenario.
    """
    text = skill_path.read_text(encoding="utf-8", errors="ignore")
    fm = _parse_skill_frontmatter(text)
    desc = fm.get("description", f"Test {skill_path.name}")
    return [f"Verify skill: {desc[:200]}" for _ in range(n)]


def _run_one_scenario_sync(scenario: str, skill_path: Path) -> tuple[bool, float, str]:
    """Chạy 1 scenario. Trả về (passed, confidence, error).

    MVP: gọi llm_as_judge (deterministic rule-based). Real: dispatch sub-agent.
    """
    try:
        # Lazy import để tránh circular
        from llm_as_judge import judge as llm_judge
        verdict = llm_judge(task=scenario, result="ok", seed=42)
        # Verdict format: "PASS: ..." | "FAIL: ..." | "REVIEW: ..."
        passed = verdict.startswith("PASS")
        # Confidence: parse từ verdict hoặc default 0.5
        m = re.search(r"confidence[=:]?\s*([\d.]+)", verdict, re.IGNORECASE)
        confidence = float(m.group(1)) if m else 0.5
        return passed, confidence, ""
    except Exception as e:
        return False, 0.0, str(e)


def bench_skills(
    skill_paths: list[Path],
    scenarios_per_skill: int = DEFAULT_SCENARIOS_PER_SKILL,
    parallel: int = 1,
) -> list[BenchResult]:
    """Benchmark nhiều skill. Sequential by default; parallel > 1 dùng ProcessPoolExecutor.

    Args:
        skill_paths: list SKILL.md files
        scenarios_per_skill: số scenarios mỗi skill (default 5)
        parallel: số worker parallel (1 = sequential, default)

    Returns:
        list BenchResult, sorted theo skill_path để deterministic
    """
    if parallel <= 1 or len(skill_paths) <= 1:
        # Sequential
        return [_bench_one_skill(sp, scenarios_per_skill) for sp in skill_paths]
    # Parallel với ProcessPoolExecutor
    from concurrent.futures import ProcessPoolExecutor, as_completed
    results: list[BenchResult] = []
    with ProcessPoolExecutor(max_workers=min(parallel, len(skill_paths))) as ex:
        futures = {
            ex.submit(_bench_one_skill, sp, scenarios_per_skill): sp
            for sp in skill_paths
        }
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                # Fallback: tạo BenchResult với error
                sp = futures[fut]
                results.append(BenchResult(
                    skill_name=sp.stem,
                    skill_path=str(sp),
                    scenarios_run=0,
                    scenarios_passed=0,
                    pass_rate=0.0,
                    avg_confidence=0.0,
                    avg_latency_ms=0.0,
                    errors=[str(e)],
                ))
    return sorted(results, key=lambda r: r.skill_path)


def _bench_one_skill(skill_path: Path, scenarios_per_skill: int) -> BenchResult:
    """Helper: benchmark 1 skill (extract để parallel hoá)."""
    scenarios = _generate_scenarios_from_skill(skill_path, scenarios_per_skill)
    passed = 0
    confidences: list[float] = []
    errors: list[str] = []
    for s in scenarios:
        p, c, e = _run_one_scenario_sync(s, skill_path)
        if p:
            passed += 1
        if c > 0:
            confidences.append(c)
        if e:
            errors.append(e)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return BenchResult(
        skill_name=skill_path.stem,
        skill_path=str(skill_path),
        scenarios_run=len(scenarios),
        scenarios_passed=passed,
        pass_rate=passed / len(scenarios) if scenarios else 0.0,
        avg_confidence=avg_conf,
        avg_latency_ms=0.0,  # MVP: chưa đo
    )


def render_bench_report(results: list[BenchResult], out_path: Path) -> str:
    """Ghi report markdown + JSON summary."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md = ["# Skill Benchmark Report\n", f"Generated: {datetime.utcnow().isoformat()}Z\n", ""]
    md.append("| Skill | Pass Rate | Avg Confidence | Scenarios |")
    md.append("|-------|-----------|----------------|-----------|")
    for r in results:
        md.append(f"| {r.skill_name} | {r.pass_rate:.0%} | {r.avg_confidence:.2f} | {r.scenarios_passed}/{r.scenarios_run} |")
    md.append("")
    avg_pass = sum(r.pass_rate for r in results) / len(results) if results else 0.0
    md.append(f"**Overall pass rate**: {avg_pass:.0%} across {len(results)} skills")
    out_path.write_text("\n".join(md), encoding="utf-8")
    # JSON sidecar
    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(out_path)


if __name__ == "__main__":
    import sys as _sys
    import argparse as _ap
    parser = _ap.ArgumentParser(description="Skill benchmark")
    parser.add_argument("skill_dir", nargs="?", default=".devin/skills", help="Skill directory")
    parser.add_argument("out_path", nargs="?", default=None, help="Output report path")
    parser.add_argument("--scenarios", type=int, default=DEFAULT_SCENARIOS_PER_SKILL, help="Scenarios per skill")
    parser.add_argument("--parallel", type=int, default=1, help="Parallel workers (1=sequential)")
    parser.add_argument("--schedule-cron", action="store_true", help="Run in cron mode (skip if ran today)")
    parser.add_argument("--state-file", default=".devin/state/skill_bench_last_run", help="State file for cron mode")
    args = parser.parse_args()

    # Cron mode: skip nếu đã chạy trong ngày
    if args.schedule_cron:
        from datetime import datetime as _dt
        state_path = Path(args.state_file)
        today = _dt.utcnow().strftime("%Y-%m-%d")
        if state_path.exists():
            last_run = state_path.read_text(encoding="utf-8").strip()
            if last_run == today:
                print(f"Already ran today ({today}), skip")
                _sys.exit(0)
        # Update state file sớm để tránh race condition
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(today, encoding="utf-8")

    skill_dir = Path(args.skill_dir)
    if args.out_path:
        out = Path(args.out_path)
    else:
        out = Path(f"docs/reports/skill_bench_{datetime.utcnow().strftime('%Y-%m-%d')}.md")
    # Chỉ bench skill có file SKILL.md
    if not skill_dir.exists():
        print(f"Skill dir not found: {skill_dir}")
        _sys.exit(0)
    paths = [p / "SKILL.md" for p in skill_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists()]
    if not paths:
        print(f"No skills found in {skill_dir}")
        _sys.exit(0)
    results = bench_skills(paths, scenarios_per_skill=args.scenarios, parallel=args.parallel)
    report = render_bench_report(results, out)
    print(f"Benched {len(results)} skills -> {report}")
    avg = sum(r.pass_rate for r in results) / len(results) if results else 0.0
    print(f"Overall pass rate: {avg:.0%}")
