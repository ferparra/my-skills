---
name: obsidian-planetary-tasks-manager
version: 1.0.0
description: Maintain planetary task notes, task schema, and task-related Bases in this personal Obsidian vault. Use when requests involve Planetary Tasks.base, Periodic Planning and Tasks Hub.base, task_kind enforcement, Jira-synced planetary tasks, maneuver-board closure signals, or planetary task schema migration and validation.
metadata:
  openclaw:
    os: [macos]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Planetary Tasks Manager

Run this skill when the request is specifically about planetary task notes, `task_kind`, or task-facing Bases.

Treat `task_kind` and adjacent `*_kind` fields as a lightweight supertag layer: the kind selects the note's type contract, and Pydantic v2 enforces the schema behind that type.

## Workflow

1. Confirm dependencies before editing:
   - `obsidian`
   - `qmd`
   - `uvx`
2. Validate task notes before mutating:
   - `uvx --from python --with pydantic --with pyyaml python .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py --glob "Periodic/*/Planetary Tasks/*.md"`
3. Migrate or normalize when needed:
   - `uvx --from python --with pydantic --with pyyaml python .skills/obsidian-planetary-tasks-manager/scripts/migrate_tasks.py --glob "Periodic/*/Planetary Tasks/*.md" --mode fix`
4. Re-run validation after edits.
5. Refresh related Bases and verify with Obsidian CLI reads.

## What This Skill Owns

- Canonical planetary task frontmatter
- `task_kind` classification and migration
- PT task notes and Jira-synced AG task notes under `Periodic/*/Planetary Tasks/`
- `10 Notes/Planetary Tasks.base`
- `Periodic/Periodic Planning and Tasks Hub.base`

## Canonical Commands

Use explicit `uvx` wrappers for every Python-backed script:

```bash
uvx --from python --with pydantic --with pyyaml python .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py --glob "Periodic/*/Planetary Tasks/*.md"
uvx --from python --with pydantic --with pyyaml python .skills/obsidian-planetary-tasks-manager/scripts/migrate_tasks.py --glob "Periodic/*/Planetary Tasks/*.md" --mode fix
```

## Guardrails

- Preserve existing metadata fields unless normalization requires filling missing canonical fields.
- Do not silently guess beyond the documented task-kind rules.
- Preserve user-authored task bodies; only add minimal planning context when the schema requires missing concept/context links.
- Keep `planning_horizon` authoritative. Do not add `objective_kind`.
- Keep Bases Obsidian-compatible YAML.

## References

- Read `references/task-schema.md` for the canonical task contract and migration policy.
- Read `references/kind-taxonomy.md` for `task_kind` and adjacent `*_kind` values.
- Use `scripts/task_models.py` as the shared source of truth for validation and route-compatible models.
