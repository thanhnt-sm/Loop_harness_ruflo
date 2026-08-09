# Attribution — Agent Harness Deploy (AHD) Main Engine

## Source

| Field | Value |
|-------|-------|
| Upstream repo | https://github.com/masteryee-labs/Tool.Agent-Harness-Deploy |
| Upstream license | MIT (see `LICENSE` if present) |
| Vendored from branch | `main` |
| Vendored on | 2026-07-07 |
| Local deploy commit | `c3278694a7b73a4e92addfba18ceb1b2e1d98b1f` |
| Upstream commit checked | `704540651f31dadf5888728f33245dd30dc611b8` (2026-07-20) |
| Author | masteryee-labs |
| Purpose | Agent Harness Deploy — main engine for Devin CLI workspace |

## Modification Policy

- **Local commit is a deploy commit**, not an upstream commit. Upstream AHD is a source of
  reference; the local `.devin/` directory has been heavily modified with 70 upgrades (U01–U70).
- **Never bulk-merge upstream AHD** into this workspace without surgical cherry-pick.
- **Protected files** (hooks, config, core canon, HLK, `.gitignore`, `.gitattributes`) must not be
  overwritten by upstream.
- To incorporate upstream bug fixes or features:
  1. Clone upstream to a temporary directory.
  2. Review each commit with `git show --stat`.
  3. Cherry-pick only non-protected files.
  4. Run `tools/verify-workspace.ps1` and `HLK/wrappers/hlk-verify-integrity.js` after each patch.

## Why not a submodule

AHD is not used as a git submodule because this workspace is a **deployed instance** with local
modifications, U01–U70 upgrades, and the HLK security layer. A submodule would force either a
frozen upstream checkout (losing local changes) or constant merge conflicts. The surgical
cherry-pick workflow preserves both upstream improvements and local customizations.
