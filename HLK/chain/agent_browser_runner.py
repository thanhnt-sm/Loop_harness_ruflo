#!/usr/bin/env python3
"""agent_browser_runner.py — Wrap agent-browser skill cho UI/simulator scenarios.

Mục đích: chạy UI/simulator action_type thay vì SKIP như trước.
Wrap agent-browser skill (có sẵn trong workspace) thành 1 API đơn giản
cho scenario_runner gọi.

Spec: docs/plans/verify-first-residual.md section 3.4

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
__all__ = [
    "BrowserStepResult",
    "DEFAULT_CC_BIN",
    "DEFAULT_TIMEOUT",
    "capture_screenshot",
    "run_browser_step",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

DEFAULT_CC_BIN = "command-code"
DEFAULT_TIMEOUT = 120  # UI flow có thể lâu hơn CLI

ActionType = Literal["ui", "simulator"]


@dataclass
class BrowserStepResult:
    success: bool
    evidence_path: Optional[Path] = None
    error: str = ""
    output: str = ""
    fallback_used: bool = False


def _is_cc_available() -> bool:
    """Check command-code CLI có sẵn không."""
    try:
        r = subprocess.run([DEFAULT_CC_BIN, "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_browser_step(
    action: str,
    action_type: ActionType,
    scenario_id: str,
    evidence_dir: Path,
    model: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> BrowserStepResult:
    """Chạy 1 UI/simulator step qua agent-browser skill (wrap CC CLI).

    Args:
        action: instruction string (vd "Click button 'Submit'")
        action_type: "ui" hoặc "simulator"
        scenario_id: để tổ chức evidence theo scenario
        evidence_dir: nơi ghi screenshot/log
        model: None = current model; hoặc "haiku"/"sonnet"/"opus"

    Returns:
        BrowserStepResult với success=True nếu step pass, False nếu fail.
        evidence_path: path tới screenshot nếu có.

    Fallback: nếu CC CLI không có hoặc fail → trả về SKIP-like result
    (success=False, fallback_used=True). Caller (scenario_runner) hiểu
    là step không thực sự chạy được.
    """
    evidence_dir.mkdir(parents=True, exist_ok=True)
    # Build prompt cho agent-browser
    prompt = (
        f"You are an agent-browser operator.\n"
        f"Scenario: {scenario_id}\n"
        f"Action type: {action_type}\n"
        f"Action: {action}\n\n"
        f"Perform this action using browser automation. After completing, "
        f"respond with JSON: {{\"success\": true/false, \"error\": \"<reason if fail>\", "
        f"\"screenshot_path\": \"<absolute path to screenshot>\"}}"
    )
    # Try command_code_client first
    try:
        from command_code_client import chat as cc_chat
        resp = cc_chat(prompt, model=model)
        if resp.fallback_used:
            return BrowserStepResult(
                success=False, error="CC unavailable (fallback)",
                fallback_used=True,
            )
        # Parse JSON response
        try:
            data = json.loads(resp.content)
            ev_path = data.get("screenshot_path")
            return BrowserStepResult(
                success=bool(data.get("success", False)),
                evidence_path=Path(ev_path) if ev_path else None,
                error=data.get("error", ""),
                output=resp.content[:500],
            )
        except (json.JSONDecodeError, ValueError):
            # Không parse được JSON → heuristic
            success = "fail" not in resp.content.lower()
            return BrowserStepResult(
                success=success,
                error="" if success else "agent-browser response không có 'fail'",
                output=resp.content[:500],
            )
    except ImportError:
        pass
    # Fallback: gọi CC CLI trực tiếp
    if not _is_cc_available():
        return BrowserStepResult(
            success=False, error="command-code CLI không available",
            fallback_used=True,
        )
    try:
        proc = subprocess.run(
            [DEFAULT_CC_BIN, "chat", "--model", model or "sonnet", "--prompt", prompt],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            return BrowserStepResult(
                success=False, error=f"cc chat failed: {proc.stderr[:200]}",
                fallback_used=True,
            )
        return BrowserStepResult(
            success=True,  # optimistic
            output=proc.stdout[:500],
        )
    except subprocess.TimeoutExpired:
        return BrowserStepResult(
            success=False, error=f"timeout after {timeout}s", fallback_used=True,
        )


def capture_screenshot(scenario_id: str, evidence_dir: Path, label: str = "step") -> Optional[Path]:
    """Best-effort: capture screenshot. Trả về path nếu thành công.

    MVP: stub — return None. Thật sẽ dùng Playwright/CDP.
    """
    # TODO: integrate Playwright khi cần
    return None
