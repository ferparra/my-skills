# Excalidraw Schema Reference

## File Format

`.excalidraw.md` files follow this structure:

### 1. Frontmatter
```yaml
---
tags: [excalidraw]
excalidraw-plugin: parsed
---
```

**Required**:
- `excalidraw-plugin: parsed` — indicates parsed format (vs raw)
- `tags` must include `excalidraw`

### 2. Warning Banner
```
==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==
```

### 3. Excalidraw Data Section
```markdown
# Excalidraw Data

## Text Elements
<text content> ^<element_id>
...

%%
## Drawing
```json
{...}
```
%%
```

## Drawing JSON Schema

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/X.XX.X",
  "elements": [...],
  "appState": {
    "theme": "light",
    "viewBackgroundColor": "#ffffff",
    "gridSize": null
  }
}
```

### Element Types

#### Common Properties (all elements)
- `id`: unique string identifier
- `type`: element type (rectangle, text, arrow, etc.)
- `x`, `y`: position
- `width`, `height`: dimensions
- `angle`: rotation in radians
- `strokeColor`, `backgroundColor`: hex colors or "transparent"
- `fillStyle`: "solid", "hachure", "cross-hatch"
- `strokeWidth`: number
- `strokeStyle`: "solid", "dashed", "dotted"
- `roughness`: 0 (smooth) to 2 (rough)
- `opacity`: 0-100
- `seed`, `version`, `versionNonce`: for deterministic rendering
- `isDeleted`: boolean
- `groupIds`: array of group IDs
- `frameId`: parent frame ID or null
- `boundElements`: array of `{id, type}` refs to bound elements
- `link`: URL or null
- `locked`: boolean
- `roundness`: `{type: 2}` or null

#### Text Element
Additional properties:
- `text`, `originalText`: text content
- `fontSize`: number
- `fontFamily`: 1 (Virgil), 5 (normal)
- `textAlign`: "left", "center", "right"
- `verticalAlign`: "top", "middle", "bottom"
- `lineHeight`: number
- `baseline`: number (deprecated)
- `containerId`: ID of container element or null

#### Arrow Element
Additional properties:
- `points`: array of `[x, y]` coordinates
- `startBinding`, `endBinding`: `{elementId, focus, gap}` or null
- `startArrowhead`, `endArrowhead`: "arrow" or null
- `lastCommittedPoint`: `[x, y]` or null

#### Shape Elements (rectangle, ellipse, diamond, frame)
No additional required properties beyond common.

#### Line/Freedraw Elements
Additional properties:
- `points`: array of `[x, y]` coordinates
- `pressures`: array (freedraw only)

#### Image Element
Additional properties:
- `fileId`: string or null
- `status`: string or null
- `scale`: `[x, y]` or null

## Anti-Patterns Detected

### Errors (fail validation)

1. **Duplicate IDs**: Multiple elements share the same `id`
2. **Broken text binding**: Text element's `containerId` references non-existent element
3. **Broken arrow binding**: Arrow's `startBinding`/`endBinding.elementId` references non-existent element
4. **Bidirectional mismatch**: Container lists text in `boundElements` but text's `containerId` doesn't point back (or vice versa)

### Warnings (non-fatal)

5. **Zero dimensions**: `width=0` or `height=0` on shapes (not lines/arrows)
6. **text/originalText drift**: `text` differs from `originalText` (may be intentional line wrapping)
7. **Invalid colors**: `strokeColor`/`backgroundColor` not matching `#RRGGBB` or `transparent`
8. **Orphaned group refs**: `groupId` appearing on only one element
9. **Text Elements sync**: Markdown `## Text Elements` section out of sync with actual text elements in JSON

## Binding Rules

### Text-Container Binding
When text is bound inside a container (rectangle, ellipse, etc.):

Container must have:
```json
{
  "id": "container_id",
  "boundElements": [
    {"id": "text_id", "type": "text"}
  ]
}
```

Text must have:
```json
{
  "id": "text_id",
  "containerId": "container_id"
}
```

Both references must exist and point to each other.

### Arrow Binding
When arrow connects to an element:

```json
{
  "type": "arrow",
  "startBinding": {
    "elementId": "target_element_id",
    "focus": 0.0,
    "gap": 10.0
  }
}
```

The `elementId` must reference an existing element.

## Compressed JSON

The plugin may store drawing data as `compressed-json`:

````
```compressed-json
<base64-encoded compressed JSON>
```
````

**Current limitation**: This validator does not yet support the compressed-json format. To validate compressed drawings:

1. Open the file in Obsidian
2. Use command palette: "Decompress current Excalidraw file"
3. Run validation on the decompressed file

The compressed format uses pako (JavaScript zlib port) with custom settings that differ from Python's zlib. Future versions may add support.
