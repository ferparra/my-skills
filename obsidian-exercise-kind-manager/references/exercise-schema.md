# Exercise Schema

## Scope

This contract applies to markdown notes under `20 Resources/Exercises/*.md`.

`exercise_kind` is the supertag-like selector. The note stays plain markdown,
but the selected kind determines which frontmatter fields are required.

## Common Managed Fields

```yaml
exercise_kind: hypertrophy | mobility_drill | warmup_flow | exercise_brief
tags:
  - type/exercise
  - exercise-kind/hypertrophy
programme: "[[...]]"            # optional on briefs
equipment:
  - "[[...]]"                   # optional on briefs and warm-up flows
progression_mode: load_reps | quality | duration
volume_tracking: primary_only | secondary_half | not_counted
volume_primary_credit: 1.0
volume_secondary_credit: 0.0
strong_exercise_names:
  - "Smith Machine Chest Press"
strong_weight_unit: kg | lbs | bodyweight
training_log_source: manual | strong_csv
strong_last_synced_at: 2026-03-14T02:30:00+00:00
strong_session_count: 18
strong_work_set_count: 54
logged_sessions: 11             # derived from body when present
avg_weekly_primary_sets_6w: 13.5
avg_weekly_secondary_sets_6w: 0.0
progression_trend: improving | stable | regressing | insufficient_data
progression_delta_pct: 6.4
recommendation_signal: maintain | add_volume | review_exercise_choice | consider_better_variant | insufficient_data
top_set_load: 140.0             # external load only
top_set_reps: 6.0
top_set_unit: kg | lbs | bodyweight
top_set_volume: 840.0
working_avg_load: 132.3
working_avg_reps: 5.5
working_avg_unit: kg
```

## `hypertrophy`

```yaml
exercise_kind: hypertrophy
category: hypertrophy
region: upper | lower | full-body | core
pattern: isolation | push | pull | squat | hinge | lunge | rotation
primary_muscle: "[[...]]"
muscle_group:
  - "[[...]]"
secondary_muscles:
  - "[[...]]"
force_profile: lengthened | mid-range | shortened
stability_profile: high | medium | low
fatigue_cost: low | moderate | high
progression_mode: load_reps
volume_tracking: primary_only | secondary_half
volume_primary_credit: 1.0
volume_secondary_credit: 0.0 | 0.5
```

## `mobility_drill`

```yaml
exercise_kind: mobility_drill
category: mobility
region: upper | lower | full-body | core
pattern: isolation | push | pull | squat | hinge | lunge | rotation
primary_muscle: "[[...]]"
muscle_group:
  - "[[...]]"
secondary_muscles:
  - "[[...]]"
force_profile: lengthened | mid-range | shortened
stability_profile: high | medium | low
fatigue_cost: low | moderate
progression_mode: quality | duration | load_reps
volume_tracking: not_counted
volume_primary_credit: 0.0
volume_secondary_credit: 0.0
```

## `warmup_flow`

```yaml
exercise_kind: warmup_flow
duration: "~7 min"
component_exercises:
  - "[[Tall-Kneeling Halo]]"
  - "[[Prying Goblet Squat]]"
progression_mode: quality | duration
volume_tracking: not_counted
volume_primary_credit: 0.0
volume_secondary_credit: 0.0
```

## `exercise_brief`

```yaml
exercise_kind: exercise_brief
progression_mode: quality
volume_tracking: not_counted
volume_primary_credit: 0.0
volume_secondary_credit: 0.0
```

## Derived Metrics Policy

- Parse `Sessions`, `Top set`, and `Working avg` from the body when the note has
  a hypertrophy-style training log.
- For Strong imports, prefer `training_log_source: strong_csv` plus the
  managed `## Training Log (Strong CSV)` section.
- Store external load only. If the log is bodyweight-based, keep
  `top_set_unit: bodyweight` and leave load fields empty when the load is not
  explicit.
- Preserve existing `last_performed`; infer it from the latest log row only when
  the note does not already provide it.

## Strong Sync Policy

- `strong_exercise_names` is the canonical mapping surface for Strong CSV names.
- Strong sync is idempotent: reruns replace the managed Strong section rather
  than appending duplicate history.
- The importer must report unresolved Strong exercise names and frontmatter name
  collisions instead of guessing.
- Weekly set averages and recommendation signals should follow
  `00 Inbox/Training guiding principles.md`, especially the default
  `12–16 sets` weekly target and the preference for low-fatigue, high-stability,
  lengthened-biased exercise selection.

## Base Support

`20 Resources/Exercises/Exercise Library.base` should expose:

- `exercise_kind`
- `primary_muscle` and `secondary_muscles`
- `stability_profile`, `fatigue_cost`, and `force_profile`
- `volume_tracking`, `volume_primary_credit`, `volume_secondary_credit`
- `training_log_source`, `strong_exercise_names`, and `strong_*`
- `avg_weekly_*`, `progression_*`, `recommendation_signal`
- `top_set_*`, `working_avg_*`, and `logged_sessions`

These fields support:

- exercise selection against the guiding principles
- primary-driver set accounting
- top-set volume and progression reviews
- Strong sync coverage audits and unresolved-mapping triage
