#!/usr/bin/env python3
"""Pre-tool-use hook — guards against dangerous operations + enforces context compaction.

Called by the AI tool before executing any tool. Receives JSON on stdin:
  {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "session_id": "..."}

Exit codes:
  0 = allow the tool call
  2 = block the tool call (stderr shown to user)
  other non-zero = error (tool decides; usually allow)

Two gates:
  1. Context-oversized gate — if context_oversized flag is set, graduated response:
     - counter < 2: allow + stderr note (compact soon)
     - counter 2-3: allow + stderr warning (compact NOW)
     - counter >= 4: block non-compaction tools (force agent to compact)
     Compaction tools (read, grep, glob, write, edit, notebook_*, todo_write, skill)
     are always allowed so the agent can actually run context-compactor.

  2. Dangerous-command gate — blocks rm -rf, force-push, etc. (Bash/shell only)

This is a safety net, not a replacement for the canon's red lines. The agent
should already know not to do these things; this hook catches it if the agent
doesn't.
"""
import ipaddress
import json
import os
import re
import shlex
import socket
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import ahd_session

# T2.4: Import cost_tracker từ .devin/scripts.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from cost_tracker import check_cost_cap
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    check_cost_cap = None  # type: ignore[assignment]

# T4.9: Import reflection_gate từ .devin/scripts.
try:
    from reflection_gate import check_reflection as _check_reflection
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    _check_reflection = None  # type: ignore[assignment]

# U15: Internal timeout — if hook runs longer than this, force-allow (fail open).
# Config timeout is 3s; this is a safety net at 2s (1s margin) to exit before config kills us.
except Exception as e:
    print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
    _check_reflection = None  # type: ignore[assignment]

# U15: Internal timeout — if hook runs longer than this, force-allow (fail open).
# Config timeout is 3s; this is a safety net at 2s (1s margin) to exit before config kills us.
HOOK_TIMEOUT_SECONDS = 2.0

# --- Context-oversized gate config ---
OVERSIZED_NOTE_THRESHOLD = 0   # counter >= this -> note
OVERSIZED_WARN_THRESHOLD = 2   # counter >= this -> warning
OVERSIZED_BLOCK_THRESHOLD = 4  # counter >= this -> block non-compaction tools

# Tools that are always allowed even during compaction block (needed to actually compact)
COMPACTION_SAFE_TOOLS = frozenset({
    "read", "Read", "grep", "Grep", "glob", "Glob", "find_file_by_name",
    "write", "Write", "edit", "Edit",
    "notebook_read", "notebook_edit",
    "todo_write", "TodoWrite",
    "skill", "Skill",
})


def detect_encoding_bypass(text: str) -> list[str]:
    """T2.10: Phát hiện các kỹ thuật encoding bypass trong text.

    Trả về danh sách các loại bypass phát hiện được (rỗng nếu sạch).
    Các loại: utf7, punycode, html_entity, hex_escape, unicode_escape,
    octal_escape, base64_pipe.
    """
    if not text:
        return []
    findings: list[str] = []

    # UTF-7: +AGY- hay +Base64-
    if re.search(r'\+[A-Za-z0-9+/]+-', text):
        findings.append("utf7")

    # Punycode: xn-- prefix
    if re.search(r'\bxn--[a-zA-Z0-9-]+\b', text):
        findings.append("punycode")

    # HTML entities: &#65; hoặc &#x41;
    if re.search(r'&#[xX]?[0-9a-fA-F]+;', text):
        findings.append("html_entity")

    # Hex escapes \xNN
    if re.search(r'\\x[0-9a-fA-F]{2}', text):
        findings.append("hex_escape")

    # Unicode escapes \uNNNN, \UNNNNNNNN
    if re.search(r'\\u[0-9a-fA-F]{4}', text) or re.search(r'\\U[0-9a-fA-F]{8}', text):
        findings.append("unicode_escape")

    # Octal escapes \NNN
    if re.search(r'\\[0-7]{1,3}', text):
        findings.append("octal_escape")

    # Base64 pipe-to-shell (U02, U51 already detect but reinforce here)
    if re.search(r'base64.*[\|<].*(bash|sh|zsh|python|perl)', text, re.IGNORECASE) or \
       re.search(r'base64.*-d.*[\|<]', text, re.IGNORECASE):
        findings.append("base64_pipe")

    return findings


