# Agent Harness Deploy (AHD) — Loop Harness

> Self-deploying cross-tool AI harness cho Devin CLI và 6+ AI coding assistants.
> 3-Phase Architecture (Plan → Approve → Execute) với deterministic governance enforcement.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-800+-green.svg)](#testing)

---

## Overview

AHD là **harness framework** — không phải AI model, mà là **hệ thống quản lý và điều phối** các AI coding assistant. AHD cung cấp:

- **3-Phase mandatory workflow**: Plan → Approve → Execute — M-tier+ tasks không được skip Plan phase
- **Deterministic enforcement**: 49 hooks chạy trước/sau mỗi tool call — không phụ thuộc model goodwill
- **Multi-provider orchestration**: Devin CLI, Claude Code, Cline, opencode, Aide, Codex/Khuym, Cursor
- **Adversarial review**: 6+ personas review đối kháng (Saboteur, Security Auditor, Architect, Code Reviewer...)
- **Token efficiency**: Caveman protocol (~65% reduction), lazy-load canon, progressive skill loading

```
┌─────────────────────────────────────────────────────┐
│                   USER TASK                         │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  TIER CLASSIFY  │  S / M / L / XL
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐   ┌────▼────┐   ┌───▼───┐
    │  PLAN   │──▶│ APPROVE │──▶│EXECUTE│
    │ (FSM)   │   │ (Gate)  │   │ (DAG) │
    └─────────┘   └─────────┘   └───────┘
    8 Scouts      Human Gate    5 Workers
    6 Reviewers   Interactive   TDD + Audit
    SDD + Plan                Verify + Report
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.11+ | Core harness engine |
| **Data models** | Pydantic 2.x | Schema validation, state management |
| **FSM** | Custom (plan_orchestrator.py) | Plan phase state machine (13 states) |
| **Execution** | DAG executor (parallel N=5) | Concurrent task dispatch with worktree isolation |
| **Security** | HLK layer (Node.js) | Sanitizer, vault, git-tools, integrity checks |
| **Locking** | filelock <3.13 | Idempotency enforcement (CVE-2026-AHD-003) |
| **Crypto** | cryptography 41+ (Ed25519) | Approval gate signature verification |
| **Testing** | pytest + hypothesis | Unit, integration, property-based tests |
| **Linting** | ruff (E/F rules) | Code quality enforcement |
| **Type check** | mypy (py311) | Static type analysis |
| **Coverage** | pytest-cov (fail_under=80%) | Code coverage gate |
| **MCP** | 4 servers (aide, spark, deepwiki, devin) | Memory, knowledge, API integration |

---

## Components Map

### Skills (26+)

| Skill | Type | Purpose |
|-------|------|---------|
| `/plan` | Orchestrator | Plan phase — FSM-driven SDD → Approval → Plan → QC |
| `/full-power` | Orchestrator | Full 3-Phase (Plan→Approve→Execute) — mandatory for M-tier+ |
| `/lightning` | Executor | SWE-1.7 Lightning — 1000 tok/s, $2.5/$12.5 MTok |
| `/glm` | Executor | GLM-5.2 High — **Free tier**, high reasoning |
| `/kimi` | Executor | Kimi K2.7 — **Free tier**, open-source |
| `/adversarial-consensus` | Review | 6+ persona adversarial review (C3 protocol) |
| `/tdd` | Development | Test-Driven Development — Red-Green-Refactor |
| `/systematic_debugging` | Development | Reproduce → Isolate → Hypothesize → Test → Fix |
| `/auditor` | Review | Adversarial code review — security, failure modes |
| `/fable-judge` | Verification | Post-completion adversarial verification |
| `/gap-scan` | Analysis | Scan gaps between current state and goal |
| `/harness-sensor` | QA | Structural, build, syntax checks |
| `/claim-grader` | QA | Grade claims: [fact] / [inference] / [unverified] |
| `/slop-detector` | QA | Detect AI-generated filler content |
| `/comment_checker` | QA | Detect over-explained/obvious comments |
| `/context-compactor` | Optimization | Caveman protocol — ~65% token reduction |
| `/aide-memory` | Memory | Persistent cross-session memory (MCP) |
| `/loop-memory` | Memory | Sync loop state across sessions |
| `/memory-audit` | Memory | Audit memory quality |
| `/harness-upgrade` | Meta | Self-review + upgrade workspace |
| `/hlk-git-tools` | Git | Safe git commit/push/doctor/sync |
| `/hlk-integrity-check` | Security | Verify HLK layer integrity |
| `/hlk-loop` | Meta | HLK pipeline self-learning loop |
| `/nuwa-skill` | Research | Cognitive skill distillation (Munger/Feynman/Taleb) |
| `/update_from_repos` | Maintenance | Safe update from upstream repos |
| `/graph-verify` | Verification | Knowledge graph integrity check |

### Agents (18)

| Agent | Role | Count |
|-------|------|-------|
| **COMMANDER** | Main orchestrator — decides, dispatches, integrates | 1 |
| **Workers** | Scout (search), Builder (implement), Verifier (read-back), Auditor (review), Memory Keeper (persist) | 5 |
| **Personas** | Architect, Code Reviewer, Git Workflow Master, Saboteur, New Hire, Security Auditor | 6 |
| **Executors** | Lightning (SWE-1.7), GLM (GLM-5.2), Kimi (K2.7) | 3 |
| **Templates** | Persona Template, Dispatch Templates, Model Tiers | 3 |

### Hooks (49 Python files)

| Category | Count | Key Hooks |
|----------|-------|-----------|
| **Pre-tool** | 12 | `pre_tool_use.py`, `plan_enforce.py`, `pre_tool_dangerous.py`, `pre_tool_secrets.py` |
| **Post-tool** | 10 | `post_tool_use.py`, `schema_gate.py`, `drift_detect.py`, `self_heal.py` |
| **Schema/Verify** | 8 | `schema_gate.py`, `coverage_enforce.py`, `cross_family_verify.py` |
| **Session** | 11 | `session_start.py`, `session_end.py`, `ahd_session.py` (+ 5 modules) |
| **Other** | 8 | `otel_instrument.py`, `context_compaction.py`, `compress_terminal_output.py` |

### Scripts (130+ Python files)

| Subsystem | Files | Purpose |
|-----------|-------|---------|
| **Plan Orchestrator** | 20+ | FSM engine, quality check, dispatch, sanitization |
| **DAG Executor** | 14 | Compile, execute, async, failure handling, state |
| **Approval Gate** | 10 | Interactive gates, crypto signing, audit trail |
| **Checkpoint** | 6 | Save/restore/backtracking, redaction |
| **Loop Memory** | 7 | Cross-session memory sync, fallback, watchdog |
| **Blackboard** | 4 | Shared memory with scoped regions |
| **Cost Tracking** | 3 | Budget enforcement, ledger, dashboard |
| **State Management** | 10+ | Router, schema, file/Redis backends, migration |
| **Runtime** | 6 | Async task graph, backpressure, cache, token budget |
| **Other** | 50+ | Coverage matrix, hook integrity, swarm, LLM-as-judge |

### Canon Protocols (15)

| Protocol | Load When |
|----------|-----------|
| `CORE_CANON.md` | BOOT (always) |
| `BOOT_PROTOCOL.md` | BOOT (always) |
| `REDLINES.md` | BOOT (top 5 only) |
| `MEMORY_PROTOCOL.md` | Writing memory |
| `LOOP_PROTOCOL.md` | Running loops |
| `VERIFICATION_PROTOCOL.md` | Verifying output |
| `CAVEMAN_PROTOCOL.md` | Compressing context |
| `HARNESS_ENGINEERING.md` | Designing harness |
| `JUDGMENT_RUBRICS.md` | Decision-making |
| `HANDOFF_LETTER.md` | Session handoff |
| `DAEMON_PROTOCOL.md` | Long-running operations |
| `LOOP_TURN/TIME/GOAL_BASED.md` | Loop variants |
| `LOOP_PROACTIVE.md` | Proactive loop |

### HLK Security Layer (70+ files)

Toggle on/off via `hlk_enabled` in `HLK/config/hlk.config.json`.

| Component | Purpose |
|-----------|---------|
| **Sanitizer** | Redact API keys, tokens, passwords |
| **Vault Bridge** | Secret management via env vars / .env |
| **Git Tools** | Safe commit (blocks secrets), safe push (no force), doctor, safe-sync |
| **Integrity Check** | Post-update file integrity verification |
| **Hook Launcher** | Bridge between HLK and tool lifecycle |
| **Setup** | Cross-platform install (sh/ps1/mjs) |

---

## Provider Support

| Provider | Config File | Auto-load | Notes |
|----------|-------------|-----------|-------|
| **Devin CLI** | `AGENTS.md` + `.devin/` | ✅ | Primary target — full harness |
| **Claude Code** | `CLAUDE.md` | ✅ | Full compatibility |
| **Cline** | `.clinerules/` | ✅ | VS Code extension |
| **opencode** | `opencode.json` | ✅ | Provider-agnostic terminal |
| **Aide** | `.aide/config.json` | ✅ | — |
| **Codex/Khuym** | `AGENTS.md` (Khuym block) | ✅ | With Khuym workflow |
| **Cursor** | `.cursor/` | ✅ | Rules system |

All providers share the same **canon protocols** and **governance rules**. Runtime state is provider-specific and gitignored.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js (for HLK layer)
- Git

### Installation

```bash
# Clone the repo
git clone https://github.com/thanhnt-sm/Loop_harness_ruflo.git
cd Loop_harness_ruflo

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[test]"

# Install HLK layer (optional)
cd HLK && npm install && cd ..

# Verify
python tools/check_governance.py
```

### Usage

```bash
# Devin CLI
devin                           # Open interactive CLI
devin -p -- "task description"  # Non-interactive

# Skills (via CLI)
/full-power <task>    # Full 3-Phase (mandatory for M-tier+)
/lightning <task>     # SWE-1.7 Lightning executor
/glm <task>           # GLM-5.2 executor (free)
/kimi <task>          # Kimi K2.7 executor (free)
/plan <task>          # Plan phase only
/adversarial-consensus <artifact>  # 6-persona adversarial review
```

### Testing

```bash
pytest                    # Run all tests
pytest --cov=.devin       # With coverage
python tools/check_governance.py   # Governance lint
```

---

## Reference Repos

AHD được xây dựng dựa trên research từ **50+ repos, papers, và documentation sources**. Xem đầy đủ tại [REPOS.md](REPOS.md).

### Core Sources

| Source | What We Took |
|--------|-------------|
| [masteryee-labs/Tool.Agent-Harness-Deploy](https://github.com/masteryee-labs/Tool.Agent-Harness-Deploy) | AHD framework — động cơ chính |
| [alchaincyf/nuwa-skill](https://github.com/alchaincyf/nuwa-skill) | Cognitive skill distillation (Munger/Feynman/Taleb) |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Token compression (~65% reduction) |
| [obra/superpowers](https://github.com/obra/superpowers) | Subagent-driven development, systematic debugging |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | Commander/Worker architecture |
| [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering) | Loop primitives, audit patterns |
| [Sahir619/fable-method](https://github.com/Sahir619/fable-method) | Adversarial done-gate, domain adapters |

### Industry Comparison

| Framework | Multi-Provider | Hooks | Plan-Execute | Guardrails |
|-----------|---------------|-------|-------------|------------|
| Claude Code | No | ✅ | Basic | ✅ |
| Devin | No | No | ✅ | Sandbox |
| OpenCode | ✅ | No | Plan/Build | Basic |
| Cline | ✅ | No | Plan/Act | Permission toggles |
| Cursor | No | ✅ | ✅ | Rules + agents |
| **AHD** | **✅ (6+)** | **✅ (49 hooks)** | **✅ (3-Phase FSM)** | **✅ (governance enforced)** |

---

## Key Features

### 1. Deterministic Governance

Hooks run **before** every tool call — not review after. `plan_enforce.py` blocks write/edit if no approved plan exists. `schema_gate.py` validates output. `drift_detect.py` monitors behavioral drift.

### 2. Adversarial Review (C3 Protocol)

6+ personas review every major artifact: Saboteur (break things), New Hire (ask obvious questions), Security Auditor (find vulnerabilities), Architect (design quality), Code Reviewer (maintainability), Git Workflow Master (branch strategy). Issues found by 2+ reviewers = elevated severity.

### 3. Self-Healing

`self_heal.py` runs Monitor → Detect → Diagnose → Recover cycle. Max 3 recovery attempts before escalating to human. Includes circuit breaker (`ahd_session_circuit.py`) for cascading failures.

### 4. Token Efficiency

- **Caveman protocol**: ~65% context reduction via structured compression
- **Lazy-load canon**: 15 protocol files loaded on-demand, not at boot
- **Progressive skill loading**: `skill_index.json` enables boot with 2KB payload
- **Context compaction**: Auto-compact when approaching context limits

### 5. Cost Optimization

Auto-routing between models based on task complexity:
- Simple ops → GLM-5.2 (free)
- Code gen → Kimi K2.7 (free)
- Complex reasoning → SWE-1.7 Lightning ($2.5/$12.5 MTok)
- Planning/review → Active model

### 6. Evidence-Graded Claims

Every claim in documentation tagged as `[fact]`, `[inference]`, or `[unverified]`. Prevents hallucinated assertions from propagating through the system.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [AGENTS.md](AGENTS.md) | Agent harness rules + governance (entry point) |
| [CLAUDE.md](CLAUDE.md) | Claude Code entry file |
| [REPOS.md](REPOS.md) | Master reference list (50+ repos) |
| [SECURITY.md](SECURITY.md) | Security policy |
| [docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md) | Complete usage guide (411 lines) |
| [docs/AGENTS_full_reference.md](docs/AGENTS_full_reference.md) | Architecture reference (464 lines) |
| [docs/PLAN_ORCHESTRATOR_GUIDE.md](docs/PLAN_ORCHESTRATOR_GUIDE.md) | Plan orchestrator technical docs (759 lines) |
| [docs/CONTINUOUS_LOOP_GUIDE.md](docs/CONTINUOUS_LOOP_GUIDE.md) | Loop engineering guide (397 lines) |
| [docs/PROPOSAL.md](docs/PROPOSAL.md) | 3-Phase architecture proposal (1068 lines) |
| [docs/REDLINES_full.md](docs/REDLINES_full.md) | 18 hard stops + enforcement (294 lines) |
| [docs/REDTEAM_AUDIT.md](docs/REDTEAM_AUDIT.md) | Red team audit — 70+ findings (723 lines) |
| [docs/INDEX.md](docs/INDEX.md) | Documentation map — full navigation |

---

## Project Structure

```
.
├── AGENTS.md                 # Entry file — harness rules
├── CLAUDE.md                 # Claude Code entry
├── REPOS.md                  # Reference repos
├── SECURITY.md               # Security policy
├── README.md                 # This file
├── pyproject.toml            # Python project config
├── opencode.json             # opencode configuration
│
├── .devin/                   # AHD harness layer
│   ├── agents/               # 18 agent definitions
│   ├── skills/               # 26+ skills
│   ├── hooks/                # 49 Python hooks
│   ├── scripts/              # 130+ runtime scripts
│   ├── canon/                # 15 protocol files
│   ├── rules/                # Governance rules
│   ├── schemas/              # JSON schemas
│   ├── config.json           # Harness configuration
│   └── ...                   # State, artifacts, logs
│
├── HLK/                      # Security layer (Node.js)
│   ├── config/               # Config + secrets
│   ├── security/             # Sanitizer + vault
│   ├── git-tools/            # Safe git operations
│   ├── wrappers/             # Hook bridge + launcher
│   └── bin/                  # CLI tools
│
├── tools/                    # Packaging & governance tools
├── tests/                    # Test suite (800+ tests)
├── docs/                     # Documentation
│   ├── plans/                # Feature plans (36 dirs)
│   ├── reports/              # Audit reports (14 files)
│   ├── research/             # Research notes
│   └── templates/            # Plan + SDD templates
│
├── .opencode/                # opencode skills
├── .clinerules/              # Cline rules
├── .githooks/                # Git hooks (pre-commit)
├── .github/                  # CI workflows
└── sbom/                     # Software Bill of Materials
```

---

## Governance

AHD enforces **strict file governance** via runtime hooks:

- **No junk files**: No scratch, `.bak`, `.tmp`, untitled files
- **Files in correct location**: Scripts → `.devin/scripts/`, Hooks → `.devin/hooks/`, Plans → `docs/plans/<slug>/`
- **Plan ↔ Act contract**: Code changes must match approved plan; plan must have execution report
- **Multi-provider isolation**: Provider state stays in provider directories (no cross-contamination)

```bash
# Check governance
python tools/check_governance.py            # Full lint
python tools/check_governance.py --plan-act # Plan↔act only
python tools/junk_file_scanner.py           # Junk file scan
python tools/gitignore_audit.py --strict    # .gitignore audit
```

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

See [AGENTS.md](AGENTS.md) for workspace governance rules. All contributions must:

1. Follow 3-Phase workflow (Plan → Approve → Execute) for M-tier+ tasks
2. Pass governance check (`python tools/check_governance.py`)
3. Include execution report in `docs/plans/<slug>/`
4. Maintain test coverage ≥ 80%

---

## Acknowledgments

Built on research from 50+ open-source repos, academic papers, and industry best practices. See [REPOS.md](REPOS.md) for the complete reference list.

Key inspirations: Martin Fowler's Harness Engineering, Anthropic's Effective Harnesses, Claude Code Harness, OpenHands, the AGENTS.md standard (Linux Foundation AAIF).
