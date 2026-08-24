#!/usr/bin/env python3
"""approval_gate_args.py — CLI argument parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _parse_args(argv: list[str]) -> dict:
    """Parse CLI args thủ công (không dùng argparse để giữ stdlib tối giản).

    Hỗ trợ: --status, --approve, --reject, --request-changes, --artifact <sd|plan>
            --reviewer <name>, --reason <text>, --comments <text>
    """
    args = {
        "plan_file": "",
        "status": False,
        "approve": False,
        "reject": False,
        "request_changes": False,
        "interactive": False,
        "reviewer": "",
        "reason": "",
        "comments": "",
        "quality_report": "",
        "artifact": "plan",
        "signature": "",
        "date": "",
    }
    i = 0
    # Bước 1: Tìm plan_file (đối số đầu tiên không phải flag)
    positional = []
    while i < len(argv):
        a = argv[i]
        if a in ("--status",):
            args["status"] = True
        elif a in ("--approve",):
            args["approve"] = True
        elif a in ("--reject",):
            args["reject"] = True
        elif a in ("--request-changes", "--request_changes"):
            args["request_changes"] = True
        elif a in ("--interactive",):
            args["interactive"] = True
        elif a in ("--reviewer",):
            i += 1
            if i < len(argv):
                args["reviewer"] = argv[i]
        elif a in ("--reason",):
            i += 1
            if i < len(argv):
                args["reason"] = argv[i]
        elif a in ("--comments",):
            i += 1
            if i < len(argv):
                args["comments"] = argv[i]
        elif a in ("--quality-report", "--quality_report"):
            i += 1
            if i < len(argv):
                args["quality_report"] = argv[i]
        elif a in ("--artifact",):
            i += 1
            if i < len(argv):
                args["artifact"] = argv[i]
        elif a in ("--signature",):
            i += 1
            if i < len(argv):
                args["signature"] = argv[i]
        elif a in ("--date",):
            i += 1
            if i < len(argv):
                args["date"] = argv[i]
        elif a.startswith("--"):
            # Flag không nhận dạng -> bỏ qua
            pass
        else:
            positional.append(a)
        i += 1
    if positional:
        args["plan_file"] = positional[0]
    # Bước 2: --reason và --comments dùng chung cho reject/request_changes
    if args["reason"] and not args["comments"]:
        args["comments"] = args["reason"]
    return args