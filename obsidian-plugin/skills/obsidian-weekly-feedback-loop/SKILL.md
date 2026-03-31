---
name: obsidian-weekly-feedback-loop
version: 1.0.0
dependencies:
  - obsidian-planetary-tasks-manager
pipeline: {}
description: Evaluate weekly Obsidian planning notes for closed-loop execution quality in this personal vault. Use when checking thread alignment, closure signals, and daily-weekly maneuver continuity under strict dependency and context-budget constraints.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Weekly Feedback Loop

Use this skill for weekly control-plane checks.

## Workflow

1. Select target week as `YYYY-Www`.
2. Run `uvx --from python --with pydantic --with pyyaml python scripts/weekly_ops.py --week YYYY-Www --mode check`.
3. If check fails, run `--mode report` to get markdown diagnostics.
4. If the week is backed by planetary tasks, validate closure-signal task notes as schema-backed artifacts with `uvx --from python --with pydantic --with pyyaml python .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py --mode check --path "Periodic/<YEAR>/Planetary Tasks/<task>.md"`.
5. Fix missing closure signals and thread alignment.
6. Re-run check until pass.

## Output Contract

`uvx --from python --with pydantic --with pyyaml python scripts/weekly_ops.py ...` supports:
- `--mode check` -> JSON compliance output
- `--mode report` -> Markdown report with compliance summary

## Weekly Quality Rules

- Keep 2-4 active priority threads visible.
- Preserve horizon links across 12-week, quarter, month, week.
- Ensure daily closure signals exist: completion count, blocker, first maneuver tomorrow.
- When the week references `Planetary Tasks.base`, treat closure-signal tasks as note-backed artifacts with canonical `task_kind: closure_signal`, not just prose placeholders.

## Dependency Policy

Fail fast when `obsidian`, `qmd`, or `uvx` is missing.
Do not finalize weekly synthesis when dependency checks fail.

## References

- Use `references/weekly-control-plane.md` for weekly standards.
- Use `references/daily-weekly-bridge.md` for maneuver continuity checks.
