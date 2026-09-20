---
name: cmdc-harness-bridge
description: Bridge skill that points command-code to the existing .devin + .opencode + HLK harness in this workspace. Use when you need to find which skill, agent, or hook to invoke for an AHD / Devin / opencode / HLK workflow. This skill is a thin index — the real playbooks live in .devin/skills/, .opencode/skills/, and HLK/ itself.
disable-model-invocation: false
user-invocable: true
argument-hint: "[]"
allowed-tools: Read
---

# cmdc-harness-bridge

This workspace runs **three parallel harness layers**:

1. **`.devin/`** — the Agent Harness Deploy (AHD) canonical layer. Source of
   truth for skills, canon, hooks, agents, and the `plan_orchestrator.py`
   3-phase engine. This is the layer the user-authored skill files in
   `.devin/skills/` come from.
2. **`.opencode/`** — the opencode-specific wrappers and the L0-L4 tool
   registry, plus a `harness.ts` plugin that bridges to the `.devin/hooks/*.py`
   scripts (best-effort, fail-open).
3. **`HLK/`** — the security + knowledge protection layer (Harness & Logic
   Knowledge Layer). Sanitizer, vault, telemetry blocker, custom hooks, git
   workflow hardening, 6 analysis prompts, 3 HLK skills, 8 git-tools, self-
   learning loop. **HLK is the load-bearing guardrail; the cmdc PreToolUse
   shell hook chain runs `deny-dangerous.sh` → `hlk-hook-launcher.mjs` →
   `bridge-devin.sh` in that order, so HLK sanitizer is the second line of
   defense after the deny list.**

The `command-code` (cmdc) CLI sits on top. This skill is the **index** that
tells you where each cmdc feature finds its source.

## Where cmdc features resolve

| cmdc surface | Resolves to | Notes |
|--------------|-------------|-------|
| Skills | `.commandcode/skills/`, `.devin/skills/`, `.opencode/skills/` (via `settings.json.skills`) | 90+ SKILL.md files; loader picks first match by name |
| MCP servers | `.mcp.json` (project scope) | `aide-memory` + `ruflo-hlk-mcp`, both local stdio |
| Hooks | `.commandcode/hooks/*.sh` + `HLK/wrappers/hlk-hook-launcher.mjs` | 4 shim scripts + HLK sanitizer/telemetry blocker |
| Permissions | `.commandcode/settings.json.permissions` | deny/ask/allow lists mirrored from `.devin/config.json` |
| Custom agents | `.commandcode/agents/*.md` | 5 harness + 5 personas + 1 HLK engineer = 11 |
| Custom slash commands | `.commandcode/commands/*.md` | 15 commands: full-power, plan, lightning, glm, kimi, adversarial-consensus, hlk-git-tools, hlk-integrity-check, hlk-loop, harness-upgrade, hlk-status, hlk-sanitize, hlk-git-doctor, hlk-max-power, hlk-prompts |

## When to use which skill

- "Run MAX-POWER, all flows, all mods, all agents" → `/full-power <task>`
  (chạy đủ 18 step, dispatch 5 harness + 5 personas + 1 HLK engineer + 5
  workers + 6 personas Devin + 15 personas opencode = **37 agents**, load
  15 canon + 88 skill + 6 HLK prompt + 3 HLK skill files theo phase)
- "Plan only, no execute" → `/plan <task>`
- "Dispatch a free-tier model" → `/glm <task>` or `/kimi <task>`
- "Use the fast paid model" → `/lightning <task>` (only when needed)
- "Red-team this artifact" → `/adversarial-consensus <artifact>`
- "Self-improve the harness" → `/harness-upgrade`
- "Verify HLK layer" → `/hlk-integrity-check` (deep) or `/hlk-status` (quick)
- "Git workflow with HLK guards" → `/hlk-git-tools <action>` or
  `/hlk-git-doctor` (pre-flight)
- "Self-learning HLK pipeline" → `/hlk-loop <action>`
- "Redact secrets in a file/text" → `/hlk-sanitize <target>`
- "Run HLK MAX POWER" → `/hlk-max-power [--verify|--doctor]`
- "Run 1 of 6 HLK analysis prompts" → `/hlk-prompts <num|keyword>`

## Delegation map (agents — total 37 across three layers)

**Harness (5)** — main thread + executors + done-gate:
- `commander` — orchestrator. Plan + dispatch + review.
- `executor-glm` / `executor-kimi` / `executor-lightning` — implementation.
- `verifier` — read-only done-gate (fable-judge style).

