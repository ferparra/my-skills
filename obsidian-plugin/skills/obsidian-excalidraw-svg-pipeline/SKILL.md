---
name: obsidian-excalidraw-svg-pipeline
version: "1.0.0"
description: "Generate Excalidraw diagrams via annotated SVG intermediate representation. Classifies diagram type, loads structural blueprint, guides LLM to generate annotated SVG, then deterministically transforms to .excalidraw.md."
triggers:
  - generate diagram
  - create excalidraw
  - svg pipeline
  - annotated svg
  - diagram from template
  - create excalidraw diagram
  - draw a diagram
  - make a diagram
tags:
  - obsidian
  - excalidraw
  - diagram-generation
  - svg-pipeline
---

# Obsidian Excalidraw SVG Pipeline

## Overview

SVG-first pipeline for generating Excalidraw diagrams. Instead of asking a model
to produce Excalidraw JSON directly (which it will hallucinate), the pipeline has
the model generate an **annotated SVG** -- a format models produce reliably --
then runs a deterministic transform to convert the SVG into a valid
`.excalidraw.md` file.

## Why SVG-First

- **Rich training data.** SVG is an open W3C standard with massive
  representation in model training corpora. Models generate valid SVG
  consistently, even less capable ones (minimax, auto-routed tiers).
- **Excalidraw JSON is proprietary.** Its schema is sparse in training data.
  Models hallucinate field names, invent enum values, and produce structurally
  invalid output. Fixing bad JSON is harder than generating good SVG.
- **Deterministic transform.** The SVG-to-Excalidraw conversion is mechanical --
  no LLM involved, no hallucination risk. Annotations in the SVG carry the
  semantic information the transform needs.

## Workflow

### Step 1 -- Classify Diagram Type

```bash
uvx --from python --with pyyaml python scripts/classify_diagram_type.py \
  --intent "<user request>"
```

Returns one of 22 diagram type slugs (e.g., `hub_spoke`, `swimlane`, `erd`).
See the [Diagram Type Catalog](references/diagram-type-catalog.md) for the full
list.

### Step 2 -- Load Reference

Read the matching annotated SVG from the reference library:

```
research/excalidraw-svg-references/annotated/
  20260403__gemini-pro-3_1__svg_immutable_reference_didactic_<type>.svg
```

Include the full SVG content in the LLM's context. This serves as a structural
blueprint -- the model should follow its annotation patterns, element layout, and
semantic grouping conventions exactly.

### Step 3 -- Generate Annotated SVG

The LLM generates a **new** annotated SVG with the user's content. It must
follow the reference's annotation schema exactly. See the full
[Annotation Schema](references/annotation-schema.md) specification and the
detailed generation instructions below.

### Step 4 -- Validate

```bash
uvx --from python python scripts/validate_annotated_svg.py \
  --path <generated.svg>
```

Confirms schema compliance: checks for required comments, desc element, semantic
role attributes, and graph consistency (every `data-from`/`data-to` references
an existing node ID).

### Step 5 -- Transform

```bash
uvx --from python python scripts/svg_to_excalidraw.py \
  --input <generated.svg> \
  --output <output.excalidraw.md>
```

Deterministic conversion from annotated SVG to `.excalidraw.md`. See
[SVG-to-Excalidraw Transform](references/svg-to-excalidraw.md) for the mapping
rules.

### Step 6 -- Quality Gate

Chain to downstream validators:

1. **`obsidian-excalidraw-drawing-manager`** -- structural validation via
   Pydantic v2 models. Confirms the generated `.excalidraw.md` has valid JSON,
   correct element types, and proper `boundElements`/`containerId` bindings.
2. **`obsidian-excalidraw-visual-validator`** -- geometric checks. Confirms
   elements do not overlap, arrows connect to their targets, and text fits
   within containers.

---

## SVG Generation Instructions for the Model

When generating an annotated SVG, follow these rules exactly.

### Root Element

```xml
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {width} {height}"
     style="background-color: #fafafa;
            font-family: -apple-system, BlinkMacSystemFont,
                         'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
```

- `viewBox` width: 1400-1800. Height: 600-1000. Choose based on content density.

### Required Metadata

1. **DIAGRAM_TYPE comment** -- first child of `<svg>`:
   ```xml
   <!-- DIAGRAM_TYPE: hub_spoke -->
   ```

2. **TOPOLOGY comment** -- second child:
   ```xml
   <!-- TOPOLOGY: Star topology with 1 central hub and 5 spoke nodes. 6 nodes, 5 bidirectional edges. -->
   ```
   Include: topology shape, node count, edge count, notable structural features.

3. **`<desc>` element** -- natural language summary for LLM consumption. 2-4
   sentences describing the diagram's content, purpose, and key relationships.

### Semantic Groups

Every visual element must be wrapped in a `<g>` group with these attributes:

| Attribute              | Required | Description                                |
|------------------------|----------|--------------------------------------------|
| `id`                   | Yes      | Unique, kebab-case (e.g., `node-api-gw`)   |
| `role`                 | Yes      | Always `"img"` (except title: `"heading"`)  |
| `aria-label`           | Yes      | Human-readable description of the element   |
| `data-semantic-role`   | Yes      | One of the vocabulary values below          |

### `data-semantic-role` Vocabulary

