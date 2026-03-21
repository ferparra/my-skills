---
name: obsidian-people-kind-manager
version: 1.0.0
description: >
  Validate, migrate, score, and enrich person notes in the People/ directory
  of this personal Obsidian vault. Use when requests involve person_kind
  enforcement, People/ schema compliance, relationship graph enrichment,
  connection_strength scoring, interaction tracking, last_interaction_date
  updates, or CRM-style queries across people notes. person_kind is the
  supertag: it selects the schema contract applied to each person note.
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

# Obsidian People Kind Manager

Run this skill for People/ lifecycle work: kind classification, frontmatter
normalisation, relationship graph scoring, and interaction enrichment.

`person_kind` is the supertag. It selects each person note's schema contract,
enforced by Pydantic v2 behind the kind. The seven kinds are: `manager`,
`collaborator`, `stakeholder`, `customer_contact`, `mentor`, `author`,
`acquaintance`.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate person notes when
dependencies are unavailable.

### 2. Read the People Surface

```bash
obsidian read path="People.base"
qmd query "person relationship connection colleague stakeholder" -c notes -l 8
qmd query "person kind manager collaborator mentor" -c inbox -l 5
```

Default scope: `People/**/*.md`.

### 3. Validate in Check Mode

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/validate_people.py \
  --glob "People/**/*.md" --mode check
```

Review per-note: `person_kind`, `status`, `errors`, `warnings`. No files are
written. Notes with errors must be resolved before or after migration.

### 4. Dry-Run Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/migrate_people.py \
  --glob "People/**/*.md" --mode check
```

Inspect `changed_fields` and `warnings`. Notes flagged `"Ambiguous"` require
manual `person_kind` confirmation before applying — do not proceed on
ambiguous notes without user sign-off.

### 5. Apply Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/migrate_people.py \
  --glob "People/**/*.md" --mode fix
```

Injects `person_kind`, `status`, normalised tags, kind-specific FIXME
placeholders. Never rewrites note bodies. Skips ambiguous notes silently (they
appear in results with `skipped: true`).

### 6. Enrich Interaction Signals

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/enrich_people.py \
  --glob "People/**/*.md" --mode check
```

Review proposed `last_interaction_date` and `interaction_frequency` updates,
then apply:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/enrich_people.py \
  --glob "People/**/*.md" --mode fix
```

Scans body for `## YYYY-MM-DD` headings. Always `only_if_missing` — never
overwrites explicit user values.

### 7. Score and Re-Validate

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/score_people.py \
  --glob "People/**/*.md" --mode fix

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/validate_people.py \
  --glob "People/**/*.md" --mode check

obsidian search query="person_kind" limit=20 total
obsidian unresolved total
```

Confirm `"ok": true` overall before closing.

### Single-Note Workflow

Target a specific note by `--path` instead of `--glob`:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/validate_people.py \
  --path "People/Damien Ngo.md"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-people-kind-manager/scripts/migrate_people.py \
  --path "People/Damien Ngo.md" --mode fix
```

## What This Skill Owns

- Canonical person frontmatter: `person_kind`, `status`, `connection_strength`,
  `potential_links`, `last_interaction_date`, `interaction_frequency`, and
  kind-specific fields.
- `person_kind` classification, migration, and Pydantic v2 schema enforcement.
- Person notes under `People/**/*.md`.
- `connection_strength` scoring from outlinks, potential_links, backlinks, and recency.
- Managed tag prefixes: `type/person`, `person-kind/*`, `status/*`.

## Guardrails

- **Never rewrite body content.** Body link enrichment belongs to
  `obsidian-interweave-engine`.
- **Never silently guess ambiguous kind.** If heuristics conflict, emit warning,
  skip write, require human confirmation.
- **Preserve existing metadata.** Only inject missing canonical fields.
- **`last_interaction_date` and `interaction_frequency` are only_if_missing.**
  Never overwrite explicit user values.
- **`status: dormant` is manual only.** The migrator never downgrades an active
  status to dormant.
- **FIXME placeholders** are safe to search: `grep -r "FIXME" People/`.
- **Keep YAML valid** — validate output before writing.

## QMD Collection Routing

| Query intent | Collection |
|---|---|
| Active relationships | `-c notes` |
| Uncategorised person captures | `-c inbox` |

```bash
qmd query "person relationship connection colleague stakeholder" -c notes -l 8
qmd query "person kind manager collaborator mentor" -c inbox -l 5
```

## References

- `references/people-schema.md` — canonical field contract and scoring formula
- `references/people-kind-taxonomy.md` — kind values, inference rules, migration policy
- `scripts/people_models.py` — shared Pydantic v2 models and utilities (source of truth)
- Cross-skill: run `obsidian-interweave-engine` after migration if body link density is low
