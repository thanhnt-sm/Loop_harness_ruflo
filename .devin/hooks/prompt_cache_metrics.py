#!/usr/bin/env python3
"""Prompt Cache Metrics Hook — tracks cache hit/miss rates for stable prefixes.

Measures:
- System prompt stability (same prefix = cache hit potential)
- Skill index stability (same metadata = cache hit potential)
- Estimates cache savings based on provider pricing

Integrates with session_state for cross-session tracking.
Reference: Anthropic prompt caching, GLM stable system prompts research.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _get_session_root(root: Path, session_id: str) -> Path:
    """Get session-specific metrics directory."""
    out_dir = root / ".devin" / "session_state" / session_id / "cache_metrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _hash_content(content: str) -> str:
    """SHA-256 hash of content (16 chars)."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


def _read_file_safe(path: Path) -> str:
    """Safely read file content."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _get_stable_prefixes(root: Path) -> dict:
    """Get hashes of stable prompt prefixes that should remain constant."""
    prefixes = {}

    # AGENTS.md - main system prompt
    agents_path = root / "AGENTS.md"
    if agents_path.exists():
        content = _read_file_safe(agents_path)
        prefixes["AGENTS.md"] = _hash_content(content)

    # CORE_CANON.md
    core_path = root / ".devin" / "canon" / "CORE_CANON.md"
    if core_path.exists():
        content = _read_file_safe(core_path)
        prefixes["CORE_CANON.md"] = _hash_content(content)

    # REDLINES.md
    redlines_path = root / ".devin" / "canon" / "REDLINES.md"
    if redlines_path.exists():
        content = _read_file_safe(redlines_path)
        prefixes["REDLINES.md"] = _hash_content(content)

    # skill_index.json - stable metadata
    skill_index_path = root / ".devin" / "skills" / "skill_index.json"
    if skill_index_path.exists():
        content = _read_file_safe(skill_index_path)
        prefixes["skill_index.json"] = _hash_content(content)

    # BOOT_PROTOCOL.md
    boot_path = root / ".devin" / "canon" / "BOOT_PROTOCOL.md"
    if boot_path.exists():
        content = _read_file_safe(boot_path)
        prefixes["BOOT_PROTOCOL.md"] = _hash_content(content)

    return prefixes


def _load_previous_hashes(root: Path, session_id: str) -> dict:
    """Load previous session's prefix hashes."""
    metrics_path = _get_session_root(root, session_id) / "prefix_hashes.json"
    if metrics_path.exists():
        try:
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
            # Return only the prefix_hashes dict, not the wrapper
            return data.get("prefix_hashes", {})
        except Exception:
            pass
    return {}


def _save_current_hashes(root: Path, session_id: str, hashes: dict) -> None:
    """Save current prefix hashes for next session comparison."""
    metrics_path = _get_session_root(root, session_id) / "prefix_hashes.json"
    data = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prefix_hashes": hashes,
    }
    try:
        metrics_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[prompt_cache_metrics] Failed to save hashes: {e}", file=sys.stderr)


def _calculate_cache_metrics(current_hashes: dict, previous_hashes: dict) -> dict:
    """Calculate cache hit/miss metrics by comparing hashes."""
    metrics = {
        "total_prefixes": len(current_hashes),
        "cache_hits": 0,
        "cache_misses": 0,
        "new_prefixes": 0,
        "hit_rate_pct": 0.0,
        "details": {},
    }

    for name, current_hash in current_hashes.items():
        prev_hash = previous_hashes.get(name)
        if prev_hash is None:
            metrics["new_prefixes"] += 1
            metrics["details"][name] = {"status": "new", "hash": current_hash}
        elif prev_hash == current_hash:
            metrics["cache_hits"] += 1
            metrics["details"][name] = {"status": "hit", "hash": current_hash}
        else:
            metrics["cache_misses"] += 1
            metrics["details"][name] = {"status": "miss", "old_hash": prev_hash, "new_hash": current_hash}

    total_comparable = metrics["cache_hits"] + metrics["cache_misses"]
    if total_comparable > 0:
        metrics["hit_rate_pct"] = round(metrics["cache_hits"] / total_comparable * 100, 1)

    return metrics


def _estimate_cache_savings(metrics: dict) -> dict:
    """Estimate token/cost savings from cache hits."""
    # Rough estimates based on typical token counts
    estimated_tokens = {
        "AGENTS.md": 2800,      # ~10KB chars / 4
        "CORE_CANON.md": 1600,  # ~6KB chars / 4
        "REDLINES.md": 750,     # ~3KB chars / 4
        "skill_index.json": 2800,  # ~11KB chars / 4
        "BOOT_PROTOCOL.md": 400,   # ~1.6KB chars / 4
    }

    hit_tokens = 0
    miss_tokens = 0
    for name, detail in metrics["details"].items():
        tokens = estimated_tokens.get(name, 0)
        if detail["status"] == "hit":
            hit_tokens += tokens
        elif detail["status"] == "miss":
            miss_tokens += tokens  # miss = full read, but could have been cached

    # Cache read cost ~$0.02/MTok vs full read ~$0.50/MTok (Anthropic)
    # Savings per cache hit ≈ 96% cost reduction
    cache_read_cost_per_mtok = 0.02
    full_read_cost_per_mtok = 0.50
    savings_per_token = full_read_cost_per_mtok - cache_read_cost_per_mtok

    estimated_savings_usd = (hit_tokens / 1_000_000) * savings_per_token

    return {
        "hit_tokens": hit_tokens,
        "miss_tokens": miss_tokens,
        "total_tokens": hit_tokens + miss_tokens,
        "estimated_savings_usd": round(estimated_savings_usd, 6),
        "cache_read_cost_per_mtok": cache_read_cost_per_mtok,
        "full_read_cost_per_mtok": full_read_cost_per_mtok,
    }


def _log_metrics(root: Path, session_id: str, metrics: dict, savings: dict) -> None:
    """Append metrics to session log."""
    log_path = _get_session_root(root, session_id) / "cache_metrics_log.jsonl"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "metrics": metrics,
        "savings": savings,
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[prompt_cache_metrics] Failed to log metrics: {e}", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print("Usage: prompt_cache_metrics.py <session_id>", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1]

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

    # Get current prefix hashes
    current_hashes = _get_stable_prefixes(root)

    # Load previous session hashes
    previous_hashes = _load_previous_hashes(root, session_id)

    # Calculate metrics
    metrics = _calculate_cache_metrics(current_hashes, previous_hashes)

    # Estimate savings
    savings = _estimate_cache_savings(metrics)

    # Save current hashes for next session
    _save_current_hashes(root, session_id, current_hashes)

    # Log metrics
    _log_metrics(root, session_id, metrics, savings)

    # Print summary
    print(f"[prompt_cache_metrics] Session: {session_id}", file=sys.stderr)
    print(f"  Prefixes tracked: {metrics['total_prefixes']}", file=sys.stderr)
    print(f"  Cache hits: {metrics['cache_hits']}", file=sys.stderr)
    print(f"  Cache misses: {metrics['cache_misses']}", file=sys.stderr)
    print(f"  New prefixes: {metrics['new_prefixes']}", file=sys.stderr)
    print(f"  Hit rate: {metrics['hit_rate_pct']}%", file=sys.stderr)
    print(f"  Estimated savings: ${savings['estimated_savings_usd']:.6f}", file=sys.stderr)
    print(f"  Hit tokens: {savings['hit_tokens']:,}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    import os
    main()