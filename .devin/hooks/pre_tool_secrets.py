#!/usr/bin/env python3
"""pre_tool_secrets.py — SSRF guard + HLK secret detection cho pre_tool_use hook.

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API:
  - _hlk_repo_root, _hlk_secret_patterns, detect_hlk_secret
  - check_ssrf, _extract_urls, _log_ssrf_block
  - _ssrf_allowlist, _pin_and_verify_url, _ssrf_pin_ttl, _ssrf_pins_path
  - _load_ssrf_pins, _save_ssrf_pins, _resolve_host
"""
import json
import os
import re
import socket
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import ahd_session
from pre_tool_encoding import _decode_ip_encoding


def _entry_mod():
    """Trả module entry (pre_tool_use hoặc __main__) để đọc helper bị monkeypatch.

    Test monkeypatch các attribute trên pre_tool_use (vd. _resolve_host,
    _ssrf_pins_path). Các hàm nội bộ phải đọc động từ module entry thay vì
    bind giá trị tĩnh, tái hiện đúng semantics module đơn của bản gốc.
    """
    import sys
    return sys.modules.get("pre_tool_use") or sys.modules.get("__main__")


def _hlk_repo_root() -> Path:
    """Repo root cho HLK config: env AHD_REPO_ROOT > cwd (hoặc walk lên)."""
    env = os.environ.get("AHD_REPO_ROOT", "")
    if env:
        return Path(env)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".devin").exists() or (parent / ".git").exists():
            return parent
    return cwd


def _hlk_secret_patterns(root: Path | None = None) -> list[str]:
    """Load redact_patterns từ HLK config (CVE-2026-AHD-007 unified detection).

    Override test: env AHD_HLK_PATTERNS (JSON list) hoặc AHD_HLK_PATTERNS_FILE.
    """
    env = os.environ.get("AHD_HLK_PATTERNS", "")
    if env:
        try:
            pats = json.loads(env)
            if isinstance(pats, list):
                return [str(p) for p in pats]
        except (ValueError, TypeError):
            pass
    root = root or _hlk_repo_root()
    try:
        cfg_path = root / "HLK" / "config" / "hlk.config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            pats = cfg.get("security_rules", {}).get("redact_patterns", []) or []
            return [str(p) for p in pats]
    except (OSError, json.JSONDecodeError):
        pass
    return []


def detect_hlk_secret(command: str, root: Path | None = None) -> list[str]:
    """Quét command bằng HLK sanitizer patterns — trả pattern khớp (rỗng nếu sạch)."""
    hits: list[str] = []
    for pattern in _hlk_secret_patterns(root):
        try:
            if re.search(pattern, command, re.IGNORECASE):
                hits.append(pattern)
        except re.error:
            continue
    return hits


# T2.9: SSRF URL extraction regex
URL_RE = re.compile(r'https?://[^\s\'"<>\)\]\}]+', re.IGNORECASE)

# T2.9: Default allowlist for outbound URLs (expandable via env AHD_SSRF_ALLOWLIST)
DEFAULT_SSRF_ALLOWLIST = {"example.com", "api.github.com", "api.openai.com"}


def _ssrf_allowlist() -> set[str]:
    """Trả về tập allowlist từ env hoặc default."""
    env = os.environ.get("AHD_SSRF_ALLOWLIST", "")
    if not env:
        return set(DEFAULT_SSRF_ALLOWLIST)
    return set(item.strip() for item in env.split(",") if item.strip())


def check_ssrf(url: str, allowlist: set[str] | None = None) -> int:
    """T2.9: Kiểm tra URL có dẫn đến SSRF không.

    Trả về:
      0 — URL an toàn hoặc nằm trong allowlist.
      2 — URL trỏ tới private/loopback/link-local -> block.
    """
    if not url:
        return 0

    if allowlist is None:
        allowlist = _ssrf_allowlist()

    try:
        parsed = urllib.parse.urlparse(url)
    except (ValueError, TypeError):
        return 0

    except Exception as e:  # noqa: BLE001
        print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
        return 0

    host = (parsed.hostname or "").lower().strip()
    if not host:
        return 0

    # Allowlist: khớp chính xác hoặc subdomain
    for allowed in allowlist:
        allowed = allowed.lower().strip()
        if not allowed:
            continue
        if host == allowed or host.endswith(f".{allowed}"):
            return 0

    # Block localhost / loopback names
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return 2
    if host.endswith(".local") or host.endswith(".localhost"):
        return 2
    if "metadata" in host and ".internal" in host:
        return 2

    # S-03: Decode IP literal encodings trước khi check — chặn decimal/hex/octal/
    # mapped-IPv6 bypass mà ipaddress.ip_address(host) không bắt được.
    decoded = _decode_ip_encoding(host)
    if decoded is not None:
        host = decoded

    # IP literal check
    try:
        import ipaddress
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
            return 2
    except ValueError:
        pass

    # Optional: DNS resolution to private IP would go here; disabled to keep hook fast.
    return 0


