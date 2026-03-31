---
name: obsidian-planetary-tasks-manager
version: 1.0.0
description: Maintain planetary task notes, task schema, and task-related Bases in this personal Obsidian vault. Use when requests involve Planetary Tasks.base, Periodic Planning and Tasks Hub.base, task_kind enforcement, Jira-synced planetary tasks, maneuver-board closure signals, or planetary task schema migration and validation.
dependencies:
  - obsidian-cli
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Planetary Tasks Manager

Run this skill when the request is specifically about planetary task notes, `task_kind`, or task-facing Bases.

Treat `task_kind` and adjacent `*_kind` fields as a lightweight supertag layer: the kind selects the note's type contract, and Pydantic v2 enforces the schema behind that type.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate task notes when dependencies are unavailable.

### 2. Validate Task Notes (Check Mode)

Before mutating any note, run validation to audit current compliance:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py \
  --glob "Periodic/*/Planetary Tasks/*.md" --mode check
```

Review the JSON output per note: `task_kind`, `ok`, `errors`, `warnings`, `concept_links`, `context_links`. No files are written. Notes with errors must be resolved before migration.

### 3. Dry-Run Migration

Inspect what the migrator would change without applying it:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/migrate_tasks.py \
  --glob "Periodic/*/Planetary Tasks/*.md" --mode check
```

Review `changed`, `warnings`, and `errors` per note. The migrator only changes frontmatter and may append a `## Planning Context` section — it never rewrites existing body content.

### 4. Apply Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/migrate_tasks.py \
  --glob "Periodic/*/Planetary Tasks/*.md" --mode fix
```

The migrator fills stable defaults, normalizes list fields, infers `thread`/`project` from related task links, derives temporal fields from anchor dates, and appends planning context when missing.

### 5. Re-Validate After Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py \
  --glob "Periodic/*/Planetary Tasks/*.md" --mode check

obsidian search query="task_kind" limit=20 total
obsidian unresolved total
```

Confirm `"ok": true` overall before closing.

### Single-Note Workflow

Target a specific note by `--path` instead of `--glob`:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py \
  --path "Periodic/2026/2026-W10/AG-7218 - Example task.md"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/migrate_tasks.py \
  --path "Periodic/2026/2026-W10/AG-7218 - Example task.md" --mode fix
