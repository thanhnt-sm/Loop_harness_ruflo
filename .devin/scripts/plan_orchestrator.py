#!/usr/bin/env python3
"""plan_orchestrator.py — Graph-based Plan Phase orchestrator v2.

Replaces the FSM-based orchestrator with a StateGraph-based orchestrator.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plan_fsm.state_machine_v2 import PlanOrchestratorV2, main as cli_main

if __name__ == "__main__":
    sys.exit(cli_main(sys.argv[1:]))