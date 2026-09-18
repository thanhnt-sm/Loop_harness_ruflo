import json

data = [
    {
        "Project": "Elastic Agent",
        "Approach": "Fleet-managed orchestration; persistent connection to Fleet Server. Pre-downloads manifest/metadata, verifies hash before upgrading. Can upgrade using just hash checking (legacy) or full manifest (modern).",
        "Pros": "Strong security (hash verification, unprivileged user ACLs), clear state machine (updates ES index, queuing actions), fallback paths.",
        "Cons": "Heavyweight architecture (requires Fleet Server and Elasticsearch), complex ACL management on Windows."
    },
    {
        "Project": "Pi Agent / Pi Coding Agent",
        "Approach": "AgentHarness layer separates low-level loop from session persistence, resource resolution, and runtime config. Uses a 'faux provider' for deterministic tests. Queue modes (immediate/live).",
        "Pros": "Clean separation of concerns, strong testing model, handles reentrancy and lifecycle hooks.",
        "Cons": "Tied to specific provider stream semantics, custom state categories."
    },
    {
        "Project": "Harness CLI",
        "Approach": "Self-contained binary distributor. In-place binary and module upgrades. Provides an automated installer/updater and dry-run inspect (`debug update_check`).",
        "Pros": "Simple UX (one-shot upgrade or `--core-only`), cross-platform (macOS/Linux), dry-run capability.",
        "Cons": "Traditional CLI updater, not an autonomous agent bootstrap layer."
    },
    {
        "Project": "OpenClaw",
        "Approach": "Embedded agent runtime distinct from external harness process. Each agent gets its own workspace, bootstrap files, and session store.",
        "Pros": "Highly isolated multi-agent routing, explicit bootstrap injection per agent.",
        "Cons": "More overhead per agent session."
    }
]

with open("tmp/harness_bootstrap_competitive_analysis.md", "w") as f:
    f.write("# Competitive Analysis: Harness Upgrade Runtime Bootstrap\n\n")
    f.write("This brief analyzes how different projects approach agent/harness bootstrapping, upgrades, and runtime isolation.\n\n")
    
    for item in data:
        f.write(f"## {item['Project']}\n\n")
        f.write(f"**Approach:** {item['Approach']}\n\n")
        f.write(f"**Pros:** {item['Pros']}\n")
        f.write(f"**Cons:** {item['Cons']}\n\n")

print("Generated tmp/harness_bootstrap_competitive_analysis.md")
