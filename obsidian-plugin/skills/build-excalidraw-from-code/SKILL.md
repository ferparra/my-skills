---
name: build-excalidraw-from-code
description: Create validated .excalidraw.md files programmatically from Python — no browser or live canvas required. Generates the correct Obsidian Excalidraw plugin format (frontmatter, text elements, JSON block with code fence) and validates against the obsidian-excalidraw-drawing-manager schema.
triggers:
  - generate an excalidraw diagram from python
  - build diagram file programmatically
  - create .excalidraw.md from code
  - excalidraw diagram without browser
  - write excalidraw json to file
tags:
  - obsidian
  - excalidraw
  - diagram-generation
  - python
---

# Build Excalidraw Diagrams Programmatically

Create validated `.excalidraw.md` files directly from Python code, without needing the Obsidian Excalidraw plugin UI or the live canvas.

## When to Use

- Build diagram files from code-based generation (AI agents, scripts, templates)
- No browser/canvas required — pure file I/O
- Output must pass `obsidian-excalidraw-drawing-manager` validation
- Diagram lives in Obsidian vault and renders in Excalidraw view

## Critical Rule: Validate Frequently

Build and validate iteratively — validate after every 2-3 elements. Never build a large diagram and validate only at the end. If there's an error, you lose the entire build. Small iterations catch problems early.

## Required Format

`.excalidraw.md` files have 5 parts:

```
---
tags: [excalidraw]
excalidraw-plugin: parsed
---

==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==

# Excalidraw Data

## Text Elements
<text content> ^<element_id>
...

%%
## Drawing
```json
{ "type": "excalidraw", "version": 2, "elements": [...], "appState": {...} }
```
%%
```

**Critical:** The JSON block MUST be wrapped in ```json ... ``` fence. Without this fence the validator's regex `r"```(compressed-)?json\s*(.*?)\n```"` fails to match.

## Python Generation Template

```python
import json, random, hashlib

_counter = [0]
def uid(prefix):
    """Globally unique ID. Prefix is truncated to 4 chars."""
    _counter[0] += 1
    h = hashlib.md5(f"{prefix}_{_counter[0]}".encode()).hexdigest()[:12]
    return f"{prefix[:4]}_{h}"

def make_rect(rid, x, y, w, h, fill="#f0f0f0", stroke="#333333"):
    return {
        "id": rid, "type": "rectangle", "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": fill, "fillStyle": "solid",
        "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0,
        "opacity": 100, "angle": 0, "seed": random.randint(1, 9999999),
        "version": 1, "versionNonce": 0, "isDeleted": False,
        "groupIds": [], "frameId": None, "roundness": {"type": 2},
        "boundElements": [], "link": None, "locked": False
    }

def make_text(tid, x, y, w, h, label, font_size=14, color="#000000", align="center"):
    return {
        "id": tid, "type": "text", "x": x, "y": y, "width": w, "height": h,
        "text": label, "originalText": label,
        "fontSize": font_size, "fontFamily": 5, "textAlign": align, "verticalAlign": "middle",
        "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
        "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0,
        "opacity": 100, "angle": 0, "seed": random.randint(1, 9999999),
        "version": 1, "versionNonce": 0, "isDeleted": False,
        "groupIds": [], "frameId": None, "boundElements": [], "link": None, "locked": False,
        "lineHeight": 1.25
    }

def make_arrow(aid, sx, sy, ex, ey, sb=None, eb=None, color="#4a4a4a"):
    return {
        "id": aid, "type": "arrow", "x": sx, "y": sy, "width": 0, "height": 0,
        "points": [[0, 0], [ex - sx, ey - sy]], "lastCommittedPoint": None,
        "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
        "strokeWidth": 1.5, "strokeStyle": "solid", "roughness": 0,
        "opacity": 100, "angle": 0, "seed": random.randint(1, 9999999),
        "version": 1, "versionNonce": 0, "isDeleted": False,
        "groupIds": [], "frameId": None, "roundness": {"type": 2},
        "boundElements": [], "link": None, "locked": False,
        "startBinding": sb, "endBinding": eb,
        "startArrowhead": None, "endArrowhead": "arrow"
    }

def bind(container, text_el):
    """Bind text inside a rectangle container. Call AFTER both elements exist."""
    container["boundElements"].append({"id": text_el["id"], "type": "text"})
    text_el["containerId"] = container["id"]

# Build elements list
elements = []

def node(col_x, row_y, label, fill, stroke, font_size=13):
    """Create a rounded rectangle with centered text inside."""
    eid = uid("box")
    tid = uid("txt")
    r = make_rect(eid, col_x, row_y, LABEL_W, NODE_H, fill, stroke)
    t = make_text(tid, col_x+6, row_y+6, LABEL_W-12, NODE_H-12, label,
                   font_size=font_size, color=stroke)
    bind(r, t)
    elements.extend([r, t])
    return eid

# IMPORTANT: never reuse IDs. uid() with counter guarantees uniqueness.

# Build JSON payload
json_payload = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/2.2.22",
    "elements": elements,
    "appState": {
        "theme": "light",
        "viewBackgroundColor": "#ffffff",
        "gridSize": None,
        "collab": {"show": False}
    }
}

# Text section: one line per text element
text_section_lines = []
for e in elements:
    if e["type"] == "text":
        text_section_lines.append(f"{e['text']} ^${e['id']}")
text_section = "\n".join(text_section_lines)

# Assemble file
json_str = json.dumps(json_payload, indent=2)
lines = [
    "---",
    "tags: [excalidraw]",
    "excalidraw-plugin: parsed",
    "---",
    "",
    "==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==",
    "",
    "# Excalidraw Data",
    "",
    "## Text Elements",
    text_section,
    "",
    "%%",
    "## Drawing",
    "```json",          # <-- CRITICAL: code fence wrapper
    json_str,
    "```",
    "%%",
]
content = "\n".join(lines)

