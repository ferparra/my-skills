---
name: excalidraw-hub-and-spoke-from-script
version: 1.1.0
dependencies: []
pipeline: {}
description: >
  Programmatically generate a hub-and-spoke Excalidraw diagram as a valid
  .excalidraw.md file with structural and geometric validation.
  Produces a clean hub (central ellipse) connected by arrows to N peripheral
  spokes. No frames — frames cause false-positive overlap/spacing warnings.
triggers:
  - "hub and spoke diagram"
  - "generate excalidraw diagram"
  - "hub-and-spoke from script"
---

# Generate Hub-and-Spoke Excalidraw Diagram from Script

## When to Use

You need a hub-and-spoke diagram (central coordinator + peripheral elements) for
an Obsidian vault. Use this instead of opening Excalidraw manually.

## Overview

1. Write a Python script that generates hub + spokes + arrows as JSON
2. Write the `.excalidraw.md` file in Obsidian's format
3. Run structural validation
4. Run geometric validation (geometric checks pass without a render)
5. Copy to vault and open in Obsidian to verify visually

## Excalidraw File Format

The Obsidian Excalidraw plugin stores drawings in this format:

```markdown
---
tags: [excalidraw]
excalidraw-plugin: parsed
---

==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==

# Excalidraw Data

## Text Elements
<bound_text> ^<element_id>
... (one per line, bound text only — free-floating text NOT listed here)

%%
## Drawing
```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/2.0.0",
  "elements": [ ... ],
  "appState": { "theme": "light", "viewBackgroundColor": "#ffffff", "gridSize": null }
}
```
%%
```

## Element Schema (Complete Fields)

Every element requires ALL of these fields — missing any causes structural validation errors:

```python
COMMON_FIELDS = {
    "id": "...", "type": "...",  # ellipse, text, arrow, rectangle, diamond, line
    "x": float, "y": float, "width": float, "height": float,
    "angle": 0,                    # rotation in radians (always 0)
    "strokeColor": "#1E1E1E",
    "backgroundColor": "#E8E8E8",
    "fillStyle": "solid",          # solid | Hachure | Cross-Hatch
    "strokeWidth": 2,
    "strokeStyle": "solid",        # solid | dashed | dotted
    "roughness": 0,                # 0 = clean, 1+ = sketchy
    "opacity": 100,
    "seed": int, "version": 1, "versionNonce": int,
    "isDeleted": False,
    "groupIds": [],
    "frameId": None,               # NEVER assign to a frame — causes false positive warnings
    "boundElements": None,          # list of {"id": "...", "type": "text"} for bound text
    "link": None,
    "locked": False,
    "roundness": None,
}
```

## Text Element Additional Fields

**Bound text** (inside a container):
```python
{
    **COMMON_FIELDS,
    "type": "text",
    "text": "Label",
    "originalText": "Label",
    "fontSize": 20,
    "fontFamily": 3,                # 3 = monospace (Inter/sans)
    "textAlign": "center",
    "verticalAlign": "middle",
    "lineHeight": 1.25,
    "baseline": 18,                # fontSize * 0.9 (approximate)
    "containerId": "<parent_element_id>",  # NOT None — binds text to container
}
```

**Free-floating text** (no container):
- `containerId`: `None`
- `boundElements`: `None`
- Position with `x`, `y` directly

## Arrow Element Additional Fields

```python
{
    **COMMON_FIELDS,
    "type": "arrow",
    "points": [[0, 0], [dx, dy]],   # relative to arrow's x,y top-left
    "lastCommittedPoint": None,
    "startBinding": {"elementId": "<source_id>", "focus": 0, "gap": 0},
    "endBinding": {"elementId": "<target_id>", "focus": 0, "gap": 0},
    "startArrowhead": None,
    "endArrowhead": "arrow",        # arrow, triangle, dot, etc.
    "tailBezierPort": None,
    "headBezierPort": None,
}
```

