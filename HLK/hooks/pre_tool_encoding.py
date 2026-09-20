#!/usr/bin/env python3
"""pre_tool_encoding.py — Phát hiện encoding bypass / cấu trúc shell khả nghi.

Tách từ pre_tool_use.py (plan refactor-long-files, section 2.13).
Giữ nguyên API công khai:
  - detect_encoding_bypass(text) -> list[str]
  - analyze_shell_structure(command) -> list[str]
  - normalize_command(command) -> str
  - _decode_ip_encoding(host) -> str | None
"""
import ipaddress
import re
import shlex


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
