# Domain Adapter Template

> Copy this file to `<domain>.md` and fill in domain-specific fraud patterns.

## Domain metadata

| Field | Value |
|-------|-------|
| **Domain** | `[FILL IN: e.g. data-ml, infrastructure, research, finance]` |
| **Typical artifacts** | `[FILL IN: notebooks, SQL queries, Terraform, reports, spreadsheets]` |
| **Common fraud vectors** | `[FILL IN: fabricated charts, stale datasets, silent data cleaning, optimistic benchmarks]` |

## Fraud table

| Fraud pattern | Evidence to hunt | Severity |
|---------------|------------------|----------|
| `[FILL IN]` | `[FILL IN]` | High/Med/Low |
| ... | ... | ... |

## Domain-specific verification commands

```bash
# Example: re-run a notebook from scratch
# jupyter nbconvert --execute analysis.ipynb
```

## Fallback

If no domain adapter matches, `fable-judge` loads `generic.md`.
