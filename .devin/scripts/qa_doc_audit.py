#!/usr/bin/env python3
"""Audit docs/source cross-references.

Quét toàn bộ file .md trong repo, tìm:
- Markdown links [x](path) / [x]: path
- Inline code paths (`path`) có vẻ là file/thư mục
- References tới scripts, hooks, skills, agents, canon, tools, tests
- Stale patterns (.claude/skills, scripts/verify.py, v.v.)

Xuất báo cáo JSON.
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

# Ép stdout/stderr dùng UTF-8 (tránh lỗi cp1258 trên Windows console với tiếng Việt)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

MD_GLOB = ["*.md", ".devin/**/*.md", "docs/**/*.md", ".devin/**/*.json"]

# Loại trừ các file log/report/plan — chứa references hợp lệ từ quá khứ hoặc từ upstream
EXCLUDE_GLOB = [
    ".devin/metadata/**",
    ".devin/reports/**",
    ".devin/prompts/**",
    ".devin/plan_state/**",
    ".devin/upgrade/**",
    ".devin/skills/nuwa-skill/**",
    "docs/plans/**",
    "docs/*_full*.md",
    "docs/research/**",
    "REPOS.md",
    "REPOS_TRACKER.json",
]

# Các pattern cần cảnh báo là stale
STALE_PATTERNS = {
    r"\.claude[/\\]skills": ".claude/skills → moved to .claude/skills-disabled or .devin/skills",
    r"\.agents[/\\]skills(?![-])": ".agents/skills → moved to .agents/skills-disabled",
    r"(?<![/\\])scripts/verify\.py": "scripts/verify.py → removed; use tools/verify-workspace.ps1",
    r"(?<![/\\])scripts/detect\.py": "scripts/detect.py → removed",
    r"(?<![/\\])scripts/distill\.py": "scripts/distill.py → removed",
    r"(?<![/\\])scripts/run\.py": "scripts/run.py → removed",
    r"\bdistil[l]?[/\\]": "distill/ → removed or not integrated in this workspace",
    r"\bv3/": "v3/ source removed",
    r"\bplugins/": "plugins/ removed",
    r"\bruflo/": "ruflo/ source removed",
    r"\b\.claude-flow/": ".claude-flow/ removed",
    r"\bDocs/09-Multi-Thinking-Modes\.md": "Docs/ → use docs/ (lowercase)",
    r"\bDocs/Agents/": "Docs/Agents/ → use docs/Agents/ (lowercase)",
}

# Các đường dẫn runtime hoặc optional được phép không tồn tại
IGNORE_PATHS = {
    ".agents/handoff_letter.md",
}

# Hardcoded platform paths cấm xuất hiện trong config (R-02): nvm version cứng,
# AppData trực tiếp, USER_HOME cứng. Thay bằng {{AIDE_MEMORY_GLOBAL}} placeholder.
HARDCODED_PATH_PATTERNS = {
    r"nvm\\v\d+\.\d+\.\d+": "nvm version hardcoded in config → use {{AIDE_MEMORY_GLOBAL}} placeholder",
    r"AppData\\Roaming\\nvm": "nvm AppData path hardcoded in config → use {{AIDE_MEMORY_GLOBAL}} placeholder",
}

# Các file config phải sạch hardcoded paths
HARDCODED_CONFIG_GLOBS = [
    ".devin/config.json",
    ".devin/mcp_config.json",
]

# Các đường dẫn cần verify tồn tại
PATH_PREFIXES = (
    ".devin/scripts/",
    ".devin/hooks/",
    ".devin/skills/",
    ".devin/agents/",
    ".devin/canon/",
    ".devin/rules/",
    "tools/",
    "tests/",
    "docs/",
    "src/",
)


_KNOWN_EXTENSIONS = (".py", ".md", ".json", ".yml", ".yaml", ".toml", ".ps1", ".sh", ".js", ".mjs", ".cjs", ".ts", ".tsx")


def _is_pathlike(token: str) -> bool:
    if not token or len(token) < 2:
        return False
    # Bỏ qua token chỉ là dấu câu / ký tự đơn
    if token in (".", "..", "...", "~"):
        return False
    # Bỏ qua nếu có khoảng trắng mà không phải command chứa path rõ ràng
    if " " in token and not any(p in token for p in PATH_PREFIXES):
        return False
    if any(token.startswith(p) for p in PATH_PREFIXES):
        return True
    if "/" in token or "\\" in token:
        # Có dấu phân cách và kết thúc bằng ext
        if any(token.lower().endswith(ext) for ext in _KNOWN_EXTENSIONS):
            return True
    return False


def _resolve_candidate(src: Path, candidate: str) -> Path | None | bool:
    """Resolve candidate path dưới repo root.
    Trả resolved Path nếu tồn tại, False nếu được bỏ qua, None nếu missing."""
    candidate = candidate.strip("\n`\"'<>()")
    if not candidate:
        return None

    # Bỏ qua placeholders như <session_id>, <name>
    if re.search(r"<[^>]+>", candidate):
        return False

    # Bỏ qua glob patterns vì chúng là mẫu, không phải path cụ thể
    if any(c in candidate for c in "*?["):
        return False

    # Bỏ qua các path runtime/optional đã biết
    if candidate in IGNORE_PATHS:
        return False

    # Nếu có dấu cách, thử tìm component là file path trong command
    candidates = [candidate]
    if " " in candidate:
        candidates = re.split(r"\s+", candidate)

    for cand in candidates:
        # Bỏ query/anchor
        cand = cand.split("#")[0].split("?")[0]
        # Nếu là URL → bỏ qua
        if cand.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # Nếu bắt đầu bằng / tuyệt đối → xem như ngoài repo
        if cand.startswith("/"):
            continue
        # Nếu bắt đầu bằng ký tự ổ đĩa → tuyệt đối
        if len(cand) > 2 and cand[1] == ":":
            continue

        # Tự động thêm .md nếu thiếu cho thư mục con của .devin/skills/ hoặc .devin/agents/
        variants = [cand]
        if cand.startswith((".devin/skills/", ".devin/agents/", ".devin/canon/")) and "." not in Path(cand).name:
            variants.append(cand.rstrip("/") + "/SKILL.md" if cand.startswith(".devin/skills/") else cand.rstrip("/") + "/AGENT.md")

        for v in variants:
            p = Path(v)
            if p.is_absolute():
                continue
            for base in [REPO_ROOT, src.parent]:
                resolved = (base / p).resolve()
                if resolved.exists():
                    return resolved
    return None


def _extract_markdown_links(text: str) -> list[str]:
    refs = []
    # [text](url)
    refs += re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", text)
    # [text]: url (reference link)
    refs += re.findall(r"^\[[^\]]+\]:\s*(.+)$", text, re.MULTILINE)
    return [r if isinstance(r, str) else r[1] for r in refs]


def _extract_inline_paths(text: str) -> list[str]:
    # Các đoạn trong backticks
    tokens = re.findall(r"`([^`]+)`", text)
    return [t for t in tokens if _is_pathlike(t)]


def _extract_plain_refs(text: str) -> list[tuple[int, str, str]]:
    """Tìm references theo pattern trong văn bản."""
    findings = []
    for pat, reason in STALE_PATTERNS.items():
        for m in re.finditer(pat, text):
            findings.append((m.start(), m.group(0), reason))
    return findings


def _audit_hardcoded_configs() -> list[dict]:
    """Quét configs tìm hardcoded platform paths (R-02)."""
    findings = []
    for glob in HARDCODED_CONFIG_GLOBS:
        for cfg_path in REPO_ROOT.glob(glob):
            try:
                text = cfg_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pat, reason in HARDCODED_PATH_PATTERNS.items():
                for m in re.finditer(pat, text):
                    findings.append({
                        "file": str(cfg_path.relative_to(REPO_ROOT)),
                        "match": m.group(0),
                        "reason": reason,
                    })
    return findings


def _should_exclude(md: Path) -> bool:
    rel = str(md.relative_to(REPO_ROOT)).replace("\\", "/")
    for pat in EXCLUDE_GLOB:
        norm_pat = pat.replace("\\", "/")
        if norm_pat.endswith("/**"):
            prefix = norm_pat[:-3]
            if rel == prefix or rel.startswith(prefix + "/"):
                return True
        elif fnmatch.fnmatch(rel, norm_pat) or fnmatch.fnmatch(rel, f"**/{norm_pat}"):
            return True
    return False


def audit() -> dict:
    all_md = set()
    for pattern in MD_GLOB:
        all_md.update(REPO_ROOT.glob(pattern))

    broken_links = []
    missing_paths = []
    stale_refs = []
    checked = set()
    for md in sorted(all_md):
        if _should_exclude(md):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            print(f"[WARN] Encoding lỗi trong {md}: {e}", file=sys.stderr)
            text = md.read_text(encoding="utf-8", errors="replace")

        # Markdown links
        for ref in _extract_markdown_links(text):
            if isinstance(ref, tuple):
                ref = ref[1]
            resolved = _resolve_candidate(md, ref)
            if resolved is False:
                continue
            if resolved is None and not ref.startswith(("http", "#", "mailto:")):
                missing_paths.append({
                    "file": str(md.relative_to(REPO_ROOT)),
                    "type": "markdown_link",
                    "target": ref,
                })

        # Inline code paths
        for token in _extract_inline_paths(text):
            if token in checked:
                continue
            checked.add(token)
            resolved = _resolve_candidate(md, token)
            if resolved is False:
                continue
            if resolved is None:
                missing_paths.append({
                    "file": str(md.relative_to(REPO_ROOT)),
                    "type": "inline_path",
                    "target": token,
                })

        # Stale patterns
        for _, match, reason in _extract_plain_refs(text):
            stale_refs.append({
                "file": str(md.relative_to(REPO_ROOT)),
                "match": match,
                "reason": reason,
            })

    return {
        "scanned_files": len(all_md),
        "missing_paths": missing_paths,
        "stale_refs": stale_refs,
        "hardcoded_paths": _audit_hardcoded_configs(),
    }


def main() -> int:
    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
