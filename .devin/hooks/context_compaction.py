#!/usr/bin/env python3
"""Context Compaction Hook — auto-compacts session/loop state when oversized.

Triggered by post_tool_use when context_oversized flag is set.
Integrates with Caveman protocol (4 compression levels).
Stores compacted state, offloads full payload to filesystem.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Compression levels
COMPRESSION_LEVELS = {
    "light": {
        "patterns": [
            (r"\b(leveraging|utilizing|facilitating|comprehensive|seamless)\b", ""),
            (r"\b(it['']s worth noting that|it should be noted that)\b", ""),
            (r"\b(delve into|dive deep into|explore in detail)\b", ""),
            (r"\b(robust|scalable|enterprise-grade|production-ready)\b", ""),
            (r"\b(in order to|please note|additionally|importantly|essentially)\b", ""),
            (r"\s+", " "),
        ],
        "target_reduction": 0.20,
    },
    "full": {
        "patterns": [
            (r"\b(leveraging|utilizing|facilitating|comprehensive|seamless)\b", ""),
            (r"\b(it['']s worth noting that|it should be noted that)\b", ""),
            (r"\b(delve into|dive deep into|explore in detail)\b", ""),
            (r"\b(robust|scalable|enterprise-grade|production-ready)\b", ""),
            (r"\b(in order to|please note|additionally|importantly|essentially)\b", ""),
            (r"\b(the|a|an)\s+(?=\w)", ""),  # drop some articles
            (r"\s+", " "),
        ],
        "target_reduction": 0.40,
    },
    "ultra": {
        "patterns": [
            (r"\b(leveraging|utilizing|facilitating|comprehensive|seamless)\b", ""),
            (r"\b(it['']s worth noting that|it should be noted that)\b", ""),
            (r"\b(delve into|dive deep into|explore in detail)\b", ""),
            (r"\b(robust|scalable|enterprise-grade|production-ready)\b", ""),
            (r"\b(in order to|please note|additionally|importantly|essentially)\b", ""),
            (r"\b(configuration|verification|implementation|initialization|operation)\b",
             lambda m: {"configuration": "config", "verification": "verify",
                        "implementation": "impl", "initialization": "init",
                        "operation": "op"}[m.group(1).lower()]),
            (r"\b(I|we|you|they|he|she|it)\s+(found|found|saw|see|see|noticed|notice|fixed|fix|resolved|resolve)\b",
             r"\2"),
            (r"\b(the|a|an)\s+(?=\w)", ""),
            (r"\s+", " "),
        ],
        "target_reduction": 0.65,
    },
    "wenyan": {
        "patterns": [
            # Classical Chinese abbreviations - keep verbatim items
        ],
        "target_reduction": 0.75,
    },
}

# Items that must NEVER be compressed (verbatim preservation)
PRESERVE_PATTERNS = [
    r"(?:^|\s)([A-Za-z0-9_./-]+\.(?:py|js|ts|json|md|txt|yaml|yml|toml|ini|conf|config))",  # file paths
    r"(?:^|\s)(\d+)",  # line numbers
    r"(?:^|\s)(ERROR|FATAL|CRITICAL|WARNING|FAILED|PASS)\b",  # error/status keywords
    r"(?:^|\s)(http[s]?://\S+)",  # URLs
    r"(?:^|\s)(ghp_|sk-|AIzaSy|npm_|xox[a-z])\w+",  # API keys (partial)
    r"(?:^|\s)(\w+\(\))",  # function calls
    r"`[^`]+`",  # inline code
]


def _estimate_tokens(text: str) -> int:
    """Estimate tokens: ~4 chars per token."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _preserve_verbatim(text: str) -> tuple[str, list[str]]:
    """Extract and preserve verbatim items, replace with placeholders."""
    preserved = []
    placeholder_map = {}

    def make_placeholder(item: str) -> str:
        placeholder = f"__PRESERVED_{len(preserved)}__"
        preserved.append(item)
        placeholder_map[placeholder] = item
        return placeholder

    result = text
    for pattern in PRESERVE_PATTERNS:
        for match in re.finditer(pattern, result):
            item = match.group(1) if match.groups() else match.group(0)
            if item not in placeholder_map.values():
                placeholder = make_placeholder(item)
                result = result.replace(item, placeholder, 1)

    return result, preserved


def _restore_verbatim(text: str, preserved: list[str]) -> str:
    """Restore preserved items from placeholders."""
    result = text
    for i, item in enumerate(preserved):
        placeholder = f"__PRESERVED_{i}__"
        result = result.replace(placeholder, item)
    return result


def _apply_compression(text: str, level: str) -> str:
    """Apply compression rules for a given level."""
    if level not in COMPRESSION_LEVELS:
        level = "light"

    rules = COMPRESSION_LEVELS[level]
    result = text

    for pattern, replacement in rules["patterns"]:
        if callable(replacement):
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        else:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result.strip()


