# AGENTS.md — Command Code project memory (tier 2)

> File này load tự động mỗi turn bởi Command Code (memory tier 2: project).
> Tier 1 (user) ở `~/.commandcode/AGENTS.md` (nếu có).
> Tier 0 (root) ở `AGENTS.md` (đã có — AHD governance cho toàn workspace).
> Tier 2 này BỔ SUNG tier 0, không thay thế.

---

## Workspace overview

Workspace này = **Agent Harness Deploy (AHD)** + **OpenCode layer** +
**HLK security layer**, tất cả wrap thành Command Code (cmdc) interface.

3 layer:
- **`.devin/`** — AHD canonical: 15 canon + 17 SKILL.md + 11 agents + 13 hooks + 22 scripts.
- **`.opencode/`** — OpenCode wrappers: 32 SKILL.md wrapper + 6 agents + 15 personas.
- **`HLK/`** — Security + knowledge protection: 5 bin + 9 wrappers + 8 git-tools + 6 prompts + 3 skills + loop.

## cmdc surface

cmdc tự động load:
- Skills: `.commandcode/skills/`, `.devin/skills/`, `.opencode/skills/` (qua `settings.json.skills`).
- MCP: `.mcp.json` (aide-memory + ruflo-hlk-mcp).
- Hooks: `.commandcode/hooks/*.sh` + `HLK/wrappers/hlk-hook-launcher.mjs`.
- Custom agents: `.commandcode/agents/*.md` (11 files).
- Custom slash commands: `.commandcode/commands/*.md` (15 files).
- MODs: `.commandcode/mods/*.ts` (1 file: `hlk-guardian.ts`).
- Memory: this file.

## Quick commands (xem `docs/CMDC_QUICKREF.md` cho đầy đủ)

- `/full-power <task>` — MAX POWER 18 step.
- `/plan <task>` — Plan only.
- `/glm` / `/kimi` / `/lightning` — executors.
- `/hlk-status` / `/hlk-max-power` — HLK.
- `/harness-upgrade` — self-improve.

## Hard guards (BINDING)

1. `disableBypass: "disable"` active → không `--yolo` / `--dangerously-skip-permissions`.
2. `disableSkillShellExecution: true` → chặn `!cmd` inline trong skill.
3. Không sửa `HLK/`, `.env`, `.git/**`, `.commandcode/settings.json` trừ khi user nói rõ.
4. Trước commit/push: `/hlk-git-doctor` bắt buộc.
5. Mọi "done" claim: `python tools/check_governance.py` + `node HLK/wrappers/hlk-verify-integrity.js` + `pytest -q`.

## Tier classification

- **S** (<5 dòng, 1 file, no destructive) → sửa trực tiếp.
- **M** (1-3 file, simple, 30min-2h) → 3-Phase qua `/full-power`.
- **L** (multi-file, 2h+) → 3-Phase + deep research.
- **XL** (architecture, security) → 3-Phase + Nuwa cognitive + 37 agent dispatch.

## Memory import

@../AGENTS.md — root memory (AHD governance, language policy, denylist).
@../.devin/canon/CORE_CANON.md — canon cốt lõi.
@./CMDC_QUICKREF.md — quick reference.
@./reports/CMDC_FULL_GUIDE.md — full guide 13 phần.
@./reports/CMDC_SECURITY_AUDIT.md — báo cáo bảo mật 35 gap.
