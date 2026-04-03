# SVG-to-Excalidraw Transform Mapping

Documents the deterministic conversion from annotated SVG elements to Excalidraw
JSON elements performed by `scripts/svg_to_excalidraw.py`.

---

## 1. Element Mapping

### Nodes: `<g data-semantic-role="node">` with `<rect>`

SVG input:
```xml
<g id="node-api-gateway" data-semantic-role="node" ...>
  <rect x="660" y="370" width="280" height="160" rx="12"
        fill="#e0e7ff" stroke="#818cf8" stroke-width="2" />
</g>
```

Excalidraw output:
```json
{
  "id": "node-api-gateway",
  "type": "rectangle",
  "x": 660,
  "y": 370,
  "width": 280,
  "height": 160,
  "roundness": { "type": 3, "value": 12 },
  "backgroundColor": "#e0e7ff",
  "strokeColor": "#818cf8",
  "strokeWidth": 2,
  "boundElements": [
    { "id": "label-api-gateway", "type": "text" },
    { "id": "edge-user-to-api", "type": "arrow" }
  ]
}
```

**Rules:**
- `rx` maps to `roundness.value`. If `rx` is present, `roundness.type` is `3`.
- `fill` maps to `backgroundColor`.
- `stroke` maps to `strokeColor`.
- `stroke-width` maps to `strokeWidth`.
- `boundElements` is populated by scanning for labels nested inside the group
  and edges that reference this node via `data-from`/`data-to`.

### Nodes: `<g data-semantic-role="node">` with `<ellipse>`

SVG input:
```xml
<g id="node-central" data-semantic-role="node" ...>
  <ellipse cx="800" cy="450" rx="100" ry="60"
           fill="#fef3c7" stroke="#f59e0b" stroke-width="2" />
</g>
```

Excalidraw output:
```json
{
  "id": "node-central",
  "type": "ellipse",
  "x": 700,
  "y": 390,
  "width": 200,
  "height": 120,
  "backgroundColor": "#fef3c7",
  "strokeColor": "#f59e0b",
  "strokeWidth": 2,
  "boundElements": []
}
```

**Rules:**
- `cx - rx` gives `x`. `cy - ry` gives `y`.
- `rx * 2` gives `width`. `ry * 2` gives `height`.

### Edges: `<g data-semantic-role="edge">` with `<path>`

SVG input:
```xml
<g id="edge-user-to-api" data-semantic-role="edge"
   data-from="node-user" data-to="node-api-gateway">
  <path d="M 370 260 L 670 410" stroke="#64748b" stroke-width="3"
        fill="none" marker-end="url(#arrow-end)" />
</g>
```

Excalidraw output:
```json
{
  "id": "edge-user-to-api",
  "type": "arrow",
  "x": 370,
  "y": 260,
  "width": 300,
  "height": 150,
  "points": [[0, 0], [300, 150]],
  "strokeColor": "#64748b",
  "strokeWidth": 3,
  "startBinding": {
    "elementId": "node-user",
    "focus": 0,
    "gap": 8
  },
  "endBinding": {
    "elementId": "node-api-gateway",
    "focus": 0,
    "gap": 8
  },
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

**Rules:**
- The first point of the path `d` attribute gives `x`, `y`.
- `points` is a list of `[dx, dy]` offsets from the first point.
- `data-from` maps to `startBinding.elementId`.
- `data-to` maps to `endBinding.elementId`.
- `marker-end` present means `endArrowhead: "arrow"`.
- `marker-start` present means `startArrowhead: "arrow"`.
- Neither marker means both arrowheads are `null` (plain line).
- `focus` defaults to `0` (centered). `gap` defaults to `8`.

### Labels: `<g data-semantic-role="label">` with `<text>`

SVG input:
```xml
<g id="label-api-gateway" data-semantic-role="label">
  <rect x="710" y="430" width="180" height="24" rx="4"
        fill="#ffffff" stroke="#cbd5e1" />
  <text x="800" y="446" text-anchor="middle" font-size="14"
        fill="#1e293b">API Gateway</text>