# CVE-2026-AHD-007: phân tích cấu trúc shell bằng shlex (sau khi decode).
def analyze_shell_structure(command: str) -> list[str]:
    """Phát hiện cấu trúc shell khả nghi (CVE-2026-AHD-007).

    - unbalanced_quotes : shlex không parse được (quote không cân bằng).
    - quote_breakout    : metachar (; & |) dính sát vào quote — dấu hiệu
                          breakout/ghép lệnh ẩn.
    - control_chars     : ký tự điều khiển (trừ \t \n \r) — encoding bypass.

    KHÔNG flag `&&`/`||`/`;` có khoảng trắng thông thường (vẫn là lệnh hợp lệ).
    """
    findings: list[str] = []
    if not command:
        return findings

    # 1. Unbalanced quotes -> shlex raise ValueError
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        list(lexer)
    except ValueError:
        findings.append("unbalanced_quotes")

    # 2. Metachar dính sát quote (không có khoảng trắng) — quote breakout
    if re.search(r'["\'][;&|]|[;&|]["\']', command):
        findings.append("quote_breakout")

    # 3. Control chars (trừ \t \n \r hợp lệ trong shell)
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', command):
        findings.append("control_chars")

    return findings


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


def normalize_command(command: str) -> str:
    """Normalize shell command before pattern matching (U02: fix regex bypass).

    Strips backslash escaping, quotes, and expands simple $(echo X) substitutions.
    Also flags base64-piped-to-shell patterns that can hide destructive commands.

    U51: Expanded encoding bypass protection:
    - Hex escape decode (\\xNN)
    - Octal escape decode (\\NNN)
    - Unicode escape decode (\\uNNNN, \\UNNNNNNNN)
    - Shell variable expansion simulation ($VAR, ${VAR})
    - Broader base64 detection (all shell variants, redirect, heredoc)
    """
    # U51-3. Decode hex escapes \xNN -> char (BEFORE backslash strip)
    normalized = re.sub(
        r'\\x([0-9a-fA-F]{2})',
        lambda m: chr(int(m.group(1), 16)),
        command,
    )

    # U51-4. Decode octal escapes \NNN (1-3 digits) -> char (BEFORE backslash strip)
    normalized = re.sub(
        r'\\([0-7]{1,3})',
        lambda m: chr(int(m.group(1), 8)),
        normalized,
    )

    # U51-5. Decode unicode escapes \uNNNN, \UNNNNNNNN -> char (BEFORE backslash strip)
    normalized = re.sub(
        r'\\U([0-9a-fA-F]{8})',
        lambda m: chr(int(m.group(1), 16)),
        normalized,
    )
    normalized = re.sub(
        r'\\u([0-9a-fA-F]{4})',
        lambda m: chr(int(m.group(1), 16)),
        normalized,
    )

    # 1. Remove backslash escaping (r\m -> rm) — after hex/octal/unicode decode
    normalized = re.sub(r'\\(.)', r'\1', normalized)

    # 2. Remove quote characters (r''m -> rm, r""m -> rm)
    normalized = re.sub(r"['\"]", "", normalized)

    # 6. Expand simple $(echo X) command substitutions
    normalized = re.sub(
        r'\$\(echo\s+(\S+)\)',
        lambda m: m.group(1),
        normalized,
    )

    # 7. Expand backtick `echo X` substitutions
    normalized = re.sub(
        r'`echo\s+(\S+)`',
        lambda m: m.group(1),
        normalized,
    )

    # U51-8. Simulate shell variable expansion — flag any $VAR / ${VAR} usage
    # We can't know the value, so we flag it as EXPANDED_VAR for pattern matching
    normalized = re.sub(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}', 'EXPANDED_VAR', normalized)
    normalized = re.sub(r'\$[A-Za-z_][A-Za-z0-9_]*', 'EXPANDED_VAR', normalized)

    # U51-9. Broader base64 detection — all shell variants, redirects, heredocs
    # Covers: base64 -d | sh, base64 -d|bash, base64<d|bash, <<<$(base64...), etc.
    if re.search(r'base64.*[\|<].*(bash|sh|zsh|python|perl)', normalized, re.IGNORECASE):
        normalized += " BASE64_PIPE_TO_SHELL_DETECTED"
    if re.search(r'base64.*-d.*[\|<]', normalized, re.IGNORECASE):
        normalized += " BASE64_PIPE_TO_SHELL_DETECTED"
    if re.search(r'<<<\$\(base64', normalized, re.IGNORECASE):
        normalized += " BASE64_PIPE_TO_SHELL_DETECTED"

    # Pentest fix: gộp split short flags của rm thành một flag duy nhất theo thứ tự chuẩn.
    # "rm -r -f /" -> "rm -rf /", "rm -f -r /" -> "rm -rf /", "rm -fr /" -> "rm -rf /".
    # Tránh bypass khi -r và -f nằm ở hai flag group riêng (rm -r -f /).
    def _merge_rm_flags(match: "re.Match[str]") -> str:
        # match.group(1) = chuỗi các flag riêng "-r -f -v" ...
        flags = re.findall(r'-([a-zA-Z])', match.group(1))
        unique = []
        for f in flags:
            if f not in unique:
                unique.append(f)
        # Sắp xếp: r trước f (chuẩn -rf), các flag khác giữ nguyên phía sau
        ordered = sorted(unique, key=lambda c: ({'r': 0, 'f': 1}.get(c, 2), c))
        return 'rm -' + ''.join(ordered) + ' '

    normalized = re.sub(
        r'\brm\s+((?:-[a-zA-Z]\s+){2,})',
        _merge_rm_flags,
        normalized,
    )

    return normalized


