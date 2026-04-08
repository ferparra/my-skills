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
        "fontSize": font_size, "fontFamily": 3, "textAlign": align, "verticalAlign": "middle",
        "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
        "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0,
        "opacity": 100, "angle": 0, "seed": random.randint(1, 9999999),
        "version": 1, "versionNonce": 0, "isDeleted": False,
        "groupIds": [], "frameId": None, "boundElements": [], "link": None, "locked": False,
        "lineHeight": 1.25
    }

def make_binding(element_id, focus=0, gap=0):
    """Create a proper Binding object for arrow endpoints."""
    return {"elementId": element_id, "focus": focus, "gap": gap}

def make_arrow(aid, sx, sy, ex, ey, sb=None, eb=None, color="#4a4a4a"):
    """Create an arrow. sb/eb should be Binding objects from make_binding(), or None."""
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

def bind_box_arrow(box_id, arrow_el, end="end"):
    """Attach an arrow to a box container at the arrow's start or end point.
    Call AFTER the arrow element exists in elements list.
    end: "start" or "end" — which endpoint of the arrow to bind to the box.
    """
    binding = make_binding(box_id, focus=0, gap=0)
    if end == "start":
        arrow_el["startBinding"] = binding
    else:
        arrow_el["endBinding"] = binding

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
# Format: "<text> ^<id>" — NO $ before the caret, NO id- prefix
# Wrong:  "text ^$tx_abc123"  or  "text ^id-tx_abc123"
# Right:  "text ^tx_abc123"
text_section_lines = []
for e in elements:
    if e["type"] == "text":
        safe_text = e["text"].replace("\n", " ")  # collapse newlines for single-line regex
        text_section_lines.append(f"{safe_text} ^{e['id']}")
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

**RECOMMENDED: SVG rendering via qlmanage** (macOS only, no network needed):
1. Generate a self-contained SVG from the Excalidraw JSON using Python (see template below)
2. Convert SVG → PNG with `qlmanage -t -s WIDTH -o /tmp output.svg`
3. This is fast (~1s), deterministic, and requires no network or browser

```python
import json, html

# Read Excalidraw JSON from .excalidraw.md file
path = "/path/to/diagram.excalidraw.md"
with open(path) as f:
    raw = f.read()

# Extract JSON from code block
m = re.search(r'```json\s*(\{.*?\})\s*```', raw, re.DOTALL)
data = json.loads(m.group(1)) if m else json.loads(raw)
elements = data.get("elements", [])

boxes = {e["id"]: e for e in elements if e.get("type") == "rectangle"}
arrows = [e for e in elements if e.get("type") == "arrow"]

# Calculate bounds
all_x, all_y = [], []
for el in elements:
    if el.get("x") is not None:
        all_x.append(el["x"]); all_y.append(el["y"])
        if el.get("width"): all_x.append(el["x"]+el["width"])
        if el.get("height"): all_y.append(el["y"]+el["height"])

min_x,max_x = min(all_x),max(all_x)
min_y,max_y = min(all_y),max(all_y)
PAD=80
OX=-min_x+PAD; OY=-min_y+PAD
W=max_x-min_x+PAD*2; H=max_y-min_y+PAD*2

BF,BS,TC,AC = "#dbeafe","#2563eb","#1e40af","#475569"
AH=8; AG=20

svg=[]
svg.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="#f8fafc"/>' % (W,H,W,H))

def bx(b): return b["x"]+OX
def by(b): return b["y"]+OY
def bw(b): return b.get("width",160)
def bh(b): return b.get("height",50)
def bcx(b): return bx(b)+bw(b)/2
def bcy(b): return by(b)+bh(b)/2
def btop(b): return (bcx(b), by(b))
def bbottom(b): return (bcx(b), by(b)+bh(b))

for box in boxes.values():
    x,y,w,h,c = bx(box),by(box),bw(box),bh(box),bcx(box)
    txt=box.get("label",{}).get("text","")
    svg.append('<rect x="%.0f" y="%.0f" width="%d" height="%d" rx="5" fill="%s" stroke="%s" stroke-width="1.5"/>' % (x,y,w,h,BF,BS))
    svg.append('<text x="%.0f" y="%.0f" text-anchor="middle" dominant-baseline="central" font-family="system-ui,sans-serif" font-size="11" fill="%s">%s</text>' % (c,bcy(box),TC,html.escape(txt)))

for arrow in arrows:
    sc = arrow.get("startBinding",{}).get("elementId")
    ec = arrow.get("endBinding",{}).get("elementId")
    if sc not in boxes or ec not in boxes: continue
    sb,eb = boxes[sc], boxes[ec]
    sx,sy = bbottom(sb)
    ex,ey = btop(eb)

    if ey > sy:
        my=sy+AG; shaft_end=ey-AH
        d="M %.0f %.0f L %.0f %.0f L %.0f %.0f L %.0f %.0f" % (sx,sy,sx,my,ex,my,ex,shaft_end)
        rot=""
    elif ey < sy:
        my=sy-AG; shaft_end=ey+AH
        d="M %.0f %.0f L %.0f %.0f L %.0f %.0f L %.0f %.0f" % (sx,sy,sx,my,ex,my,ex,shaft_end)
        rot="rotate(180 %.0f %.0f)" % (ex,ey)
    else:
        dirn=-1 if ex<sx else 1; shaft_end_x=ex-dirn*AH
        d="M %.0f %.0f L %.0f %.0f" % (sx,sy,shaft_end_x,ey)
        rot="rotate(%d %.0f %.0f)" % (90 if dirn<0 else -90, ex, ey)

    svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.5" stroke-linejoin="round"/>' % (d,AC))
    transform = 'transform="translate(%.0f,%.0f)%s"' % (ex,ey,(" "+rot if rot else ""))
    svg.append('<polygon points="0,%.0f %.0f,0 0,%.0f" fill="%s" %s/>' % (-AH/2,AH,AH/2,AC,transform))

svg.append('</svg>')
content = "\n".join(svg)
with open("/tmp/diagram.svg","w") as f: f.write(content)
# Then: qlmanage -t -s 1200 -o /tmp /tmp/diagram.svg
```