with open(out_path, "w", encoding="utf-8") as f:
    f.write(content)
```

## Validation (Structural)

**Correct path** (skills live under `obsidian-plugin/skills/` in the repo):
```bash
cd ~/my-skills
uvx --from python --with pydantic --with pyyaml \
  python obsidian-plugin/skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py \
  --glob "**/your_diagram.excalidraw.md" --mode check
```

Pass criteria: `"ok": true`, `"errors": []`.

## Validation (Visual Geometric)

After structural validation passes, run the geometric checks (no PNG needed):
```bash
cd ~/my-skills
uvx --from python --with pydantic --with pyyaml --with playwright \
  python obsidian-plugin/skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --glob "**/your_diagram.excalidraw.md" --mode check
```

This checks: overlap (>15%), spacing consistency (CV<0.5), text overflow, arrow endpoint accuracy (15px), composition balance. Zero errors = diagram is geometrically sound.

**Render to PNG** (`--render`) is separate — it uses Playwright to generate a screenshot. This step is optional for validation; geometric checks pass/fail independently.

## Render to PNG — Known Limitation

The visual validator's `--render` flag uses `esm.sh` CDN to load Excalidraw's JS bundle. If network access is restricted or the CDN is unreachable, `Page.wait_for_function` times out and render fails with:
```
"Playwright error: Page.wait_for_function: Timeout 10000ms exceeded."
```

This is an **environment limitation**, not a diagram error. Geometric checks still pass.

**Workaround options**:
1. **Obsidian screenshot** (most reliable): Open the file in Obsidian, then `obsidian dev:screenshot path=/tmp/output.png`. The file must be copied to a vault Obsidian has open, and the Obsidian window must be focused.
2. **Local npm bundle**: `npm install @excalidraw/excalidraw@0.17.0` in a temp dir, serve over a local HTTP server, use Playwright with a custom HTML template loading the local bundle. `file://` protocol blocks ES module imports.
3. **Cloud Playwright**: Use a CI environment with unrestricted network access.

## Open in Obsidian

```bash
obsidian tab:open path="Excalidraw/your_diagram.excalidraw.md" view=excalidraw vault=my-vault
```

Requires Obsidian app to be running with the vault open. Does not work over Tailscale/gateway — must be local.

## Key Constraints
- All element IDs must be unique within the file
- Arrow `startBinding`/`endBinding.elementId` must reference real elements
- Text bound in container: container needs `boundElements: [{id, type}]`, text needs `containerId: <id>`
- `fontFamily: 3` = monospace (what the visual validator checks for as "clean/technical" font). `fontFamily: 1` = hand-drawn Virgil. `fontFamily: 5` may render but is non-standard.
- `roundness: {"type": 2}` = rounded corners on rectangles. For ellipses, `roundness: null` (not applicable — ellipses are already curved).

## Pitfalls Discovered Through Trial and Error

### 1. Validate OFTEN — every 2-3 elements
Do NOT build a large diagram and validate at the end. If something is wrong, you have to discard the whole thing. Build iteratively: add a few elements → validate → repeat.

### 2. Missing code fence (validation fails)
The validator uses `r"```(compressed-)?json\s*(.*?)\n```"`. Without the ```json fence, `extract_excalidraw_json` returns None and validation fails with "Could not find JSON or compressed-json code block in ## Drawing section".

### 3. Duplicate element IDs
MD5-hash-based IDs like `uid(label)` can collide when the same label is used multiple times (hash is not unique enough with only 12 chars from a short prefix). Fix: use a global integer counter appended to the input string — guarantees uniqueness.

### 4. Arrow binding references must exist
`startBinding.elementId` and `endBinding.elementId` must reference actual element IDs in the `elements` array. If they reference a non-existent ID, validation will catch it as a broken arrow binding error.

### 5. Multiline text IDs
Text elements bound inside containers must have `containerId` set. Free-floating text should have `containerId: None`.

### 6. Text elements with newlines in labels
Role labels like `"Knowledge\nLayer"` produce multiline entries in `## Text Elements`. The regex `r"^(.+?)\s+\^([a-zA-Z0-9_-]+)\s*$"` only matches single-line entries. These appear as warnings in validation but are non-fatal.
