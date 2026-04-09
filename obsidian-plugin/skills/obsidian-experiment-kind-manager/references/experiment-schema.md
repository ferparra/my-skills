# Experiment Schema — Field Contract

Source of truth: `scripts/experiment_models.py` (`ExperimentFrontmatter`).

## Identity Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `experiment_kind` | `ExperimentKind` | Yes | Supertag — selects schema contract and council routing |
| `experiment_id` | `str` | Yes | Pattern: `exp-YYYY-NNN`. Stable once set — never regenerate. |
| `created` | `str (ISO date)` | Yes | `YYYY-MM-DD` |
| `modified` | `str (ISO datetime)` | Yes | Updated on every write |
| `status` | `ExperimentStatus` | Yes | Lifecycle stage |
| `council_owner` | `str` | Yes | Derived from `experiment_kind` — see routing table |
| `domain_tag` | `str` | Yes | Derived from `experiment_kind` — see routing table |

## Question Frame Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | `str` | Yes | "What is the effect of X on Y?" |
| `hypothesis` | `str` | Yes | "I believe X will cause Y because Z" |

## Design Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `method` | `str` | Yes | Protocol description |
| `metrics` | `list[str]` | Required if `status` ∈ {`design`, `running`} | What will be measured |
| `duration_days` | `int \| None` | No | Planned duration in days |
| `start_date` | `str \| None` | No | `YYYY-MM-DD` |
| `end_date` | `str \| None` | No | `YYYY-MM-DD`. Must be ≥ `start_date`. |

## Execution Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `interventions` | `list[str]` | No | What is being changed or introduced |
| `controls` | `list[str]` | No | What stays constant to isolate the variable |
| `confounders` | `list[str]` | No | Known external factors that could contaminate results |

## Outcome Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `outcome` | `ExperimentOutcome` | No | Defaults to `ongoing` |
| `findings` | `str \| None` | Required if `status == concluded` | Summary of what was learned |
| `confidence` | `ConfidenceLevel \| None` | No | `low`, `medium`, `high` |
| `next_experiments` | `list[str]` | No | Wikilinks to follow-on experiments |

## Vault Graph Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `aliases` | `list[str]` | No | Alternative names for the experiment |
| `connection_strength` | `float [0.0–1.0]` | No | Defaults to `0.5` |
| `related` | `list[str]` | No | Wikilinks to related notes |
| `potential_links` | `list[str]` | No | Suggested future links |
| `tags` | `list[str]` | Yes | Must include managed prefixes |

## Managed Tag Prefixes

The migrator owns these prefixes — never set them manually:
- `type/experiment`
- `experiment-kind/{kind}`
- `status/{status}`

User-defined tags are preserved alongside managed tags.

## connection_strength Scoring (future)

```
outlink_score  = min(body_outlinks / 6, 1.0) × 0.30
pl_score       = min(potential_links / 5, 1.0) × 0.25
backlink_score = min(backlinks / 3, 1.0) × 0.25
maturity_score = recency of findings + confidence level × 0.20
```

## Validation Rules

1. `experiment_id` must match `exp-YYYY-NNN` pattern.
2. `council_owner` and `domain_tag` must match the `experiment_kind` routing table.
3. `metrics` must be non-empty when `status` ∈ {`design`, `running`}.
4. `findings` must be non-empty when `status == concluded`.
5. `outcome` cannot be `ongoing` when `status == concluded`.
6. `start_date` ≤ `end_date` when both are set.
7. `next_experiments`, `related`, `potential_links` must be wikilinks.
8. Tags must include `type/experiment`, `experiment-kind/{kind}`, `status/{status}`.
