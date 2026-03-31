---
name: jira-sprint-sync
version: 1.0.0
dependencies:
  - obsidian-planetary-tasks-manager
description: >
  Sync Jira issues assigned to the current user in active sprints into the Obsidian
  vault. Writes one note per issue into `Periodic/YEAR/Planetary Tasks/` with full
  frontmatter so they appear in Planetary Tasks.base views, and overwrites
  `00 Inbox/Tasks.md` as a quick-reference summary. Jira is always the source of
  truth. Use when the user asks to: sync Jira tasks, update sprint tasks, refresh
  their task list from Jira, pull active sprint issues into the vault, organise work
  tasks, or check what's on their Jira board.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins:
        - uvx
---

# Jira Sprint Sync

## Overview

Two outputs per sync:
1. **Per-issue notes** — one `.md` per issue in `Periodic/<YEAR>/Planetary Tasks/`, feeds `Planetary Tasks.base` views.
2. **Summary note** — `00 Inbox/Tasks.md` overwritten as a flat quick-reference index.

Jira is authoritative. Vault edits to synced properties are overwritten on every sync.
The synced issue notes still need to satisfy the canonical planetary task schema.

## Sync Workflow

### 1. Fetch from Jira

```
getAccessibleAtlassianResources()   → get cloudId
searchJiraIssuesUsingJql(
  jql: "assignee = currentUser() AND sprint in openSprints() ORDER BY priority ASC, status ASC",
  fields: ["summary", "status", "priority", "issuetype", "project"],
  maxResults: 100
)
```

### 2. Map Jira → note properties

| Jira field | Note property | Values |
|---|---|---|
| `status.statusCategory.key == "indeterminate"` | `task_status` | `in_progress` |
| `status.statusCategory.key == "new"` | `task_status` | `next` |
| `status.statusCategory.key == "done"` | `task_status` / `done` | `completed` / `true` |
| `priority.name` | `priority` | `High` / `Medium` / `Low` |

`done` defaults to `false` unless `task_status == "completed"`.

Also set the canonical task fields:
- `task_id: task-<key lowercased>`
- `task_kind: external_ticket`
- `thread: unassigned`
- `source_note: "[[00 Inbox/Tasks|Tasks]]"`
- `horizon_note: "[[Periodic/<YEAR>/<YEAR>-Www|<YEAR>-Www]]"` derived from the sync date
- `context`: include `source_note`, `horizon_note`, and `[[Periodic/Periodic Planning and Tasks Hub|Periodic Planning and Tasks Hub]]`
- `potential_links`: include `[[10 Notes/Planetary Tasks.base|Planetary Tasks Base]]` plus any deterministic project/person/company links the sync can resolve
- `tags`: include `type/task`, `planning/planetary`, `task-kind/external_ticket`, and a status tag aligned to `task_status`

### 3. Write per-issue notes

For each issue, render the canonical note through the shared schema layer, then write `Periodic/<YEAR>/Planetary Tasks/<KEY> - <SUMMARY>.md`:

```bash
uvx --from python --with pydantic --with pyyaml python .skills/jira-sprint-sync/scripts/render_jira_task.py \
  --mode write \
  --vault-root . \
  --key AG-XXXX \
  --summary "Summary text here" \
  --status-category indeterminate \
  --priority High \
  --jira-url https://autograb.atlassian.net/browse/AG-XXXX \
  --last-synced 2026-03-06T09:00:00+11:00
```

The renderer imports the shared Pydantic v2 task models from `obsidian-planetary-tasks-manager`, so Jira-backed notes and manual PT notes stay on the same contract.

**Filename rules:**
- Pattern: `AG-XXXX - Jira summary text here.md`
- Matches the PT-note convention (`PT-NNN - Description.md`)
- The summary portion is the Jira issue `summary` field, used verbatim
- If an existing note has a bare `<KEY>.md` filename (no summary), rename it to include the summary before overwriting

```markdown
---
task_id: task-ag-xxxx
task_kind: external_ticket
task_status: in_progress
done: false
planning_system: planetary
planning_horizon: maneuver
timeframe: anytime
domain: work
thread: unassigned
source_note: "[[00 Inbox/Tasks|Tasks]]"
horizon_note: "[[Periodic/<YEAR>/<YEAR>-Www|<YEAR>-Www]]"
context:
  - "[[00 Inbox/Tasks|Tasks]]"
  - "[[Periodic/<YEAR>/<YEAR>-Www|<YEAR>-Www]]"
  - "[[Periodic/Periodic Planning and Tasks Hub|Periodic Planning and Tasks Hub]]"
potential_links:
  - "[[10 Notes/Planetary Tasks.base|Planetary Tasks Base]]"
tags:
  - type/task
  - planning/planetary
  - task-kind/external_ticket
  - status/actionable
jira_sync: true
jira_key: AG-XXXX
jira_url: <webUrl>
priority: High
last_synced: <ISO-8601 local time>
---

# AG-XXXX · Summary text here

> [View in Jira](<webUrl>) · `High` · In Progress
```

`<YEAR>` = current year from `currentDate` (e.g. `2026`).

**Data quality guard — rename stale files:**
Before writing, glob for `Periodic/<YEAR>/Planetary Tasks/<KEY>*.md`. If an existing file matches the key but has a different or missing summary in the filename, rename it to `<KEY> - <SUMMARY>.md` (using `mv`) and update any wikilinks in the vault that referenced the old filename.

**Schema guard — validate after write:**
After writing each note, run:

```bash
uvx --from python --with pydantic --with pyyaml python .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py --mode check --path "Periodic/<YEAR>/Planetary Tasks/<KEY> - <SUMMARY>.md"
```

If validation fails, stop the sync and surface the schema errors instead of leaving partially compliant task notes behind.

### 4. Write summary note

Overwrite `00 Inbox/Tasks.md` entirely:

```markdown
---
jira_sync: true
last_synced: <ISO-8601>
tags:
  - status/processing
---

# Sprint Tasks

> Synced from Jira · <YYYY-MM-DD HH:MM>

## 🔄 In Progress

- [ ] [AG-XXXX](<webUrl>) Summary here `High`

## 📋 To Do

- [ ] [AG-YYYY](<webUrl>) Another summary `Medium`

## ✅ Done

- [x] [AG-ZZZZ](<webUrl>) Completed task `Low`
```

Omit a section entirely if its group is empty. Done issues use `- [x]`.

## Sync Rules

| Rule | Behaviour |
|---|---|
| Existing issue note | Overwrite completely from Jira — vault edits to synced properties are lost. If filename lacks summary, rename first. |
| New issue | Create note in `Periodic/<YEAR>/Planetary Tasks/<KEY> - <SUMMARY>.md` |
| Issue removed from sprint | Note is NOT deleted; data becomes stale — manual cleanup required |
| Done issues | Set `task_status: completed` + `done: true` |
| No issues found | Write "No active sprint issues." in both outputs, update `last_synced` |
| Schema drift | Re-render canonical frontmatter, then validate with the planetary task validator before finalizing the sync |

## After Syncing

Report to the user:
- Total issues synced
- Breakdown: N In Progress · N To Do · N Done
- Confirm both `Periodic/<YEAR>/Planetary Tasks/` (N files) and `00 Inbox/Tasks.md` were updated
