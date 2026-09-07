# Upstream Update Report

**Generated:** 2026-09-07T14:06:58.472375+00:00
**Schema version:** 1.0

| ID | Type | Status | Current | Upstream | Strategy | Notes |
|----|------|--------|---------|----------|----------|-------|
| ahd-main-engine | repo | api-error | `7045406` | `7045406` | surgical-cherry-pick | Local deploy commit c327869 not in upstream; AHD update must be surgical only. |
| nuwa-skill | vendored-skill | api-error | `27642f5` | `27642f5` | direct-copy-vendored | Updated to 27642f5 on 2026-08-09. Core files only, 3 examples kept. |
| caveman | canon-source | api-error | `2f49f0e` | `2f49f0e` | manual-canon-update | Reviewed 2026-08-22: 3 commits (4a96dc6, 3c28a20, 2f49f0e) chỉ README/logo changes, không có concept mới. CAVEMAN_PROTOCOL.md không cần update. |
| agency-agents | canon-source | api-error | `unknown` | `ebe9c99` | manual-canon-update | Concepts distilled into COMMANDER.md / PERSONA_TEMPLATE.md. |
| superpowers | canon-source | api-error | `unknown` | `b36e082` | manual-canon-update | Concepts distilled into COMMANDER.md / systematic_debugging.md / tdd.md. |
| loop-engineering | canon-source | api-error | `804a4e9` | `804a4e9` | manual-canon-update | Reviewed 2026-08-22: 2 commits (890999e, 804a4e9) là automated chores (star-history SVG + daily triage STATE.md), không có concept mới. LOOP_PROTOCOL.md không cần update. |
| fable-method | canon-source | api-error | `unknown` | `88b5cf3` | manual-canon-update | Concepts distilled into fable-judge.md. |

## Recommendations

- All tracked sources are up-to-date.
