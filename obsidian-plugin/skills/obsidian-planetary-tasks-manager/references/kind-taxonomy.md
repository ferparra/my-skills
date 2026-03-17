# Planetary Kind Taxonomy

These kinds act like typed tags: they are lightweight metadata on the note surface, but each one corresponds to a stricter schema expectation enforced by Pydantic v2.

## `task_kind`

- `action`
  - A manually managed planetary maneuver or actionable task note.
- `external_ticket`
  - A task note synchronized from Jira or another external system of record.
- `closure_signal`
  - A maneuver-board or review-closing artifact such as completion count, blocker, or tomorrow's first maneuver.

## Adjacent `*_kind` Fields

Use these only on notes directly participating in the planetary task graph.

### `goal_kind`

- `health_goal`
- `career_goal`
- `relationship_goal`
- `capability_goal`

### `project_kind`

- `initiative`
- `reporting_stream`
- `platform_workstream`
- `delivery_system`

### `person_kind`

- `manager`
- `collaborator`
- `stakeholder`
- `customer_contact`

### `company_kind`

- `employer`
- `customer`
- `partner`
- `vendor`

## Selection Guidance

- Prefer the smallest stable enum that improves retrieval.
- Reuse note `type` and `para_type`; `_kind` should refine, not replace, those fields.
- Do not introduce `objective_kind`; `planning_horizon` already carries that planning-layer role.
