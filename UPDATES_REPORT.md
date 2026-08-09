# Upstream Update Report

**Generated:** 2026-08-09T11:19:18.501680+00:00
**Schema version:** 1.0

| ID | Type | Status | Current | Upstream | Strategy | Notes |
|----|------|--------|---------|----------|----------|-------|
| ahd-main-engine | repo | behind | `c327869` | `7045406` | surgical-cherry-pick | Local deploy commit c327869 not in upstream; AHD update must be surgical only. |
| nuwa-skill | vendored-skill | up-to-date | `27642f5` | `27642f5` | direct-copy-vendored | Updated to 27642f5 on 2026-08-09. Core files only, 3 examples kept. |
| caveman | canon-source | behind | `unknown` | `11ddc0c` | manual-canon-update | Concepts distilled into CAVEMAN_PROTOCOL.md; update only if new concepts. |
| agency-agents | canon-source | behind | `unknown` | `ebe9c99` | manual-canon-update | Concepts distilled into COMMANDER.md / PERSONA_TEMPLATE.md. |
| superpowers | canon-source | behind | `unknown` | `44c9b2d` | manual-canon-update | Concepts distilled into COMMANDER.md / systematic_debugging.md / tdd.md. |
| loop-engineering | canon-source | behind | `unknown` | `75dba7a` | manual-canon-update | Concepts distilled into LOOP_PROTOCOL.md. |
| fable-method | canon-source | behind | `unknown` | `88b5cf3` | manual-canon-update | Concepts distilled into fable-judge.md. |

## Recommendations

- **ahd-main-engine** is behind upstream. Use `surgical-cherry-pick`.
- **caveman** is behind upstream. Use `manual-canon-update`.
- **agency-agents** is behind upstream. Use `manual-canon-update`.
- **superpowers** is behind upstream. Use `manual-canon-update`.
- **loop-engineering** is behind upstream. Use `manual-canon-update`.
- **fable-method** is behind upstream. Use `manual-canon-update`.
