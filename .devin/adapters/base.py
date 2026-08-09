"""Base adapter — shared logic for all tool adapters.

Each per-tool adapter imports `BaseAdapter` and binds a `tool_id` from registry.json.
The heavy lifting (path expansion, detection, backup, write, read-back) lives here so
adapters stay thin and the registry stays the single source of tool-specific data.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"
ROOT = Path(__file__).resolve().parent.parent

# Asset source directories in the deployer repo. These get copied into each detected
# tool's native config location so the multi-agent architecture is actually deployable —
# not just referenced in text.
ASSET_SOURCES = {
    "skills": ROOT / "distill" / "skills",
    "orchestrator": ROOT / "distill" / "orchestrator",
    "canon": ROOT / "distill" / "canon",
    "vault": ROOT / "core" / "assets" / "vault",
    # Vendored external skills (anti-link-rot). nuwa-skill is a cognitive-diversity
    # skill distillation factory, vendored from alchaincyf/nuwa-skill so users never
    # need to download it separately. See core/assets/skills/nuwa-skill/ATTRIBUTION.md.
    "nuwa_skill": ROOT / "core" / "assets" / "skills" / "nuwa-skill",
    # Runtime layer: hooks (guards/loggers/cleanup), settings templates (permissions
    # + hook registration), MCP templates (server registration). This is what makes
    # the harness rules actually execute at the tool level — not just exist as text.
    "runtime": ROOT / "core" / "assets" / "runtime",
    # Runtime helper scripts that need to be reachable from a deployed project.
    "runtime_scripts": ROOT / "scripts",
}


def expand(path: str) -> str:
    """Expand env vars (${HOME}, ${APPDATA}, ...) and ~ in a path string.

    Cross-platform fallbacks:
    - On Unix: ${APPDATA} → ~/.config, ${LOCALAPPDATA} → ~/.local/share,
      ${USERPROFILE} → ~ (Windows-only vars mapped to XDG/home equivalents).
    - On Windows: ${HOME} → %USERPROFILE% (Unix-only var mapped to Windows
      equivalent). Windows does not set HOME by default, so registry paths
      using ${HOME} (e.g. Windsurf, Cline, Roo, Continue MCP files) would
      never expand without this fallback.
    This prevents paths like ${APPDATA}/Claude becoming /Claude (root) on Unix,
    and ${HOME}/.codeium/... staying as a literal ${HOME} directory on Windows.
    """
    if path is None:
        return None
    # Platform-specific env var fallbacks
    if sys.platform != "win32":
        fallbacks = {
            "APPDATA": os.path.join(os.path.expanduser("~"), ".config"),
            "LOCALAPPDATA": os.path.join(os.path.expanduser("~"), ".local", "share"),
            "USERPROFILE": os.path.expanduser("~"),
        }
    else:
        # Windows: HOME is not set by default; map to USERPROFILE (os.path.expanduser("~"))
        fallbacks = {
            "HOME": os.path.expanduser("~"),
        }
    for var, val in fallbacks.items():
        if var not in os.environ:
            os.environ[var] = val
    # ${VAR} style
    for key, val in os.environ.items():
        path = path.replace(f"${{{key}}}", val)
    # ~ style
    path = os.path.expanduser(path)
    return path


def load_registry() -> dict:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_bak_marker(bak_path: Path) -> None:
    """Write a sidecar marker next to a .bak file created by new AHD.

    This allows migrate.py to distinguish:
    - .bak with marker = created by new AHD's --global deploy (normal, don't restore)
    - .bak without marker = created by old AHD's pollution (legacy, safe to restore)

    The marker is a tiny JSON file named ``<bak_path>.ahd_managed``.
    """
    marker_path = Path(str(bak_path) + ".ahd_managed")
    marker = {
        "managed_by": "Agent Harness Deploy",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "purpose": "MCP config backup from --global deploy (not legacy pollution)",
    }
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")


def get_tool_spec(tool_id: str) -> dict:
    reg = load_registry()
    for t in reg["tools"]:
        if t["id"] == tool_id:
            return t
    raise KeyError(f"tool_id '{tool_id}' not in registry.json")


@dataclass
class DetectResult:
    tool_id: str
    name: str
    detected: bool
    evidence: str


@dataclass
class SyncResult:
    tool_id: str
    name: str
    target_path: str
    status: str  # "written" | "skipped" | "backup_created" | "failed"
    backup_path: Optional[str]
    error: Optional[str]


class BaseAdapter:
    """Shared adapter logic. Subclasses set `tool_id`; everything else comes from registry."""

    tool_id: str = ""

    def __init__(self, project_root: str | Path = "."):
        self.project_root = Path(project_root).resolve()
        self.spec = get_tool_spec(self.tool_id)
        self.name = self.spec["name"]
        self.config = self.spec["config"]

    # --- detection -------------------------------------------------------
    def detect(self) -> DetectResult:
        checks = self.spec["detect"]["checks"]
        method = self.spec["detect"]["method"]  # "any" or "all"
        results = []
        for chk in checks:
            ok, ev = self._run_check(chk)
            results.append((ok, ev))
            if method == "any" and ok:
                return DetectResult(self.tool_id, self.name, True, ev)
        if method == "all" and all(r[0] for r in results):
            return DetectResult(self.tool_id, self.name, True, "; ".join(r[1] for r in results))
        return DetectResult(self.tool_id, self.name, False, "no check passed")

    def _run_check(self, chk: dict) -> tuple[bool, str]:
        ctype = chk["type"]
        val = expand(chk["value"])
        scope = chk.get("scope", "global")
        if ctype == "command":
            try:
                r = subprocess.run(
                    chk["value"], shell=True, capture_output=True, timeout=10
                )
                return (r.returncode == 0, f"cmd:{chk['value']} rc={r.returncode}")
            except Exception as e:
                return (False, f"cmd:{chk['value']} err={e}")
        if ctype == "dir":
            p = Path(val)
            if scope == "project" and not p.is_absolute():
                p = self.project_root / p
            return (p.is_dir(), f"dir:{p} exists={p.is_dir()}")
        if ctype == "file":
            p = Path(val)
            if scope == "project" and not p.is_absolute():
                p = self.project_root / p
            return (p.is_file(), f"file:{p} exists={p.is_file()}")
        if ctype == "glob":
            p = Path(val)
            matches = list(p.parent.glob(p.name))
            return (len(matches) > 0, f"glob:{val} matches={len(matches)}")
        return (False, f"unknown check type {ctype}")

    # --- path resolution -------------------------------------------------
    def project_entry_path(self) -> Optional[Path]:
        p = self.config.get("project_entry")
        if not p:
            return None
        return self.project_root / p

    def global_entry_path(self) -> Optional[Path]:
        p = self.config.get("global_entry")
        if not p:
            return None
        return Path(expand(p))

    # --- sync ------------------------------------------------------------
    def sync(self, canonical_body: str, *, global_too: bool = False) -> list[SyncResult]:
        results: list[SyncResult] = []
        det = self.detect()
        if not det.detected:
            results.append(SyncResult(self.tool_id, self.name, "(undetected)",
                                      "skipped", None, "tool not detected"))
            return results

        # project-level entry
        proj_path = self.project_entry_path()
        if proj_path is not None:
            results.append(self._write_entry(proj_path, canonical_body))

        # global-level entry (opt-in)
        if global_too:
            gpath = self.global_entry_path()
            if gpath is not None:
                results.append(self._write_entry(gpath, canonical_body))

        # assets (skills, orchestrator prompts, vault) — project-level only.
        # Without this, the entry file tells the agent to "see COMMANDER.md" but that
        # file is never copied to the tool's config location. The multi-agent architecture
        # exists in the deployer repo but never reaches the user's tool.
        results.extend(self._sync_assets())

        # runtime layer (hooks, settings, MCP).
        # This is what makes the harness rules actually execute at the tool level.
        # The prompt layer tells the agent what to do; the runtime layer makes the
        # tool itself enforce it (guards, loggers, cleanup, permissions, MCP).
        # Project-scoped runtime files are always written; global-scoped files
        # (e.g. ~/.codeium/windsurf/mcp_config.json) are only written when
        # global_too=True, preventing cross-project pollution.
        results.extend(self._sync_runtime(global_too=global_too))

        return results

    def _write_entry(self, target: Path, body: str) -> SyncResult:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if target.exists():
                backup = target.with_suffix(target.suffix + ".bak")
                shutil.copy2(target, backup)
            # Rewrite canonical source paths to deployed paths before wrapping/writing.
            body = self._rewrite_text(body)
            # Cursor .mdc needs frontmatter
            if self.config.get("format") == "mdc":
                body = self._wrap_mdc(body)
            # Claude Desktop JSON is a different shape
            if self.config.get("format") == "json":
                body = self._wrap_json(target, body)
            target.write_text(body, encoding="utf-8")
            return SyncResult(self.tool_id, self.name, str(target), "written",
                              str(backup) if backup else None, None)
        except Exception as e:
            return SyncResult(self.tool_id, self.name, str(target), "failed", None, str(e))

    # --- asset sync ------------------------------------------------------
    def _sync_assets(self) -> list[SyncResult]:
        """Copy skills, orchestrator prompts, canon, and vault assets to the tool's config dirs.

        This is what makes the multi-agent architecture actually deployable. The entry
        file (CLAUDE.md, AGENTS.md, instructions.md) contains rules that reference
        orchestrator prompts, skills, canon, and vault assets. Without copying those
        files to the tool's native config location, the agent reads "see COMMANDER.md"
        but can't find it.

        Targets are read from registry.json: skills_dir, agents_dir. Tools without these
        fields (Cursor, Claude Desktop, CLI variants) get no asset copy — their entry
        file already contains the full canonical body inline.
        """
        results = []

        skills_src = ASSET_SOURCES["skills"]
        orchestrator_src = ASSET_SOURCES["orchestrator"]
        canon_src = ASSET_SOURCES["canon"]
        vault_src = ASSET_SOURCES["vault"]
        nuwa_src = ASSET_SOURCES["nuwa_skill"]

        # Skills → skills_dir
        skills_dir_rel = self.config.get("skills_dir")
        if skills_dir_rel and skills_src.is_dir():
            target = self.project_root / skills_dir_rel
            results.extend(self._copy_tree(skills_src, target))

        # Orchestrator prompts (Commander, dispatch templates, worker personas) → agents_dir
        agents_dir_rel = self.config.get("agents_dir")
        if agents_dir_rel and orchestrator_src.is_dir():
            target = self.project_root / agents_dir_rel
            results.extend(self._copy_tree(orchestrator_src, target))

        # Canonical protocols (REDLINES, BOOT, LOOP, etc.) → <config_root>/canon/
        cfg_root = self._config_root_rel()
        if cfg_root and canon_src.is_dir():
            target = self.project_root / cfg_root / "canon"
            results.extend(self._copy_tree(canon_src, target))

        # Vault assets (anti-link-rot templates) → <skills_dir|agents_dir>/assets/vault/
        vault_base_rel = skills_dir_rel or agents_dir_rel
        if vault_base_rel and vault_src.is_dir():
            target = self.project_root / vault_base_rel / "assets" / "vault"
            results.extend(self._copy_tree(vault_src, target))

        # Vendored nuwa-skill (cognitive-diversity skill factory) →
        # <skills_dir|agents_dir>/nuwa-skill/
        # Deployed alongside the project's own skills so the tool's AI can invoke it
        # without any download. See core/assets/skills/nuwa-skill/ATTRIBUTION.md.
        if vault_base_rel and nuwa_src.is_dir():
            target = self.project_root / vault_base_rel / "nuwa-skill"
            results.extend(self._copy_tree(nuwa_src, target))

        return results

    # --- runtime sync ----------------------------------------------------
    def _sync_runtime(self, *, global_too: bool = False) -> list[SyncResult]:
        """Deploy runtime layer: hooks, settings, MCP config.

        This is what makes the harness rules actually execute at the tool level.
        The prompt layer (CLAUDE.md, skills) tells the agent what to do; the
        runtime layer (hooks, permissions, MCP) makes the tool itself enforce it.

        Three pieces:
        1. Hook scripts (Python, cross-platform) → hooks_dir
        2. Settings file (permissions + hook registration) → settings_file (merged)
        3. MCP config (server registration) → mcp_file (merged)

        Scope handling:
        - Project-relative paths (e.g. '.mcp.json', '.claude/hooks/') are always
          written — they don't affect other projects.
        - Global paths (e.g. '${HOME}/.codeium/windsurf/mcp_config.json') are
          only written when ``global_too=True`` (the --global flag). Without it,
          global-scoped runtime files are skipped to prevent cross-project
          pollution.

        All merges preserve existing user config — Agent Harness Deploy only adds/updates
        its own keys. A .bak backup is created before any overwrite.
        """
        results = []
        rt = self.spec.get("runtime", {})
        if not rt.get("enabled"):
            return results

        runtime_src = ASSET_SOURCES["runtime"]
        if not runtime_src.is_dir():
            return results

        # 1. Copy hook scripts to hooks_dir
        hooks_dir_rel = rt.get("hooks_dir")
        if hooks_dir_rel:
            hooks_src = runtime_src / "hooks"
            if hooks_src.is_dir():
                target = self._resolve_scoped_path(hooks_dir_rel, global_too)
                if target is not None:
                    results.extend(self._copy_tree(hooks_src, target))

        # 2. Merge settings file (permissions + hook registration)
        settings_file_rel = rt.get("settings_file")
        settings_template = rt.get("settings_template")
        settings_format = rt.get("settings_format", "json")
        if settings_file_rel and settings_template:
            template_path = runtime_src / "settings" / settings_template
            if template_path.is_file():
                target = self._resolve_scoped_path(settings_file_rel, global_too)
                if target is not None:
                    results.append(self._merge_settings(target, template_path, settings_format))

        # 3. Merge MCP config
        mcp_file_rel = rt.get("mcp_file")
        mcp_template = rt.get("mcp_template")
        mcp_format = rt.get("mcp_format", "json")
        if mcp_file_rel and mcp_template:
            template_path = runtime_src / "mcp" / mcp_template
            if template_path.is_file():
                target = self._resolve_scoped_path(mcp_file_rel, global_too)
                if target is not None:
                    results.append(self._merge_mcp(target, template_path, mcp_format))

        # 4. Copy runtime helper scripts to <runtime_root>/scripts/ and seed session runtime dirs
        #    These are needed by the orchestrator prompts regardless of tool-specific hooks.
        #    Runtime root is tool-specific (e.g. .agents/ for Antigravity, .claude/ for Claude Code).
        runtime_root = self._runtime_root_rel()
        scripts_dir = self.project_root / runtime_root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ("session_state", "loop_state", "loop_state_archive", "context_flags"):
            (self.project_root / runtime_root / subdir).mkdir(parents=True, exist_ok=True)

        # Ensure .agents/ exists for shared state files (user_profile.md,
        # knowledge_distill.md, handoff_letter.md, context_quick_lookup.md).
        # These are shared across all tools and always live at .agents/, even
        # if Antigravity is not installed.
        if runtime_root != ".agents":
            (self.project_root / ".agents").mkdir(parents=True, exist_ok=True)
            # Migrate: if shared state files exist in this tool's root but not
            # in .agents/, copy them so existing users don't lose their data.
            for sf in ("user_profile.md", "knowledge_distill.md",
                       "handoff_letter.md", "context_quick_lookup.md"):
                tool_copy = self.project_root / runtime_root / sf
                agents_copy = self.project_root / ".agents" / sf
                if tool_copy.exists() and not agents_copy.exists():
                    shutil.copy2(tool_copy, agents_copy)

        for script_name in (
            "worktree.py", "plan_dispatch.py", "session_manager.py",
            "loop_memory_sync.py", "memory_audit.py", "pre_task_audit.py"
        ):
            src = ASSET_SOURCES["runtime_scripts"] / script_name
            if src.is_file():
                results.append(self._copy_file_with_rewrite(src, scripts_dir / script_name))

        # 5. Copy ahd_session.py to .agents/scripts/ so scripts can import it
        ahd_src = ASSET_SOURCES["runtime"] / "hooks" / "ahd_session.py"
        if ahd_src.is_file():
            results.append(self._copy_file_with_rewrite(ahd_src, scripts_dir / "ahd_session.py"))
            # Also copy to hooks dir if it was not already present (some tools may only copy scripts)
            hooks_dir_rel = rt.get("hooks_dir")
            if hooks_dir_rel:
                hooks_dir = self.project_root / hooks_dir_rel
                if hooks_dir.exists():
                    results.append(self._copy_file_with_rewrite(ahd_src, hooks_dir / "ahd_session.py"))

        return results

    def _merge_settings(self, target: Path, template_path: Path, fmt: str) -> SyncResult:
        """Merge a settings template into the target file, preserving existing config.

        For JSON: deep-merge — existing keys are kept, Agent Harness Deploy keys are added/updated.
        For TOML: append Agent Harness Deploy section (simplest safe merge for TOML).
        """
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if target.exists():
                backup = target.with_suffix(target.suffix + ".bak")
                shutil.copy2(target, backup)

            if fmt == "json":
                return self._merge_json_settings(target, template_path, backup)
            elif fmt == "toml":
                return self._merge_toml_settings(target, template_path, backup)
            elif fmt == "yaml":
                return self._merge_yaml_settings(target, template_path, backup)
            else:
                # Unknown format — just copy the template
                shutil.copy2(template_path, target)
                return SyncResult(self.tool_id, self.name, str(target), "written",
                                  str(backup) if backup else None, None)
        except Exception as e:
            return SyncResult(self.tool_id, self.name, str(target), "failed", None, str(e))

    def _merge_json_settings(self, target: Path, template_path: Path, backup) -> SyncResult:
        """Deep-merge JSON settings: existing user keys preserved, Agent Harness Deploy keys added."""
        # Load existing
        existing = {}
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        # Load template
        template = json.loads(template_path.read_text(encoding="utf-8"))

        # Deep merge: Agent Harness Deploy keys override, user keys preserved
        merged = self._deep_merge(existing, template)

        target.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
        return SyncResult(self.tool_id, self.name, str(target), "written",
                          str(backup) if backup else None, None)

    def _merge_toml_settings(self, target: Path, template_path: Path, backup) -> SyncResult:
        """Merge TOML settings: append Agent Harness Deploy sections if not present.

        TOML doesn't have a standard deep-merge. We use a simple approach:
        - If target doesn't exist → copy template
        - If target exists → append template content with an Agent Harness Deploy marker
          (user can deduplicate manually if needed; .bak preserves original)
        """
        if not target.exists():
            shutil.copy2(template_path, target)
            return SyncResult(self.tool_id, self.name, str(target), "written", None, None)

        existing = target.read_text(encoding="utf-8")
        template = template_path.read_text(encoding="utf-8")

        # Check if Agent Harness Deploy sections already present
        if "[hooks]" in existing and "agent harness deploy" in existing.lower():
            # Already has Agent Harness Deploy hooks — skip (idempotent)
            return SyncResult(self.tool_id, self.name, str(target), "skipped",
                              None, "agent harness deploy hooks already present")

        # Append Agent Harness Deploy sections
        marker = "\n# --- Agent Harness Deploy runtime (auto-generated, merge with care) ---\n"
        target.write_text(existing + marker + template, encoding="utf-8")
        return SyncResult(self.tool_id, self.name, str(target), "written",
                          str(backup) if backup else None, None)

    def _merge_yaml_settings(self, target: Path, template_path: Path, backup) -> SyncResult:
        """Merge YAML settings: append Agent Harness Deploy hooks if not present.

        Similar to TOML — append with marker. YAML doesn't have a standard
        deep-merge library in stdlib, so we use the same append approach.
        """
        if not target.exists():
            shutil.copy2(template_path, target)
            return SyncResult(self.tool_id, self.name, str(target), "written", None, None)

        existing = target.read_text(encoding="utf-8")
        template = template_path.read_text(encoding="utf-8")

        # Check if Agent Harness Deploy hooks already present
        if "agent harness deploy" in existing.lower() and "hooks:" in existing:
            return SyncResult(self.tool_id, self.name, str(target), "skipped",
                              None, "agent harness deploy hooks already present")

        marker = "\n# --- Agent Harness Deploy runtime (auto-generated, merge with care) ---\n"
        target.write_text(existing + marker + template, encoding="utf-8")
        return SyncResult(self.tool_id, self.name, str(target), "written",
                          str(backup) if backup else None, None)

    def _deep_merge(self, base: dict, overlay: dict) -> dict:
        """Deep-merge overlay onto base. Overlay keys win; base keys preserved if not in overlay."""
        result = dict(base)
        for key, val in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = self._deep_merge(result[key], val)
            else:
                result[key] = val
        return result

    def _config_root_rel(self) -> Optional[str]:
        """Return the tool config root (parent of skills_dir/agents_dir) relative to project root.

        Examples:
        - claude_code: .claude/
        - antigravity: .agents/
        - devin: .devin/
        """
        for rel in (self.config.get("skills_dir"), self.config.get("agents_dir"),
                    self.config.get("rules_dir"),
                    self.spec.get("runtime", {}).get("hooks_dir")):
            if rel:
                p = Path(rel)
                parts = [part for part in p.parts if part not in (".", "")]
                if not parts:
                    continue
                # First directory component is the config root.
                root = parts[0]
                return root + "/"
        return None

    def _runtime_root_rel(self) -> str:
        """Return the directory (relative to project root) for runtime scripts and
        session state dirs.

        Defaults to the tool's config root (e.g. ``.agents`` for Antigravity,
        ``.claude`` for Claude Code). Falls back to ``.agents`` if no config root
        can be determined (e.g. Claude Desktop, which is global-only).

        This is what fixes the config-root mismatch issue: Antigravity expects
        ``.agents/`` but the deployer was previously hardcoding the wrong directory
        for runtime scripts and session state dirs, making the deployed project unusable.
        """
        cfg_root = self._config_root_rel()
        if cfg_root:
            return cfg_root.rstrip("/")
        return ".agents"

    def _resolve_scoped_path(self, rel: str, global_too: bool) -> Optional[Path]:
        """Resolve a runtime path from registry, respecting global/project scope.

        - Project-relative paths (e.g. '.mcp.json', '.claude/settings.json') →
          always resolved against project_root. These don't affect other projects.
        - Global paths (e.g. '${HOME}/.codeium/windsurf/mcp_config.json',
          '${APPDATA}/Claude/claude_desktop_config.json') → only resolved when
          ``global_too=True``; returns ``None`` otherwise so the caller skips.

        This fixes two bugs:
        1. Env vars (${HOME}, ${APPDATA}) were never expanded for runtime paths,
           creating literal '${HOME}' directories under the project root.
        2. Global-scoped MCP/settings files were written even without --global,
           polluting global config from a project-level deploy.
        """
        if not rel:
            return None
        expanded = expand(rel)
        if os.path.isabs(expanded):
            if not global_too:
                return None
            return Path(expanded)
        return self.project_root / rel

    def _path_replacements(self) -> list[tuple[str, str]]:
        """Build source -> deployed path replacements for this tool.

        Canonical text uses repo-root paths (distill/..., core/..., scripts/...).
        When deployed, these must point to the tool's native config location.
        """
        reps: list[tuple[str, str]] = []
        skills_dir = self.config.get("skills_dir")
        agents_dir = self.config.get("agents_dir")
        vault_base = skills_dir or agents_dir
        cfg_root = self._config_root_rel()

        # canon → <config_root>/canon/
        if cfg_root:
            reps.append(("distill/canon/", cfg_root + "canon/"))
        # orchestrator prompts → agents_dir (or config root for antigravity-style)
        if agents_dir:
            reps.append(("distill/orchestrator/", agents_dir.replace("\\", "/").rstrip("/") + "/"))
        elif cfg_root:
            reps.append(("distill/orchestrator/", cfg_root))
        # skills → skills_dir
        if skills_dir:
            reps.append(("distill/skills/", skills_dir.replace("\\", "/").rstrip("/") + "/"))
        elif cfg_root:
            reps.append(("distill/skills/", cfg_root + "skills/"))
        # vault and nuwa-skill
        if vault_base:
            vault_dir = vault_base.replace("\\", "/").rstrip("/") + "/assets/vault/"
            nuwa_dir = vault_base.replace("\\", "/").rstrip("/") + "/nuwa-skill/"
            reps.append(("core/assets/vault/", vault_dir))
            reps.append(("core/assets/skills/nuwa-skill/", nuwa_dir))
        # Runtime helper scripts → <runtime_root>/scripts/
        runtime_root = self._runtime_root_rel()
        scripts_dst = runtime_root + "/scripts/"
        reps.append(("scripts/worktree.py", scripts_dst + "worktree.py"))
        reps.append(("scripts/plan_dispatch.py", scripts_dst + "plan_dispatch.py"))
        reps.append(("scripts/session_manager.py", scripts_dst + "session_manager.py"))
        reps.append(("scripts/loop_memory_sync.py", scripts_dst + "loop_memory_sync.py"))
        reps.append(("scripts/memory_audit.py", scripts_dst + "memory_audit.py"))
        reps.append(("scripts/pre_task_audit.py", scripts_dst + "pre_task_audit.py"))
        # Hook helper
        reps.append(("core/assets/runtime/hooks/ahd_session.py", scripts_dst + "ahd_session.py"))
        # Runtime state directory: rewrite canonical .agents/ placeholder to the
        # tool's actual config root. This covers canon/skills/scripts references.
        # Only added when the runtime root differs from the placeholder.
        if runtime_root != ".agents":
            reps.append((".agents/", runtime_root + "/"))
            # Shared state files are project-owned and always live at .agents/
            # (the canonical state root). They are shared across all tools, so
            # we reverse the blanket replacement for these specific files.
            # Without this, Codex/Windsurf/Devin would look for
            # .codex/user_profile.md etc. which don't exist.
            #
            # Per-tool session state (loop_state.md, loop_state/, session_state/,
            # context_flags/) stays at the tool's runtime root — each tool
            # manages its own sessions independently.
            shared_state_files = [
                "knowledge_distill.md",
                "user_profile.md",
                "handoff_letter.md",
                "context_quick_lookup.md",
            ]
            for sf in shared_state_files:
                reps.append((f"{runtime_root}/{sf}", f".agents/{sf}"))
        return reps

    def _rewrite_text(self, text: str) -> str:
        """Rewrite canonical source paths to deployed paths.

        Must be called on the canonical body and on every copied asset file.
        """
        for old, new in self._path_replacements():
            text = text.replace(old, new)
        return text

    def _copy_file_with_rewrite(self, src: Path, dst: Path) -> SyncResult:
        """Copy a single file, rewriting source paths for text files.

        Backs up an existing file before overwrite. Returns a SyncResult.
        """
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if dst.exists():
                if dst.read_bytes() == src.read_bytes():
                    return SyncResult(
                        self.tool_id, self.name, str(dst), "skipped",
                        None, "identical content")
                backup = dst.with_suffix(dst.suffix + ".bak")
                shutil.copy2(dst, backup)

            data = src.read_bytes()
            if src.suffix.lower() in {".md", ".py", ".json", ".toml", ".yaml", ".yml", ".txt", ".mdc", ".mdx"}:
                try:
                    text = data.decode("utf-8")
                    text = self._rewrite_text(text)
                    data = text.encode("utf-8")
                except UnicodeDecodeError:
                    pass
            dst.write_bytes(data)
            return SyncResult(
                self.tool_id, self.name, str(dst), "written",
                str(backup) if backup else None, None)
        except Exception as e:
            return SyncResult(
                self.tool_id, self.name, str(dst), "failed", None, str(e))

    def _merge_mcp(self, target: Path, template_path: Path, fmt: str) -> SyncResult:
        """Merge MCP config template into target, preserving existing MCP servers."""
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if target.exists():
                backup = target.with_suffix(target.suffix + ".bak")
                shutil.copy2(target, backup)
                # Mark this .bak as managed by new AHD so migrate.py doesn't
                # mistake it for legacy pollution from old AHD versions.
                _write_bak_marker(backup)

            if fmt == "json":
                existing = {}
                if target.exists():
                    try:
                        existing = json.loads(target.read_text(encoding="utf-8"))
                    except Exception:
                        existing = {}

                template = json.loads(template_path.read_text(encoding="utf-8"))

                # Merge mcpServers: existing servers preserved, template servers added.
                # Strip any non-standard _-prefixed keys (e.g. _disabled, _enable_instructions,
                # _comment_*) from server configs and from the mcpServers map itself, so that
                # re-running sync cleans up legacy deploys that polluted user MCP files.
                existing_servers = existing.get("mcpServers", {})
                template_servers = template.get("mcpServers", {})

                def _clean_servers(servers: dict) -> dict:
                    cleaned = {}
                    for name, cfg in servers.items():
                        if name.startswith("_"):
                            continue  # drop _comment_* pseudo-servers
                        if isinstance(cfg, dict):
                            cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
                        cleaned[name] = cfg
                    return cleaned

                merged_servers = _clean_servers(existing_servers)
                for name, cfg in _clean_servers(template_servers).items():
                    if name not in merged_servers:
                        merged_servers[name] = cfg
                existing["mcpServers"] = merged_servers

                target.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
                return SyncResult(self.tool_id, self.name, str(target), "written",
                                  str(backup) if backup else None, None)
            else:
                # TOML or other — just copy template if target doesn't exist
                if not target.exists():
                    shutil.copy2(template_path, target)
                return SyncResult(self.tool_id, self.name, str(target), "written",
                                  str(backup) if backup else None, None)
        except Exception as e:
            return SyncResult(self.tool_id, self.name, str(target), "failed", None, str(e))

    def _copy_tree(self, src: Path, dst: Path) -> list[SyncResult]:
        """Copy a directory tree recursively, backing up existing files before overwriting.

        Idempotent: if a file already exists with identical content, it is skipped (no
        .bak created). If content differs, the existing file is backed up to .bak first.
        Text files (md, py, json, toml, yaml, yml, txt, mdc, mdx) are rewritten in place
        so that source paths (distill/..., core/..., scripts/...) map to the deployed
        location.
        """
        results = []
        if not src.exists() or not src.is_dir():
            return results

        for src_file in sorted(src.rglob("*")):
            if src_file.is_dir():
                continue
            # Skip runtime cache / bytecode artifacts (red line: never ship .pyc)
            if "__pycache__" in src_file.parts or src_file.suffix == ".pyc":
                continue
            rel = src_file.relative_to(src)
            dst_file = dst / rel
            results.append(self._copy_file_with_rewrite(src_file, dst_file))
        return results

    def _wrap_mdc(self, body: str) -> str:
        front = (
            "---\n"
            "description: Agent Harness Deploy harness rules\n"
            "globs: **/*\n"
            "alwaysApply: true\n"
            "---\n\n"
        )
        return front + body

    def _wrap_json(self, target: Path, body: str) -> str:
        """For Claude Desktop: inject a pointer, not the full canon body."""
        try:
            existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        except Exception:
            existing = {}
        existing.setdefault("mcpServers", {})
        existing["_agent_harness_deploy"] = {
            "installed": True,
            "rules_pointer": "See distill/canon/ in the Agent Harness Deploy repo for full harness rules.",
        }
        return json.dumps(existing, indent=2, ensure_ascii=False)

    # --- verify ----------------------------------------------------------
    def verify(self) -> list[tuple[str, bool, str]]:
        """Read back written entries and copied assets; confirm integrity."""
        out = []
        for label, path in (("project", self.project_entry_path()),
                            ("global", self.global_entry_path())):
            if path is None or not path.exists():
                continue
            try:
                content = path.read_text(encoding="utf-8")
                # Cursor mdc wraps in frontmatter; check body after '---'
                if self.config.get("format") == "mdc":
                    content = content.split("---", 2)[-1] if content.count("---") >= 2 else content
                ok = "Agent Harness Deploy" in content or "agent harness deploy" in content.lower()
                out.append((f"{label}:{path}", ok, "marker present" if ok else "marker missing"))
            except Exception as e:
                out.append((f"{label}:{path}", False, str(e)))

        # Asset verification — check that key files were actually copied
        skills_dir_rel = self.config.get("skills_dir")
        if skills_dir_rel:
            skills_dir = self.project_root / skills_dir_rel
            # Check a representative skill file
            auditor_path = skills_dir / "auditor.md"
            exists = auditor_path.exists()
            out.append((f"asset:{auditor_path}", exists,
                        "skill present" if exists else "skill missing"))

        agents_dir_rel = self.config.get("agents_dir")
        if agents_dir_rel:
            agents_dir = self.project_root / agents_dir_rel
            # Check the Commander prompt (the core orchestrator file)
            commander_path = agents_dir / "COMMANDER.md"
            exists = commander_path.exists()
            out.append((f"asset:{commander_path}", exists,
                        "orchestrator present" if exists else "orchestrator missing"))

        # Canon check — canonical protocols were copied to <config_root>/canon/
        cfg_root = self._config_root_rel()
        if cfg_root:
            canon_dir = self.project_root / cfg_root / "canon"
            for canon_file in ("CAVEMAN_PROTOCOL.md", "BOOT_PROTOCOL.md", "REDLINES.md"):
                path = canon_dir / canon_file
                exists = path.exists()
                out.append((f"asset:{path}", exists,
                            "canon present" if exists else "canon missing"))

        # Vault check — at least one vault asset file
        vault_base_rel = skills_dir_rel or agents_dir_rel
        if vault_base_rel:
            vault_dir = self.project_root / vault_base_rel / "assets" / "vault"
            caveman_path = vault_dir / "caveman_template.json"
            exists = caveman_path.exists()
            out.append((f"asset:{caveman_path}", exists,
                        "vault asset present" if exists else "vault asset missing"))

            # Vendored nuwa-skill check — SKILL.md must be deployed
            nuwa_path = self.project_root / vault_base_rel / "nuwa-skill" / "SKILL.md"
            exists = nuwa_path.exists()
            out.append((f"asset:{nuwa_path}", exists,
                        "nuwa-skill present" if exists else "nuwa-skill missing"))

        # Runtime helper scripts check
        runtime_root = self._runtime_root_rel()
        scripts_dir = self.project_root / runtime_root / "scripts"
        for script_name in (
            "worktree.py", "plan_dispatch.py", "session_manager.py",
            "loop_memory_sync.py", "memory_audit.py", "ahd_session.py"
        ):
            script_path = scripts_dir / script_name
            exists = script_path.exists()
            out.append((f"runtime:{script_path}", exists,
                        "helper script present" if exists else "helper script missing"))

        # Session state directory check
        session_state_dir = self.project_root / runtime_root / "session_state"
        loop_state_dir = self.project_root / runtime_root / "loop_state"
        for label, d in (("session_state", session_state_dir), ("loop_state", loop_state_dir)):
            out.append((f"runtime:{d}", d.exists(), f"{label} dir present" if d.exists() else f"{label} dir missing"))

        # Runtime layer verification — hooks, settings, MCP
        # Uses _resolve_scoped_path with global_too=True so that global-scoped
        # paths (e.g. ~/.codeium/windsurf/mcp_config.json) are resolved to their
        # real location instead of a literal ${HOME} directory under project root.
        # Global-scoped files are only verified if they exist (they're optional —
        # only written with --global).
        rt = self.spec.get("runtime", {})
        if rt.get("enabled"):
            # Hook scripts
            hooks_dir_rel = rt.get("hooks_dir")
            if hooks_dir_rel:
                hooks_dir = self._resolve_scoped_path(hooks_dir_rel, global_too=True)
                if hooks_dir is not None:
                    for hook_name in ("pre_tool_use.py", "post_tool_use.py", "stop.py"):
                        hook_path = hooks_dir / hook_name
                        exists = hook_path.exists()
                        if not exists:
                            out.append((f"runtime:{hook_path}", False, "hook missing"))
                            continue
                        # Basic sanity check: post_tool_use must resolve session_id
                        if hook_name == "post_tool_use.py":
                            try:
                                content = hook_path.read_text(encoding="utf-8", errors="ignore")
                                ok = "get_session_id" in content or "session_id" in content
                                out.append((f"runtime:{hook_path}", ok,
                                            "hook present with session_id fallback" if ok else "hook missing session_id fallback"))
                            except Exception as e:
                                out.append((f"runtime:{hook_path}", False, str(e)))
                        else:
                            out.append((f"runtime:{hook_path}", True, "hook present"))

            # Settings file
            settings_file_rel = rt.get("settings_file")
            if settings_file_rel:
                settings_path = self._resolve_scoped_path(settings_file_rel, global_too=True)
                if settings_path is not None:
                    exists = settings_path.exists()
                    if exists:
                        try:
                            content = settings_path.read_text(encoding="utf-8")
                            # Check for Agent Harness Deploy marker or hook references
                            ok = "agent harness deploy" in content.lower() or "pre_tool_use" in content
                            out.append((f"runtime:{settings_path}", ok,
                                        "settings has agent harness deploy hooks" if ok else "settings missing agent harness deploy hooks"))
                        except Exception as e:
                            out.append((f"runtime:{settings_path}", False, str(e)))
                    else:
                        out.append((f"runtime:{settings_path}", False, "settings file missing"))

            # MCP config
            mcp_file_rel = rt.get("mcp_file")
            if mcp_file_rel:
                mcp_path = self._resolve_scoped_path(mcp_file_rel, global_too=True)
                if mcp_path is not None:
                    exists = mcp_path.exists()
                    if exists:
                        try:
                            content = mcp_path.read_text(encoding="utf-8")
                            ok = "mcpServers" in content or "mcp_servers" in content
                            out.append((f"runtime:{mcp_path}", ok,
                                        "mcp config present" if ok else "mcp config malformed"))
                        except Exception as e:
                            out.append((f"runtime:{mcp_path}", False, str(e)))
                    else:
                        # Global-scoped MCP files are optional (only written with --global).
                        # Don't fail verification for missing global MCP — just skip.
                        expanded = expand(mcp_file_rel)
                        if os.path.isabs(expanded):
                            out.append((f"runtime:{mcp_path}", True, "global MCP not written (use --global to deploy)"))
                        else:
                            out.append((f"runtime:{mcp_path}", False, "mcp file missing"))

        return out