def _compress_text(text: str, level: str = "full") -> tuple[str, dict]:
    """Compress text with verbatim preservation."""
    original_tokens = _estimate_tokens(text)

    # Extract and preserve verbatim items
    text_with_placeholders, preserved = _preserve_verbatim(text)

    # Apply compression
    compressed = _apply_compression(text_with_placeholders, level)

    # Restore verbatim items
    final = _restore_verbatim(compressed, preserved)

    compressed_tokens = _estimate_tokens(final)
    reduction_pct = ((original_tokens - compressed_tokens) / original_tokens * 100) if original_tokens > 0 else 0

    return final, {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "reduction_pct": round(reduction_pct, 1),
        "preserved_count": len(preserved),
        "level": level,
    }


def _get_session_root(root: Path, session_id: str) -> Path:
    """Get session-specific compaction directory."""
    out_dir = root / ".devin" / "session_state" / session_id / "compaction"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _offload_full_context(root: Path, session_id: str, original_content: str, metadata: dict) -> str:
    """Store full context to filesystem, return reference handle."""
    session_root = _get_session_root(root, session_id)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = session_root / f"full_context_{timestamp}.json"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "content": original_content,
        "metadata": metadata,
        "size_chars": len(original_content),
    }

    try:
        file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[context_compaction] Failed to offload: {e}", file=sys.stderr)
        return ""

    return str(file_path)


def _compact_session_state(root: Path, session_id: str, level: str = "full") -> dict | None:
    """Compact session_state JSON."""
    state_path = root / ".devin" / "session_state" / f"{session_id}.json"
    if not state_path.exists():
        return None

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        original = json.dumps(state, ensure_ascii=False, indent=2)
        compressed, stats = _compress_text(original, level)

        # Offload full state
        offload_path = _offload_full_context(root, session_id, original, {"type": "session_state", "level": level})

        # Write compacted state
        compacted_state = json.loads(compressed)
        compacted_state["_compaction"] = {
            "level": level,
            "original_tokens": stats["original_tokens"],
            "compressed_tokens": stats["compressed_tokens"],
            "reduction_pct": stats["reduction_pct"],
            "offload_path": offload_path,
            "compacted_at": datetime.now(timezone.utc).isoformat(),
        }
        state_path.write_text(json.dumps(compacted_state, ensure_ascii=False, indent=2), encoding="utf-8")

        return stats
    except Exception as e:
        print(f"[context_compaction] Session state compaction failed: {e}", file=sys.stderr)
        return None


def _compact_loop_state(root: Path, session_id: str, level: str = "full") -> dict | None:
    """Compact loop_state markdown."""
    state_path = root / ".devin" / "loop_state" / f"{session_id}.md"
    if not state_path.exists():
        return None

    try:
        content = state_path.read_text(encoding="utf-8")
        compressed, stats = _compress_text(content, level)

        # Offload full state
        offload_path = _offload_full_context(root, session_id, content, {"type": "loop_state", "level": level})

        # Write compacted state with compaction header
        header = f"<!-- COMPACTED: L{level[0].upper()} | {stats['reduction_pct']}% saved | Offloaded to {offload_path} -->\n"
        state_path.write_text(header + compressed, encoding="utf-8")

        return stats
    except Exception as e:
        print(f"[context_compaction] Loop state compaction failed: {e}", file=sys.stderr)
        return None


def _clear_context_flag(root: Path, session_id: str) -> None:
    """Clear the context_oversized flag after compaction."""
    flag_path = root / ".devin" / "context_flags" / f"{session_id}.json"
    if flag_path.exists():
        try:
            flag_path.write_text(json.dumps({"context_oversized": False, "cleared_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("Usage: context_compaction_hook.py <session_id> [level]", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1]
    level = sys.argv[2] if len(sys.argv) > 2 else "full"

    # Find repo root
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        root = Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else Path.cwd()
    except Exception:
        root = Path.cwd()

    print(f"[context_compaction] Compacting session {session_id} at level {level}", file=sys.stderr)

    # Compact session state
    session_stats = _compact_session_state(root, session_id, level)

    # Compact loop state
    loop_stats = _compact_loop_state(root, session_id, level)

    # Clear oversized flag
    _clear_context_flag(root, session_id)

    # Report
    if session_stats:
        print(f"  Session state: {session_stats['original_tokens']} → {session_stats['compressed_tokens']} tokens ({session_stats['reduction_pct']}% saved)", file=sys.stderr)
    if loop_stats:
        print(f"  Loop state: {loop_stats['original_tokens']} → {loop_stats['compressed_tokens']} tokens ({loop_stats['reduction_pct']}% saved)", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    import os
    main()