## Arrow Coordinate Math

Arrow `x,y` is the top-left of the bounding box containing both endpoints.
Arrow `width,height` is the span of the arrow.

```python
# For an arrow from spoke center toward hub center:
dx = hub_cx - spoke_cx
dy = hub_cy - spoke_cy
dist = sqrt(dx**2 + dy**2)
nx = dx / dist; ny = dy / dist   # unit vector

# Start: edge of spoke ellipse
start_x = spoke_cx + nx * (spoke_w / 2)
start_y = spoke_cy + ny * (spoke_h / 2)
# End: edge of hub ellipse
end_x = hub_cx - nx * (hub_w / 2)
end_y = hub_cy - ny * (hub_h / 2)

# Arrow bbox top-left
arrow_x = min(start_x, end_x)
arrow_y = min(start_y, end_y)

# points relative to arrow x,y
points = [[start_x - arrow_x, start_y - arrow_y],
          [end_x - arrow_x, end_y - arrow_y]]
```

## Text Overflow Prevention

The validator checks `text_element.width` vs container's inner width (container width
minus padding). The text element's `width` field IS the text width — the validator
measures text against the element's own width field, not the container.

**Rule**: Set `text.width = container_width - (2 * desired_padding)` and ensure
`text.width >= actual_text_width_pixels`.

At fontSize=14 and fontFamily=3 (monospace):
- "Services" ≈ 126px → needs container with element width ≥ 130px
- "Analytics" ≈ 144px → needs container with element width ≥ 148px

Safe padding: `container_width - 20` for the text element width field.
Then add 10px to `x` offset for actual text position inside container.

## NO Frames

**Never wrap elements in a frame.** Frames cause:
- 100% overlap false positives (frame bbox encloses all children)
- Spacing CV degradation (all children report 0px gap to frame)
- "very close" warnings

Use free-floating labels above the hub instead.

## Workflow

### 1. Generate the file

```python
import json, uuid

def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

hub_x, hub_y = 400, 290
hub_w, hub_h = 200, 120
hub_cx, hub_cy = hub_x + hub_w/2, hub_y + hub_h/2

spoke_w, spoke_h = 170, 80
gap = 200
spoke_positions = [
    ("top",    hub_cx - spoke_w/2,  hub_y - gap - spoke_h),
    ("right",  hub_x + hub_w + gap, hub_cy - spoke_h/2),
    ("bottom", hub_cx - spoke_w/2,  hub_y + hub_h + gap),
    ("left",   hub_x - gap - spoke_w, hub_cy - spoke_h/2),
]
spoke_labels = ["Services", "Storage", "Analytics", "Clients"]
spoke_colors = ["#9966FF", "#3399FF", "#00CC66", "#FFB366"]

elements = []
hub_id, hub_text_id = uid("hub"), uid("hub_text")
spoke_ids = [uid(f"spoke_{i}") for i in range(4)]
spoke_text_ids = [uid(f"spoke_text_{i}") for i in range(4)]
arrow_ids = [uid(f"arrow_{i}") for i in range(4)]

# Hub ellipse + hub text
elements.append({**COMMON, "id": hub_id, "type": "ellipse", ...})
elements.append({**BOUND_TEXT, "id": hub_text_id, "containerId": hub_id, ...})

# Spokes
for i, (name, sx, sy) in enumerate(spoke_positions):
    scx, scy = sx + spoke_w/2, sy + spoke_h/2
    elements.append({**COMMON, "id": spoke_ids[i], "type": "ellipse",
                     "backgroundColor": spoke_colors[i], ...})
    elements.append({**BOUND_TEXT, "id": spoke_text_ids[i],
                     "containerId": spoke_ids[i], "text": spoke_labels[i], ...})

# Arrows
for i, (name, sx, sy) in enumerate(spoke_positions):
    # (use arrow math from section above)
    elements.append({**ARROW_FIELDS, ...})

# Text Elements section (bound text only)
bound_lines = [f"{spoke_labels[i]} ^{spoke_text_ids[i]}" for i in range(4)]
bound_lines.append(f"API Gateway ^{hub_text_id}")

drawing = {"type": "excalidraw", "version": 2,
           "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/2.0.0",
           "elements": elements,
           "appState": {"theme": "light", "viewBackgroundColor": "#ffffff", "gridSize": None}}

# Assemble markdown
lines = ["---", "tags: [excalidraw]", "excalidraw-plugin: parsed", "---", "",
         "==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==",
         "", "# Excalidraw Data", "", "## Text Elements",
         "\n".join(bound_lines), "", "%%", "## Drawing", "```json",
         json.dumps(drawing, indent=2), "```", "%%"]

