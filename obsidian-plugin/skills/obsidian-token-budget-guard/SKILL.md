---
name: obsidian-token-budget-guard
version: 1.0.0
description: Enforce strict context and token budget gates for this personal Obsidian vault before substantial note reads or edits. Use when candidate files are known and you must validate max files, max chars, and max snippet counts with fail-fast obsidian/qmd dependency checks.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Token Budget Guard

Use this skill before loading broad context.

## Workflow

1. Build candidate file list with minimal search.
2. Run `uvx --from python python scripts/token_guard.py --candidate-files "<csv>" --max-files 5 --max-chars 22000 --max-snippets 12`.
3. If guard fails, reduce scope and rerun.
4. Proceed only when guard returns `ok: true`.

## Output Contract

`uvx --from python python scripts/token_guard.py ...` returns JSON with:
- `ok`
- `summary`
- `limits`
- `violations`
- `remediation`

Exit code is non-zero on any gate violation.

## Dependency Policy

Fail fast when `obsidian`, `qmd`, or `uvx` is missing.
Do not continue with broad reads after dependency failures.

## References

- Use `references/token-budget-rules.md` for enforced thresholds.
- Use `references/compaction-playbook.md` for scope reduction patterns.
