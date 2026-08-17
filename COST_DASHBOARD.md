# Cost Tracking Dashboard — Harness Optimization Savings
**Generated**: 2026-08-16T18:06:51.567286+00:00
**Repo**: workspace

## Executive Summary

| Layer | Optimization | Savings | Description |
|-------|-------------|---------|-------------|
| Input | Progressive Skill Loading (U-H7) | **~38K tokens** | 164KB → 11KB at boot |
| Output | Terminal Compression (U-H17) | **60-94%** | git diff, npm, ls, git status |
| Output | Observation Masking (U-H18) | Variable | Large tool outputs masked |
| State | Compaction Protocol (U-H9) | **15-20%** | Session/loop state |
| Cost | Model Routing (U-H12) | **60-95%** | Route to free models |

## Detailed Breakdown

### Input Context Savings

- **U-H7 Progressive Skill Loading**: 164KB → 11KB
  - Tokens saved: **38,250** (~153KB)
  - Mechanism: Load skill_index.json (11KB) at boot, full skill bodies on-demand

### Output Context: Terminal Compression (U-H17)

| Command | Reduction | Mechanism |
|---------|-----------|-----------|
| git_diff | **80%** | U-H17: collapse unchanged hunks |
| npm_install | **70%** | U-H17: strip progress/audit |
| ls_l | **83%** | U-H17: entry names only |
| git_status | **94%** | U-H17: summarize |

### Output Context: Observation Masking (U-H18)

- Masks tool outputs >1KB after first read
- Stores full output to session_state/tool_outputs/<call_id>.json
- Replaces with handle reference: `[MASKED: tool_output:Read:call-abc123]`
- Agent can request full output back by referencing handle

### State Compaction (U-H9)

| State Type | Reduction | Mechanism |
|------------|-----------|-----------|
| session_state | **16%** | U-H9: Caveman protocol |
| loop_state | **16%** | U-H9: Caveman protocol |

- 4 compression levels: light (20%), full (40%), ultra (65%), wenyan (75%)
- Verbatim preservation: file paths, line numbers, errors, URLs, API keys, function calls
- Full payload offloaded to filesystem for recovery

### Cost Routing (U-H12)

| Task Type | Executor | Cost Tier | Savings |
|-----------|----------|-----------|---------|
| simple_ops_to_glm | N/A | N/A | **95%** |
| coding_to_kimi | N/A | N/A | **85%** |
| complex_to_lightning | N/A | N/A | **0%** |
| planning_to_active | N/A | N/A | **0%** |

- **Free models**: GLM-5.2 (free), Kimi K2.7 (free until 2026-07-05)
- **Premium**: SWE-1.7 Lightning ($2.5/$12.5 MTok)
- Routing rules defined in config.json `_u12_model_routing`

### Prompt Caching Metrics (U-H11)

- **Hit Rate**: 100.0%
- **Cache Hits**: 5
- **Cache Misses**: 0
- **Estimated Savings**: $0.004008
- **Hit Tokens**: 8,350

### Cost Ledger Summary

- **Total Entries**: 4
- **Unique Sessions**: 4
- **Total Tracked Cost**: $0.006000
- **Cumulative Cost**: $0.006000

### Iteration History

| Iteration | Upgrades | Key Achievements |
|-----------|----------|------------------|
| ITERATION 5 — HLK Security Layer + Skill Fix | 0 | See log |
| ITERATION 6 — Runtime Unblock + REVIEW phase | 0 | See log |
| ITERATION 7 — Plan binding/persistence root-fix + context-rot | 0 | See log |
| ITERATION 8 — HLK Auto-Review Flow cho merge-ours.log (U-HLK-12) | 0 | See log |
| ITERATION 9 — V5-01 Agent Registry Lifecycle (U-REG-1) | 0 | See log |
| ITERATION 10 — V5-02 slug-collision + V5-04 telemetry test + V5-01 ext persistence | 0 | See log |
| ITERATION 11 — Fix 31 pre-existing test failures + coverage gate | 0 | See log |
| ITERATION 12 — Token Efficiency: Terminal Compression + Progressive Skills | 3 | See log |
| ITERATION 13 — Context Efficiency: Observation Masking + Model Routing + Prompt Caching | 3 | See log |
| ITERATION 14 — Compaction Protocol Enhancement (U-H9) | 2 | See log |

## Recommendations

1. **Enable Prompt Caching** — Ensure provider supports caching (Anthropic, GLM). Monitor hit rate.
2. **Tune Model Routing** — Adjust routing rules based on actual task distribution.
3. **Measure Cache Hit Rate** — Run `prompt_cache_metrics.py` at session start to track stability.
4. **Cost Cap Enforcement** — Set per-session cost caps via `cost_tracker.py --set-cap`.
5. **Regular Dashboard Review** — Run this dashboard weekly to track optimization effectiveness.