**Other options**:
1. **Obsidian screenshot** (most reliable for full fidelity): Open the file in Obsidian, then `obsidian dev:screenshot path=/tmp/output.png`. The file must be copied to a vault Obsidian has open, and the Obsidian window must be focused.
2. **Local npm bundle**: `npm install @excalidraw/excalidraw@0.17.0` in a temp dir, serve over a local HTTP server, use Playwright with a custom HTML template loading the local bundle. `file://` protocol blocks ES module imports.
3. **Cloud Playwright**: Use a CI environment with unrestricted network access.

## Open in Obsidian

```bash
obsidian tab:open path="Excalidraw/your_diagram.excalidraw.md" view=excalidraw vault=my-vault
```

Requires Obsidian app to be running with the vault open. Does not work over Tailscale/gateway — must be local.

## Key Constraints
- All element IDs must be unique within the file
- Arrow `startBinding`/`endBinding` must be `Binding` objects: `{"elementId": "...", "focus": 0, "gap": 0}`
  - `startBinding.elementId` and `endBinding.elementId` must reference real element IDs in the elements array
  - The `elementId` in a Binding references the container box, not the text label inside it
  - Do NOT use `start.containerId` / `end.containerId` — that is a different format from a different library
  - Do NOT use `yHack` — it is not a valid Binding field
- Text bound in container: container needs `boundElements: [{id, type}]`, text needs `containerId: <id>`
- `fontFamily: 3` = monospace (what the visual validator checks for as "clean/technical" font). `fontFamily: 1` = hand-drawn Virgil. `fontFamily: 5` may render but is non-standard.
- `roundness: {"type": 2}` = rounded corners on rectangles. For ellipses, `roundness: null` (not applicable — ellipses are already curved).
- The Obsidian Excalidraw plugin uses a flat `elements` array at the top level of the JSON. Do NOT use a `sceneAndContainer` or `elementCollection` nested format — those are from different Excalidraw libraries and will not render in Obsidian.

## Two Excalidraw JSON Formats (Know Which You're Using)

**Obsidian plugin format** (what this skill generates — use this):
```json
{ "type": "excalidraw", "version": 2, "elements": [...], "appState": {...} }
```
Top-level keys: `type`, `version`, `source`, `elements` (flat array), `appState`.

