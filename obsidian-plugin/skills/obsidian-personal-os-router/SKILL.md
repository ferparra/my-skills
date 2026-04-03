---
name: obsidian-personal-os-router
version: 1.0.0
description: Route Obsidian vault tasks to the minimum-context workflow before reading or editing files. Use when a request targets this personal Obsidian vault and you need progressive disclosure, strict read budgets, and fail-fast dependency checks for obsidian CLI, qmd, and downstream manager skills such as portfolio holdings, brokerage activity, planetary tasks, and zettel maintenance.
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
| `hub-manager` | `notes` | — |
| `interweave-engine` | `notes` | `clippings` |
| `agent-memory-capture` | `notes` | `inbox` |
| `token-budget-guard` | `all` | — |
| fallback | `all` | — |

Default when collection is unknown: `-c all` (scoped to knowledge folders, excludes `.trash/`, `scripts/`, etc.).

## References

- Use `references/routing-map.md` for route definitions and full collection reference table.
- Use `references/task-intent-taxonomy.md` for intent classification keywords.
- Route planetary task work before weekly review work so `Periodic Planning and Tasks Hub` and `Planetary Tasks.base` requests do not get absorbed by the generic `periodic` route.
- Route exercise schema, Strong CSV sync, and `Exercise Library.base` work before generic resource/interweave handling so typed exercise-note requests resolve to the exercise manager.
- Route portfolio holdings, holdings history, and actual-holdings/base requests before brokerage export or token-guard handling so derived holdings work lands on the holdings manager.
- Route brokerage export, transaction ledger, and `brokerage_activity_kind` requests before generic interweave or token-guard handling so investment-import work lands on the typed ledger workflow.
