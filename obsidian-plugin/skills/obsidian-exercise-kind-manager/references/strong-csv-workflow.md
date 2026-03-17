# Strong CSV Workflow

## Scope

Use this workflow when `strong_workouts.csv` from the Strong iOS app needs to be
merged into `20 Resources/Exercises/*.md` without duplicating entries.

## Source Model

Strong exports one row per set with these required columns:

- `Date`
- `Workout Name`
- `Duration`
- `Exercise Name`
- `Set Order`
- `Weight`
- `Reps`
- `Distance`
- `Seconds`
- `Notes`
- `Workout Notes`
- `RPE`

`Set Order: W` means warm-up and is excluded from work-set volume metrics.

## Matching Rules

The importer is intentionally conservative. A row maps to an exercise note only
when the normalized Strong exercise name matches one of:

- `strong_exercise_names`
- `strong_name`
- `aliases`
- the note title

If multiple notes claim the same normalized Strong name, treat that as a
collision and fix the frontmatter before applying a write pass.

If a Strong exercise name does not map cleanly, report it. Do not fuzzy-merge
or auto-create notes unless the user explicitly requests note creation.

## Managed Fields

Strong sync owns these fields when present:

- `training_log_source`
- `strong_exercise_names`
- `strong_last_synced_at`
- `strong_session_count`
- `strong_work_set_count`
- `logged_sessions`
- `last_performed`
- `avg_weekly_primary_sets_6w`
- `avg_weekly_secondary_sets_6w`
- `progression_trend`
- `progression_delta_pct`
- `recommendation_signal`
- `top_set_*`
- `working_avg_*`

## Managed Body Section

Strong sync owns only this section:

```markdown
## Training Log (Strong CSV)
```

Re-runs replace that section in place. Other body content, including older
manual notes and non-Strong training logs, should remain untouched.

## Derived Analysis

- Dedupe exact duplicate CSV rows before aggregation.
- Group sets into sessions by mapped note, workout timestamp, and workout name.
- Exclude warm-up rows from work-set counts and set-volume metrics.
- Compute 6-week average primary and secondary sets using note-level volume
  credits from `volume_tracking`.
- Use progression trend bands:
  - `improving` when the recent block is at least 5% above the earlier block
  - `regressing` when it is at least 5% below
  - `stable` otherwise
  - `insufficient_data` when fewer than 4 scored sessions exist

## Recommendation Rules

Apply recommendation signals only to `exercise_kind: hypertrophy` notes:

- `add_volume` when average weekly primary sets are below the 12-set floor from
  `00 Inbox/Training guiding principles.md`
- `review_exercise_choice` when progression is regressing on a moderate or
  high-fatigue lift
- `consider_better_variant` when progression is flat and selection score is low
- `maintain` otherwise

## Preferred Commands

```bash
uvx --from python --with polars --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/sync_strong_workouts.py \
  --csv "strong_workouts.csv" \
  --mode check

uvx --from python --with polars --with pydantic --with pyyaml python \
  .skills/obsidian-exercise-kind-manager/scripts/sync_strong_workouts.py \
  --csv "strong_workouts.csv" \
  --mode fix \
  --report-path "20 Resources/Exercises/Retrospectives/Strong Training Retrospective.md"
```