# Patterns that are always blocked
DANGEROUS_PATTERNS = [
    # rm -rf with broad targets
    # Pentest fix: thêm EXPANDED_VAR (sau khi $HOME được normalize) và
    # chấp nhận cả -fr (f trước r) vì normalize_command đã gộp split flags.
    (r"\brm\s+(-[a-z]*r[a-z]*f|--recursive\s+--force)\s+(/|/\*|~|\$HOME|EXPANDED_VAR|\.\.|\*|\.|\.git|\.git/)", "rm -rf with broad target"),
    # Pentest fix: rm -fr (f trước r, gộp trong một flag) cũng phải block
    (r"\brm\s+-[a-z]*f[a-z]*r[a-z]*\s+(/|/\*|~|\$HOME|EXPANDED_VAR|\.\.|\*|\.|\.git|\.git/)", "rm -fr with broad target"),
    # git push --force / -f to any branch
    (r"\bgit\s+push\s+(--force|-f)\b", "force-push"),
    # git reset --hard to remote
    (r"\bgit\s+reset\s+--hard\b.*\b(origin|upstream)\b", "hard reset to remote"),
    # curl/wget pipe to shell
    (r"\b(curl|wget)\b.*\|\s*(bash|sh|zsh)\b", "pipe-to-shell from URL"),
    # chmod -R 777
    (r"\bchmod\s+-R\s+777\b", "chmod 777 recursive"),
    # dd to disk device
    (r"\bdd\b.*\bof=/dev/(sd|nvme|hd)", "dd to disk device"),
    # mkfs
    (r"\bmkfs\b", "filesystem format"),
    # S-04: Disk partition / LVM / crypto destructive ops (bypass via fdisk/parted)
    (r"\b(fdisk|sfdisk|gdisk|parted|mkpart)\b", "disk partition tool"),
    (r"\b(lvremove|vgremove|pvremove|lvreduce|vgreduce)\b", "LVM destructive op"),
    (r"\b(cryptsetup\s+(luksFormat|luksRemoveKey|erase|remove|reformat))\b", "cryptsetup destructive op"),
    (r"\b(swapoff)\b", "swapoff"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "host power control"),
    # GitHub token / API key in command
    (r"\b(ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{48}|AKIA[A-Z0-9]{16})\b", "secret in command"),
    # base64 decoded piped to shell (U02: prevent encoding bypass)
    (r"base64\s+-d\s*\|\s*(bash|sh|zsh)", "base64 decoded piped to shell"),
    # BASE64_PIPE_TO_SHELL_DETECTED flag from normalize_command
    (r"BASE64_PIPE_TO_SHELL_DETECTED", "base64 encoded command piped to shell"),
    # U43: Network egress to known-bad domains
    (r"\b(curl|wget)\b.*\b(malicious|evil|attacker|hack|exploit)\.(com|net|org|io)\b", "network egress to suspicious domain"),
    # U43: Exfiltration patterns — curl/wget with data upload
    (r"\b(curl|wget)\b.*\b(--upload-file|-T\s|--data|-d\s|--post-data)\b.*\b(http|ftp)\b", "potential data exfiltration"),
]

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


