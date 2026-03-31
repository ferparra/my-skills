---
name: obsidian-vault-health-auditor
version: 1.0.0
dependencies:
  - obsidian-base-engine
pipeline: {}
description: >
  Systematically audit an Obsidian vault for health issues including broken
  wiki-links, orphaned notes, schema drift, misplaced files, duplicate zettel
  IDs, and stale notes. Supports auto-fix mode for correctable issues.
metadata:
  openclaw:
    os:
      - darwin
    requires:
      bins:
        - obsidian
        - qmd
        - uvx
---

# Obsidian Vault Health Auditor

Run this skill to perform a comprehensive health audit of an Obsidian vault.
It identifies structural and content issues, produces a structured JSON report,
and optionally auto-fixes correctable problems.

## What This Skill Checks

| Check | Description | Auto-fixable |
|---|---|---|
| Broken wiki-links | Links to non-existent files | No |
| Orphaned notes | No incoming or outgoing links | No |
| Low connection strength | Notes with connection_strength < 2 | No |
| Schema drift | `*_kind` value not in known taxonomy | Yes |
| Misplaced notes | Path doesn't match declared kind directory | Yes |
| Duplicate zettel IDs | Same zettel_id appears in multiple notes | Yes |
| Stale notes | No modification in >90 days | No |

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not audit when dependencies
are unavailable.

### 2. Run Full Audit (Read-Only Check Mode)

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-vault-health-auditor/scripts/audit_vault.py \
  --vault-root "." --output vault_health_report.json
```

This produces `vault_health_report.json` with the full breakdown:

```json
{
  "ok": false,
  "summary": {
    "total_notes": 847,
    "broken_links": 23,
    "orphaned_notes": 12,
    "low_connection_strength": 34,
    "schema_drift": 5,
    "misplaced_notes": 3,
    "duplicate_zettel_ids": 2,
    "stale_notes": 45
  },
  "broken_links": [...],
  "orphaned_notes": [...],
  "low_connection_strength": [...],
  "schema_drift": [...],
  "misplaced_notes": [...],
  "duplicate_zettel_ids": [...],
  "stale_notes": [...]
}
```

Exit code is non-zero if any issues are found.

### 3. Run Auto-Fix Mode

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-vault-health-auditor/scripts/fix_issues.py \
  --vault-root "." --report vault_health_report.json --mode fix
```

Auto-fix handles:
- Adding missing frontmatter (`person_kind`, `exercise_kind`, etc.)
- Moving misplaced notes to correct directories
- Removing duplicate zettel IDs (keeps oldest, regenerates others)
- Injecting FIXME placeholders for schema drift requiring manual review

### 4. Verify Fixes

```bash
# Re-run audit to confirm resolution
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-vault-health-auditor/scripts/audit_vault.py \
  --vault-root "." --output vault_health_report.json

# Show only remaining issues
obsidian search query="status: needs_review" limit=50
```

## Targeting Specific Checks

Run only specific checks with `--checks`:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-vault-health-auditor/scripts/audit_vault.py \
  --vault-root "." --checks broken_links,orphaned_notes,duplicate_zettel_ids
```

Available check names: `broken_links`, `orphaned_notes`, `low_connection_strength`,
`schema_drift`, `misplaced_notes`, `duplicate_zettel_ids`, `stale_notes`

## Output Contract

`audit_vault.py` returns JSON with:
- `ok`: true only when all checks pass
- `summary`: counts per issue type
- `broken_links`: list of `{file, link, target}` objects
- `orphaned_notes`: list of `{path, incoming, outgoing}` objects
- `low_connection_strength`: list of `{path, connection_strength}` objects
- `schema_drift`: list of `{path, kind_field, value, allowed_values}` objects
- `misplaced_notes`: list of `{path, expected_dir, actual_dir}` objects
- `duplicate_zettel_ids`: list of `{zettel_id, paths}` objects
- `stale_notes`: list of `{path, last_modified, days_since_modified}` objects

Exit code: 0 if `ok: true`, 1 otherwise.

## Kind Directory Mapping

The auditor uses this mapping to detect misplaced notes:

| Kind field | Expected directory |
|---|---|
| `person_kind` | `People/` |
| `exercise_kind` | `20 Resources/Exercises/` |
| `brokerage_activity_kind` | `20 Resources/Investments/Brokerage Activity/` |
| `portfolio_holding_kind` | `20 Resources/Investments/Portfolio Holdings/` |
| `cv_entry_kind` | `20 Resources/Career/` |
| `zettel_kind` | `30 Zettelkasten/` |
| `key_date_kind` | `20 Resources/Key Dates/` |

## Staleness Thresholds

| Category | Threshold |
|---|---|
| Default stale | >90 days without modification |
| Active notes | Modified within 90 days |
| Zombie notes | >180 days without any incoming links |

## Known Taxonomies

Schema drift is detected against these known kind values:

- `person_kind`: manager, collaborator, stakeholder, customer_contact, mentor, author, acquaintance
- `exercise_kind`: hypertrophy, strength, mobility_drill, warmup_flow, exercise_brief
- `brokerage_activity_kind`: trade_buy, trade_sell, distribution, distribution_reinvestment, cash_deposit, cash_withdrawal, fee, tax, fx, adjustment, cash_interest
- `cv_entry_kind`: role, education, certification, award, community
- `zettel_kind`: atomic, literature, project, archive

## Auto-Fix Safety

- **Never rewrites body content** — only frontmatter and file paths
- **Always creates backup** — `fix_issues.py --mode fix` writes `.bak` copies
- **Duplicate zettel IDs** — keeps the note with earliest `created` date, regenerates IDs for others
- **Misplaced notes** — moves the file, updates all incoming wiki-links in other notes
- **Schema drift** — injects `FIXME_review_required` tag; does not change `*_kind` value

## Dependencies

- `pydantic >= 2.0` for model validation
- `pyyaml` for frontmatter parsing
- `obsidian` CLI for vault operations
- `qmd` for search and embedding

## References

- `references/vault-health-checks.md` — detailed check logic and thresholds
- `references/kind-taxonomies.md` — all known kind values per schema
- `scripts/vault_health_models.py` — Pydantic models for all report structures
