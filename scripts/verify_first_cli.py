#!/usr/bin/env python3
"""Stable repository entrypoint for the Verify-First chain."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from HLK.chain.verify_first_cli import main
if __name__ == '__main__': raise SystemExit(main())
