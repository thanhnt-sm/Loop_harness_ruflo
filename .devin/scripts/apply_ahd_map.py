#!/usr/bin/env python3
"""
apply_ahd_map.py — Path mapping và protected patterns cho AHD patch.

Chứa: PATH_MAP, PROTECTED_PATTERNS, SKIP_UPSTREAM_DIRS, RISKY_NEW_DIRS,
      map_path, is_protected, _glob_match, is_upstream_skip, is_risky_new.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import update_common


REPO_ROOT = update_common.REPO_ROOT

TRACKER_PATH = REPO_ROOT / ".devin" / "metadata" / "REPOS_TRACKER.json"


# Ánh xạ cấu trúc upstream -> local
# Hỗ trợ cả layout cũ (distill/, scripts/, adapters/) và layout mới (.devin/)
PATH_MAP: dict[str, str] = {
    # Layout mới: .devin/ pass-through
    ".devin/canon/": ".devin/canon/",
    ".devin/skills/": ".devin/skills/",
    ".devin/agents/workers/": ".devin/agents/workers/",
    ".devin/agents/": ".devin/agents/",
    ".devin/scripts/": ".devin/scripts/",
    ".devin/hooks/": ".devin/hooks/",
    ".devin/adapters/": ".devin/adapters/",
    # Layout cũ: distill/ etc.
    "distill/canon/": ".devin/canon/",
    "distill/skills/": ".devin/skills/",
    "distill/orchestrator/workers/": ".devin/agents/workers/",
    "distill/orchestrator/": ".devin/agents/",
    "distill/agents/": ".devin/agents/",
    "scripts/": ".devin/scripts/",
    "core/assets/runtime/hooks/": ".devin/hooks/",
    "adapters/": ".devin/adapters/",
}

# File/thư mục tuyệt đối không được đụng
PROTECTED_PATTERNS = [
    ".env",
    "*.pem",
    "*.key",
    "secrets/*",
    "credentials/*",
    "HLK/*",
    ".devin/hooks/",
    ".devin/config.json",
    ".devin/mcp_config.json",
    ".devin/canon/BOOT_PROTOCOL.md",
    ".devin/canon/CORE_CANON.md",
    ".devin/canon/REDLINES.md",
    ".devin/AGENTS.md",
    ".devin/AGENTS_full.md",
    ".claude/settings.json",
    ".gitignore",
    ".gitattributes",
]

# Các thư mục upstream chỉ là docs/promo, không deploy
SKIP_UPSTREAM_DIRS = ["Docs/", "README", "promo/", ".github/"]

# Các thư mục không được tạo file mới
RISKY_NEW_DIRS = [".devin/adapters/", ".devin/scripts/", ".devin/tests/"]


def _glob_match(name: str, pat: str) -> bool:
    """fnmatch đơn giản hỗ trợ * và ?."""
    pat = pat.replace(".", r"\.")
    pat = pat.replace("*", ".*")
    pat = pat.replace("?", ".")
    return bool(re.fullmatch(pat, name))


def map_path(rel: str, repo_root: Path = REPO_ROOT) -> str | None:
    """Ánh xạ đường dẫn upstream sang local, chuẩn hóa và chặn path traversal."""
    root = repo_root.resolve()
    for up, loc in PATH_MAP.items():
        if rel.startswith(up):
            mapped = loc + rel[len(up):]
            resolved = (root / mapped).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                print(f"[WARN] path traversal blocked: {rel} -> {mapped}")
                return None
            return mapped
    if rel in ("AGENTS.md", ".devin/AGENTS.md"):
        resolved = (root / ".devin" / "AGENTS.md").resolve()
        return str(resolved.relative_to(root)).replace("\\", "/")
    return None


def is_protected(path: str, protected: list[str]) -> bool:
    """Kiểm tra path có thuộc protected patterns không, dùng path đã chuẩn hóa."""
    norm = Path(path).as_posix().lower()
    for p in protected:
        pl = p.lower()
        # Hỗ trợ glob cơ bản: *, ?
        if any(c in pl for c in "*?"):
            if _glob_match(norm, pl):
                return True
            continue
        if pl.endswith("/**"):
            prefix = pl[:-3]
            if norm == prefix or norm.startswith(prefix + "/"):
                return True
        elif norm == pl or norm.startswith(pl + "/") or norm.endswith("/" + pl) or "/" + pl in norm:
            return True
    return False


def is_upstream_skip(rel: str) -> bool:
    """Kiểm tra file upstream có nên skip không."""
    for d in SKIP_UPSTREAM_DIRS:
        if rel.startswith(d) or rel == d.rstrip("/"):
            return True
    return False


def is_risky_new(target: str) -> bool:
    """Kiểm tra target có nằm trong thư mục rủi ro không."""
    for d in RISKY_NEW_DIRS:
        if target.startswith(d):
            return True
    return False


def get_protected_files() -> list[str]:
    """Lấy danh sách protected files từ tracker + PROTECTED_PATTERNS."""
    data = update_common.load_tracker(TRACKER_PATH)
    for s in data.get("sources", []):
        if s.get("id") == "ahd-main-engine":
            return list(set(s.get("protected_files", []) + PROTECTED_PATTERNS))
    return PROTECTED_PATTERNS