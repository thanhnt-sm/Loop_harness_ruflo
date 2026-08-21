#!/usr/bin/env python3
"""plan_orchestrator.py — entry point cho Plan Phase FSM.

Gọi plan_fsm.cli để chạy step-based orchestrator (--init, --step, --status).
"""
import sys
from pathlib import Path

# Thêm thư mục .devin/scripts để import package plan_fsm khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

from plan_fsm.cli import main

if __name__ == "__main__":
    sys.exit(main())