#!/usr/bin/env python3
"""Sandboxed hook wrapper for macOS Seatbelt.

Executes hooks via seatbelt sandbox. Fail-open if seatbelt unavailable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SEATBELT_PROFILE = Path(__file__).with_name("seatbelt.hook.sb")


def _seatbelt_available() -> bool:
    """Check if seatbelt is available on this system."""
    try:
        subprocess.run(
            ["seatbelt", "--help"],
            capture_output=True,
            timeout=2,
            check=False
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def run_hook_sandboxed(hook_script: str, *args: str) -> int:
    """Run a hook script inside the seatbelt sandbox.

    Args:
        hook_script: Path to the hook script to execute
        *args: Arguments to pass to the hook script

    Returns:
        Exit code from the sandboxed execution (0 on success, non-zero on failure)
    """
    if os.environ.get("HOOK_SANDBOX", "0") != "1":
        # Sandbox disabled, run directly
        cmd = [sys.executable, hook_script] + list(args)
        result = subprocess.run(cmd, capture_output=False)
        return result.returncode

    if not SEATBELT_PROFILE.exists():
        print(f"[sandboxed_hook] WARNING: Seatbelt profile not found at {SEATBELT_PROFILE}, running unsandboxed", file=sys.stderr)
        cmd = [sys.executable, hook_script] + list(args)
        result = subprocess.run(cmd, capture_output=False)
        return result.returncode

    if not _seatbelt_available():
        print("[sandboxed_hook] WARNING: seatbelt not available, running unsandboxed (fail-open)", file=sys.stderr)
        cmd = [sys.executable, hook_script] + list(args)
        result = subprocess.run(cmd, capture_output=False)
        return result.returncode

    cmd = ["seatbelt", "-p", str(SEATBELT_PROFILE), sys.executable, hook_script] + list(args)
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print(f"[sandboxed_hook] Hook exited with code {result.returncode}", file=sys.stderr)

    return result.returncode


def main() -> int:
    """CLI entry point: sandboxed_hook.py <hook_script> [args...]"""
    if len(sys.argv) < 2:
        print("Usage: sandboxed_hook.py <hook_script> [args...]", file=sys.stderr)
        return 1

    hook_script = sys.argv[1]
    args = sys.argv[2:]
    return run_hook_sandboxed(hook_script, *args)


if __name__ == "__main__":
    sys.exit(main())