def _decode_ip_encoding(host: str) -> str | None:
    """S-03: Decode IPv4 literal encodings về dạng dotted-decimal chuẩn.

    Chặn SSRF bypass qua: decimal integer (2130706433), hex (0x7f000001),
    octal integer (017700000001), octal/hex dotted (0177.0.0.1, 0x7f.0.0.1),
    IPv4-mapped IPv6 (::ffff:127.0.0.1, ::ffff:7f00:1).

    Trả về dạng "a.b.c.d" nếu host là IP literal encoded, ngược lại None.
    """
    if not host:
        return None
    h = host.strip().lower()
    if not h:
        return None

    # IPv4-mapped IPv6: ::ffff:<v4> — lấy phần v4 rồi xử lý tiếp.
    m = re.fullmatch(r"(?:::f{4}:)([0-9a-f.]+)", h)
    if m:
        h = m.group(1)

    # Hex integer: 0x7f000001
    if re.fullmatch(r"0x[0-9a-f]{1,8}", h):
        return str(ipaddress.IPv4Address(int(h, 16)))

    # Decimal integer: 2130706433 (loại trừ dạng octal leading-zero: 0177...)
    if re.fullmatch(r"[0-9]{1,10}", h) and not re.fullmatch(r"0[0-7]+", h):
        v = int(h, 10)
        if v <= 0xFFFFFFFF:
            return str(ipaddress.IPv4Address(v))
        return None

    # Octal integer: 017700000001
    if re.fullmatch(r"0[0-7]{1,11}", h):
        return str(ipaddress.IPv4Address(int(h, 8)))

    # Dotted/partial form: 0177.0.0.1 / 0x7f.0.0.1 / 127.1 / 127.0.0.1
    # Hỗ trợ shorthand IPv4 (127.1 == 127.0.0.1): thành phần cuối chiếm các byte còn lại.
    parts = h.split(".")
    if 1 <= len(parts) <= 4:
        try:
            octets: list[int] = []
            for p in parts:
                if re.fullmatch(r"0[0-7]{1,3}", p) and not re.fullmatch(r"0+", p):
                    octets.append(int(p, 8))
                elif re.fullmatch(r"0x[0-9a-f]{1,8}", p):
                    octets.append(int(p, 16))
                elif p.isdigit():
                    octets.append(int(p, 10))
                else:
                    return None
            if len(octets) == 1:
                if 0 <= octets[0] <= 0xFFFFFFFF:
                    return str(ipaddress.IPv4Address(octets[0]))
                return None
            if len(octets) == 2 and 0 <= octets[0] <= 255 and 0 <= octets[1] <= 0xFFFFFF:
                return str(ipaddress.IPv4Address((octets[0] << 24) | octets[1]))
            if len(octets) == 3 and 0 <= octets[0] <= 255 and 0 <= octets[1] <= 255 and 0 <= octets[2] <= 0xFFFF:
                return str(ipaddress.IPv4Address((octets[0] << 24) | (octets[1] << 16) | octets[2]))
            if len(octets) == 4 and all(0 <= o <= 255 for o in octets):
                return ".".join(str(o) for o in octets)
            return None
        except (ValueError, OverflowError):
            return None
    return None


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

    except Exception as e:
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
    except Exception as e:
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
        p = _ssrf_pins_path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_ssrf_pins(pins: dict) -> None:
    """Ghi pin atomic (tmp + rename). Lỗi ghi không chặn tool call."""
    try:
        p = _ssrf_pins_path()
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
        ipaddress.ip_address(host)
        return 0, ""
    except ValueError:
        pass
    if _decode_ip_encoding(host) is not None:
        return 0, ""

    ips, ok = _resolve_host(host)
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


# Patterns that are warned but allowed (exit 0 with stderr note)
WARN_PATTERNS = [
    (r"\bgit\s+push\b(?!.*--force)", "git push (not force)"),
    (r"\bnpm\s+publish\b", "npm publish"),
    (r"\bpip\s+install\b", "pip install"),
]


