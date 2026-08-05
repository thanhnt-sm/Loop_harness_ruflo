---
name: slop-patterns-updates
description: "U30: Slop pattern versioning + update tracking"
version: "1.0.0"
created: "2026-07-07"
---

# Slop Pattern Updates

> U30: Track slop pattern changes + quarterly review process.

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-01-15 | Initial slop-detector.md with 10 patterns | Original |
| 1.1.0 | 2026-07-07 | Added Vietnamese slop patterns (U19), version tracking (U30) | GLM-5.2 High |

## Quarterly Review Process

### When to review
- **Q1**: January (start of year)
- **Q2**: April
- **Q3**: July
- **Q4**: October

### Review checklist
1. **Scan recent AI outputs** — check last quarter's commits, PRs, docs for new slop patterns
2. **Check community sources** — AI slop detection repos, blog posts, new patterns
3. **Evaluate false positives** — any patterns causing too many false alarms?
4. **Evaluate false negatives** — any slop slipping through?
5. **Update patterns** — add new, remove obsolete, refine existing
6. **Bump version** — increment version in slop-detector.md frontmatter
7. **Update this file** — add entry to version history table
8. **Test** — run slop-detector on sample outputs to verify

### Review criteria for new patterns
- **Observable** — pattern must be detectable via text matching
- **Actionable** — detecting it should lead to a concrete fix
- **Non-trivial** — pattern should catch real slop, not just common words
- **Low false positive** — pattern should not flag legitimate writing

### Removal criteria
- Pattern no longer relevant (AI models improved, pattern obsolete)
- Pattern causes too many false positives (>20% of detections)
- Pattern overlaps significantly with another pattern

## Pattern categories

| Category | Count | Examples |
|----------|-------|---------|
| Filler words | 5 | "leverage", "utilize", "facilitate" |
| Generic abstractions | 3 | "various", "multiple", "numerous" |
| Meaningless identifiers | 2 | "data", "info", "util" |
| Vietnamese filler (U19) | 7 | "Bước 1", "Tiếp theo", "Lưu ý" |
| Vietnamese restating (U19) | 5 | "gán x bằng", "tăng biến đếm" |

## Next review
- **Q3 2026**: July 2026 (current — done as part of U30)
- **Q4 2026**: October 2026
