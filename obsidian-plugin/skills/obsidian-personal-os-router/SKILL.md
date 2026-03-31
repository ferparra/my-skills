---
name: obsidian-personal-os-router
version: 1.0.0
dependencies:
  - obsidian-planetary-tasks-manager
  - obsidian-exercise-kind-manager
  - obsidian-portfolio-holdings-manager
  - obsidian-brokerage-activity-manager
  - obsidian-notebooklm-bases-manager
  - obsidian-key-dates-base-manager
  - obsidian-weekly-feedback-loop
  - obsidian-cv-entry-manager
  - obsidian-interweave-engine
  - obsidian-agent-memory-capture
  - obsidian-token-budget-guard
description: >
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Personal OS Router

Run this skill first for vault work that may touch multiple notes.

## Workflow

1. Classify intent from the request.
2. Run `uvx --from python --with pydantic --with pyyaml python scripts/route_task.py --intent "<request>" --mode plan`.
3. Enforce returned `read_budget` before reading notes.
4. Load only references relevant to the selected route.
5. Run the selected downstream skill in plan-first mode.

## Route Outputs

`uvx --from python --with pydantic --with pyyaml python scripts/route_task.py ...` returns typed JSON with:
- `selected_route`
- `selected_skill`
- `required_commands`
- `read_budget`
- `dependency_status`

Treat this JSON as a contract.

## Dependency Policy

Fail fast when `obsidian`, `qmd`, or `uvx` is missing.
Do not mutate notes when dependency checks fail.
Use the fallback checklist printed by the script.

## Strict Budget Policy

Default hard limits:
- Max files: `5`
- Max chars: `22000`
- Max snippets: `12`

## QMD Collection Routing

Each route targets specific collections to minimise token cost. Never use `-c obsidian` (removed).

| Route | Primary collection | Secondary collection |
|---|---|---|
| `planetary-tasks-manager` | `periodic` | `projects` |
| `exercise-kind-manager` | `resources` | `inbox` |
| `portfolio-holdings-manager` | `resources` | `inbox` |
| `brokerage-activity-manager` | `resources` | `inbox` |
| `notebooklm-bases-manager` | `inbox` | `notes` |
| `key-dates-base-manager` | `periodic` | `inbox` |
| `weekly-feedback-loop` | `periodic` | `inbox` |
| `cv-entry-manager` | `resources` | `projects` |
| `interweave-engine` | `notes` | `clippings` |
| `agent-memory-capture` | `notes` | `inbox` |
| `token-budget-guard` | `all` | — |
| fallback | `all` | — |

Default when collection is unknown: `-c all` (scoped to knowledge folders, excludes `.trash/`, `scripts/`, etc.).

## References

- Use `references/routing-map.md` for route definitions and full collection reference table.
- Use `references/task-intent-taxonomy.md` for intent classification keywords.
- Route `key_dates_base` work first — the broad `"review"` keyword in `weekly_feedback` would otherwise steal date-related intents such as "annual performance review" or "date link broken".
- Route planetary task work before weekly review work so `Periodic Planning and Tasks Hub` and `Planetary Tasks.base` requests do not get absorbed by the generic `periodic` route.
- Route exercise schema, Strong CSV sync, and `Exercise Library.base` work before generic resource/interweave handling so typed exercise-note requests (including natural-language workout logs) resolve to the exercise manager.
- Route portfolio holdings, holdings history, and actual-holdings/base requests before brokerage export or token-guard handling so derived holdings work lands on the holdings manager.
- Route brokerage export, transaction ledger, and `brokerage_activity_kind` requests before generic interweave or token-guard handling so investment-import work lands on the typed ledger workflow.
- Route zettel management before weekly feedback — "hub synthesis" and "fleeting capture" are zettel signals, not weekly-review signals.
- Route CV entry management before weekly feedback and interweave — "career", "resume", and "role" are CV signals, not generic periodic or linking signals.
