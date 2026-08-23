#!/usr/bin/env python3
"""approval_gate_interactive.py — Interactive approval mode."""

from __future__ import annotations

from pathlib import Path

from approval_gate_commands import cmd_approve, cmd_reject, cmd_request_changes
from approval_gate_summary import _parse_plan_summary, _parse_quality_report
from approval_gate_state import _repo_root, _plan_state_name
from approval_gate_constants import (
    STATUS_PENDING,
    ARTIFACT_PLAN,
    ARTIFACT_SD,
)


def cmd_interactive(plan_path: Path, reviewer: str, quality_report_path: str = "", artifact: str = ARTIFACT_PLAN) -> dict:
    """--interactive: Present plan/SDD summary + hỏi user approve/reject/modify."""
    if not plan_path.exists():
        return {"error": f"Không tìm thấy file: {plan_path}"}

    root = _repo_root(plan_path)
    summary = _parse_plan_summary(plan_path)
    qr_summary = {}
    if quality_report_path:
        qr_path = Path(quality_report_path).resolve()
        qr_summary = _parse_quality_report(qr_path)

    title = "SDD APPROVAL GATE — Human Review Required" if artifact == ARTIFACT_SD else "PLAN APPROVAL GATE — Human Review Required"
    artifact_label = "Solution Design" if artifact == ARTIFACT_SD else "Plan"

    # Bước 1: Present summary
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()
    print(f"## {artifact_label} Summary")
    print(f"  Feature:           {summary.get('feature', 'N/A')}")
    print(f"  Risk Tier:         {summary.get('risk_tier', 'N/A')}")
    print(f"  Tasks:             {summary.get('tasks_count', 0)}")
    print(f"  Requirements:      {summary.get('requirements_count', 0)}")
    print(f"  Files to change:   {summary.get('files_count', 0)}")
    if qr_summary:
        print(f"  Quality scorecard: {qr_summary.get('scorecard', 'N/A')}")
        print(f"  Overall:           {'PASS' if qr_summary.get('all_pass') else 'FAIL'}")
    print()
    print(f"  {artifact_label} file:    {plan_path}")
    if quality_report_path:
        print(f"  Quality report:    {quality_report_path}")
    print()
    print("-" * 60)
    print("  Options:")
    print("    [y]     Approve")
    print("    [n]     Reject")
    print("    [m]     Approve with modifications")
    print("    [i]     Request more information")
    print("-" * 60)

    # Bước 2: Hỏi user
    try:
        response = input("\n  Decision [y/n/m/i]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  [Aborted by user]")
        return {"status": STATUS_PENDING, "reason": "User aborted"}

    # Bước 3: Xử lý response
    label = "SDD" if artifact == ARTIFACT_SD else "Plan"
    if response == "y":
        state = cmd_approve(plan_path, reviewer, "Approved via interactive mode", artifact=artifact)
        print(f"\n  [APPROVED] {label} state written: {_plan_state_name(plan_path, artifact)}.json")
        return state
    elif response == "n":
        try:
            reason = input("  Reason for rejection (optional): ").strip()
        except (EOFError, KeyboardInterrupt):
            reason = "Rejected via interactive mode"
        state = cmd_reject(plan_path, reviewer, reason or "Rejected via interactive mode", artifact=artifact)
        print(f"\n  [REJECTED] Reason: {reason}")
        return state
    elif response == "m":
        try:
            modifications = input("  Specify modifications needed: ").strip()
        except (EOFError, KeyboardInterrupt):
            modifications = "Modifications requested via interactive mode"
        state = cmd_request_changes(plan_path, reviewer, modifications, artifact=artifact)
        print(f"\n  [CHANGES REQUESTED] {modifications}")
        return state
    elif response == "i":
        try:
            question = input("  What information do you need? ").strip()
        except (EOFError, KeyboardInterrupt):
            question = "Information requested"
        print(f"\n  [INFO REQUESTED] {question}")
        return {"status": STATUS_PENDING, "reason": f"Info requested: {question}"}
    else:
        print(f"\n  [INVALID] Response '{response}' not recognized. Use y/n/m/i.")
        return {"status": STATUS_PENDING, "reason": f"Invalid response: {response}"}