</g>
```

Excalidraw output:
```json
{
  "id": "label-api-gateway",
  "type": "text",
  "x": 710,
  "y": 430,
  "width": 180,
  "height": 24,
  "text": "API Gateway",
  "fontSize": 14,
  "fontFamily": 1,
  "textAlign": "center",
  "verticalAlign": "middle",
  "containerId": "node-api-gateway",
  "strokeColor": "#1e293b"
}
```

**Rules:**
- If the label is nested inside a node group, `containerId` is set to that
  node's ID.
- If the label is nested inside an edge group, `containerId` is `null` and the
  label is positioned independently.
- `text-anchor="middle"` maps to `textAlign: "center"`.
- `font-size` maps to `fontSize` (strip units).
- `fontFamily` is always `1` (Virgil/hand-drawn) for Excalidraw.
- The `<rect>` background inside a label group is discarded -- Excalidraw
  handles text backgrounds via `containerId` binding.

---

## 2. Color Mapping

SVG hex colors map directly to Excalidraw color properties:

| SVG Attribute | Excalidraw Property   | Notes                                    |
|---------------|-----------------------|------------------------------------------|
| `fill`        | `backgroundColor`     | On shapes. `"none"` maps to `"transparent"` |
| `stroke`      | `strokeColor`         | On shapes and arrows                     |
| `fill` (text) | `strokeColor`         | Text color uses `strokeColor` in Excalidraw |

Tailwind palette hex values pass through unchanged. No color remapping is
performed.

---

## 3. Coordinate Mapping

SVG uses absolute coordinates with optional `transform="translate(x, y)"` on
nested `<g>` groups.

**Rules:**
- If a shape is inside a `<g transform="translate(tx, ty)">`, add `tx` to the
  shape's `x` and `ty` to the shape's `y`.
- Nested transforms stack: apply all ancestor transforms cumulatively.
- Excalidraw coordinates are absolute (no transform groups).

Example:
```xml
<g id="node-billing" data-semantic-role="node" ...>
  <g transform="translate(140, 600)">
    <rect width="220" height="80" rx="12" fill="#fdf2f8" stroke="#f472b6" />
  </g>
</g>
```
The `<rect>` has implicit `x=0, y=0`. After applying the transform:
Excalidraw `x = 0 + 140 = 140`, `y = 0 + 600 = 600`.

---

## 4. `.excalidraw.md` File Format

The output file is an Obsidian-compatible Excalidraw markdown file with three
sections:

### Frontmatter

```yaml
---
excalidraw-plugin: parsed
tags:
  - excalidraw
excalidraw-open-md: true
---
```

### Text Elements Section

Lists all text content for searchability within Obsidian:

```markdown
%%
# Text Elements
API Gateway ^label-api-gateway
Web Client ^label-web-client
Token Translation ^label-token-translation
%%
```

Each line: `{text content} ^{element-id}`

### Drawing JSON Block

The full Excalidraw scene JSON wrapped in a code block:

````markdown
%%
# Drawing
```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin",
  "elements": [ ... ],
  "appState": {
    "theme": "light",
    "viewBackgroundColor": "#fafafa",
    "gridSize": null
  },
  "files": {}
}
```
%%
````

---

## 5. ID Generation Strategy

The SVG group `id` attribute is used directly as the Excalidraw element ID:

- `<g id="node-api-gateway">` becomes Excalidraw element `"id": "node-api-gateway"`
- `<g id="edge-user-to-api">` becomes Excalidraw element `"id": "edge-user-to-api"`
- `<g id="label-api-gateway">` becomes Excalidraw element `"id": "label-api-gateway"`

This 1:1 mapping ensures traceability between SVG source and Excalidraw output,
and allows the quality gate validators to cross-reference elements by ID.

IDs must be unique within a single SVG. The transform will fail if duplicate IDs
are detected.

---

## 6. Elements Not Mapped

The following SVG elements are consumed for metadata but do not produce
Excalidraw elements:

- `<!-- DIAGRAM_TYPE: ... -->` -- used for classification only
- `<!-- TOPOLOGY: ... -->` -- used for validation only
- `<desc>` -- used for LLM context only
- `<defs>` and `<marker>` -- arrowhead style is inferred from `marker-end`/
  `marker-start` attributes on paths
- `<rect>` inside a `<g data-semantic-role="label">` -- background rectangles
  for labels are discarded (Excalidraw handles this via `containerId`)
- `data-upstream`/`data-downstream` -- graph adjacency is reconstructed from
  `data-from`/`data-to` on edges
