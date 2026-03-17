---
name: obsidian-key-dates-base-manager
description: Maintain and evolve `10 Notes/Key Dates.base` in this personal Obsidian vault. Use when asked to create, audit, or update key-date formulas, date-link fields, date-based views, or path conventions, and when verifying that generated links map to existing vault notes using Obsidian CLI and qmd.
---

# Obsidian Key Dates Base Manager

Use this skill for every task that touches `10 Notes/Key Dates.base`.

## Workflow

1. Check dependencies before editing:
   - `obsidian help`
   - `qmd status`
2. Read only the minimum context:
   - `obsidian read path="10 Notes/Key Dates.base"`
3. Discover existing date-note targets:
   - `qmd ls obsidian | awk -F 'qmd://obsidian/' 'NF > 1 { print $2 }' | rg '^00-inbox/[0-9]{4}-[0-9]{2}-[0-9]{2}[.]md$|^periodic/[0-9]{4}/[0-9]{4}-w[0-9]{2}[.]md$|^periodic/[0-9]{4}/[0-9]{4}-[0-9]{2}-monthly-review[.]md$|^periodic/[0-9]{4}/[0-9]{4}[.]md$'`
4. Apply the smallest safe `.base` edit that satisfies the request.
5. Verify after edits:
   - `obsidian read path="10 Notes/Key Dates.base"`
   - `obsidian links path="10 Notes/Key Dates.base" total`
   - `obsidian unresolved total`
6. Report updated formulas/views and verification outputs.

## Edit Rules

- Keep YAML valid and Obsidian Bases-compatible.
- Preserve existing properties and views unless the user explicitly asks for redesign.
- Prefer existence-checked formula links:
  - `if(path != "" && file(path), link(path, label), "")`
- Use explicit `.md` suffixes in generated paths.
- Keep canonical fallback order for anchor dates:
  - `target_date` -> `date` -> `window_start` -> parsed `file.basename` date.
- Keep vault path casing consistent with actual files:
  - `00 Inbox/...`
  - `Periodic/<year>/...`

## Date Targets

- Daily inbox note: `00 Inbox/YYYY-MM-DD.md`
- Daily periodic note: `Periodic/YYYY/YYYY-MM-DD.md`
- Weekly note: `Periodic/YYYY/YYYY-WNN.md`
- Monthly review: `Periodic/YYYY/YYYY-MM-Monthly-Review.md`
- Year note: `Periodic/YYYY/YYYY.md`

## References

- Use `references/key-dates-patterns.md` for reusable formulas and path patterns.