def _extract_urls(text: str) -> list[str]:
    """Trích các URL http/https từ chuỗi."""
    if not text:
        return []
    return URL_RE.findall(text)


def _log_ssrf_block(url: str, reason: str, session_id: str) -> None:
    """T2.9: Ghi OTel-style log khi SSRF bị block."""
    try:
        root = ahd_session.get_repo_root()
        tel_dir = ahd_session.get_config_root(root) / "telemetry"
        tel_dir.mkdir(parents=True, exist_ok=True)
        log_path = tel_dir / "ssrf_blocks.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event.name": "ssrf.block",
            "url": url,
            "reason": reason,
            "session_id": session_id,
        }
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[pre_tool_use] unexpected exception in _log_ssrf_block: {e}", file=sys.stderr)
        # Best-effort logging only — never blocks the tool call on log failure.


# ---------------------------------------------------------------------------
# CVE-2026-AHD-008: SSRF DNS pinning
# ---------------------------------------------------------------------------
def _ssrf_pin_ttl() -> int:
    """TTL pin DNS (giây). Cấu hình qua env AHD_SSRF_PIN_TTL, default 60."""
    try:
        return max(1, int(os.environ.get("AHD_SSRF_PIN_TTL", "60")))
    except (ValueError, TypeError):
        return 60


def _ssrf_pins_path() -> Path:
    """Đường dẫn file pin: <config_root>/state/ssrf_pins.json."""
    root = ahd_session.get_repo_root()
    cfg = ahd_session.get_config_root(root)
    return cfg / "state" / "ssrf_pins.json"


def _load_ssrf_pins() -> dict:
    try:
        p = getattr(_entry_mod(), "_ssrf_pins_path", globals()["_ssrf_pins_path"])()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_ssrf_pins(pins: dict) -> None:
    """Ghi pin atomic (tmp + rename). Lỗi ghi không chặn tool call."""
    try:
        p = getattr(_entry_mod(), "_ssrf_pins_path", globals()["_ssrf_pins_path"])()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(pins), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def _resolve_host(host: str) -> tuple[list[str], bool]:
    """getaddrinfo → list IP (sorted, dedup). Trả (ips, ok); ok=False khi DNS lỗi."""
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ips = sorted({info[4][0] for info in infos})
        return ips, True
    except (socket.gaierror, OSError):
        return [], False


def _pin_and_verify_url(url: str) -> tuple[int, str]:
    """CVE-2026-AHD-008: DNS pinning — resolve + verify chống rebinding.

    - Hostname resolve ra private/loopback/link-local → block (SSRF qua DNS).
    - DNS resolve lỗi → block (fail CLOSED).
    - Pin IP tại lần check đầu; lần sau (trong TTL) resolve lại:
      không còn IP chung → DNS rebinding → block.
    - IP literal (kể cả dạng encoded) không cần DNS — đã check ở check_ssrf.

    Trả (0, "") nếu OK; (2, reason) nếu block.
    """
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower().strip()
    if not host:
        return 0, ""
    # IP literal / encoded → không cần DNS (đã xử lý trong check_ssrf)
    try:
        import ipaddress
        ipaddress.ip_address(host)
        return 0, ""
    except ValueError:
        pass
    if _decode_ip_encoding(host) is not None:
        return 0, ""

    resolve_host = getattr(_entry_mod(), "_resolve_host", globals()["_resolve_host"])
    ips, ok = resolve_host(host)
    if not ok:
        # DNS lỗi tại check time → fail CLOSED (CVE-2026-AHD-008)
        return 2, f"dns_resolution_failed:{host}"
    for ip in ips:
        try:
            addr = ipaddress.ip_address(ip.split("%")[0])
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_unspecified:
            return 2, f"dns_resolves_to_private:{host}:{ip}"

    # Verify pin (rebinding check)
    ttl = _ssrf_pin_ttl()
    now = time.time()
    pins = _load_ssrf_pins()
    pin = pins.get(host)
    if pin and isinstance(pin, dict) and now - pin.get("ts", 0) < ttl:
        old_ips = set(pin.get("ips", []) or [])
        if not old_ips.intersection(set(ips)):
            # Không còn IP nào trùng trong TTL → DNS rebinding
            return 2, f"dns_rebinding:{host}:{sorted(old_ips)}->{ips}"
        pin["ips"] = sorted(old_ips | set(ips))
        pin["ts"] = now
    else:
        pin = {"host": host, "ips": sorted(ips), "ts": now}
    pins[host] = pin
    _save_ssrf_pins(pins)
    return 0, ""