**Personas (5 cmdc + 6 Devin + 15 opencode = 26)** — review lens, dispatch
song song ở step 9 của full-power:
- `persona-architect` / `persona-code-reviewer` / `persona-saboteur` /
  `persona-security-auditor` / `persona-new-hire`
- 6 personas Devin: `architect`, `code_reviewer`, `git_workflow_master`,
  `new_hire`, `saboteur`, `security_auditor`
- 15 personas/roles opencode: architect, auditor, builder, code_reviewer,
  commander, git_workflow_master, 3 executors (glm/kimi/lightning),
  memory_keeper, new_hire, saboteur, scout, security_auditor, verifier

**Workers (5 AHD)** — chạy ở phase EXECUTE:
- `SCOUT` (research), `BUILDER` (code change), `AUDITOR` (quality),
  `MEMORY_KEEPER` (memory write-back), `VERIFIER` (independent done-gate).

**HLK operator (1 cmdc)** — security layer specialist:
- `hlk-engineer` — HLK status, integrity, sanitize, git-tools, MAX POWER,
  prompt-driven analysis, loop self-learning. Read-only by default.

## How hooks bridge the three layers

```
cmdc tool call (shell)
  → .commandcode/hooks/deny-dangerous.sh        (line 1: deny destructive)
    → node HLK/wrappers/hlk-hook-launcher.mjs   (line 2: HLK sanitizer + telemetry blocker)
      → .commandcode/hooks/bridge-devin.sh       (line 3: forward to .devin/hooks/*.py)
        → opencode .plugins/harness.ts          (line 4: bridge to .devin/hooks/*.py from opencode side, separate path)
```

`hlk-hook-launcher.mjs` calls `hlk-hook-bridge.mjs`, which applies HLK
sanitizer (28 redact patterns from `HLK/config/hlk.config.json`) to the
stdin payload and blocks telemetry per the config. Output is consumed by
`pre_tool_use` semantics (fire-and-forget, fail-open, never blocks cmdc).

## Hard invariants

1. **Never edit `HLK/`, `.env`, security policies** unless task explicitly
   authorizes that exact file.
2. **Never force-push, never `rm -rf /` or `~`.** The deny-dangerous.sh
   hook enforces this in cmdc; the matching rules in
   `settings.json.permissions.deny` enforce it again.
3. **M+ tier tasks must go through `/full-power`** (Plan → Approve → Execute).
   S-tier (1 file, <5 dòng) can be fixed directly.
4. **Deterministic gate** is mandatory before any "done" claim. Run
   `python tools/check_governance.py` + `node HLK/wrappers/hlk-verify-integrity.js`
   + `pytest -q` (relevant module).
5. **Report** in the canonical location
   (`docs/plans/<slug>/EXECUTION_REPORT.md` or
   `docs/reports/<SUBJECT>_<YYYY-MM-DD>.md`).
6. **HLK self-test is part of preflight**: every full-power run should call
   `node HLK/bin/hlk-status.mjs --self-test` and `node HLK/wrappers/hlk-verify-integrity.js`
   before declaring ready.

## Security hardening (2026-08-27)

`settings.json` đã được hard-max theo `commandcode.ai/docs/security` + best
practices 2026:

- `disableBypass: "disable"` → chặn `--yolo` / `--dangerously-skip-permissions`
  ở mọi layer.
- `disableSkillShellExecution: true` → block inline `!cmd` + fenced shell
  trong SKILL.md (chống supply chain skill).
- `defaultMode: "default"` + permission rules deny/ask/allow đầy đủ (xem
  `settings.json.permissions` để biết chi tiết).
- MCP tool allowlist cụ thể (không `*`) cho `aide-memory` (5 tool: recall /
  remember / search / update / forget); `ruflo-hlk-mcp` giữ wildcard do
  chưa liệt kê được tool name (sẽ narrow sau khi `/mcp` show).
- Deny: secret material (.env, ~/.ssh, ~/.aws, ~/.gnupg, ~/.kube); persistence
  vectors (.bashrc, .zshrc, .profile, .gitconfig, .gitmodules, .mcp.json,
  .commandcode settings); control surfaces (.git/**, HLK config/wrappers/bin/
  security/custom-hooks); filesystem root + home.
- Hook chain 4 line: `deny-dangerous.sh` → `schema-validate.sh` → HLK
  sanitizer → `bridge-devin.sh`. Mỗi layer chồng chéo, fail-open khi
  conflict, deny rule cmdc engine luôn thắng.
- Personal overrides: `.commandcode/settings.local.json` (gitignored) cho
  rule cá nhân không commit.
- `additionalDirectories: ["HLK"]` → tường minh audit, không rely on workspace
  default.
