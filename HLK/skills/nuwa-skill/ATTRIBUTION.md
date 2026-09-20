# .devin/skills/nuwa-skill/ — Vendored Nuwa Skill

> **Anti-link-rot vendored copy.** This directory is a local mirror of the
> `alchaincyf/nuwa-skill` repository, fetched at deployer-build time and committed
> to this repo so that **users never need to download it separately**.
> The deployer deploys it from here; no runtime network fetch.

---

## Source

| Field | Value |
|-------|-------|
| Upstream repo | https://github.com/alchaincyf/nuwa-skill |
| Upstream license | MIT (see `LICENSE` in this directory) |
| Vendored from branch | `main` |
| Vendored on | 2026-08-09 |
| Upstream commit SHA | `27642f5bfed2dc1bbf8ee59a2c1ee602a626bbd7` |
| Author | alchaincyf |
| Purpose | Cognitive-diversity skill distillation factory for the Nuwa Team |

## Why vendored (not linked)

The Agent Harness Deploy follows an **anti-link-rot architecture**: every external
dependency is committed locally so the harness works even if the upstream repo disappears.
This is the same philosophy as `.devin/skills/assets/vault/` — no runtime fetch, no network dependency.

Users invoke the Nuwa skill through the Devin CLI skill system; the vendored copy lives
at `.devin/skills/nuwa-skill/` and is discovered automatically. **Users do not need
to clone or download `alchaincyf/nuwa-skill` themselves.**

## What is vendored

### Core (always deployed)
| Path | Purpose |
|------|---------|
| `SKILL.md` | The Nuwa skill definition — distillation factory for perspective skills |
| `LICENSE` | MIT license (preserved for attribution) |
| `README.md` / `README_EN.md` | Upstream documentation (zh / en) |
| `references/extraction-framework.md` | Research-to-skill extraction methodology |
| `references/fidelity-scorecard.md` | Fidelity scoring for distilled perspectives |
| `references/skill-template.md` | Template for new perspective skills |
| `scripts/download_subtitles.sh` | YouTube subtitle fetcher (research input) |
| `scripts/merge_research.py` | Merge multi-source research into one corpus |
| `scripts/quality_check.py` | Quality gate for distilled skills |
| `scripts/srt_to_transcript.py` | SRT → transcript converter |
| `COMMUNITY.md` / `CONTRIBUTING.md` | Community / contribution guidelines |

### Example perspectives (3 vendored, referenced by `.devin/skills/nuwa-skill/SKILL.md`)
| Perspective | Cognitive angle | Files |
|-------------|-----------------|-------|
| `munger-perspective` | Charlie Munger — inversion, mental models, 25 cognitive biases | SKILL.md + FIDELITY.md + 4 reference files |
| `feynman-perspective` | Richard Feynman — first-principles, simple explanation, analogies | SKILL.md + FIDELITY.md + 6 reference files |
| `taleb-perspective` | Nassim Taleb — antifragility, black swans, skin in the game | SKILL.md + FIDELITY.md + 5 reference files |

These 3 are the cognitive angles explicitly referenced in `.devin/skills/nuwa-skill/SKILL.md` as
the default Nuwa Team composition. The upstream repo contains 13 perspectives total;
the other 10 (karpathy, musk, naval, jobs, paul-graham, ilya, mrbeast, trump,
zhang-yiming, zhangxuefeng, x-mastery-mentor) can be added on demand by copying the
additional perspective directories from the upstream repo.

### Not vendored (intentionally skipped)
- `*.png`, `*.gif`, `*.mp4`, `*.pdf`, `*.jpg` — promotional images / videos (not functional)
- `README_ES.md`, `README_JA.md`, `README_KO.md` — non-EN/ZH translations (on-demand)
- `promo/` — promotional deck / cards / landing page assets
- `wechat-qrcode.jpg` — author contact QR code
- `x-thread-en.md` — promotional thread
- `.github/` — upstream CI workflows (not relevant to vendored deploy)

## Modification policy

- **This vendored copy is immutable during deploy.** The Devin CLI skill system uses it as-is.
- To update: fetch the latest from the upstream repo, then commit the updated files.
- To add more example perspectives: copy the additional perspective directories from
  the upstream repo, then commit.
- Upstream license (MIT) is preserved in `LICENSE`. Attribution to `alchaincyf` is
  required when redistributing.

## How the Devin CLI uses this

1. The Nuwa skill is vendored at `.devin/skills/nuwa-skill/`.
2. The Devin CLI skill system loads `SKILL.md` from that path when the user invokes
   `/nuwa-skill` or the skill is auto-triggered.
3. Users can then say "distill a Munger perspective" and the active model loads
   `SKILL.md` from the local path — no download needed.

## Upstream reference (preserved for attribution, not required at runtime)

- Repo: https://github.com/alchaincyf/nuwa-skill
- Author: alchaincyf
- License: MIT
