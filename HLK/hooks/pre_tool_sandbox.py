#!/usr/bin/env python3
"""pre_tool_sandbox.py — RC-4 macOS Seatbelt Sandbox Integration.

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API:
  - _seatbelt_available, _get_seatbelt_profile_path, _run_hook_sandboxed, _check_sandbox_gate
"""
import os
import subprocess
import sys
from pathlib import Path

import ahd_session


# --- RC-4: macOS Seatbelt Sandbox Integration ---
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


def _get_seatbelt_profile_path() -> Path:
    """Get path to seatbelt profile."""
    root = ahd_session.get_repo_root()
    return root / ".devin" / "hooks" / "seatbelt.hook.sb"


def _run_hook_sandboxed(hook_script: str, *args: str) -> int:
    """Run a hook script inside the seatbelt sandbox. Fail-open if seatbelt unavailable."""
    if os.environ.get("HOOK_SANDBOX", "0") != "1":
        # Sandbox disabled, run directly
        cmd = [sys.executable, hook_script] + list(args)
        result = subprocess.run(cmd, capture_output=False)
        return result.returncode

    profile_path = _get_seatbelt_profile_path()
    if not profile_path.exists():
        print(f"[sandboxed_hook] WARNING: Seatbelt profile not found at {profile_path}, running unsandboxed", file=sys.stderr)
        cmd = [sys.executable, hook_script] + list(args)
        result = subprocess.run(cmd, capture_output=False)
        return result.returncode

    if not _seatbelt_available():
        print("[sandboxed_hook] WARNING: seatbelt not available, running unsandboxed (fail-open)", file=sys.stderr)
        cmd = [sys.executable, hook_script] + list(args)
        result = subprocess.run(cmd, capture_output=False)
        return result.returncode

    cmd = ["seatbelt", "-p", str(_get_seatbelt_profile_path()), sys.executable] + list(args)
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print(f"[sandboxed_hook] Hook exited with code {result.returncode}", file=sys.stderr)

    return result.returncode


def _check_sandbox_gate(data: dict) -> None:
    """RC-4: Run hook through seatbelt sandbox if HOOK_SANDBOX=1."""
    try:
        tool_name = data.get("tool_name", "")

        # Only sandbox hook scripts (not all tools)
        if os.environ.get("HOOK_SANDBOX", "0") != "1":
            return

        tool_input = data.get("tool_input", {})
        hook_script = tool_input.get("hook_script", "")

        if not hook_script:
            return

        result_code = _run_hook_sandboxed(hook_script)
        if result_code != 0:
            print(
                f"[RC-4 Sandbox] Hook execution failed with exit code {result_code}",
                file=sys.stderr,
            )
            sys.exit(result_code)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        _gate_error_sandbox(e)


def _gate_error_sandbox(exc: Exception) -> None:
    """Sandbox gate fail-closed trên internal error."""
    print(f"[pre_tool_use] sandbox internal error: {exc}", file=sys.stderr)
    if os.environ.get("AHD_FAIL_OPEN", "0") == "1":
        return
    print(
        "[pre_tool_use] sandbox FAILED CLOSED: blocked on internal error. "
        "Set AHD_FAIL_OPEN=1 to allow.",
        file=sys.stderr,
    )
    sys.exit(2)
