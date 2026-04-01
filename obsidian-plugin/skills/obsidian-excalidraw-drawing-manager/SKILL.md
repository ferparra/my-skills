---
name: obsidian-excalidraw-drawing-manager
version: 1.0.0
description: >
  Validate Excalidraw drawings (.excalidraw.md) with Pydantic v2 models. Detects broken bindings,
  duplicate IDs, zero-dimension shapes, invalid colors. Use for excalidraw validation, schema
  enforcement, drawing integrity checks. Outputs {"ok": bool} for autoresearcher.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Excalidraw Drawing Manager

## Overview

This skill validates `.excalidraw.md` files created by the obsidian-excalidraw-plugin. It enforces strict schema compliance and detects structural anti-patterns that break drawings: broken element bindings, duplicate IDs, orphaned references, and markdown/JSON inconsistencies.

All validation uses strictly typed Pydantic v2 models with discriminated unions by element type. Outputs clear `{"ok": bool}` JSON for autoresearcher compatibility.

## Workflow

### 1. Confirm Dependencies

Check that required commands are available:
```bash
uvx --version
obsidian --version
qmd status
```

If any are missing, consult the router's fallback checklist.

### 2. Read Surface

Use `qmd` and `obsidian` to read the drawing files:
```bash
qmd query "excalidraw drawing diagram" -c notes -l 8
qmd query "excalidraw" -c inbox -l 5
```

### 3. Validate

Run the validation script:
```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py \
  --glob "**/*.excalidraw.md" \
  --mode check
```

**Modes**:
- `--mode check` (default): Exit code 1 if errors found
- `--mode report`: Always exit code 0, report all results

**Output**: JSON with `{"ok": bool, "count": N, "results": [...]}`

Each result includes:
- `path`: relative file path
- `ok`: boolean validation status
- `errors`: array of error messages (structural failures)
- `warnings`: array of warning messages (non-fatal issues)
- `element_count`: total elements
- `text_element_count`: number of text elements

### 4. Fix Issues (if validation fails)

Based on error messages:

- **Broken text binding**: Remove invalid `containerId` or add missing container element
- **Broken arrow binding**: Remove invalid binding or add missing target element
- **Bidirectional mismatch**: Sync `boundElements` array with text's `containerId`
- **Duplicate IDs**: Regenerate unique IDs for duplicate elements

**Never manually edit JSON** — use Excalidraw VIEW to fix, or delete and recreate elements.

### 5. Re-validate

After fixes, re-run validation to confirm `ok: true`.

## Anti-Pattern Rules

See [references/excalidraw-schema.md](references/excalidraw-schema.md) for full schema and anti-pattern catalogue.

### Critical Errors (fail validation)
1. Duplicate element IDs
2. Text `containerId` pointing to non-existent element
3. Arrow binding referencing non-existent element
4. Container/text bidirectional binding mismatch

### Warnings (non-fatal)
5. Zero-dimension shapes (width=0 or height=0)
6. text/originalText mismatch (may be line wrapping)
7. Invalid color format
8. Orphaned group IDs (appearing on single element)
9. Markdown `## Text Elements` out of sync with JSON

## Guardrails

- **Never modify drawing JSON directly** — use Excalidraw VIEW to make changes
- **Preserve existing metadata**: Don't strip frontmatter fields beyond validation
- **Decompress before validation**: Most vault files use `compressed-json` format. To validate:
  1. Open file in Obsidian
  2. Command palette → "Decompress current Excalidraw file"
  3. Run validation
  
  The plugin uses pako (JavaScript) compression which is incompatible with Python's zlib.
- **Respect isDeleted flag**: Deleted elements may still exist in JSON (Excalidraw's undo buffer)

## Schema Versions

This validator enforces **Excalidraw schema version 2** only. Files with version 1 or 3+ will fail validation.

Source field should reference:
```
https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/X.XX.X
```

## References

- [excalidraw-schema.md](references/excalidraw-schema.md) — Complete element schema and anti-pattern catalogue
- [obsidian-excalidraw-plugin](https://github.com/zsviczian/obsidian-excalidraw-plugin) — Plugin repository
