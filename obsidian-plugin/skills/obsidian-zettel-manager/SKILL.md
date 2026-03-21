---
name: obsidian-zettel-manager
version: 1.0.0
description: >
  Validate, migrate, and score zettel notes in this personal Obsidian vault.
  Use when requests involve zettel_kind enforcement, zettel_id generation,
  connection_strength scoring, promoting fleeting captures, or normalising
  knowledge notes in 10 Notes/ and 00 Inbox/. Treats zettel_kind as the
  Tana-supertag equivalent: it selects the note's schema contract.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Zettel Manager

Run this skill for zettel lifecycle work: kind classification, frontmatter
normalisation, graph health scoring, and status promotion.

`zettel_kind` is the supertag. It selects the note's schema contract, and
Pydantic v2 enforces that contract behind the kind.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate notes when dependencies
are unavailable.

### 2. Validate Before Editing

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/validate_zettels.py \
  --glob "10 Notes/**/*.md"
```

For inbox sweeps, add `--glob "00 Inbox/**/*.md"` or pass both globs.

Review the JSON output: `ok`, `errors`, `warnings`, `zettel_kind` per note.

### 3. Check Migration Dry-Run

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/migrate_zettels.py \
  --glob "10 Notes/**/*.md" --mode check
```

Review `changed` notes and `warnings`. If any note shows `"Ambiguous"` in its
warnings, confirm `zettel_kind` manually before proceeding.

### 4. Apply Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/migrate_zettels.py \
  --glob "10 Notes/**/*.md" --mode fix
```

The script skips notes with ambiguous kind inference or validation errors
— it will not silently corrupt a note.

### 5. Score connection_strength

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/score_zettels.py \
  --glob "10 Notes/**/*.md" --mode fix
```

Only writes if the score changed by > 0.01. Falls back to 0 backlinks if
`obsidian` CLI is unavailable (scores outlinks and potential_links only).

### 6. Re-Validate

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/validate_zettels.py \
  --glob "10 Notes/**/*.md"
```

Confirm `"ok": true` overall before closing.

### 7. Verify with Obsidian CLI

```bash
obsidian read path="10 Notes/<note>.md"
obsidian links path="10 Notes/<note>.md" total
obsidian backlinks path="10 Notes/<note>.md" counts total
obsidian unresolved counts total
```

### Single-Note Workflow

Target a specific note by `--path` instead of `--glob`:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/validate_zettels.py \
  --path "10 Notes/Context Engineering.md"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/migrate_zettels.py \
  --path "10 Notes/Context Engineering.md" --mode fix
```

## What This Skill Owns

- Canonical zettel frontmatter: `zettel_id`, `zettel_kind`, `status`,
  `connection_strength`, `potential_links`, and kind-specific fields.
- `zettel_kind` classification, migration, and Pydantic v2 schema enforcement.
- Knowledge notes under `10 Notes/**/*.md`.
- Fleeting captures under `00 Inbox/**/*.md`.
- `connection_strength` scoring from outlinks, potential_links, and backlinks.

## Guardrails

- **Never rewrite body content.** Body link enrichment belongs to
  `obsidian-interweave-engine`.
- **Never silently guess ambiguous kind.** If heuristics conflict, emit warning,
  skip write, require human confirmation.
- **Preserve existing metadata.** Only inject missing canonical fields.
- **Preserve `pit_status` and period fields** on PIT notes — never overwrite
  historical snapshot values.
- **Keep YAML valid** — validate output before writing.
- **Do not edit `.obsidian/` configs.**

## QMD Collection Routing

| Query intent | Collection |
|---|---|
| Zettel discovery | `-c notes` |
| Fleeting capture candidates | `-c inbox` |

```bash
qmd query "zettel kind status connection_strength" -c notes -l 8
qmd query "fleeting capture friction insight" -c inbox -l 5
```

## References

- `references/zettel-schema.md` — canonical zettel contract and migration policy
- `references/zettel-kind-taxonomy.md` — kind values, title patterns, kind-specific rules
- `scripts/zettel_models.py` — shared Pydantic v2 models and utilities (source of truth)
- Cross-skill: run `obsidian-interweave-engine` after migration if body link density is below minimum
