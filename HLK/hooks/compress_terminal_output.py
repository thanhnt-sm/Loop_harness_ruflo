#!/usr/bin/env python3
"""Terminal output compression hook — compresses predictable noise from shell commands.

Compresses:
- git diff: collapses unchanged hunks, keeps changed lines
- Lockfiles (package-lock.json, yarn.lock, Cargo.lock): drops entirely
- npm/yarn/pnpm install: strips progress bars, audit summaries, deprecation warnings
- ls -l / find -ls: reduces to entry names only
- git status: summarizes

Banner contract (non-optional): prepends compression info + opt-out instruction.
Original output preserved in transcript (not shown to model).

Reference: VS Code 1.120 chat.tools.compressOutput.enabled, agentpatterns.ai
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Only compress if output exceeds this size (chars)
MIN_COMPRESS_SIZE = 500

# Compression patterns for noise-dominated output
NOISE_PATTERNS = {
    "git_diff": {
        "detect": lambda cmd: cmd and re.match(r"^git\s+diff(\s|$)", cmd),
        "compress": lambda out: _compress_git_diff(out),
        "banner": "compress-git-diff: collapsed unchanged hunks",
    },
    "lockfile": {
        "detect": lambda cmd: cmd and any(
            lock in cmd for lock in ["package-lock.json", "yarn.lock", "Cargo.lock", "pnpm-lock.yaml"]
        ),
        "compress": lambda out: "[lockfile diff dropped — use --no-compress to see raw]",
        "banner": "compress-lockfile: dropped lockfile diff",
    },
    "npm_install": {
        "detect": lambda cmd: cmd and re.match(r"^(npm|yarn|pnpm)\s+(install|ci|add)(\s|$)", cmd),
        "compress": lambda out: _compress_npm_output(out),
        "banner": "compress-npm-install: stripped progress/audit",
    },
    "ls_long": {
        "detect": lambda cmd: cmd and re.match(r"^(ls|find)\s+.*-[lL]", cmd),
        "compress": lambda out: _compress_ls_output(out),
        "banner": "compress-ls: reduced to entry names",
    },
    "git_status": {
        "detect": lambda cmd: cmd and re.match(r"^git\s+status(\s|$)", cmd),
        "compress": lambda out: _compress_git_status(out),
        "banner": "compress-git-status: summarized",
    },
}


def _compress_git_diff(output: str) -> str:
    """Collapse unchanged hunks (lines starting with space) in git diff."""
    lines = output.splitlines()
    result = []
    unchanged_count = 0
    for line in lines:
        if line.startswith(" ") and not line.startswith(("+++", "---", "@@")):
            unchanged_count += 1
            if unchanged_count == 1:
                result.append("  [... unchanged context collapsed ...]")
        else:
            if unchanged_count > 1:
                result.append(f"  [... {unchanged_count - 1} more unchanged lines ...]")
            unchanged_count = 0
            result.append(line)
    if unchanged_count > 1:
        result.append(f"  [... {unchanged_count - 1} more unchanged lines ...]")
    return "\n".join(result)


def _compress_npm_output(output: str) -> str:
    """Strip npm/yarn/pnpm progress bars, audit summaries, deprecation warnings."""
    lines = output.splitlines()
    result = []
    skip_patterns = [
        r"^\s*(added|removed|updated|audited)\s+\d+\s+package",
        r"^\s*\d+\s+(package|vulnerabilit)",
        r"^\s*(found|fixed)\s+\d+\s+(vulnerabilit|issue)",
        r"^\s*npm\s+(notice|WARN|ERR!)",
        r"^\s*(deprecated|warning|notice)",
        r"^\s*[│├└─]\s",
        r"^\s*[#▓░▒░]+\s+\d+%",
        r"^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]",  # spinners
        r"^\s*reify:",
        r"^\s*timing\s+",
    ]
    skip_regex = [re.compile(p, re.IGNORECASE) for p in skip_patterns]

    for line in lines:
        if any(r.search(line) for r in skip_regex):
            continue
        result.append(line)

    # If we stripped everything, keep a summary
    if not result and output.strip():
        return "[npm output compressed — progress/audit stripped. Rerun with --no-compress for raw.]"
    return "\n".join(result)


def _compress_ls_output(output: str) -> str:
    """Reduce ls -l / find -ls to just entry names."""
    lines = output.splitlines()
    result = []
    for line in lines:
        # ls -l format: perms links owner group size date name
        parts = line.split()
        if len(parts) >= 9:
            # Keep only the name (last part), preserve symlinks
            name = " ".join(parts[8:])
            if " -> " in line:
                # Symlink — keep target
                result.append(name)
            else:
                result.append(parts[-1])
        else:
            result.append(line)
    return "\n".join(result)


def _compress_git_status(output: str) -> str:
    """Summarize git status output by parsing sections."""
    lines = output.splitlines()
    staged = 0
    unstaged = 0
    untracked = 0
    section = None  # "staged", "unstaged", "untracked"
    for line in lines:
        stripped = line.strip()
        # Detect section headers
        if "Changes to be committed" in stripped:
            section = "staged"
            continue
        if "Changes not staged for commit" in stripped:
            section = "unstaged"
            continue
        if "Untracked files" in stripped:
            section = "untracked"
            continue
        # Skip section instructions
        if stripped.startswith("(use") or stripped.startswith("use \"git"):
            continue
        if not stripped:
            continue
        # Count files in each section (lines starting with modified/new file/deleted/renamed/copied)
        if section == "staged" and re.match(r"^(modified|new file|deleted|renamed|copied):", stripped, re.IGNORECASE):
            staged += 1
        elif section == "unstaged" and re.match(r"^(modified|deleted|renamed|copied):", stripped, re.IGNORECASE):
            unstaged += 1
        elif section == "untracked" and stripped:
            untracked += 1
    parts = []
    if staged:
        parts.append(f"{staged} staged")
    if unstaged:
        parts.append(f"{unstaged} unstaged")
    if untracked:
        parts.append(f"{untracked} untracked")
    if parts:
        return f"[git status: {', '.join(parts)}]"
    return "[git status: clean]"


def _should_compress(command: str, output: str) -> tuple[str, callable, str] | None:
    """Check if output should be compressed. Returns (banner, compress_fn, pattern_name) or None."""
    if not command or not output:
        return None
    if len(output) < MIN_COMPRESS_SIZE:
        return None

    for pattern_name, pattern in NOISE_PATTERNS.items():
        if pattern["detect"](command):
            compressed = pattern["compress"](output)
            if len(compressed) < len(output):
                return (pattern["banner"], pattern["compress"], pattern_name)
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})

    # Only compress Bash/terminal tool output
    if tool_name not in ("Bash", "bash", "Shell", "Execute", "exec", "terminal"):
        sys.exit(0)

    command = tool_input.get("command", "")
    output = ""
    if isinstance(tool_response, dict):
        output = str(tool_response.get("content", tool_response.get("output", "")))
    elif isinstance(tool_response, str):
        output = tool_response

    compress_info = _should_compress(command, output)
    if not compress_info:
        sys.exit(0)

    banner, compress_fn, pattern_name = compress_info
    compressed = compress_fn(output)
    original_size = len(output)
    compressed_size = len(compressed)

    # Only apply if we actually saved space
    if compressed_size >= original_size:
        sys.exit(0)

    # Banner is non-optional — model must know compression happened
    banner_text = f"[{banner}, {original_size} -> {compressed_size} chars. To disable: rerun with --no-compress in the command.]\n\n"

    # Return compressed output via hookSpecificOutput (Claude Code format)
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": banner_text + compressed
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()