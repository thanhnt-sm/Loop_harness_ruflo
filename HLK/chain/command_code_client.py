#!/usr/bin/env python3
"""command_code_client.py — Wrap Command Code CLI làm LLM judge.

Mục đích: cung cấp LLM-as-judge bằng cách spawn subprocess `command-code`
(mặc định), thay vì gọi OpenRouter/Anthropic API trực tiếp. Cho phép
dùng chung provider với session hiện tại + hỗ trợ cross-model.

Spec: docs/plans/verify-first-residual.md section 3.2

Behavior:
- model=None → dùng model hiện tại của session (env CMDC_CURRENT_MODEL hoặc default)
- model="haiku"/"sonnet"/"opus" → override
- Subprocess fail → return mock response (graceful fallback)
- Circuit breaker: nếu 5 fail liên tiếp → disable CC cho session

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional
__all__ = [
    "CCConfig",
    "CCResponse",
    "CIRCUIT_BREAKER_COOLDOWN_SECONDS",
    "DEFAULT_CC_BIN",
    "DEFAULT_CIRCUIT_BREAKER_THRESHOLD",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT",
    "chat",
    "parallel_chat",
    "pick_cross_model",
    "reset_circuit_breaker",
]



_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

DEFAULT_CC_BIN = "command-code"
DEFAULT_TIMEOUT = 60  # giây
DEFAULT_MAX_RETRIES = 3
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5  # fail liên tiếp → disable
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 1800  # 30 phút

ModelName = Literal["haiku", "sonnet", "opus", "mock"]
DEFAULT_AVAILABLE_MODELS: list[str] = ["haiku", "sonnet", "opus"]

# Shell metacharacters không bao giờ được phép trong cc_cli_path
# Note: backslash (\\) được phép vì Windows path dùng nó, nhưng /\\c/... vẫn bị reject bởi ".." check
_SHELL_METACHARS = set("|&;<>()$`\"'*?{}\n\r\t")


def _validate_cc_cli_path(path: str) -> tuple[bool, str]:
    """Validate cc_cli_path chống command injection (fix P0 security).

    Allowlist:
    - chính xác "command-code" (no path) - default
    - absolute path kết thúc bằng "/command-code" hoặc "\\command-code"
    - relative path an toàn: phải có basename là "command-code" (no "..", no metachar)

    Reject:
    - chứa "..", bắt đầu bằng "/", shell metacharacters
    - rỗng
    - path chỉ tới file khác

    Returns:
        (ok, error_msg). error_msg="" nếu ok.
    """
    if not path or not isinstance(path, str):
        return False, "cc_cli_path rỗng hoặc không phải string"
    # Reject shell metacharacters
    bad_chars = [c for c in path if c in _SHELL_METACHARS]
    if bad_chars:
        return False, f"cc_cli_path chứa shell metacharacters: {bad_chars[:5]}"
    # Reject ".."
    if ".." in path:
        return False, "cc_cli_path chứa '..' (path traversal)"
    # Allow exact "command-code"
    if path == "command-code":
        return True, ""
    # Allow "/foo/command-code" or "\\foo\\command-code" or "C:\\foo\\command-code"
    # Basename phải là "command-code"
    import os.path as _op
    basename = _op.basename(path)
    if basename != "command-code":
        return False, f"basename phải là 'command-code', got: {basename!r}"
    # Path phải có dấu phân cách (để tránh "command-codeX")
    if not (_op.sep in path or "/" in path or "\\" in path):
        return False, "cc_cli_path phải là path tuyệt đối hoặc tên binary"
    return True, ""


@dataclass
class CCResponse:
    content: str
    confidence: float  # 0..1
    model: str
    latency_ms: int
    fallback_used: bool = False
    error: str = ""


# Circuit breaker state (module-level)
_circuit_state = {
    "consecutive_failures": 0,
    "disabled_until": 0.0,  # epoch seconds
}


@dataclass
class CCConfig:
    cc_cli_path: str = DEFAULT_CC_BIN
    available_models: list[str] = field(default_factory=lambda: list(DEFAULT_AVAILABLE_MODELS))
    timeout_seconds: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    cross_model_strategy: Literal["cheapest", "newest", "rotate"] = "cheapest"


def _load_config() -> CCConfig:
    """Load config từ env + defaults. Graceful fallback."""
    cli_raw = os.environ.get("AHD_CC_CLI_PATH", DEFAULT_CC_BIN)
    cli_ok, cli_err = _validate_cc_cli_path(cli_raw)
    if not cli_ok:
        import sys
        print(f"[command_code_client] WARNING: invalid AHD_CC_CLI_PATH={cli_raw!r}: {cli_err}. Falling back to default 'command-code'.", file=sys.stderr)
        cli = DEFAULT_CC_BIN
    else:
        cli = cli_raw
    try:
        timeout = int(os.environ.get("AHD_CC_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    try:
        retries = int(os.environ.get("AHD_CC_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
    except ValueError:
        retries = DEFAULT_MAX_RETRIES
    return CCConfig(
        cc_cli_path=cli,
        available_models=list(DEFAULT_AVAILABLE_MODELS),
        timeout_seconds=timeout,
        max_retries=retries,
    )


def _current_model() -> str:
    """Model hiện tại của session. Default 'sonnet'."""
    return os.environ.get("CMDC_CURRENT_MODEL", "sonnet")


def pick_cross_model(current: Optional[str] = None, strategy: str = "cheapest") -> str:
    """Pick 1 model khác current. Strategy: cheapest (Haiku đầu tiên), rotate, newest."""
    cfg = _load_config()
    available = [m for m in cfg.available_models if m != current]
    if not available:
        return current or "sonnet"
    if strategy == "cheapest":
        # Haiku < Sonnet < Opus theo giá
        price_order = {"haiku": 0, "sonnet": 1, "opus": 2}
        return min(available, key=lambda m: price_order.get(m, 99))
    if strategy == "newest":
        # Opus mới nhất
        return "opus" if "opus" in available else available[0]
    if strategy == "rotate":
        return random.choice(available)
    return available[0]


def _circuit_open() -> bool:
    """Check circuit breaker có đang open không."""
    now = time.time()
    if _circuit_state["disabled_until"] > now:
        return True
    if _circuit_state["disabled_until"] > 0 and now >= _circuit_state["disabled_until"]:
        # Cooldown xong → reset
        _circuit_state["disabled_until"] = 0.0
        _circuit_state["consecutive_failures"] = 0
    return False


def _record_failure() -> None:
    _circuit_state["consecutive_failures"] += 1
    if _circuit_state["consecutive_failures"] >= DEFAULT_CIRCUIT_BREAKER_THRESHOLD:
        _circuit_state["disabled_until"] = time.time() + CIRCUIT_BREAKER_COOLDOWN_SECONDS


def _record_success() -> None:
    _circuit_state["consecutive_failures"] = 0


def _fallback_response(prompt: str, model: str, latency_ms: int, error: str) -> CCResponse:
    """Trả về mock response khi CC fail hoặc disabled."""
    # Heuristic: trả về PASS/FAIL dựa trên keyword
    low = prompt.lower()
    if "pass" in low and "fail" not in low:
        content = "PASS (fallback)"
        conf = 0.5
    elif "fail" in low:
        content = "FAIL (fallback)"
        conf = 0.5
    else:
        content = "REVIEW (fallback)"
        conf = 0.3
    return CCResponse(
        content=content, confidence=conf, model=model,
        latency_ms=latency_ms, fallback_used=True, error=error,
    )


def _invoke_cc(prompt: str, model: str, cfg: CCConfig) -> CCResponse:
    """Gọi CC subprocess 1 lần, không retry."""
    start = time.time()
    cmd = [cfg.cc_cli_path, "chat", "--model", model, "--prompt", prompt]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=cfg.timeout_seconds,
        )
        latency = int((time.time() - start) * 1000)
        if proc.returncode != 0:
            return _fallback_response(prompt, model, latency, proc.stderr[:200])
        # Parse JSON output nếu có
        try:
            data = json.loads(proc.stdout)
            content = str(data.get("content", data.get("response", proc.stdout)))
            conf = float(data.get("confidence", 0.7))
        except (json.JSONDecodeError, ValueError, TypeError):
            content = proc.stdout[:5000]
            conf = 0.7
        return CCResponse(content=content, confidence=conf, model=model, latency_ms=latency)
    except subprocess.TimeoutExpired:
        latency = int((time.time() - start) * 1000)
        return _fallback_response(prompt, model, latency, f"timeout after {cfg.timeout_seconds}s")
    except FileNotFoundError:
        latency = int((time.time() - start) * 1000)
        return _fallback_response(prompt, model, latency, f"CC CLI not found: {cfg.cc_cli_path}")
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return _fallback_response(prompt, model, latency, str(e))


def chat(prompt: str, model: Optional[str] = None) -> CCResponse:
    """Public API: gọi CC 1 lần với retry. Trả về CCResponse.

    Args:
        prompt: full prompt
        model: None = current session model; "haiku"/"sonnet"/"opus" override

    Phase 3 hardening: redact secrets trong prompt trước khi gửi (P1 security).
    """
    # Redact secrets trước khi gửi (P1 từ adversarial review)
    try:
        from secret_scanner import redact as redact_secrets
        redacted_prompt = redact_secrets(prompt)
    except ImportError:
        redacted_prompt = prompt
    if _circuit_open():
        return _fallback_response(redacted_prompt, model or _current_model(), 0, "circuit breaker open")
    cfg = _load_config()
    use_model = model or _current_model()
    last_error = ""
    for attempt in range(cfg.max_retries):
        resp = _invoke_cc(redacted_prompt, use_model, cfg)
        if not resp.fallback_used:
            _record_success()
            return resp
        last_error = resp.error
        if attempt < cfg.max_retries - 1:
            time.sleep(2 ** attempt)  # exponential backoff
    # Tất cả retry fail → record + fallback
    _record_failure()
    return _fallback_response(redacted_prompt, use_model, 0, last_error)


def parallel_chat(prompts: list[tuple[str, Optional[str]]], max_workers: int = 3) -> list[CCResponse]:
    """Gọi chat() song song cho nhiều prompt. Mỗi item là (prompt, model).

    Dùng cho redteam round: spawn N sub-agent song song, mỗi agent dùng model riêng.
    """
    if not prompts:
        return []
    results: list[Optional[CCResponse]] = [None] * len(prompts)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(chat, prompt, model): i
            for i, (prompt, model) in enumerate(prompts)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:
                results[idx] = _fallback_response(
                    prompts[idx][0], prompts[idx][1] or _current_model(), 0, str(e)
                )
    return [r for r in results if r is not None]


def reset_circuit_breaker() -> None:
    """Public API: reset circuit breaker (testing hoặc manual)."""
    _circuit_state["consecutive_failures"] = 0
    _circuit_state["disabled_until"] = 0.0


if __name__ == "__main__":
    # Demo
    resp = chat("Đánh giá task: test pass?", model=None)
    print(f"Response: model={resp.model}, confidence={resp.confidence:.2f}, fallback={resp.fallback_used}")
    print(f"Content: {resp.content[:200]}")
    # Parallel
    prompts = [
        ("Đánh giá task 1: pass?", "haiku"),
        ("Đánh giá task 2: pass?", "sonnet"),
        ("Đánh giá task 3: pass?", "opus"),
    ]
    resps = parallel_chat(prompts, max_workers=3)
    print(f"\nParallel: {len(resps)} responses")
    for r in resps:
        print(f"  - {r.model}: {r.content[:80]}")
