---
name: obsidian-excalidraw-visual-validator
version: 2.0.0
dependencies:
  - obsidian-excalidraw-drawing-manager
description: >
  Render Excalidraw drawings to PNG via Playwright and validate visual quality:
  overlap detection, spacing consistency, text overflow, arrow accuracy,
  composition balance. Imports models from drawing-manager (DRY). Outputs
  {"ok": bool} for autoresearcher.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [uvx]
      anyBins: [obsidian, playwright]
---

# Obsidian Excalidraw Visual Validator

## Overview

Validates **visual quality** of `.excalidraw.md` files. Complements
`obsidian-excalidraw-drawing-manager` (structural/schema) with geometric and
spatial checks. Imports Pydantic models from drawing-manager — no duplication.

Checks: overlap detection (>15% bbox), spacing consistency (CV < 0.5), text
overflow, arrow endpoint accuracy (15px tolerance), composition balance
(quadrant skew < 70%), size hierarchy (>= 2 tiers), dangling arrows, arrow
crossings.

## Workflow

### 1. Run Structural Validation First

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py \
  --glob "Excalidraw/**/*.excalidraw.md" --mode check
```

Fix structural issues before visual validation.

### 2. Run Visual Validation

Geometric checks only (fast, no Playwright):
```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --glob "Excalidraw/**/*.excalidraw.md" --mode check
```

With PNG rendering:
```bash
uvx --from python --with pydantic --with pyyaml --with playwright python \
  .skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --glob "Excalidraw/**/*.excalidraw.md" --mode check --render
```

### 3. Review and Fix

View renders: `open .skills/excalidraw-renders/`

Iterate: render → review → fix in Excalidraw VIEW → re-validate.

## Thresholds (VisualValidatorConfig)

| Check | Default | Severity |
|-------|---------|----------|
| Max overlap ratio | 15% | Warning |
| Min element gap | 20px | Warning |
| Spacing CV | 0.5 | Warning |
| Text padding | 10px | Error |
| Arrow snap tolerance | 15px | Error |
| Quadrant skew | 70% | Warning |
| Center-of-mass offset | 30% | Warning |
| Min size tiers | 2 | Warning |

## Guardrails

- Run structural validation first — visual validator assumes valid JSON
- Geometric checks work without Playwright
- Renders go to `.skills/excalidraw-renders/` (add to `.gitignore`)

## References

- [visual-heuristics.md](references/visual-heuristics.md) — 27-item quality checklist
- [design-patterns.md](references/design-patterns.md) — Visual pattern library
- [element-templates.md](references/element-templates.md) — Copy-paste JSON snippets
- [semantic-color-palette.md](references/semantic-color-palette.md) — Semantic color system