def _gate_error(gate_name: str, exc: Exception) -> None:
    """Security/resource gates fail closed on internal errors.

    An unexpected exception inside a gate must NOT silently allow the tool call.
    Default: block (exit 2). Opt-in fail-open via AHD_FAIL_OPEN=1 (same convention
    as the U52 timeout handling in main()).
    """
    print(f"[pre_tool_use] {gate_name} internal error: {exc}", file=sys.stderr)
    if os.environ.get("AHD_FAIL_OPEN", "0") == "1":
        print(
            f"[pre_tool_use] {gate_name} allowing on internal error (AHD_FAIL_OPEN=1).",
            file=sys.stderr,
        )
        return
    print(
        f"[pre_tool_use] {gate_name} FAILED CLOSED: blocked on internal error. "
        f"Set AHD_FAIL_OPEN=1 to allow.",
        file=sys.stderr,
    )
    sys.exit(2)


def _check_context_oversized_gate(data: dict) -> None:
    """Gate 1: context-oversized graduated enforcement.

    Checks .devin/context_flags/<session_id>.json for context_oversized flag.
    If set, responds based on how many tool calls have passed without compaction:
      - counter < WARN_THRESHOLD: allow + stderr note
      - WARN_THRESHOLD <= counter < BLOCK_THRESHOLD: allow + stderr warning
      - counter >= BLOCK_THRESHOLD: block non-compaction tools (exit 2)

    Compaction-safe tools (read, grep, write, etc.) are always allowed so the
    agent can actually run the context-compactor skill.
    """
    try:
        session_id = ahd_session.get_session_id(data)
        root = ahd_session.get_repo_root()
        flags = ahd_session.read_context_flags(session_id, root)

        if not flags.get("context_oversized"):
            return  # no flag -> no gate

        counter = flags.get("oversized_tool_calls_since_flag", 0)
        tool_name = data.get("tool_name", "")

        # Always allow compaction-safe tools — agent needs them to compact
        if tool_name in COMPACTION_SAFE_TOOLS:
            if counter >= OVERSIZED_WARN_THRESHOLD:
                print(
                    f"[Agent Harness Deploy] context_oversized: {counter} tool calls "
                    f"without compaction. You are using a compaction-safe tool — good. "
                    f"Continue compacting, then clear the flag.",
                    file=sys.stderr,
                )
            return

        # Non-compaction tool — graduated response
        if counter >= OVERSIZED_BLOCK_THRESHOLD:
            # Block: force the agent to compact before doing more work
            print(
                f"[Agent Harness Deploy] BLOCKED: context_oversized for {counter}+ tool calls "
                f"without compaction. Run the context-compactor skill first: "
                f"(1) offload large outputs to .devin/tmp/, keep head+tail+path. "
                f"(2) lower caveman_level to compact or ultra. "
                f"(3) clear context_oversized flag in "
                f".devin/context_flags/{session_id}.json. "
                f"Then retry this tool call.",
                file=sys.stderr,
            )
            sys.exit(2)
        elif counter >= OVERSIZED_WARN_THRESHOLD:
            print(
                f"[Agent Harness Deploy] WARNING: context_oversized for {counter} tool calls. "
                f"Compact NOW — run context-compactor skill before the next non-essential tool call. "
                f"At {OVERSIZED_BLOCK_THRESHOLD}+ calls, non-compaction tools will be BLOCKED.",
                file=sys.stderr,
            )
        else:
            print(
                f"[Agent Harness Deploy] NOTE: context_oversized detected. "
                f"Run context-compactor skill soon to offload large outputs.",
                file=sys.stderr,
            )
    except SystemExit:
        raise
    except Exception as e:
        _gate_error("context_oversized", e)


