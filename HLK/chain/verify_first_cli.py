#!/usr/bin/env python3
"""verify_first_cli.py — CLI tool chạy full chain verify-first 1 lệnh.

Usage:
    python verify_first_cli.py <BRD.md> [--out-dir DIR] [--simulate] [--verbose]

Pipeline: BRD → scenarios → rubrics → tests → pytest → gate verdict → audit log

Output:
    <out-dir>/rubric.json
    <out-dir>/test_RB-*.py
    <out-dir>/EXECUTION_REPORT.md
    <out-dir>/audit.jsonl (nếu gate PASS)

Exit codes:
    0 = all pass
    1 = gate fail (block)
    2 = error (BRD invalid, missing file, etc.)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 output để tránh charmap error trên Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add HLK root to path (parent of chain/)
HLK_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HLK_ROOT))

from chain._platform_utils import run_python, ensure_utf8_output  # noqa: E402
ensure_utf8_output()

from chain.brd_validator import parse_brd_file
from chain.rubric_generator import generate_rubric_file
from chain.test_generator import generate_from_rubric_file
from chain.scenario_runner import make_scenarios_from_brd
from chain.auto_pr_runner import should_auto_merge, write_audit_log, GateVerdict


def _print(msg: str, verbose: bool = True) -> None:
    if verbose:
        print(msg)


def run_chain(
    brd_path: Path,
    out_dir: Path,
    simulate: bool = True,
    verbose: bool = True,
    force: bool = False,
) -> int:
    """Chạy full chain. Trả về exit code (0=pass, 1=gate fail, 2=error)."""
    _print(f"\n{'=' * 60}", verbose)
    _print(f"verify_first_cli — {brd_path}", verbose)
    _print(f"out_dir: {out_dir}", verbose)
    _print(f"simulate: {simulate}", verbose)
    _print(f"{'=' * 60}\n", verbose)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse BRD
    _print("[1/6] Parse BRD...", verbose)
    try:
        brd = parse_brd_file(brd_path)
    except Exception as e:
        _print(f"  ERROR: {e}", verbose)
        return 2
    _print(f"  OK: {brd.title} ({len(brd.actors)} actors, {len(brd.functional_requirements)} FR, {len(brd.non_functional_requirements)} NFR)", verbose)

    # Step 2: Generate Scenarios
    _print("\n[2/6] Generate scenarios...", verbose)
    scenarios = make_scenarios_from_brd(brd)
    _print(f"  OK: {len(scenarios)} scenarios", verbose)

    # Step 3: Generate Rubrics
    _print("\n[3/6] Generate rubrics...", verbose)
    rubric_path = out_dir / "rubric.json"
    try:
        rubric_path = generate_rubric_file(brd, rubric_path)
    except Exception as e:
        _print(f"  ERROR: {e}", verbose)
        return 2
    data = json.loads(rubric_path.read_text(encoding="utf-8"))
    _print(f"  OK: {len(data['binary_rubrics'])} binary + {len(data['score_rubrics'])} score", verbose)

    # Step 4: Generate Tests
    _print("\n[4/6] Generate tests...", verbose)
    tests = generate_from_rubric_file(rubric_path, out_dir)
    _print(f"  OK: {len(tests)} test file(s)", verbose)

    # Step 5: Run pytest
    _print("\n[5/6] Run pytest...", verbose)
    result = subprocess.run(
        ["py", "-m", "pytest", str(out_dir), "-o", "addopts=", "-p", "no:cacheprovider", "--no-cov", "-q"],
        capture_output=True, text=True, cwd=str(HLK_DIR.parent),
    )
    pytest_pass = result.returncode == 0
    _print(f"  Exit code: {result.returncode}", verbose)
    if verbose:
        for line in result.stdout.strip().splitlines()[-5:]:
            _print(f"    {line}", True)

    # Step 6: Gate verdict
    _print("\n[6/6] Run auto-PR gate...", verbose)
    pr_files = [str(t.path) for t in tests]
    pr_files += [str(rubric_path)]
    pr_diff = f"+ generated {len(tests)} test file(s)\n+ rubric: {rubric_path}\n"
    verdict = should_auto_merge(
        pr_files=pr_files,
        pr_diff=pr_diff,
        branch_prefix="verify-first/",
        pr_title=f"verify-first: auto-generated tests from {brd_path.stem}",
        rubric_file=rubric_path,
        task_result={
            "status": "done" if pytest_pass else "tests_failed",
            "evidence": f"{len(tests)} tests, pytest {'pass' if pytest_pass else 'fail'}",
            "brd_id": brd_path.stem,
            "scenario_count": len(scenarios),
            "rubric_score": 0.8 if pytest_pass else 0.3,
        },
        mode="simulate",  # CLI luôn simulate (an toàn)
        force=force,
    )
    _print(f"  Verdict: passed={verdict.passed}, error={verdict.error or ''}", verbose)
    for c in verdict.checks:
        _print(f"    - {c.name}: {c.result.value}", True)

    # Write EXECUTION_REPORT
    report_path = out_dir / "EXECUTION_REPORT.md"
    report_lines = [
        "# Verify-First CLI Execution Report\n",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}\n",
        f"BRD: `{brd_path}`\n",
        f"Mode: {'simulate' if simulate else 'live'}\n",
        "",
        "## Metrics",
        "",
        f"- BRD actors: {len(brd.actors)}",
        f"- FR: {len(brd.functional_requirements)}",
        f"- NFR: {len(brd.non_functional_requirements)}",
        f"- Scenarios generated: {len(scenarios)}",
        f"- Binary rubrics: {len(data['binary_rubrics'])}",
        f"- Score rubrics: {len(data['score_rubrics'])}",
        f"- Test files: {len(tests)}",
        f"- Pytest pass: {pytest_pass}",
        f"- Gate verdict: {'PASS' if verdict.passed else 'FAIL'}",
        "",
        "## Gate checks",
        "",
    ]
    for c in verdict.checks:
        report_lines.append(f"- **{c.name}**: {c.result.value} — {c.details}")
    if verdict.error:
        report_lines.append(f"\n**Error**: {verdict.error}")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    _print(f"\nReport: {report_path}", verbose)

    # Write audit log nếu gate PASS
    if verdict.passed:
        write_audit_log(
            pr_url=f"simulate://{brd_path.stem}",
            branch_prefix="verify-first/",
            gate_verdict=verdict,
            brd_id=brd_path.stem,
            scenario_count=len(scenarios),
            rubric_score=0.8 if pytest_pass else 0.3,
        )
        _print("Audit log written", verbose)
        return 0
    else:
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Verify-First CLI: chạy full chain từ BRD → gate verdict",
        epilog="""examples:
  py verify_first_cli.py docs/plans/foo/BRD.md
  py verify_first_cli.py docs/plans/foo/BRD.md --out-dir ./out
  py verify_first_cli.py docs/plans/foo/BRD.md --live --force  # DANGEROUS: real merge

exit codes:
  0 = all pass
  1 = gate fail (block)
  2 = error (BRD invalid, missing file, etc.)
""",
    )
    parser.add_argument("brd", help="Path to BRD.md file")
    parser.add_argument("--out-dir", default="./verify-first-output", help="Output directory")
    parser.add_argument("--simulate", action="store_true", default=True, help="Simulate auto-PR (default True)")
    parser.add_argument("--live", action="store_true", help="Use live auto-PR (DANGEROUS, opt-in)")
    parser.add_argument("--verbose", "-v", action="store_true", default=True, help="Verbose output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
    parser.add_argument("--force", action="store_true", help="Bypass rate limit (for CI/test)")
    args = parser.parse_args()

    if args.quiet:
        args.verbose = False
    if args.live:
        args.simulate = False

    return run_chain(
        brd_path=Path(args.brd),
        out_dir=Path(args.out_dir),
        simulate=args.simulate,
        verbose=args.verbose,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())