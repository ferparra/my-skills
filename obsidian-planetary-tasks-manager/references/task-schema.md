# Planetary Task Schema

## Scope

This contract applies to notes under `Periodic/*/Planetary Tasks/`.

The schema follows a supertag-like model: `task_kind` turns a plain markdown note into a typed task object, and the Pydantic v2 models in `scripts/task_models.py` enforce that contract.

## Required Frontmatter

```yaml
task_id: pt-xxxxxxxxxx | task-ag-0000
task_kind: action | external_ticket | closure_signal
task_status: next | in_progress | waiting | completed
done: false
planning_system: planetary
planning_horizon: day | maneuver | maneuver_board
timeframe: anytime | someday | dated
domain: work | personal
thread: T1 | T2 | T3 | T4 | unassigned
source_note: "[[...]]"
horizon_note: "[[...]]"
context:
  - "[[...]]"
potential_links:
  - "[[...]]"
tags:
  - type/task
  - planning/planetary
  - task-kind/action
```

## Optional Frontmatter

```yaml
project: "[[...]]"
goal: "[[...]]"
people:
  - "[[People/...]]"
companies:
  - "[[Companies/...]]"
target_date: 2026-03-11
date: 2026-03-05
week: 10
month: 3
quarter: 1
cycle_12w: "2026-Q1-C1"
source_path: "00 Inbox/Tasks.md"
source_line: 42
horizon_source_note: "[[...]]"
jira_sync: true
jira_key: AG-7218
jira_url: https://...
priority: High
last_synced: 2026-03-05T00:00:00+11:00
due_date: 2026-03-11
```

## Task-Kind Rules

- `external_ticket`
  - Use when `jira_sync: true` or `jira_key` is present.
- `closure_signal`
  - Use when `planning_horizon: maneuver_board` or the task body/title is one of:
    - completion count
    - main blocker observed
    - main blocker noticed
    - first maneuver for tomorrow
- `action`
  - Default for all other planetary tasks.

## Typed-Tag Principle

- `task_kind` is the primary type selector for task notes.
- Adjacent `goal_kind`, `project_kind`, `person_kind`, and `company_kind` refine linked entity notes in the same graph.
- Tags remain useful for retrieval, but kinds are the authoritative schema boundary.

## Migration Policy

- PT notes keep their existing `task_id`.
- AG notes receive `task_id: task-<jira_key lowercased>`.
- Existing user content stays intact.
- Missing planning context may be appended when required to satisfy concept/context link checks.
- Ambiguous inferences are reported. They must not be accepted silently.

## Interweaving Minimum

Each task body must include:

- at least one concept link
- at least one context link

Typical concept links:

- `[[Project – ...]]`
- `[[Companies/...]]`
- `[[People/...]]`
- `[[Goal - ...]]`

Typical context links:

- `[[Periodic/...]]`
- `[[00 Inbox/...]]`
- `[[Periodic/Periodic Planning and Tasks Hub|Periodic Planning and Tasks Hub]]`