**Core roles** (used in all diagram types):
- `node` -- a box, circle, or shape representing an entity
- `edge` -- a line or arrow connecting two nodes
- `annotation` -- explanatory text or decoration not part of the graph
- `label` -- text label attached to a node or edge
- `title` -- diagram title group
- `legend` -- legend or key group
- `container` -- a grouping rectangle containing child nodes
- `layer` -- a horizontal layer in a layered architecture
- `lane` -- a vertical or horizontal swimlane

**Domain-specific roles** (used by specific diagram types):
- `state` -- a state node (UML state machine)
- `initial-state` -- the filled circle start state
- `final-state` -- the bullseye end state
- `guard-condition` -- a bracketed transition guard
- `transition` -- a state-to-state edge (alias for edge in state machines)
- `stock` -- a stock (accumulation) in system dynamics
- `flow` -- a flow (rate) pipe in system dynamics
- `valve` -- a flow-rate controller (diamond on a flow pipe)
- `cloud` -- a source/sink cloud in system dynamics
- `auxiliary` -- an auxiliary variable in system dynamics
- `entity` -- an entity box in an ER diagram
- `relationship` -- an edge with cardinality in an ER diagram
- `aggregate-root` -- a DDD aggregate root box
- `value-object` -- a DDD value object box

### Node Attributes

Every `<g data-semantic-role="node">` (and `stock`, `entity`, `state`, etc.)
must include:

- `data-upstream="node-id-1,node-id-2"` -- comma-separated IDs of nodes that
  feed into this node
- `data-downstream="node-id-1,node-id-2"` -- comma-separated IDs of nodes this
  node feeds into
- Omit the attribute (do not use empty string) if there are no connections in
  that direction.

### Edge Attributes

Every `<g data-semantic-role="edge">` (and `relationship`, `transition`, `flow`)
must include:

- `data-from="node-source-id"` -- ID of the source node
- `data-to="node-target-id"` -- ID of the target node

### Domain-Specific Attributes

Use these when the diagram type requires them:

| Attribute              | Used by          | Example                       |
|------------------------|------------------|-------------------------------|
| `data-cardinality`     | erd              | `"1:0..*"`                    |
| `data-lane`            | swimlane         | `"customer"`                  |
| `data-layer`           | layered_arch     | `"presentation"`              |
| `data-visibility`      | design_level     | `"public"`                    |
| `data-trigger`         | uml_state        | `"timeout"`                   |
| `data-entity-fields`   | erd              | `"id PK, name, email"`        |
| `data-label`           | erd, flow        | `"PLACES"`                    |

### ID Naming Conventions

- All IDs are kebab-case
- Prefix with the semantic role: `node-`, `edge-`, `label-`, `lane-`,
  `stock-`, `flow-`, `entity-`, `state-`, etc.
- Examples: `node-api-gateway`, `edge-user-to-auth`, `label-request-count`,
  `lane-customer`, `stock-prey-population`

### Visual Rules

- **Rounded rectangles**: `rx="12"` for standard nodes
- **Colors**: Use the Tailwind CSS color palette (slate, gray, red, orange,
  amber, yellow, lime, green, emerald, teal, cyan, sky, blue, indigo, violet,
  purple, fuchsia, pink, rose). Use light fills (50-100 range) with darker
  strokes (400-600 range).
- **Fonts**: System font stack only (declared in the root `style`). No external
  font imports.
- **Arrows**: Use `<marker>` definitions for arrowheads. Standard pattern:
  ```xml
  <marker id="arrow-end" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="6" markerHeight="6" orient="auto">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
  </marker>
  ```
  Apply with `marker-end="url(#arrow-end)"` on `<path>` elements.
- **Edge labels**: Nest a `<g data-semantic-role="label">` inside the edge
  group, containing a small `<rect>` background and `<text>`.

---

## Diagram Type Reference

| # | Type Slug                | Description                                              |
|---|--------------------------|----------------------------------------------------------|
| 1 | `big_picture_timeline`   | Horizontal timeline with era groupings and milestones    |
| 2 | `bounded_context_map`    | DDD bounded contexts with integration patterns           |
| 3 | `cloud_cluster`          | Cloud infrastructure nodes grouped by region/VPC         |
| 4 | `concept_map`            | Free-form nodes with labeled relationship edges          |
| 5 | `convergence`            | Multiple inputs funneling to a single output             |
| 6 | `design_level_aggregate` | DDD aggregate root with value objects and entities        |
| 7 | `erd`                    | Entity-Relationship diagram with Crow's Foot notation    |
| 8 | `fan_out`                | Single source distributing to multiple targets           |
| 9 | `hub_spoke`              | Central hub with radial spoke connections                 |
|10 | `iterative_cycle`        | Circular process with feedback loops                     |
|11 | `layered_architecture`   | Horizontal layers with vertical dependency arrows        |
|12 | `mind_map`               | Central topic with branching subtopics                   |
|13 | `pipeline`               | Linear left-to-right processing stages                   |
|14 | `process_level_flow`     | Business process flowchart with decisions and branches    |
|15 | `sequence`               | Vertical timeline showing actor interactions             |
|16 | `service_blueprint`      | Customer journey with frontstage/backstage separation    |
|17 | `stock_and_flow`         | System dynamics stocks, flows, valves, and clouds        |
|18 | `swimlane`               | Parallel lanes with cross-lane handoffs                  |
|19 | `system_control`         | Control loop with sensor, controller, and actuator       |
|20 | `systems_thinking`       | Causal loop diagram with reinforcing/balancing feedback  |
|21 | `tree`                   | Hierarchical parent-child tree structure                  |
|22 | `uml_state_machine`      | States, transitions, guards, and initial/final states    |