def _check_cost_cap_gate(data: dict) -> None:
    """T2.4: Kiểm tra cost cap trước khi gọi tool.

    - Dưới 80%: cho phép.
    - Từ 80% đến dưới 100%: in cảnh báo stderr, vẫn cho phép.
    - Đạt/vượt 100%: block (exit 2), set flag cost_cap_exceeded.

    CVE-2026-AHD-013: cumulative cost đọc từ append-only LEDGER
    (cost_ledger.py, HMAC-signed) — không tin session state (dễ bị sửa).
    Nếu ledger không cấu hình key -> fallback session state (legacy).
    """
    try:
        session_id = ahd_session.get_session_id(data)
        if not session_id:
            return

        root = ahd_session.get_repo_root()
        state = ahd_session.read_session_state(session_id, root)

        # CVE-2026-AHD-013: ưu tiên ledger đã verify (HMAC)
        try:
            from cost_ledger import cumulative_from_ledger
            ledger_cum = cumulative_from_ledger(root, session_id)
            if ledger_cum is not None:
                state["cumulative_cost"] = ledger_cum
        except (ImportError, ModuleNotFoundError, ValueError, TypeError):
            pass

        status = check_cost_cap(state)
        if status == 0:
            return

        cumulative = float(state.get("cumulative_cost", 0.0))
        cost_cap = float(state.get("cost_cap", 5.0))
        pct = (cumulative / cost_cap * 100) if cost_cap > 0 else 0

        if status == 2:
            print(
                f"[U17 COST CAP] BLOCKED: ${cumulative:.4f} >= ${cost_cap:.4f} cap "
                f"({pct:.0f}%). Stop escalation.",
                file=sys.stderr,
            )
            ahd_session.update_session_state(session_id, {
                "cost_cap_exceeded": True,
            }, root)
            sys.exit(2)

        # status == 1
        print(
            f"[U17 COST CAP] WARNING: ${cumulative:.4f} is {pct:.0f}% of ${cost_cap:.4f} cap.",
            file=sys.stderr,
        )
    except SystemExit:
        raise
    except Exception as e:
        _gate_error("cost_cap", e)


def _check_ssrf_gate(data: dict) -> None:
    """T2.9: Kiểm tra SSRF trong command hoặc các trường URL rõ ràng.

    - Trích URL từ command (Bash/Shell) và các trường URL rõ ràng (url, endpoint, host).
    - Bỏ qua content/new_string/old_string của Write/Edit để tránh false positive.
    - URL private/loopback/link-local -> block (exit 2) + ghi OTel log.
    """
    try:
        session_id = ahd_session.get_session_id(data)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}

        # Pentest fix: chỉ quét nguồn có khả năng chứa URL đích thực sự.
        sources: list[str] = []
        command = tool_input.get("command", "")
        if command:
            sources.append(command)
        # Các trường URL rõ ràng
        for url_field in ("url", "endpoint", "host", "base_url", "api_url"):
            value = tool_input.get(url_field, "")
            if isinstance(value, str) and value and value not in sources:
                sources.append(value)

        allowlist = _ssrf_allowlist()
        seen: set[str] = set()
        for text in sources:
            for url in _extract_urls(text):
                if url in seen:
                    continue
                seen.add(url)
                status = check_ssrf(url, allowlist)
                if status == 2:
                    print(
                        f"[U43/T2.9 SSRF guard] BLOCKED: {url} resolves to private/loopback/link-local.",
                        file=sys.stderr,
                    )
                    _log_ssrf_block(url, "private_or_internal_host", session_id)
                    sys.exit(2)
                # CVE-2026-AHD-008: DNS pinning — resolve + verify rebinding
                pin_status, reason = _pin_and_verify_url(url)
                if pin_status == 2:
                    print(
                        f"[CVE-2026-AHD-008 SSRF DNS pinning] BLOCKED: {url} ({reason}).",
                        file=sys.stderr,
                    )
                    _log_ssrf_block(url, reason, session_id)
                    sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:
        _gate_error("ssrf", e)


