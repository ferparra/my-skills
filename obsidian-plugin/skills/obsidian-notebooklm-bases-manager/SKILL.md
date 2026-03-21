---
name: obsidian-notebooklm-bases-manager
version: 1.0.0
metadata:
  openclaw:
    os: [macos]
    requires:
      bins: [obsidian, qmd, uvx]
description: Maintain NotebookLM notebook metadata and Obsidian Bases in this vault. Use when asked to create, audit, or update a NotebookLM-related `.base` file, standardise frontmatter for NotebookLM notes, classify NotebookLM notes into skill-development lanes, or validate NotebookLM note metadata before those notes are surfaced in Bases views.
---

# Obsidian NotebookLM Bases Manager

Use this skill whenever a task combines NotebookLM notebook notes with Obsidian Bases.

## Workflow

1. Check dependencies before editing:
   - `obsidian help`
   - `qmd status`
   - `uvx --version`
2. Read only the minimum context:
   - target `.base` file if it already exists
   - `00 Inbox/NotebookLM map.md`
   - the NotebookLM note(s) being added or audited
3. Parse and validate NotebookLM frontmatter before touching the base:
   - `uvx --from python --with pyyaml python scripts/parse_notebooklm_frontmatter.py --path "<note>.md"`
   - `uvx --from python --with pyyaml --with jsonschema python scripts/validate_notebooklm_frontmatter.py --path "<note>.md"`
4. If the library view should expose raw NotebookLM inventory items, materialize per-notebook notes first:
   - `uvx --from python --with pyyaml python scripts/materialize_notebooklm_notes.py --inventory "00 Inbox/Notebook LM notebooks.md" --summaries "00 Inbox/My NotebookLM notebooks.md" --output-dir "20 Resources/NotebookLM"`
5. If the base needs to be created or refreshed, scaffold it deterministically:
   - `uvx --from python --with pyyaml python scripts/render_notebooklm_base.py --output "10 Notes/NotebookLM Notebooks.base"`
6. Apply the smallest safe `.base` edit that satisfies the request.
7. Verify after edits:
   - `obsidian read path="10 Notes/NotebookLM Notebooks.base"` or the requested base path
   - `obsidian links path="<base>.base" total`
   - `obsidian unresolved total`
8. Report the base/view changes and validation findings.

## Frontmatter Contract

- Use `references/notebooklm-frontmatter-contract.md` for field definitions and lane meanings.
- The validator script loads `scripts/notebooklm_frontmatter_schema.json` as the canonical schema.
- Treat `notebooklm_note_kind` as the routing field:
  - `index`
  - `map`
  - `notebook`
- For notebook records that should appear in Bases views, require:
  - `notebooklm_title`
  - `notebooklm_url`
  - `notebooklm_lane`
  - `connection_strength`
  - `potential_links`

## Base Rules

- Keep YAML valid and compatible with `$schema: vault://schemas/obsidian/bases-2025-09.schema.json`.
- Preserve existing views and properties unless the user explicitly asks for redesign.
- Prefer formulas that tolerate missing properties with `if(...)`.
- Keep lane names stable:
  - `ai-systems`
  - `strategic-judgment`
  - `philosophy-meaning`
  - `health-resilience`
  - `pkm-operations`
  - `unassigned`
- Prefer `10 Notes/NotebookLM Notebooks.base` as the default base path when creating a new base.

## References

- Use `references/notebooklm-frontmatter-contract.md` for field definitions and examples.
- Use `references/notebooklm-base-patterns.md` for reusable base formulas and view layouts.
