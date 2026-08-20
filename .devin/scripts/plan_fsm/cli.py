#!/usr/bin/env python3
"""CLI cho plan_orchestrator: --init, --step, --status."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import constants as C
from .state_machine import next_action, process_step
from .storage import create_initial_state, load_state, repo_root, save_state, state_path


def cmd_init(task_description: str) -> dict:
    """--init: Khởi tạo orchestrator state, trả next action."""
    root = repo_root()
    state = create_initial_state(task_description, root)
    sp = state_path(root, state["task_slug"])
    save_state(sp, state)
    action = next_action(state, root)
    save_state(sp, state)
    return {
        "state_file": str(sp),
        "task_slug": state["task_slug"],
        "task_fingerprint": state["task_fingerprint"],
        "task_description": state["task_description"],
        "tier": state["tier"],
        "current_state": state["state"],
        "next_action": action,
    }


def cmd_step(state_file: str, results_file: str) -> dict:
    """--step: Xử lý results, chuyển state, trả next action."""
    root = repo_root()
    sp = Path(state_file)
    state = load_state(sp)
    if not state:
        return {"error": f"Cannot load state file: {state_file}"}
    try:
        results = json.loads(Path(results_file).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Cannot load results file: {results_file}: {e}"}
    action = process_step(state, root, results)
    save_state(sp, state)
    return {
        "state_file": str(sp),
        "current_state": state["state"],
        "next_action": action,
    }


def cmd_status(state_file: str) -> dict:
    """--status: Trả trạng thái hiện tại."""
    state = load_state(Path(state_file))
    if not state:
        return {"error": f"Cannot load state file: {state_file}"}
    root = repo_root()
    action = next_action(state, root)
    return {
        "state_file": state_file,
        "current_state": state["state"],
        "tier": state.get("tier"),
        "round": state.get("round", 0),
        "revision_round": state.get("revision_round", 0),
        "qc_round": state.get("qc_round", 0),
        "sdd_path": state.get("sdd_path"),
        "sdd_approved": state.get("sdd_approved", False),
        "plan_path": state.get("plan_path"),
        "quality_report_path": state.get("quality_report_path"),
        "plan_approved": state.get("plan_approved", False),
        "approval_status": state.get("approval_status"),
        "next_action": action,
    }


def _parse_args(argv: list[str]) -> dict:
    """Parse CLI args thủ công."""
    args = {
        "init": False,
        "step": False,
        "status": False,
        "task": "",
        "state": "",
        "results": "",
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--init":
            args["init"] = True
        elif a == "--step":
            args["step"] = True
        elif a == "--status":
            args["status"] = True
        elif a == "--task":
            i += 1
            if i < len(argv):
                args["task"] = argv[i]
        elif a == "--state":
            i += 1
            if i < len(argv):
                args["state"] = argv[i]
        elif a == "--results":
            i += 1
            if i < len(argv):
                args["results"] = argv[i]
        i += 1
    return args


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    if argv is None:
        argv = sys.argv[1:]
    args = _parse_args(argv)

    if args["init"]:
        if not args["task"]:
            print("Error: --init requires --task '<description>'", file=sys.stderr)
            return 2
        data = cmd_init(args["task"])
    elif args["step"]:
        if not args["state"] or not args["results"]:
            print("Error: --step requires --state <file> and --results <file>", file=sys.stderr)
            return 2
        data = cmd_step(args["state"], args["results"])
    elif args["status"]:
        if not args["state"]:
            print("Error: --status requires --state <file>", file=sys.stderr)
            return 2
        data = cmd_status(args["state"])
    else:
        print(
            "Usage: python plan_orchestrator.py --init --task '<task>' | "
            "--step --state <state.json> --results <results.json> | "
            "--status --state <state.json>",
            file=sys.stderr,
        )
        return 2

    # Ép UTF-8 trước khi in (tránh lỗi cp1258 trên Windows console với tiếng Việt)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if "error" not in data else 1


if __name__ == "__main__":
    sys.exit(main())