def _check_encoding_bypass_gate(data: dict) -> None:
    """T2.10 + CVE-2026-AHD-007: Phát hiện encoding bypass trong lệnh shell.

    CVE-2026-AHD-007 fix — detection order:
    1. Chạy detect_encoding_bypass TRÊN normalize_command() trước (payload
       decode-revealed như UTF-7 ẩn trong \\xNN bị lộ sau khi decode).
    2. Chạy tiếp trên command raw (escape gốc vẫn bị flag).
    3. analyze_shell_structure() bằng shlex: unbalanced quotes / quote
       breakout / control chars.
    4. HLK sanitizer patterns (redact_patterns) quét secret trong command.

    Block (exit 2) nếu BẤT KỲ detection nào có finding.
    """
    try:
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
            return

        command = tool_input.get("command", "")
        if not command:
            return

        # CVE-2026-AHD-007: ưu tiên phát hiện trên command ĐÃ normalize
        normalized = normalize_command(command)
        findings = detect_encoding_bypass(normalized)
        if not findings:
            findings = detect_encoding_bypass(command)

        # Phân tích cấu trúc shell (shlex)
        findings += analyze_shell_structure(command)

        # HLK sanitizer patterns — secret trong command
        hlk_hits = detect_hlk_secret(command)
        if findings or hlk_hits:
            detail = ", ".join(findings) if findings else ""
            if hlk_hits:
                detail = f"{detail}; hlk_secret({len(hlk_hits)} pattern)" if detail else f"hlk_secret({len(hlk_hits)} pattern)"
            print(
                f"[T2.10 Encoding bypass] BLOCKED: detected {detail}",
                file=sys.stderr,
            )
            sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:
        _gate_error("encoding_bypass", e)


def _check_reflection_gate(data: dict) -> None:
    """T4.9: Reflection gate — đánh giá action trước khi thực hiện.

    Phát hiện action destructive (delete, force_push, drop, reset_hard) qua
    reflection_gate.check_reflection. Nếu block -> exit 2 + yêu cầu human confirm.
    Không thực hiện destructive op — chỉ cảnh báo/block.
    """
    if _check_reflection is None:
        return
    try:
        tool_input = data.get("tool_input", {}) or {}
        # Xây action input từ tool_input: category suy ra từ tool_name + command pattern
        tool_name = data.get("tool_name", "")
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

        # Chỉ áp dụng cho Bash/shell (nơi có thể có destructive op)
        if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
            return
        if not command:
            return

        # Suy ra category từ command pattern (dùng normalized command để phát hiện đúng cờ).
        category = "read"
        destructive = False
        cmd_lower = normalize_command(command).lower()
        # Chỉ coi là delete nguy hiểm khi rm có cả -r và -f hoặc các dạng tương đương.
        if "rm -rf" in cmd_lower or "rm -fr" in cmd_lower or "del /f" in cmd_lower or "rmdir" in cmd_lower:
            category = "delete"
            destructive = True
        elif "git push --force" in cmd_lower or "git push -f" in cmd_lower:
            category = "force_push"
            destructive = True
        elif "drop table" in cmd_lower or "drop database" in cmd_lower or "drop schema" in cmd_lower:
            category = "drop"
            destructive = True
        elif "git reset --hard" in cmd_lower:
            category = "reset_hard"
            destructive = True
        elif command.strip().startswith(("curl", "wget")):
            category = "external_call"
        elif command.strip().startswith(("write", "edit")) or " > " in command or " >> " in command:
            category = "write"
        else:
            # Không phải action cần reflection -> skip
            return

        action_input = {
            "id": f"pre_tool_{tool_name}",
            "category": category,
            "target": command[:512],
            "args": {},
            "destructive": destructive,
        }
        # CVE-2026-AHD-014: verdict theo schema chuẩn + input đã sanitize
        try:
            from reflection_gate import verdict_to_dict, sanitize_action_input
            action_input = sanitize_action_input(action_input)
        except (ImportError, ModuleNotFoundError):
            pass
        verdict = _check_reflection(action_input)
        if verdict is None:
            return
        if verdict.block:
            print(
                f"[T4.9 Reflection gate] BLOCKED: {verdict.reason}",
                file=sys.stderr,
            )
            if verdict.human_confirm_required:
                print(
                    "[T4.9 Reflection gate] Human confirm required before executing.",
                    file=sys.stderr,
                )
            sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:
        _gate_error("reflection", e)


