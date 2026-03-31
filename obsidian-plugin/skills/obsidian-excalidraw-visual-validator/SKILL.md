---
name: obsidian-excalidraw-visual-validator
version: 1.0.0
dependencies:
  - obsidian-excalidraw-drawing-manager
pipeline: {}
description: >
  Render Excalidraw drawings to PNG via Playwright and validate visual quality: overlap
  detection, spacing consistency, text overflow, arrow accuracy, composition balance.
  Outputs {"ok": bool} for autoresearcher.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx, playwright]
---

# Obsidian Excalidraw Visual Validator

## Overview

This skill validates the **visual quality** of `.excalidraw.md` files created by the obsidian-excalidraw-plugin. It complements `obsidian-excalidraw-drawing-manager` (which validates structural/schema correctness) by detecting geometric and spatial issues:

- **Rendering**: Generates PNG previews via Playwright + Excalidraw's `exportToSvg`
- **Overlap detection**: Flags elements with >15% bbox overlap
- **Spacing consistency**: Checks for even gaps between elements (CV < 0.5)
- **Text overflow**: Detects text wider than its container
- **Arrow accuracy**: Verifies arrow endpoints land within 15px of target bboxes
- **Composition balance**: Checks center-of-mass offset and quadrant distribution
- **Size hierarchy**: Ensures multiple distinct size tiers exist

All checks produce clear `{"ok": bool}` JSON output for autoresearcher compatibility.

## Workflow

### 1. Confirm Dependencies

Check that required commands are available:
```bash
uvx --version
obsidian --version
qmd status
playwright --version || python -m playwright install chromium
```

If Playwright's Chromium browser is missing, install it:
```bash
python -m playwright install chromium
```

### 2. Run Structural Validation First

Always validate schema correctness before visual quality:
```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py \
  --glob "**/*.excalidraw.md" --mode check
```

If structural validation fails, fix those issues first. Visual validation assumes valid JSON structure.

### 3. Run Visual Validation

Without rendering (geometric checks only, fast):
```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --glob "**/*.excalidraw.md" \
  --mode check
```

With rendering to PNG (requires Playwright, slower):
```bash
uvx --from python --with pydantic --with pyyaml --with playwright python \
  .skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --glob "**/*.excalidraw.md" \
  --mode check \
  --render \
  --output-dir ".skills/excalidraw-renders"
```

**Modes**:
- `--mode check` (default): Exit code 1 if errors found
- `--mode report`: Always exit code 0, report all results

**Output**: JSON with `{"ok": bool, "count": N, "results": [...]}`

Each result includes:
- `path`: relative file path
- `ok`: boolean validation status
- `errors`: array of error messages (fail validation)
- `warnings`: array of warning messages (non-fatal)
- `element_count`: total active elements
- `render_path`: PNG path (if `--render` used)

### 4. Review PNG Renders

If you used `--render`, view the PNG files to visually inspect diagram quality:
```bash
open .skills/excalidraw-renders/
```

Audit against the quality checklist in `references/visual-heuristics.md`.

### 5. Render-View-Fix Loop (Manual)

For diagrams with visual issues:

1. **Render**: Generate PNG preview
2. **View**: Open PNG, identify issues (overlap, uneven spacing, poor composition)
3. **Fix**: Open drawing in Excalidraw VIEW mode in Obsidian, adjust element positions/sizes
4. **Re-render**: Generate new PNG, verify fixes

Repeat 2-4 iterations until the diagram passes all checks.

## Visual Quality Checklist

See [references/visual-heuristics.md](references/visual-heuristics.md) for the full 27-item checklist covering:

- **Depth & Evidence**: Research, evidence artifacts, multi-zoom levels
- **Conceptual**: Isomorphism, argument, variety, no uniform containers
- **Container Discipline**: <30% text in containers, lines as structure, typography hierarchy
- **Structural**: Arrows for relationships, clear flow, size = importance
- **Technical**: fontFamily:3, roughness:0, opacity:100
- **Visual Validation**: No overflow/overlap, even spacing, arrows land correctly, balanced composition

## Design Resources

- **Color palette**: [references/semantic-color-palette.md](references/semantic-color-palette.md) — Semantic color system (start=orange, end=green, etc.)
- **Element templates**: [references/element-templates.md](references/element-templates.md) — Copy-paste JSON snippets
- **Design patterns**: [references/design-patterns.md](references/design-patterns.md) — Visual pattern library (fan-out, tree, hub-and-spoke, etc.)

## Guardrails

- **Run structural validation first**: Visual validator assumes valid JSON structure
- **Playwright requirement**: Rendering requires Chromium browser installed via `python -m playwright install chromium`
- **PNG output location**: Renders written to `.skills/excalidraw-renders/` (add to `.gitignore`)
- **Geometric checks work without Playwright**: Overlap, spacing, text overflow, arrow accuracy, composition checks run without rendering
- **CI/test considerations**: Render tests skip if Playwright unavailable (see `@pytest.mark.skipif` in tests)

## Thresholds (Configurable)

Default thresholds in `VisualValidatorConfig`:
- Max overlap: 15% of smaller element
- Min element gap: 20px
- Spacing CV: 0.5
- Text padding: 10px
- Arrow snap tolerance: 15px
- Max quadrant skew: 70%
- Center-of-mass offset: 30%
- Min size tiers: 2

Override via config if needed for specific use cases.
