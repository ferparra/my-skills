---
name: obsidian-cv-entry-manager
version: 1.0.0
description: >
  Validate, migrate, extract, and export structured CV entry notes in this
  personal Obsidian vault. Use when requests involve cv_entry_kind enforcement,
  career entry schema, CV Entries.base, extracting cv-master.md into typed
  role/education/credential notes, pillar-filtered CV export, quantification
  gap tracking, or career timeline queries. cv_entry_kind is the supertag:
  it selects the schema contract applied to each career entry note.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian CV Entry Manager

Run this skill for career-entry lifecycle work: kind classification,
frontmatter normalisation, cv-master.md extraction, Base rendering,
and pillar-filtered CV export.

`cv_entry_kind` is the supertag. It selects each career note's schema
contract, enforced by Pydantic v2 behind the kind. The five kinds are:
`role`, `education`, `certification`, `award`, `community`.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate career notes when
dependencies are unavailable.

### 2. Read the Career Surface

```bash
obsidian read path="20 Resources/Career/CV Entries.base"
qmd query "cv entry career role pillar achievement" -c resources -l 8
qmd query "cv master career pathway job search" -c projects -l 5
```

Default scope: `20 Resources/Career/**/*.md`.

### 3. Validate in Check Mode

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/validate_cv.py \
  --glob "20 Resources/Career/**/*.md" --mode check
```

Review per-note: `cv_entry_kind`, `status`, `errors`, `warnings`. No files
are written. Notes with errors must be resolved before or after migration.

### 4. Extract from CV Master (One-Time)

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/extract_cv_master.py \
  --vault-root . --mode check
```

Inspect the output. When ready to create notes:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/extract_cv_master.py \
  --vault-root . --mode fix
```

Creates directories and individual typed notes under `20 Resources/Career/`.
Idempotent via `cv_entry_id`.

### 5. Migrate/Normalize

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/migrate_cv.py \
  --glob "20 Resources/Career/**/*.md" --mode check
```

Inspect `changed_fields` and `warnings`, then apply:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/migrate_cv.py \
  --glob "20 Resources/Career/**/*.md" --mode fix
```

### 6. Render Base

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/render_cv_base.py \
  --output "20 Resources/Career/CV Entries.base"
```

Generates views: Career Timeline, By Pillar (P1/P2/P3), Education &
Credentials, Community, Needs Quantification, All Entries.

### 7. Export Tailored CV

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/export_cv.py \
  --vault-root . --pillars P1,P2 --headline analytics-forward \
  --output cv-export.md
```

Available headlines: `analytics-forward`, `pm-forward`, `growth-forward`,
`player-coach`.

### 8. Re-Validate and Verify

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/validate_cv.py \
  --glob "20 Resources/Career/**/*.md" --mode check

obsidian search query="cv_entry_kind" limit=20 total
obsidian unresolved total
```

Confirm `"ok": true` overall before closing.

### Single-Note Workflow

Target a specific note by `--path` instead of `--glob`:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/validate_cv.py \
  --path "20 Resources/Career/Roles/2024-03 AutoGrab Senior Analytics Engineer.md"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-cv-entry-manager/scripts/migrate_cv.py \
  --path "20 Resources/Career/Roles/2024-03 AutoGrab Senior Analytics Engineer.md" --mode fix
```

## What This Skill Owns

- Canonical career-entry frontmatter: `cv_entry_id`, `cv_entry_kind`,
  `status`, `pillars`, `recency_weight`, `bullets`, and kind-specific fields.
- `cv_entry_kind` classification, migration, and Pydantic v2 schema enforcement.
- Career notes under `20 Resources/Career/**/*.md`.
- `CV Entries.base` rendering.
- Pillar-filtered CV export.
- Managed tag prefixes: `type/cv-entry`, `cv-entry-kind/*`, `status/*`.

## Guardrails

- **Never rewrite body content.** Body link enrichment belongs to
  `obsidian-interweave-engine`.
- **Preserve existing metadata.** Only inject missing canonical fields.
- **`bullets` are preserved exactly as authored** — never reorder or deduplicate.
- **FIXME placeholders** are safe to search: `grep -r "FIXME" "20 Resources/Career/"`.
- **Keep YAML valid** — validate output before writing.
- **`extract_cv_master.py` is idempotent** via `cv_entry_id` — re-extraction
  updates existing notes, not duplicates.

## QMD Collection Routing

| Query intent | Collection |
|---|---|
| Career entry notes | `-c resources` |
| CV master and job search context | `-c projects` |

```bash
qmd query "cv entry career role pillar achievement" -c resources -l 8
qmd query "cv master career pathway job search" -c projects -l 5
```

## References

- `references/cv-entry-schema.md` — canonical field contract and kind-specific requirements
- `references/cv-entry-kind-taxonomy.md` — kind values, pillar definitions, recency weights
- `scripts/cv_models.py` — shared Pydantic v2 models and utilities (source of truth)
- Cross-skill: run `obsidian-interweave-engine` after extraction if body link density is low