content = "\n".join(lines)
Path("vault/Excalidraw/hub-and-spoke.excalidraw.md").write_text(content)
```

### 2. Validate structurally

```bash
cd ~/my-skills
uvx --from python --with pydantic --with pyyaml python \
  obsidian-plugin/skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py \
  --glob "**/hub-and-spoke*" --mode check
```

Expected: `{"ok": true, ... "errors": [], "warnings": []}`

### 3. Validate geometrically

```bash
cd ~/my-skills
uvx --from python --with pydantic --with pyyaml --with playwright python \
  obsidian-plugin/skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --glob "**/hub-and-spoke*" --mode check
```

Expected: `{"ok": true, ... "errors": [], "warnings": []}`

### 4. Copy to vault and open

```bash
cp vault/Excalidraw/hub-and-spoke.excalidraw.md ~/my-vault/Excalidraw/
obsidian open vault=my-vault "path=Excalidraw/hub-and-spoke.excalidraw.md"
```

## Pitfalls

1. **Missing fields** → structural validation fails with "Field required"
2. **Frame wrapper** → causes false positive overlap/spacing warnings
3. **Text overflow** → validator rejects if text.width > container available space.
   Always use wider containers than you think needed (170px spoke for 14px font labels)
4. **Arrow coordinates wrong** → arrow endpoint errors. Always compute from ellipse-edge math
5. **Free-floating text in ## Text Elements** → causes "text in JSON but not in ## Text Elements" warning.
   Only list bound text in ## Text Elements section
6. **fontFamily: 1** (default) → validator may flag this. Use `fontFamily: 3` for monospace

## Render to PNG

### Python + Playwright (recommended)

The working pipeline uses the render script with esm.sh CDN. The script handles decompression internally.

**One-time setup:**
```bash
python3 -m playwright install chromium
cd ~/.hermes/skills/obsidian/obsidian-excalidraw-file-generation && npm install lz-string
```

**Render:**
```bash
python3 ~/.hermes/skills/obsidian/obsidian-excalidraw-file-generation/references/render_excalidraw.py \
  ~/my-vault/Excalidraw/your-diagram.excalidraw.md --output /tmp/output.png --scale 2
```

The render script:
- Loads Excalidraw via `https://esm.sh/@excalidraw/excalidraw?bundle` (browser-compatible ESM)
- Handles both plain ` ```json ` and ` ```compressed-json ` blocks
- Decompresses `compressed-json` via LZString (Node.js, with lz-string module bundled in skill/node_modules)
- Uses Playwright to render and screenshot the SVG

**Why bun-based approaches failed:**
- `@excalidraw/excalidraw` npm bundle (dist/prod/index.js) uses webpack-transformed import syntax that Chromium's V8 cannot parse as native ESM ("Unexpected token '*'")
- bun's ESM closure capture causes `resolve()` to return `undefined` for closure parameters, breaking local HTTP servers
- The esm.sh CDN bundle works because it serves a properly formatted ESM output

### Quick PNG alternative (no setup)

1. Open the file in Obsidian (Excalidraw view)
2. Use `obsidian dev:screenshot path=/tmp/output.png`
