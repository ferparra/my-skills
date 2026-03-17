# Exercise Kind Taxonomy

`exercise_kind` acts like a typed tag for notes in `20 Resources/Exercises/`.
It is the schema boundary: Pydantic v2 decides which frontmatter contract
applies from this field.

## `exercise_kind`

- `hypertrophy`
  - Progressive-overload lift counted toward primary-muscle weekly volume.
  - Requires primary driver metadata, selection heuristics, and progression
    metrics when a training log exists.

- `mobility_drill`
  - Single drill used to improve position, range, or stability.
  - Not counted toward hypertrophy set volume.

- `warmup_flow`
  - Multi-drill sequence or pre-lift flow that bundles several exercises into
    one warm-up note.
  - Requires `duration` and `component_exercises`.

- `exercise_brief`
  - Meta note describing drill constraints, principles, or selection rules for
    exercises rather than a single executable movement.
  - Use sparingly for outliers such as the current `Mobility drill.md` brief.

## Selection Heuristics

The skill materialises fields that map to `00 Inbox/Training guiding principles`:

- `stability_profile`
  - `high`, `medium`, `low`
  - Encodes the "Position" preference for stable setups and low unnecessary
    stabilisation demand.

- `fatigue_cost`
  - `low`, `moderate`, `high`
  - Encodes the "local stimulus > systemic fatigue" rule.

- `force_profile`
  - Reuses the existing exercise metadata.
  - `lengthened` is preferred for hypertrophy selection work.

## Volume Accounting

The canonical default is primary-driver counting:

- `volume_tracking: primary_only`
  - `volume_primary_credit: 1.0`
  - `volume_secondary_credit: 0.0`

- `volume_tracking: secondary_half`
  - Optional advanced mode.
  - `volume_primary_credit: 1.0`
  - `volume_secondary_credit: 0.5`

- `volume_tracking: not_counted`
  - For mobility drills, warm-up flows, and exercise briefs.
  - Both credits are `0.0`.

## Migration Rules

- Infer `hypertrophy` from `category: hypertrophy`.
- Infer `mobility_drill` from `category: mobility`.
- Infer `warmup_flow` from notes tagged `fitness/warmup` that define a timed
  flow with multiple component drill links.
- Infer `exercise_brief` for meta-notes without exercise-shape metadata but with
  warm-up or mobility briefing content.
- Never rewrite note bodies during migration.
