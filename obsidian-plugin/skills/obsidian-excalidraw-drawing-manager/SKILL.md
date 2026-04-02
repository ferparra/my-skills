---
name: obsidian-excalidraw-drawing-manager
version: 2.0.0
dependencies: []
description: >
  Validate and construct Excalidraw diagrams (.excalidraw.md) with Pydantic v2
  models. Phased construction for concept maps, feedback loops, architecture
  diagrams. Git checkpoint undo/redo. Outputs {"ok": bool} for autoresearcher.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [git, uvx]
      anyBins: [obsidian]
---

# Obsidian Excalidraw Drawing Manager

## Overview

Validates `.excalidraw.md` files and orchestrates phased diagram construction.
Pydantic v2 models with discriminated unions enforce strict schema compliance.
The visual-validator skill imports from this skill's `excalidraw_models.py` —
single source of truth, no duplication.

## Workflow

### 1. Confirm Dependencies

```bash
uvx --version
git --version
obsidian --help 2>/dev/null || echo "obsidian CLI optional"
```

### 2. Validate

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py \
  --glob "Excalidraw/**/*.excalidraw.md" --mode check
```

Output: `{"ok": bool, "count": N, "results": [...]}`

### 3. Phased Construction

Complex diagrams (>5 elements) MUST be built in phases — never one-shot.

| Phase | Action | Gate |
|-------|--------|------|
| 1. Skeleton | Place shapes with positions/sizes | No overlaps, proper spacing |
| 2. Connect | Add arrows with bindings | All bindings resolve |
| 3. Label | Add text in containers | No text overflow |
| 4. Style | Apply colors, fill, stroke | Valid enums and colors |
| 5. QA | Structural + visual validation chain | Git commit or revert |

Validate after every 2-3 elements. Do not batch >5 elements before validating.

### 4. Git Checkpoint Protocol

```bash
# Before modification
git add "Excalidraw/<diagram>.excalidraw.md"
git commit -m "checkpoint: <diagram> before <action>"

# Validate after modification
uvx ... validate_excalidraw.py --path "<file>" --mode check

# Pass → commit; Fail → revert
git checkout HEAD -- "Excalidraw/<diagram>.excalidraw.md"  # revert
git tag "v1-<diagram-name>"                                 # milestone
```

### 5. Visual Validation Chain

After structural validation, chain to visual-validator:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --path "Excalidraw/<diagram>.excalidraw.md" --mode check
```

### 6. Fix Issues

- **Broken text binding**: Remove invalid `containerId` or add missing container
- **Broken arrow binding**: Remove invalid binding or add missing target
- **Bidirectional mismatch**: Sync `boundElements` with text's `containerId`
- **Duplicate IDs**: Regenerate unique IDs

**Never manually edit JSON** — use Excalidraw VIEW or programmatic generation.

## Model Routing

| Task | Tier | Why |
|------|------|-----|
| Concept extraction, layout planning | Capable (Opus/Sonnet) | Spatial reasoning |
| Coordinate math, template filling | Fast (Haiku/Flash) | Deterministic geometry |
| Visual QA scoring | Vision (Gemini Flash 2.5) | Spatial perception |
| Validation, git, rendering | None — scripts | No model needed |

Subagent pattern for complex diagrams:
```
Coordinator (Capable) → Layout Agent (Fast) + Connection Agent (Fast) + QA Agent (Vision)
```

## Diagram Kind Support

Supports all `diagram_kind` taxonomy values. Key construction patterns:

### Concept Map (`concept_map`)
Focus Question (top) → Main Concepts → Sub-concepts → Cross-links → Examples.
All arrows labeled with relationship verbs. 3-5 depth levels. No orphan concepts.
Vetted exemplars: `prototypical-concept-map`, `order-fulfillment-concept-map`.

### Causal Loop / Feedback Loop (`feedback_loop`)
Variables in circular layout → causal arrows with `+`/`-` polarity labels →
loop indicators (`R`/`B`) at center. Minimum 3 variables per loop.

### Stock-Flow (`systems_flowchart`)
Stocks (large rectangles) → flows (arrows with valve diamonds) → converters
(ellipses) → dashed connectors from converters to valves.

### Control System (`systems_flowchart`)
Plant → Sensor → Controller → Actuator → Plant (rectangular loop).
Setpoint input at Controller. Error signal labeled.

### Architecture (`architecture_diagram`)
Boundary rectangles → component rectangles inside → connection arrows with
protocol labels. Horizontal layers: Client → Gateway → Services → Data.

### Hub and Spoke (`hub_and_spoke`)
Hub at center (hero size) → spokes at equal angular spacing → arrows with labels.

## Anti-Pattern Rules

See [references/excalidraw-schema.md](references/excalidraw-schema.md).

### Errors
1. Duplicate element IDs
2. Text `containerId` → non-existent element
3. Arrow binding → non-existent element
4. Bidirectional binding mismatch
5. Invalid fillStyle/strokeStyle
6. Numeric ranges (opacity, roughness, fontFamily)

### Warnings
7. Zero-dimension shapes
8. text/originalText mismatch
9. Invalid color format
10. Orphaned group IDs
11. Text Elements section out of sync

## Guardrails

- Never modify drawing JSON directly — use Excalidraw VIEW
- Decompress before validation: command palette → "Decompress current Excalidraw file"
- Respect `isDeleted` flag (Excalidraw undo buffer)
- Git is the memory — every iteration committed, milestones tagged
- Phase-based construction only for >5 elements
- Validate after every 2-3 elements

## References

- [excalidraw-schema.md](references/excalidraw-schema.md) — Element schema and anti-pattern catalogue
- Cross-skill: `obsidian-excalidraw-visual-validator` — geometric QA (imports this skill's models)