def _check_risk_contract(tool_name: str, tool_input: dict) -> None:
    """U28: Warn on critical file modifications per risk_contract.json.

    Non-blocking — only logs warning to stderr. Does not deny the tool call.
    """
    write_tools = {"Write", "write", "Edit", "edit", "notebook_edit", "NotebookEdit"}
    if tool_name not in write_tools:
        return

    file_path = ""
    for key in ("file_path", "path", "notebook_path", "file"):
        if key in tool_input:
            file_path = tool_input[key]
            break
    if not file_path:
        return

    try:
        root = ahd_session.get_repo_root()
        contract_path = root / ".devin" / "risk_contract.json"
        if not contract_path.exists():
            return

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        critical_files = contract.get("critical_files", {})

        # Normalize path for matching
        norm_path = str(file_path).replace("\\", "/")
        for pattern, rules in critical_files.items():
            norm_pattern = pattern.replace("\\", "/")
            if norm_pattern in norm_path or norm_path.endswith(norm_pattern):
                risk = rules.get("risk", "unknown")
                review = rules.get("required_review", "self")
                print(
                    f"[U28 Risk Contract] WARNING: Modifying critical file "
                    f"{file_path} (risk: {risk}, review: {review})",
                    file=sys.stderr,
                )
                return
    except Exception as e:
        print(f"[pre_tool_use] unexpected exception in _check_risk_contract: {e}", file=sys.stderr)
        # Non-blocking warning-only gate — never denies the tool call.


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
        # U42: Fail-closed mode — exit 2 on parse error if configured
        fail_closed = os.environ.get("AHD_FAIL_CLOSED", "0") == "1"
        if fail_closed:
            print("[U42 Fail-closed] stdin parse error — blocking.", file=sys.stderr)
            sys.exit(2)
        # Can't parse input — allow (don't block on parse failure)
        sys.exit(0)

    # Gate 1: context-oversized enforcement (all tools)
    _check_context_oversized_gate(data)

    # Gate 1.4: T2.4 — Cost cap enforcement (pre-tool-use)
    if check_cost_cap is not None:
        _check_cost_cap_gate(data)

    # Gate 1.5: U28 — Risk contract check for critical file modifications
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    _check_risk_contract(tool_name, tool_input)

    # Gate 1.6: T2.9 — SSRF guard
    _check_ssrf_gate(data)

    # Gate 1.7: T2.10 — Encoding bypass guard
    _check_encoding_bypass_gate(data)

    # Gate 2: dangerous-command check (Bash/shell only)
    # tool_name + tool_input already extracted above (Gate 1.5)

    if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
        sys.exit(0)

    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Normalize before pattern matching (U02: fix regex bypass via shell encoding)
    normalized = normalize_command(command)

    # Check dangerous patterns against BOTH raw and normalized command
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE) or \
           re.search(pattern, normalized, re.IGNORECASE):
            print(f"[Agent Harness Deploy guard] BLOCKED: {reason}", file=sys.stderr)
            print(f"Command: {command[:200]}", file=sys.stderr)
            print(f"Pattern: {pattern}", file=sys.stderr)
            sys.exit(2)

    # Gate 2.1: T4.9 — Reflection gate (pre-action reflection, multi-level)
    # Chạy sau dangerous-pattern gate để giữ thông báo quen thuộc cho các lệnh
    # destructive đã được nhận diện; reflection gate bổ sung cho trường hợp còn lại.
    _check_reflection_gate(data)

    # Check warn patterns (allow but note)
    for pattern, reason in WARN_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            print(f"[Agent Harness Deploy guard] NOTE: {reason} — proceed carefully", file=sys.stderr)
            break

    sys.exit(0)


if __name__ == "__main__":
    # U52: Fail-closed default — block on timeout unless AHD_FAIL_OPEN=1.
    # Previous behavior (U15): fail open. New default: fail closed for security.
    # Set env AHD_FAIL_OPEN=1 to restore old fail-open behavior.
    result = {"code": 0}

    def _run():
        try:
            main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception as e:
            # U52: fail-closed on unexpected error too (was fail-open)
            print(f"[pre_tool_use] unexpected exception: {e}", file=sys.stderr)
            fail_open = os.environ.get("AHD_FAIL_OPEN", "0") == "1"
            result["code"] = 0 if fail_open else 2

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        # U52: Timeout — fail closed by default, fail open only if AHD_FAIL_OPEN=1
        fail_open = os.environ.get("AHD_FAIL_OPEN", "0") == "1"
        if fail_open:
            print("[pre_tool_use] U52 timeout — allowing (AHD_FAIL_OPEN=1)", file=sys.stderr)
            sys.exit(0)
        else:
            print("[pre_tool_use] U52 timeout — blocking (fail-closed default)", file=sys.stderr)
            sys.exit(2)
    sys.exit(result["code"])
