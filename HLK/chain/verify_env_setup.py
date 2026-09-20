#!/usr/bin/env python3
"""verify_env_setup.py — Boot app/simulator/fixture cho scenario test.

Mục đích: chuẩn bị môi trường verify (web server, CLI fixture, API mock,
mobile emulator) trước khi chạy scenario. Hỗ trợ 4 env type:
- web: start dev server + wait ready signal
- cli: PATH setup + sample data + chạy 1 lệnh
- api: mock server (WireMock) + test DB
- mobile: start emulator + install app (best-effort)

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 4.5

Usage:
    from verify_env_setup import VerifyEnv, boot_env
    env = VerifyEnv(type="web", boot_cmd=["npm", "run", "dev"], ready_signal=r"Local:.*http", ...)
    handle = boot_env(env)  # trả về EnvHandle
    # ... chạy scenario ...
    handle.cleanup()

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional
__all__ = [
    "EnvHandle",
    "VerifyEnv",
    "boot_env",
    "boot_env_from_yaml",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

EnvType = Literal["web", "cli", "api", "mobile"]


@dataclass
class VerifyEnv:
    type: EnvType
    boot_cmd: list[str]
    ready_signal: str = ""  # regex; nếu rỗng thì coi như ready ngay
    ready_timeout_seconds: int = 30
    fixture_paths: list[str] = field(default_factory=list)
    cleanup_cmd: list[str] = field(default_factory=list)
    working_dir: Optional[str] = None
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class EnvHandle:
    """Handle tới 1 env đang chạy."""

    env: VerifyEnv
    pid: int = 0
    log_path: Optional[Path] = None
    ready: bool = False
    cleanup_cmd: list[str] = field(default_factory=list)

    def cleanup(self) -> None:
        """Dừng env + chạy cleanup_cmd. Best-effort, không raise."""
        if self.pid:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.pid)],
                        capture_output=True, timeout=10,
                    )
                else:
                    os.killpg(os.getpgid(self.pid), 15)
            except (ProcessLookupError, OSError, PermissionError):
                pass
        for cmd in self.cleanup_cmd:
            try:
                subprocess.run(cmd if isinstance(cmd, list) else shlex.split(cmd),
                               capture_output=True, timeout=30)
            except (subprocess.TimeoutExpired, OSError):
                pass


def _wait_for_ready(proc: subprocess.Popen, signal_re: str, timeout: int, log_path: Path) -> bool:
    """Đợi log xuất hiện signal_re (regex), hoặc timeout. Trả về True nếu ready."""
    if not signal_re:
        return True
    pattern = re.compile(signal_re, re.IGNORECASE)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False  # process died
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(content):
                return True
        time.sleep(0.5)
    return False


def boot_env(env: VerifyEnv) -> EnvHandle:
    """Boot env và trả về EnvHandle. Raise nếu không ready trong timeout."""
    log_path = Path(".devin/state/verify_env.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Pre-copy fixtures
    for fx in env.fixture_paths:
        src = Path(fx)
        if not src.exists():
            raise FileNotFoundError(f"Fixture không tồn tại: {src}")

    full_env = {**os.environ, **env.env_vars}
    cwd = env.working_dir or os.getcwd()

    try:
        log_file = open(log_path, "ab", buffering=0)
    except OSError:
        log_file = open(log_path, "ab")

    # On POSIX, start in new process group để kill cả group khi cleanup
    popen_kwargs: dict = {
        "args": env.boot_cmd,
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "env": full_env,
        "cwd": cwd,
    }
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(**popen_kwargs)
    ready = _wait_for_ready(proc, env.ready_signal, env.ready_timeout_seconds, log_path)

    handle = EnvHandle(
        env=env,
        pid=proc.pid,
        log_path=log_path,
        ready=ready,
        cleanup_cmd=env.cleanup_cmd,
    )
    if not ready:
        # cleanup ngay để tránh leak process
        handle.cleanup()
        raise TimeoutError(
            f"Env '{env.type}' không ready trong {env.ready_timeout_seconds}s. "
            f"Log: {log_path}"
        )
    return handle


def boot_env_from_yaml(path: str | Path) -> EnvHandle:
    """Boot env từ verify_env.yaml (Phase 0 spec).

    YAML schema:
        type: web|cli|api|mobile
        boot_cmd: ["cmd", "args"]
        ready_signal: "regex"
        ready_timeout_seconds: 30
        fixture_paths: ["path1", ...]
        cleanup_cmd: ["cmd", "args"]
        working_dir: "."
        env_vars: {KEY: VALUE}
    """
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML chưa cài. Cài bằng: pip install pyyaml")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"YAML không tồn tại: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    env = VerifyEnv(
        type=data["type"],
        boot_cmd=data["boot_cmd"],
        ready_signal=data.get("ready_signal", ""),
        ready_timeout_seconds=int(data.get("ready_timeout_seconds", 30)),
        fixture_paths=data.get("fixture_paths", []),
        cleanup_cmd=data.get("cleanup_cmd", []),
        working_dir=data.get("working_dir"),
        env_vars=data.get("env_vars", {}),
    )
    return boot_env(env)
