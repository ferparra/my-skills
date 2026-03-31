---
name: obsidian-exercise-kind-manager
version: 1.0.0
dependencies: []
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
description: Validate, migrate, sync, and maintain typed exercise notes in this personal Obsidian vault. Use when requests involve `exercise_kind` enforcement, Strong CSV workout imports, gym exercise schemas, `20 Resources/Exercises/*.md`, `Exercise Library.base`, exercise selection heuristics, top-set progression metrics, or primary-muscle volume accounting for progressive overload review.
---

# Obsidian Exercise Kind Manager

## Overview

Run this skill when exercise notes need a real typed contract instead of loose
frontmatter. `exercise_kind` is the supertag: it selects the Pydantic v2 schema
behind each note and keeps the exercise Base aligned with the same contract.
For workout history, the skill also owns an idempotent Strong CSV import path
backed by Polars, Pydantic v2, and `uvx`.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate exercise notes when the
tooling is unavailable.

### 2. Read Only the Required Surface

```bash
obsidian read path="20 Resources/Exercises/Exercise Library.base"
obsidian read path="00 Inbox/Training guiding principles.md"
qmd query "exercise selection hypertrophy volume progressive overload" -c resources -l 8
qmd query "training guiding principles hypertrophy volume" -c inbox -l 5
```

Default read scope stays inside:

- `20 Resources/Exercises/*.md`
- `20 Resources/Exercises/Exercise Library.base`
- `00 Inbox/Training guiding principles.md`
- `strong_workouts.csv` when a Strong import or retrospective request is in scope

### 3. Validate Before Editing

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/validate_exercises.py \
  --glob "20 Resources/Exercises/*.md" --mode check
```

Review `exercise_kind`, inferred kind, and validation errors before fixing.

### 4. Dry-Run Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/migrate_exercises.py \
  --glob "20 Resources/Exercises/*.md" --mode check
```

The migrator only changes frontmatter. It preserves note bodies, images, and
training-log tables.

### 5. Apply Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/migrate_exercises.py \
  --glob "20 Resources/Exercises/*.md" --mode fix
```

The script fills stable defaults:

- `exercise_kind`
- `secondary_muscles`
- `stability_profile`
- `fatigue_cost`
- `progression_mode`
- `volume_tracking`
- `volume_primary_credit`
- `volume_secondary_credit`
- parsed top-set metrics from body logs when present

### 6. Dry-Run Strong CSV Sync

Use this when the request mentions the iOS Strong app, `strong_workouts.csv`,
exercise log import, deduped workout history, or retrospective analysis.

```bash
uvx --from python --with polars --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/sync_strong_workouts.py \
  --csv "strong_workouts.csv" \
  --mode check
```

The sync script:

- validates the Strong CSV schema with Pydantic v2
- uses Polars for dedupe, grouping, and weekly-set rollups
- matches rows only through explicit note names (`strong_exercise_names`,
  `strong_name`, aliases, or note title)
- reports unresolved Strong exercise names instead of fuzzy-merging them
- keeps Strong-owned content inside `## Training Log (Strong CSV)` so re-syncs
  stay idempotent and manual logs are not overwritten

### 7. Apply Strong CSV Sync

```bash
uvx --from python --with polars --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/sync_strong_workouts.py \
  --csv "strong_workouts.csv" \
  --mode fix \
  --report-path "20 Resources/Exercises/Retrospectives/Strong Training Retrospective.md"
```

The fix pass updates Strong-managed frontmatter fields such as:

- `training_log_source`
- `strong_last_synced_at`
- `strong_session_count`
- `strong_work_set_count`
- `avg_weekly_primary_sets_6w`
- `avg_weekly_secondary_sets_6w`
- `progression_trend`
- `progression_delta_pct`
- `recommendation_signal`

### 8. Render the Exercise Base

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/render_exercise_base.py \
  --output "20 Resources/Exercises/Exercise Library.base"
```

The rendered Base exposes:

- selection score from `force_profile`, `stability_profile`, `fatigue_cost`,
  and `volume_tracking`
- primary versus secondary volume credit
- Strong sync coverage and source fields
- top-set progression summaries plus 6-week volume and recommendation signals

### 9. Re-Validate and Verify

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/validate_exercises.py \
  --glob "20 Resources/Exercises/*.md" --mode check

obsidian read path="20 Resources/Exercises/Exercise Library.base"
obsidian search query="exercise_kind" limit=20 total
obsidian search query="training_log_source: strong_csv" limit=20 total
obsidian unresolved total
```

## Kind Rules

Use `references/exercise-kind-taxonomy.md` for the canonical taxonomy.

- `hypertrophy`
  - Count toward primary-muscle volume.
  - Prefer `volume_tracking: primary_only` unless the user explicitly wants
    `secondary_half`.

- `mobility_drill`
  - Track selection and execution context, not hypertrophy set volume.

- `warmup_flow`
  - Represent a sequence note with `duration` plus `component_exercises`.

- `exercise_brief`
  - Reserve for rare meta-notes that describe drill constraints rather than a
    single exercise.

## Guardrails

- Never rewrite note bodies during schema migration.
- Preserve existing metadata unless the skill owns the field.
- Prefer filling missing heuristics over overwriting explicit user values.
- Treat parsed top-set metrics as derived fields from the note body.
- Treat `## Training Log (Strong CSV)` as the only Strong-managed body section.
- Do not auto-create missing exercise notes during Strong sync unless the user
  explicitly asks for note creation; unresolved names should be reported.
- Keep `volume_tracking: primary_only` as the default to match
  `00 Inbox/Training guiding principles.md`.

## References

- `references/exercise-kind-taxonomy.md` — canonical note kinds and migration rules
- `references/exercise-schema.md` — field contract and Base support surface
- `references/strong-csv-workflow.md` — Strong CSV mapping, dedupe, and retrospective rules
- `scripts/exercise_models.py` — source of truth for the Pydantic v2 schema