**sceneAndContainer format** (NOT the Obsidian plugin — avoid this):
```json
{ "type": "excalidraw", "version": 2, "elementCollection": { "elements": [...] } }
```
This has `elementCollection.elements` nesting and uses `start.containerId` / `end.containerId` for arrow bindings. It comes from the Excalidraw `scene` data format and will NOT render properly in Obsidian's Excalidraw plugin view.

## Arrow Labels (Floating Midpoint Labels)

To add a label on an arrow's midpoint, create a floating text element positioned at the arrow's midpoint. The label is NOT bound to the arrow — it's a separate text element that visually overlaps the arrow path:

```python
def arrow_with_label(elements, sx, sy, ex, ey, color, label, label_offset_y=-22):
    """Arrow plus floating label at midpoint."""
    aid = uid("ar")
    arr = make_arrow(aid, sx, sy, ex, ey, color)
    elements.append(arr)
    mx = (sx + ex) // 2
    my = (sy + ey) // 2 + label_offset_y
    lid = uid("lbl")
    lbl = make_text(lid, mx - len(label)*4, my - 10, len(label)*8 + 16, 22,
                    label, font_size=11, color="#555555")
    elements.append(lbl)
    return aid, lid
```

Use `font_size=11` for arrow labels — smaller than node text (14) to avoid visual clutter.

## Geometric Layout Guidance

- **Complex diagrams (>3 levels, 30+ elements) become visually busy** — geometric validation passes, but readability degrades. Target 2–3 levels maximum for didactic diagrams.
- **Overlap warnings from radial arrow routing are inherent** — arrows from a central node to surrounding nodes cross through empty space between center and branches. These are warnings (not errors) and do not fail geometric validation.
- **Node sizing:** root/level-1 = RW=220,RH=70; level-2 = LW=200,LH=55; leaf = EW=180,EH=48
- **Horizontal spacing:** at least 60px gap between sibling nodes to avoid overlap warnings
- **Arrow endpoint tolerance:** validator allows 15px deviation — do not over-engineer anchor points

## Rendering & Image Analysis

**Playwright render** (via visual validator, outputs to `--output-dir`):
```bash
cd ~/my-skills
uvx --from python --with pydantic --with pyyaml --with playwright \
  python obsidian-plugin/skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py \
  --glob "**/your_diagram.excalidraw.md" --render --output-dir /tmp
```

**Image analysis via OpenRouter** (base64-encoded image to Gemini Flash):
```python
import json, os, base64, urllib.request
api_key = os.environ.get("OPENROUTER_API_KEY", "")
with open(os.path.expanduser("~/.hermes/.env")) as f:
    for line in f:
        if line.startswith("OPENROUTER_API_KEY="):
            api_key = line.split("=",1)[1].strip(); break
with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()
payload = {"model": "google/gemini-2.0-flash-001", "messages": [{"role": "user", "content": [
    {"type": "text", "text": "your question here"},
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
]}]}
req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as resp:
    print(json.loads(resp.read())["choices"][0]["message"]["content"])
```

**Open in Obsidian for live verification:**
```bash
obsidian tab:open "Excalidraw/your_diagram.excalidraw.md" view=excalidraw vault=my-vault
```
Note: Obsidian screenshot (`obsidian dev:screenshot`) requires the window to stay focused — notifications or focus loss produce blank screenshots. Use Playwright render for reliable captures.

## File Location Convention

**DIAGRAMS DO NOT GO IN my-skills.** The `~/my-skills` repository is reserved for skill code only. Diagram `.excalidraw.md` files belong in:
- `~/my-vault/Excalidraw/<descriptive-name>.excalidraw.md` — canonical location
- Local git checkpointing: commit diagrams to a local-only branch in a separate local repo, NOT in my-skills

## Pitfalls Discovered Through Trial and Error

### 1. Validate OFTEN — every 2–3 elements
Build iteratively: add elements → validate → repeat. Never build a large diagram and validate only at the end.

