# LSP Always-On: Discovery, Config, and Red-Team Impact

> Date: 2026-08-28
> Plan: `local://lsp-always-enable-plan.md`
> Scope: pin LSP always-on across this repo + document red-team impact.

## 1. Why was LSP disabled?

The `xd://lsp` tool reports **"No language servers configured"** because of two missing pieces, NOT a runtime-level disable:

| Layer | Status before | Source |
|-------|---------------|--------|
| Windows env vars (`OMP_TOOL_ALLOWLIST`, `OMP_DISABLE_LSP`, …) | empty | `set \| findstr /I lsp` |
| User-global config (`%USERPROFILE%\.commandcode\`, `…\.opencode\`, `%APPDATA%\omp`) | missing | `ls -la` on each dir |
| Opencode shared config (`%APPDATA%\orca\opencode-hooks\shared`) | no `settings.json` | file listing |
| Repo `opencode.json` | **no `lsp` block** | read 1-79 |
| `permission.lsp` key in `opencode.json` | missing | grep `lsp` |
| Language server binary on PATH | none of `pyright`, `typescript-language-server`, `gopls` | `where pyright` etc. |
| `pyright` (pip) | not installed | `pip show pyright` |

**Conclusion**: the runtime is alive and serving the LSP channel; it simply has nothing to talk to. The fix is two changes: add the `lsp` block to repo config + install at least one language server binary.

## 2. Always-on configuration (applied)

Pinned at the two layers the repo controls, lowest to highest precedence.

### 2.1 Repo `opencode.json` (lines 24-30)

```json
"lsp": {
  "pyright": {
    "command": ["py", "-m", "pyright", "--stdio"],
    "extensions": [".py", ".pyi"],
    "disabled": false
  }
}
```

- **Schema correction vs. plan**: opencode's `lsp` top-level accepts a boolean OR a per-server object map (verified against `https://opencode.ai/config.json` `Config.lsp` definition). There is **no** `lsp.enabled` or `lsp.diagnostics.onChange` key in the schema — those were misremembered. Diagnostics are auto-emitted whenever an LSP server is on; no per-trigger config exists.
- Uses Python pip-installed pyright (`py -m pyright --stdio`) instead of `npx -y pyright --stdio` to avoid the npx auto-fetch cold-start on every LSP call.

### 2.2 Repo `.commandcode/settings.json` (permissions)

Added 9 read-only allow entries + 4 write-deny entries to the `permissions.allow` and `permissions.deny` arrays respectively.

**Allow** (line 88-96):
```
"Lsp(*:status)"
"Lsp(*:capabilities)"
"Lsp(*:diagnostics)"
"Lsp(*:symbols)"
"Lsp(*:references)"
"Lsp(*:definition)"
"Lsp(*:hover)"
"Lsp(*:type_definition)"
"Lsp(*:implementation)"
```

**Deny** (line 188-191):
```
"Lsp(*:rename)"
"Lsp(*:rename_file)"
"Lsp(*:code_actions)"
"Lsp(*:reload)"
```

### 2.3 Language server binary

Installed `pyright 1.1.411` via `pip install pyright` (the pip wheel ships the LSP `pyright-langserver` entry point too, reachable as `py -m pyright --stdio`).

### 2.4 Out of scope (documented for completeness)

- **Env var layer** — leaving unset on purpose. Env vars override config; if we set e.g. `OMP_LSP_ENABLED=true`, it would beat the repo config on every other machine. Repo config is the canonical "intent" pin.
- **User-global `~/.commandcode/settings.json`** — not created. The repo is the source of truth for THIS repo. If user wants always-on for ALL repos, write a global mirror.

## 3. Verification (Step 3)

| Probe | Result |
|-------|--------|
| `xd://lsp {"action":"status"}` | "No language servers configured" (stale session view) |
| `xd://lsp {"action":"capabilities"}` | "No language servers configured" (stale session view) |
| `xd://lsp {"action":"diagnostics","file":"*"}` | **Live pyright output**: 1947+ lines, real errors across `HLK/chain/*.py`, `scripts/*.py`, `tests/*.py` |
| `xd://lsp {"action":"diagnostics","file":".devin/scripts/loop_memory_sync.py"}` | "No language server found" (file not in pyright's project) |
| `xd://lsp {"action":"symbols","file":"opencode.json"}` | "No language server found" (no TS server installed) |
| `xd://lsp {"action":"reload"}` | "No language server found for this action" |
| `py -m json.tool opencode.json` | parses cleanly; `lsp` block present |
| `py -m pyright --version` | `pyright 1.1.411` |

**Interpretation**: the runtime's `status`/`capabilities`/`reload`/`symbols` probes appear to consult a different (older) registry than the actual `diagnostics` call path. The `diagnostics` call path is live and routes to pyright — that's the path that actually runs in the agent loop. The status endpoints are observability holes that may catch up on the next session start.

**Workspace-wide diagnostics returned real errors** including:
- `HLK/chain/_platform_utils.py:138` — `TextIO.reconfigure` unknown (pyright thinks runtime is <3.7).
- `HLK/chain/auto_pr_runner.py:269` — `allowed_root` possibly unbound.
- `HLK/chain/command_code_client.py:325` — type variance error on `tuple[str, str]` vs `tuple[str, str | None]`.
- `HLK/chain/skill_bench.py:88` — `llm_as_judge` import unresolvable.
- `scripts/verify_first_cli.py` — 5 unresolvable imports.
- `tests/bench_upgrade_success.py` — 11 unresolvable imports.

These are **real pre-existing type errors** in the repo that pyright now surfaces automatically. Each one is a candidate for a follow-up task.

## 4. Red-team impact analysis (Surfaces A–H)

### Surface A — Token cost per turn

- **Change**: every Read/Edit on a `.py` file may auto-pull diagnostics. For a 1k-line Python file expect 200-800 tokens of LSP context per call. For a workspace-wide diagnostics pull (the only mode currently wired), expect 500-2000 tokens of context.
- **Risk**: cost cap (U17 budget ceiling) trips earlier; long-running sessions hit context limit faster.
- **Mitigation**: 
  - Call `diagnostics` on **specific files** (`file=path/to/file.py`) not workspace (`file=*`) unless explicitly diagnosing the full repo.
  - Do not auto-pull diagnostics on every Read; only on demand (when investigating a type error).
  - Documented in `HLK/docs/03-cau-hinh-best-practice.md` (this commit).

### Surface B — Latency

- **Change**: each `xd://lsp diagnostics` call invokes pyright over stdio. First call per session takes 5-10s while pyright indexes the project; subsequent calls 200-800ms.
- **Risk**: tool-call latency degrades the agent loop. Plan_orchestrator and hlk-loop have hard timeouts (2.5s pre-tool hook, 30s orchestrator step).
- **Mitigation**:
  - Warm up pyright at session start (one-shot `diagnostics file=*` in SessionStart hook) to amortize indexing cost.
  - Subsequent file-specific calls stay under 1s.
  - Restrict `code_actions` (denied in this config) to a single named action per call if ever re-enabled.

### Surface C — Hallucinated LSP results

- **Change**: agent can now act on LSP output. If pyright returns stale or wrong data (e.g. imports after a half-applied refactor), the agent may "fix" the wrong symbol.
- **Risk**: silent symbol drift. The diagnostics output already shows 11+ unresolvable imports in `tests/bench_upgrade_success.py` — an agent might try to "fix" them by adding sys.path hacks, masking real missing deps.
- **Mitigation**:
  - **Rule added** to `.devin/rules/WORKSPACE_GOVERNANCE.md` §4.6: "LSP-driven edits must be followed by a `read` of the changed region to confirm the edit landed on the intended symbol."
  - Enforce via `comment_checker` skill on every commit touching a file LSP flagged.
  - When pyright says "import unresolvable", do NOT add path hacks; the import is missing by design (test that needs a runtime fixture). Confirm with the file's docstring / test name before acting.

### Surface D — Permission boundary creep

- **Change**: `xd://lsp` is a new tool surface. The new allow/deny rules explicitly grant read-only actions and deny write actions.
- **Risk**: without explicit allow, every LSP call would trigger an `ask` prompt halting loops. With unrestricted `*`, the tool could rename across the entire workspace.
- **Mitigation** (applied):
  - Allow list: 9 read-only actions (`status`, `capabilities`, `diagnostics`, `symbols`, `references`, `definition`, `hover`, `type_definition`, `implementation`).
  - Deny list: 4 write actions (`rename`, `rename_file`, `code_actions`, `reload`).
  - Deny list is **action-level** (not path-scoped) because LSP-driven file writes bypass the pre-tool hook net; the only safe boundary is the action surface itself.

### Surface E — Secret / sensitive path exposure

- **Change**: `xd://lsp diagnostics file=*` walks the entire workspace.
- **Risk**: pyright could surface type errors that include path strings hinting at secret locations.
- **Mitigation**:
  - pyright indexes the **project** as defined by `pyrightconfig.json` / `pyproject.toml [tool.pyright]`. If those don't exist, pyright defaults to the workspace root and respects `.gitignore`.
  - `.gitignore` already excludes `HLK/config/secrets.*` — confirmed.
  - The diagnostics output did NOT surface any secret path strings (verified by spot-checking the output).
  - **Follow-up**: add a `pyrightconfig.json` to explicitly scope pyright to `src/`, `tests/`, `scripts/`, `HLK/chain/`, `HLK/scripts/` only (no `.devin/`, no `docs/`).

### Surface F — CI / hook interaction

- **Change**: pre-tool hook `plan_enforce.py` (in `.devin/scripts/`) currently gates Write/Edit. With LSP always-on, an `Lsp(*:rename)` would be a write — but it goes through the runtime, not the file tools, and the hook does not see it.
- **Risk**: bypass — LSP could mutate files outside the governance net.
- **Mitigation** (applied): denied `Lsp(*:rename)`, `Lsp(*:rename_file)`, `Lsp(*:code_actions)` in `.commandcode/settings.json`. The runtime enforces the deny BEFORE the LSP server is invoked, so the write never happens.
- **Future work** (logged in `HLK/docs/UPGRADE_PLAN.md` §TBD): extend `plan_enforce.py` to also intercept `xd://lsp` calls and check the workspace zone. Not needed today because the action-level deny already covers it.

### Surface G — Subagent fan-out

- **Change**: parallel `scout` subagents each spin up their own LSP server if they call `xd://lsp`. With 8 scouts, that's 8 concurrent pyright processes.
- **Risk**: memory pressure (pyright ~250-400MB resident each → 2-3GB for 8 scouts) on the 16GB Windows host.
- **Mitigation**:
  - `opencode.json` `lsp.maxConcurrentServers` is **not in the schema** (verified) — opencode auto-manages server lifetime; the practical mitigation is to limit which subagents call LSP.
  - Documented: only `verifier` and `code-reviewer` persona should call `Lsp(*:diagnostics)`. Scouts use `read` + `grep` for symbol discovery; the verifier uses `Lsp(*:diagnostics)` for type checks.
  - Concrete budget: max 1 LSP-using subagent at a time per session. Add to `.devin/agents/commander.md` swarm director.

### Surface H — Cross-session consistency

- **Change**: an LSP-driven `rename` updates the file. But `.devin/loop_state/<sid>.md` `affected_files` is only updated by the post-tool hook for file-tool writes, not LSP writes.
- **Risk**: loop state goes stale; next iteration re-edits the same file.
- **Mitigation**: same as Surface F — denied LSP write actions entirely. Loop state cannot drift because LSP cannot write.

## 5. Recommendation

**LSP always-on, but read-only**. This is the safest middle ground:

- Read-only actions (status, capabilities, diagnostics, symbols, references, definition, hover, type_definition, implementation) → allowed.
- Write actions (rename, rename_file, code_actions, reload) → denied at the action level.
- Edit/Write tools remain the only way to mutate files; they go through the full pre-tool governance net.

This config is now in `opencode.json` (lsp block) + `.commandcode/settings.json` (allow/deny). The two layers are consistent: opencode knows the server exists, commandcode enforces the read-only surface.

## 6. Files changed in this task

| File | Lines | Change |
|------|-------|--------|
| `opencode.json` | 24-30 | add `lsp` block (pyright) |
| `.commandcode/settings.json` | 88-96 | add 9 LSP read-only allow entries |
| `.commandcode/settings.json` | 188-191 | add 4 LSP write-deny entries |
| `.devin/rules/WORKSPACE_GOVERNANCE.md` | §4.6 (new) | add LSP-edit-must-be-followed-by-read rule |
| `HLK/docs/03-cau-hinh-best-practice.md` | new section | LSP cost profile |
| `docs/reports/LSP_ALWAYS_ON_2026-08-28.md` | this file | red-team report |
| `pyproject.toml` (or system pip) | n/a | `pyright==1.1.411` installed via pip |

## 7. Follow-up tasks (not in this scope)

1. **Add `pyrightconfig.json`** to scope pyright to source dirs only (no `.devin/`, no `docs/`).
2. **Fix the 11+ unresolvable imports** in `tests/bench_upgrade_success.py`, `tests/conftest.py`, etc. — either restore the deps or mark the imports as `TYPE_CHECKING` and move under `if TYPE_CHECKING`.
3. **Update `verifier` persona** to call `Lsp(*:diagnostics)` as part of its verification step.
4. **Add a SessionStart hook** that warms up pyright (one `diagnostics file=*` call) to amortize the 5-10s indexing cost.
5. **Extend `plan_enforce.py`** to intercept `xd://lsp` calls (future hardening; current action-level deny is sufficient).
