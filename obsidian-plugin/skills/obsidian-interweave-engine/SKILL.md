---
name: obsidian-interweave-engine
version: 1.0.0
description: Audit and enrich note interweaving for this personal Obsidian vault without diluting source information. Use when linking concept/context notes, enforcing zettel tracking fields, and checking unresolved-link risk with strict dependency and budget discipline.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Interweave Engine

Use this skill for high-density, non-dilutive enrichment.

## Workflow

1. Read target note and immediate hubs only.
2. Run `uvx --from python python scripts/link_audit.py --path "<note-path>"`.
3. Inspect `missing_fields`, `concept_links`, `context_links`, and unresolved findings.
4. Apply minimal edits that preserve original information density.
5. Re-run audit to confirm compliance.

## Output Contract

`uvx --from python python scripts/link_audit.py ...` returns JSON with:
- `concept_links`
- `context_links`
- `missing_fields`
- `status_tags`
- unresolved link diagnostics

## Interweave Rules

- Preserve existing metadata unless explicitly asked to clean up.
- Maintain valid YAML frontmatter.
- Ensure one concept link plus one context link in body text when note class requires weaving.

## Dependency Policy

Fail fast when `obsidian`, `qmd`, or `uvx` is missing.
Do not perform enrichment edits after dependency failures.

## References

- Use `references/interweave-checklist.md` for required checks.
- Use `references/link-patterns.md` for concept/context linking patterns.