### 2. Missing code fence (validation fails)
Without the ```json fence, `extract_excalidraw_json` returns None — validation fails with "Could not find JSON or compressed-json code block".

### 3. Duplicate element IDs
MD5-hash-based IDs alone can collide with repeated labels. Use a global integer counter appended to the input string — guarantees uniqueness.

### 4. Arrow binding references must exist
`startBinding.elementId` and `endBinding.elementId` must reference real element IDs. Validation catches broken bindings.

### 5. Text elements with newlines in labels
Multiline labels produce non-fatal warnings in the `## Text Elements` section regex.

### 6. Complex diagrams fail readability despite geometric validation
174-element, 4-level diagrams pass geometric validation but are too busy for practical use. Keep didactic diagrams to 2–3 levels and ≤50 elements for clean visual hierarchy.

### 7. `## Text Elements` ID format — caret prefix is bare `^id`, never `^$id` or `^id-<prefix>`
The validator regex `TEXT_ELEMENT_LINE = re.compile(r"^(.+?)\s+\^([a-zA-Z0-9_-]+)\s*$", re.MULTILINE)` captures the bare ID after the caret. The correct format is:
```
Concept Map ^tx_3096b182d1f5
```
Not `^$tx_...` (literal characters), not `^id-tx_...` (extra prefix). Use: `f"{text} ^{e['id']}"`.

### 8. fontFamily: use 3 (monospace), not 5
`fontFamily: 5` renders but is non-standard. Use `fontFamily: 3` for monospace text. The visual validator checks for fontFamily=3 as "clean/technical" font.

### 9. Arrow overlap in radial layouts is expected — not an error
When arrows radiate from a central node to branch nodes around it (e.g. concept maps), they inherently overlap each other at the center. The geometric validator will flag these as warnings at 15% overlap threshold, but `ok: true` is determined by **errors only**. If your layout is radial/star-shaped and arrows share a common origin point, expect overlap warnings — they are inherent to the topology. Fix only if you can reroute arrows without breaking the diagram semantics.

### 10. Obsidian Excalidraw plugin may close before screenshot
`obsidian dev:screenshot` often captures a "plugin gone away" blank pane. Workaround: use the visual validator's `--render` flag (Playwright + esm.sh), which reliably produces a PNG at `--output-dir`. Fall back to that if Obsidian screenshot shows only the error pane.

### 7. `f"Label ^${id}"` produces a literal `$` — use `f"Label ^{id}"`
Python f-strings treat `${var}` as literal `$` followed by the expression result. `f"Start ^${s_tid}"` → `"Start ^$txt_abc123"` (double `^^` in output). Use string concatenation or `f"Start ^{s_tid}"` instead:
```python
# WRONG — produces "Start ^$txt_abc"
text_section_lines.append(f"Label ^${tid}")

# CORRECT — produces "Label ^txt_abc"
text_section_lines.append(f"Label ^{tid}")
```

### 8. Geometric validator has false positives for L-shaped arrows
The visual validator uses **segment-rectangle intersection** (not just bounding boxes) for overlap/crossing checks. L-shaped or multi-point arrows will always trigger warnings like:
- `"Arrow X crosses through element Y"` (even when visually clean)
- `"Elements text and arrow overlap by N%"` (even at safe clearance)

**This is a validator limitation, not a diagram error.** If structural validation passes (`"errors": []`) the file is correct and will render fine in Obsidian. Do NOT try to route around these warnings with complex waypoints — it makes things worse. For safe arrow routing:
- **Use straight horizontal or vertical arrows** between same-Y elements
- Avoid multi-point L-shaped arrows if the validator warnings bother you
- If you must use L-shaped arrows, ensure at least 20px clearance from all box edges in both dimensions

### 9. Bug in `excalidraw_models.py` — `import json` scoped inside `if is_compressed:`
**File:** `obsidian-plugin/skills/obsidian-excalidraw-drawing-manager/scripts/excalidraw_models.py`
**Line ~371:** `import json` was placed inside the `if is_compressed:` block, so `json.loads()` in the `else` (uncompressed JSON path) raises `NameError: cannot access local variable 'json' where it is not associated with a value`.

**Fix applied in my-skills:** Move `import json` to the top of `extract_excalidraw_json()` function. If the validator gives `"Failed to extract JSON: cannot access local variable 'json'"` on a plain JSON file, check whether this bug is present and patch it.
