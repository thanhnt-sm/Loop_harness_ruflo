#!/usr/bin/env python3
"""Context Compaction Hook — auto-compacts session/loop state when oversized.

Triggered by post_tool_use when context_oversized flag is set.
Integrates with Caveman protocol (4 compression levels).
Stores compacted state, offloads full payload to filesystem.

Extended with P1-04: Adaptive WM + Prefix-Cache Compaction
- Auto WM budget from context window (adapts on model swap)
- Prefix-cache aware: static system prompt + pinned memory
- Pressure-based compaction (not turn count)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# P1-04: Import config constants
try:
    from post_tool_config import (
        MODEL_CONTEXT_WINDOWS,
        WM_BUDGET_FRACTION,
        RESERVED_TOKENS_HEADROOM_PCT,
        COMPACT_AT_CONTEXT_FRACTION,
        RETAIN_CONTEXT_FRACTION,
        PREFIX_CACHE_ITEMS,
    )
except ImportError:
    # Fallback defaults
    MODEL_CONTEXT_WINDOWS = {
        "default": 8192,
        "glm-5.2": 200000,
        "kimi-k2.7": 128000,
        "lightning": 200000,
        "small": 8192,
    }
    WM_BUDGET_FRACTION = 0.8
    RESERVED_TOKENS_HEADROOM_PCT = 0.20
    COMPACT_AT_CONTEXT_FRACTION = 0.5
    RETAIN_CONTEXT_FRACTION = 0.15
    PREFIX_CACHE_ITEMS = ["system_prompt", "pinned_memory", "tool_schemas"]

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


# ============================================================================
# P1-04: Adaptive WM + Prefix-Cache Compaction
# ============================================================================

@dataclass
class AdaptiveWM:
    """Auto Working Memory budget from context window.

    Adapts automatically when model is swapped:
    - 8K model → ~6K WM (80% of 8K - 20% headroom)
    - 200K model → ~128K WM (80% of 200K - 20% headroom)
    """
    model: str = "default"
    window_size: int = 8192
    reserved_tokens: int = 0  # system prompt + pinned memory + tool schemas (user-set, capped at headroom)

    def __post_init__(self):
        self.window_size = MODEL_CONTEXT_WINDOWS.get(self.model, 8192)

    @property
    def reserved_budget(self) -> int:
        """Reserved tokens for system prompt, pinned memory, tool schemas (20% headroom cap)."""
        return int(self.window_size * RESERVED_TOKENS_HEADROOM_PCT)

    @property
    def wm_budget(self) -> int:
        """WM budget = 80% of (window - reserved_budget)."""
        available = max(0, self.window_size - self.reserved_budget)
        return int(available * WM_BUDGET_FRACTION)

    @property
    def total_budget(self) -> int:
        """Total context budget (WM + reserved_budget)."""
        return self.wm_budget + self.reserved_budget

    @property
    def usage_pct(self) -> float:
        """Current usage as percentage of window."""
        if self.window_size == 0:
            return 0.0
        return (self.wm_budget + self.reserved_tokens) / self.window_size * 100

    def set_model(self, model: str) -> None:
        """Switch model and recalculate budget."""
        self.model = model
        self.window_size = MODEL_CONTEXT_WINDOWS.get(model, 8192)

    def set_reserved(self, tokens: int) -> None:
        """Set reserved tokens (system prompt + pinned memory + tool schemas)."""
        self.reserved_tokens = min(tokens, int(self.window_size * RESERVED_TOKENS_HEADROOM_PCT))

    def should_compact(self, current_usage: int) -> bool:
        """Check if compaction should trigger based on pressure (not turn count)."""
        threshold = int(self.window_size * COMPACT_AT_CONTEXT_FRACTION)
        return current_usage >= threshold


class PrefixCache:
    """Prefix-cache aware compaction — keeps pinned items byte-identical.

    Ensures warm cache hits by preserving:
    - system_prompt: static identity + tools
    - pinned_memory: critical facts
    - tool_schemas: tool definitions
    """
    def __init__(self):
        self._pinned: dict[str, str] = {}
        self._lock = threading.Lock()

    def pin(self, key: str, value: str) -> None:
        """Pin a prefix item (must remain byte-identical)."""
        if key in PREFIX_CACHE_ITEMS:
            with self._lock:
                self._pinned[key] = value

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._pinned.get(key)

    def get_all_pinned(self) -> dict[str, str]:
        with self._lock:
            return self._pinned.copy()

    def prefix_hash(self) -> str:
        """Compute hash of all pinned items for cache validation."""
        with self._lock:
            content = "".join(f"{k}:{v}" for k, v in sorted(self._pinned.items()))
            return hashlib.sha256(content.encode()).hexdigest()[:16]

    def is_stable(self, previous_hash: str) -> bool:
        """Check if prefix cache is stable (unchanged)."""
        return self.prefix_hash() == previous_hash

    def clear(self) -> None:
        with self._lock:
            self._pinned.clear()


class PressureCompactor:
    """Compacts by context-size pressure, not turn count.

    Triggers at COMPACT_AT_CONTEXT_FRACTION (50%),
    retains RETAIN_CONTEXT_FRACTION (15%) newest verbatim.
    """
    def __init__(self, wm: AdaptiveWM, prefix_cache: PrefixCache):
        self.wm = wm
        self.prefix_cache = prefix_cache
        self._previous_prefix_hash: str | None = None

    def compact_if_needed(self, content: str, level: str = "full") -> tuple[str, dict] | None:
        """Compact if pressure threshold exceeded."""
        current_usage = _estimate_tokens(content)

        if not self.wm.should_compact(current_usage):
            return None

        # Verify prefix cache stability before compaction
        if self._previous_prefix_hash:
            if not self.prefix_cache.is_stable(self._previous_prefix_hash):
                print(f"[context_compaction] WARNING: Prefix cache changed before compaction", file=sys.stderr)

        # Compact with verbatim preservation
        compressed, stats = _compress_text(content, level)

        # Update prefix hash after compaction
        self._previous_prefix_hash = self.prefix_cache.prefix_hash()

        stats["trigger"] = "pressure"
        stats["wm_budget"] = self.wm.wm_budget
        stats["pressure_threshold"] = int(self.wm.window_size * COMPACT_AT_CONTEXT_FRACTION)
        return compressed, stats

    def retain_newest_fraction(self, content: str, fraction: float = RETAIN_CONTEXT_FRACTION) -> str:
        """Retain only the newest fraction of content verbatim."""
        # Split into lines/segments, keep newest fraction
        lines = content.splitlines()
        keep = max(1, int(len(lines) * fraction))
        if keep >= len(lines):
            return content
        return "\n".join(lines[-keep:])


# Global instances per session
_ADAPTIVE_WM: dict[str, AdaptiveWM] = {}
_PREFIX_CACHES: dict[str, PrefixCache] = {}
_PRESSURE_COMPACTORS: dict[str, PressureCompactor] = {}
_GLOBAL_LOCK = threading.Lock()


def get_adaptive_wm(session_id: str) -> AdaptiveWM:
    with _GLOBAL_LOCK:
        if session_id not in _ADAPTIVE_WM:
            _ADAPTIVE_WM[session_id] = AdaptiveWM()
        return _ADAPTIVE_WM[session_id]


def get_prefix_cache(session_id: str) -> PrefixCache:
    with _GLOBAL_LOCK:
        if session_id not in _PREFIX_CACHES:
            _PREFIX_CACHES[session_id] = PrefixCache()
        return _PREFIX_CACHES[session_id]


def get_pressure_compactor(session_id: str) -> PressureCompactor:
    with _GLOBAL_LOCK:
        if session_id not in _PRESSURE_COMPACTORS:
            # Create components without calling the getter functions to avoid lock recursion
            if session_id not in _ADAPTIVE_WM:
                _ADAPTIVE_WM[session_id] = AdaptiveWM()
            wm = _ADAPTIVE_WM[session_id]
            
            if session_id not in _PREFIX_CACHES:
                _PREFIX_CACHES[session_id] = PrefixCache()
            pc = _PREFIX_CACHES[session_id]
            
            _PRESSURE_COMPACTORS[session_id] = PressureCompactor(wm, pc)
        return _PRESSURE_COMPACTORS[session_id]


def reset_session_compaction(session_id: str) -> None:
    """Reset all compaction state for a session."""
    with _GLOBAL_LOCK:
        _ADAPTIVE_WM.pop(session_id, None)
        _PREFIX_CACHES.pop(session_id, None)
        _PRESSURE_COMPACTORS.pop(session_id, None)


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