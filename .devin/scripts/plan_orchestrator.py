#!/usr/bin/env python3
"""plan_orchestrator.py — FSM orchestrator cho Plan Phase.

Điểm vào mỏng: logic chính đã được module hóa vào package `plan_fsm`.

Usage:
  python plan_orchestrator.py --init --task "<task>"
  python plan_orchestrator.py --step --state <state.json> --results <results.json>
  python plan_orchestrator.py --status --state <state.json>
"""
import sys

from plan_fsm.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