```

## What This Skill Owns

- Canonical planetary task frontmatter: `task_id`, `task_kind`, `task_status`, `done`, `planning_system`, `planning_horizon`, `timeframe`, `domain`, `thread`, and adjacent `*_kind` fields.
- `task_kind` classification, migration, and Pydantic v2 schema enforcement.
- Task notes under `Periodic/*/Planetary Tasks/`.
- `10 Notes/Planetary Tasks.base`
- `Periodic/Periodic Planning and Tasks Hub.base`
- Managed tag prefixes: `type/task`, `planning/planetary`, `task-kind/*`, `domain/*`, `timeframe/*`, `status/*`.

## task_kind Taxonomy

`task_kind` is the primary supertag for planetary task notes. It selects the Pydantic v2 schema contract applied to each note:

| Kind | When to Use | Canonical Horizon |
|------|-------------|-------------------|
| `action` | Manually managed planetary maneuvers, actionable task notes | `day`, `maneuver` |
| `external_ticket` | Jira-synced or externally sourced task notes (`jira_sync: true` or `jira_key` present) | `maneuver` |
| `closure_signal` | Maneuver-board or review-closing artifacts: completion count, blocker, tomorrow's first maneuver | `maneuver_board` |

### Kind Inference Rules

The migrator auto-classifies `task_kind` using these heuristics:

1. If `jira_sync: true` or `jira_key` is present → `external_ticket`
2. If `planning_horizon: maneuver_board` → `closure_signal`
3. If title/body contains closure hints (`completion count`, `main blocker observed`, `first maneuver for tomorrow`) → `closure_signal`
4. Otherwise → `action`

### Adjacent `*_kind` Fields

These refine linked entity notes in the planetary task graph. They are optional on task notes but required when the linked entity participates in the task graph:

| Field | Kinds |
|-------|-------|
| `goal_kind` | `health_goal`, `career_goal`, `relationship_goal`, `capability_goal` |
| `project_kind` | `initiative`, `reporting_stream`, `platform_workstream`, `delivery_system` |
| `person_kind` | `manager`, `collaborator`, `stakeholder`, `customer_contact` |
| `company_kind` | `employer`, `customer`, `partner`, `vendor` |

## Frontmatter Schema

### Required Fields

Every planetary task note must have these fields:

```yaml
task_id: pt-xxxxxxxxxx | task-ag-xxxx
task_kind: action | external_ticket | closure_signal
task_status: next | in_progress | waiting | completed
done: false | true
planning_system: planetary
planning_horizon: day | maneuver | maneuver_board
timeframe: anytime | someday | dated
domain: work | personal
thread: T1 | T2 | T3 | T4 | unassigned
source_note: "[[00 Inbox/Tasks|Tasks]]"
horizon_note: "[[Periodic/2026/2026-W10|2026-W10]]"
context:
  - "[[00 Inbox/Tasks|Tasks]]"
  - "[[Periodic/2026/2026-W10|2026-W10]]"
  - "[[Periodic/Periodic Planning and Tasks Hub|Periodic Planning and Tasks Hub]]"
potential_links:
  - "[[10 Notes/Planetary Tasks.base|Planetary Tasks Base]]"
tags:
  - type/task
  - planning/planetary
  - task-kind/action
  - domain/work
  - timeframe/anytime
  - status/actionable | status/completed
```

### Optional Fields

```yaml
# Relation fields
project: "[[Projects/...]]"
goal: "[[Goal - ...]]"
people:
  - "[[People/...]]"
companies:
  - "[[Companies/...]]"

# Temporal fields (auto-derived from anchor date)
target_date: 2026-03-11
due_date: 2026-03-11
date: 2026-03-05
week: 10
month: 3
quarter: 1
cycle_12w: "2026-Q1-C1"
horizon_source_note: "[[Periodic/2026/2026-W10|2026-W10]]"

# Jira-specific (required for external_ticket)
jira_sync: true
jira_key: AG-7218
jira_url: https://autograb.atlassian.net/browse/AG-7218
last_synced: 2026-03-05T09:00:00+11:00

# Priority
priority: High | Medium | Low

# Source tracking
source_path: "00 Inbox/Tasks.md"
source_line: 42
```

### Pydantic Validation Rules

The `PlanetaryTaskFrontmatter` model enforces these consistency rules:

- `task_status: completed` requires `done: true`
- `done: true` requires `task_status: completed`
- `external_ticket` requires `jira_sync: true`, `jira_key`, and `jira_url`
- `tags` must include `type/task`, `planning/planetary`, and `task-kind/<kind>`
- `context` must be a non-empty list
- `potential_links` must be a non-empty list

## Scripts Reference

### `scripts/task_models.py` — Source of Truth

Shared Pydantic v2 models and utilities. Contains:

- `PlanetaryTaskFrontmatter` — canonical frontmatter model with validation
- `TaskKind`, `GoalKind`, `ProjectKind`, `PersonKind`, `CompanyKind`, `Timeframe` — enum definitions
- `load_markdown_note()`, `split_frontmatter()`, `dump_frontmatter()` — note I/O
- `classify_task_kind()` — kind inference logic
- `validate_frontmatter()` — returns `(ok: bool, errors: list[str])`
- `parse_frontmatter()` — returns `PlanetaryTaskFrontmatter`
- `render_markdown()`, `render_document()` — note rendering
- `classify_body_links()` — concept/context link extraction
- `temporal_fields_for_date()` — week/month/quarter/cycle derivation

### `scripts/validate_tasks.py` — Schema Auditor

Validates task notes against the canonical schema without mutating files.

**Usage:**
```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py \
  --glob "Periodic/*/Planetary Tasks/*.md" --mode check
```

**Output contract:**
```json
{
  "ok": true,
  "count": 42,
  "results": [
    {
      "path": "Periodic/2026/2026-W10/AG-7218 - Example task.md",
      "ok": true,
      "task_kind": "external_ticket",
      "errors": [],
      "warnings": [],
      "concept_links": ["[[Companies/Autograb]]"],
      "context_links": ["[[Periodic/2026/2026-W10|2026-W10]]"],
      "frontmatter_keys": ["task_id", "task_kind", ...]
    }
  ]
}
```

**Validation checks:**
- Pydantic frontmatter validation (required fields, type consistency, enum values)
- Body must contain at least one concept link (`[[Project/...]]`, `[[Companies/...]]`, `[[People/...]]`, `[[Goal - ...]]`)
- Body must contain at least one context link (`[[Periodic/...]]`, `[[00 Inbox/...]]`)
- Body must contain a `## Planning Context` section
- `closure_signal` tasks normally use `planning_horizon: maneuver_board` (warning only)

### `scripts/migrate_tasks.py` — Schema Normalizer

Normalizes task notes to the canonical schema. Only changes frontmatter and may append `## Planning Context` — never rewrites existing body content.

**Usage:**
```bash
# Dry-run
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/migrate_tasks.py \
  --glob "Periodic/*/Planetary Tasks/*.md" --mode check

# Apply
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/migrate_tasks.py \
  --glob "Periodic/*/Planetary Tasks/*.md" --mode fix
```

**Normalization steps:**
1. Classify `task_kind` using inference rules
2. Generate `task_id` (preserve existing, or derive from `jira_key`, or generate `pt-<sha1-prefix>`)
3. Set `planning_system: planetary`
4. Set `planning_horizon` defaults (`maneuver_board` for closure_signal, `maneuver` for external_ticket, `day` otherwise)
5. Normalize `domain` and `timeframe` to known values
6. Set `done` from `task_status`
7. For `external_ticket`: derive `thread` from related task links or periodic note threads, derive `project` from related tasks, set `companies: [Autograb]`, fill temporal fields
8. Infer `people`, `companies`, `goal` from body wikilinks
9. Build `context` list (source_note + horizon_note + hub + existing context)
10. Build `potential_links` list (project + goal + people + companies + default bases)
11. Normalize managed tags
12. Ensure `context` and `potential_links` are non-empty lists
13. Append `## Planning Context` section if missing

## Validate → Migrate → Render Pipeline

The canonical workflow for any task note mutation:

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. VALIDATE (check mode)                                           │
│     validate_tasks.py --glob "..." --mode check                     │
│     ↓                                                               │
│     Review errors, warnings, concept/context links                  │
│     ↓ (only if validation passes)                                   │
│  2. MIGRATE (check mode first)                                      │
│     migrate_tasks.py --glob "..." --mode check                      │
│     ↓                                                               │
│     Review changed_fields, warnings, errors                         │
│     ↓ (only if migration is safe)                                  │
│  3. MIGRATE (fix mode)                                              │
│     migrate_tasks.py --glob "..." --mode fix                        │
│     ↓                                                               │
│     Frontmatter normalized, planning context appended                │
│     ↓                                                               │
│  4. RE-VALIDATE (confirm compliance)                               │
│     validate_tasks.py --glob "..." --mode check                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Rendering** happens implicitly in `migrate_tasks.py` via `render_markdown(frontmatter, body)`. For explicit Base rendering, see `obsidian-portfolio-holdings-manager` or `obsidian-brokerage-activity-manager` which derive their Bases from brokerage activity notes that use this skill's schema.

## How Other Skills Depend on This

### `jira-sprint-sync`

The Jira sprint sync skill imports shared Pydantic v2 task models from `obsidian-planetary-tasks-manager/scripts/task_models.py` and uses `validate_tasks.py` as a schema guard after writing each synced note.

**Dependency chain:**
```
jira-sprint-sync → obsidian-planetary-tasks-manager (task_models.py, validate_tasks.py)
```

**Key integration point:**
```bash
# After writing each Jira-synced note, validate:
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py \
  --mode check --path "Periodic/<YEAR>/Planetary Tasks/<KEY> - <SUMMARY>.md"
```

### `obsidian-weekly-feedback-loop`

The weekly feedback loop skill validates closure-signal task notes as schema-backed artifacts using `validate_tasks.py`.

**Dependency chain:**
```
obsidian-weekly-feedback-loop → obsidian-planetary-tasks-manager (validate_tasks.py)
```

**Key integration point:**
```bash
# Validate closure-signal tasks when the week references Planetary Tasks.base:
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py \
  --mode check --path "Periodic/<YEAR>/Planetary Tasks/<task>.md"
```

### `obsidian-personal-os-router`

The personal OS router routes `planetary-tasks-manager` requests to this skill. It does not directly import from this skill's scripts but routes user requests to this skill's workflow.

**Dependency chain:**
```
obsidian-personal-os-router → obsidian-planetary-tasks-manager (routes to)
```

**Routing table entry:**
```python
RouteSpec(
    route_id="planetary-tasks-manager",
    keywords=["planetary task", "task_kind", "planetary tasks base", ...],
    selected_skill="obsidian-planetary-tasks-manager",
    required_commands=["obsidian", "qmd", "uvx"],
)
```

## Guardrails

- **Never rewrite body content.** The migrator may append `## Planning Context` but never modifies existing body text.
- **Preserve existing metadata.** Only inject missing canonical fields during migration.
- **Do not silently guess ambiguous kind.** If heuristics conflict, emit a warning and report — do not guess.
- **Validate before mutation.** Always run `validate_tasks.py --mode check` before `migrate_tasks.py --mode fix`.
- **Keep `planning_horizon` authoritative.** Do not add `objective_kind` — `planning_horizon` already carries that planning-layer role.
- **Keep YAML valid.** Validate output frontmatter before writing.
- **Preserve user-authored task bodies.** Only add minimal planning context when the schema requires missing concept/context links.

## QMD Collection Routing

| Query intent | Collection |
|---|---|
| Active planetary tasks | `periodic` |
| Task inbox captures | `inbox` |
| Project-linked tasks | `projects` |

```bash
qmd query "planetary task action closure_signal" -c periodic -l 8
qmd query "task_kind external_ticket Jira sync" -c inbox -l 5
```

## References

- `references/task-schema.md` — canonical field contract, required/optional fields, migration policy
- `references/kind-taxonomy.md` — `task_kind` and adjacent `*_kind` values and selection guidance
- `scripts/task_models.py` — shared Pydantic v2 models and utilities (source of truth)
- Cross-skill: `jira-sprint-sync` imports shared models and uses validate_tasks.py as post-write schema guard
- Cross-skill: `obsidian-weekly-feedback-loop` uses validate_tasks.py to validate closure-signal tasks
