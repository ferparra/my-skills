---
name: obsidian-excalidraw-file-generation
version: "2.0.0"
description: "Reference specification for the .excalidraw.md file format used by the Obsidian Excalidraw plugin. Covers format rules, validation checklist, read/write patterns, and PNG rendering. Used downstream by obsidian-excalidraw-svg-pipeline for the transform step."
triggers:
  - fix excalidraw file
  - excalidraw parsing failed
  - excalidraw not rendering
  - excalidraw format spec
  - excalidraw file structure
---

# Obsidian Excalidraw File Format Reference

## Workflow

To **generate new diagrams**, use `obsidian-excalidraw-svg-pipeline` — it produces annotated SVGs then transforms them to `.excalidraw.md` using this format spec.

To **fix or debug existing** `.excalidraw.md` files:

1. **Diagnose** using the validation checklist below.
2. **Validate structurally** with `obsidian-excalidraw-drawing-manager`.
3. **Validate geometrically** with `obsidian-excalidraw-visual-validator`.
4. **Render to PNG** with the render script to confirm visual output.
5. **Open in Obsidian** to verify live.

## Format Specification (studied from plugin source code)

### File Structure (top to bottom)

```
---
tags: [excalidraw]
excalidraw-plugin: parsed
---

==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== You can decompress Drawing data with the command palette: 'Decompress current Excalidraw file'. For more info check in plugin settings under 'Saving'


# Excalidraw Data

## Text Elements
<text value> ^<element_id>
... (one per text element, standalone AND container-bound)

%%
## Drawing
```json
<full Excalidraw JSON scene>
```
%%
```

### Key Rules

1. **Frontmatter**: `excalidraw-plugin: parsed` (NOT `raw`) + `tags: [excalidraw]`
2. **Warning banner**: use the SHORT form — `==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==` The longer banner with decompression instructions causes silent rendering failures.
3. **Text Elements section**: list ALL `type: "text"` elements from JSON — both standalone AND container-bound. Format: `<text> ^<id>`
4. **`%%` markers** at TWO positions:
   - After last text element line (before `## Drawing`)
   - After closing code fence (end of file)
5. **Drawing code block**: use ` ```json` (uncompressed) — the plugin handles both compressed and uncompressed. Do NOT use ` ```compressed-json` unless implementing full msgpack5 pipeline.
6. `%%` after `## Drawing` code block must have blank line before it
7. Text element IDs in markdown (after `^`) must EXACTLY match JSON `id` fields
8. Container-bound text elements: JSON `containerId` must reference parent shape's `id`
9. **Closing fence format**: the final `}` of the JSON **must be on its own line**, then a newline, then ` ``` ` on the next line. A common mistake is `}``` ` (brace and fence on same line) — always verify byte-level structure.

### Mandatory Validation Checklist (run after EVERY write)

After writing an `.excalidraw.md` file, always verify ALL of the following:

```python
import json

with open(path, 'rb') as f:
    raw = f.read()

# 1. Opening fence: ```json{ must be followed by \n (brace on same line as fence, newline after)
fp = raw.find(b'```json{')
assert fp >= 0, "Missing ```json{ fence"
assert raw[fp+7] == 10, "Opening fence must be ```json{\\n (newline required after brace)"
json_start = fp + 7

# 2. JSON must parse cleanly
for json_end in range(len(raw), json_start, -1):
    try:
        data = json.loads(raw[json_start:json_end])
        break
    except json.JSONDecodeError:
        pass
assert json_end > json_start, "JSON did not parse"

# 3. All text element IDs in ## Text Elements section must match JSON
text_section_start = raw.find(b'## Text Elements\n') + len(b'## Text Elements\n')
text_section_end = raw.find(b'\n%%', text_section_start)
text_section = raw[text_section_start:text_section_end].decode('utf-8')
section_ids = set()
for line in text_section.split('\n'):
    line = line.strip()
    if line and '^' in line:
        section_ids.add(line.split('^')[-1])
json_ids = {e['id'] for e in data['elements'] if e['type'] == 'text'}
assert section_ids == json_ids, f"ID mismatch: section={section_ids - json_ids}, json={json_ids - section_ids}"

# 4. Closing fence: } and ``` must NOT be on same line
# Correct: "}\n```\n" — wrong: "}```\n"
last_ticks = raw.rfind(b'```')
last_brace = raw[json_start:json_end].rfind(b'}') + json_start  # last } of JSON
gap = raw[last_brace+1:last_ticks]
# Closing scene } is on its own line, then blank line, then ``` on next line
assert gap == b'\n\n', f"Closing fence gap must be \\n\\n (newline + blank line), got: {gap!r}"
assert raw[last_ticks-1:last_ticks+1] == b'\n```', "Closing fence must follow newline"

# 5. %% markers: both must exist
pct_positions = [i for i in range(len(raw)-1) if raw[i:i+2] == b'%%']
assert len(pct_positions) == 2, f"Expected 2 %% markers, found {len(pct_positions)}"

# 6. All arrow bindings must reference valid element IDs
all_ids = {e['id'] for e in data['elements']}
for arrow in [e for e in data['elements'] if e['type'] == 'arrow']:
    sb = arrow.get('startBinding') or {}
    eb = arrow.get('endBinding') or {}
    for binding in [sb, eb]:
        eid = binding.get('elementId')
        if eid:
            assert eid in all_ids, f"Arrow {arrow['id']} references non-existent element {eid}"

# 7. No deleted elements
deleted = [e['id'] for e in data['elements'] if e.get('isDeleted')]
assert not deleted, f"Found isDeleted=true elements: {deleted}"

# 8. All element IDs unique
ids = [e['id'] for e in data['elements']]
assert len(ids) == len(set(ids)), f"Duplicate element IDs found"

print("ALL CHECKS PASSED")
```

### JSON Scene Structure (minimum valid)

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/2.22.0",
  "elements": [...],
  "appState": {
    "theme": "light",
    "viewBackgroundColor": "#ffffff",
    "gridSize": null
  }
}
```

### Text Element (standalone)

```json
{
  "id": "title_1",
  "type": "text",
  "x": 100, "y": 60, "width": 480, "height": 44,
  "text": "Hermes Diagramming System",
  "fontSize": 32,
  "fontFamily": 5,
  "textAlign": "center",
  "containerId": null,
  "originalText": "Hermes Diagramming System",
  "boundElements": [],
  "groupIds": [],
  "frameId": null,
  "roundness": null,
  "strokeColor": "#000",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "angle": 0,
  "seed": 1001,
  "version": 1,
  "versionNonce": 0,
  "isDeleted": false,
  "link": null,
  "locked": false,
  "lineHeight": 1.25,
  "baseline": 28,
  "verticalAlign": "middle"
}
```

### Text Element (container-bound)

Same as above but with:
- `"containerId": "parent_shape_id"` (not null)
- `"text"` and `"originalText"` set to the label text

### Rectangle Shape

```json
{
  "id": "rectfr",
  "type": "rectangle",
  "x": 80, "y": 170,
  "width": 540, "height": 80,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "#f5f5f5",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "angle": 0,
  "roundness": {"type": 2},
  "groupIds": [],
  "frameId": null,
  "seed": 1003,
  "version": 1,
  "versionNonce": 0,
  "isDeleted": false,
  "boundElements": [{"id": "<text_id>", "type": "text"}],
  "link": null,
  "locked": false
}
```

### Font Family Values

- `1` = Arial
- `2` = Comic Sans
- `3` = Courier New
- `4` = Georgia
- `5` = Helvetica (default, most common)
- `6` = Inter
- `7` = JetBrains Mono
- `8` = Palatino
- `9` = system-ui
- `10` = Times New Roman
- `11` = Caveat
- `12` = Sett

---

## Editing Existing Excalidraw Files

**Key issue**: When you load, modify, and save an `.excalidraw.md` file, naive string concatenation corrupts the JSON because `json.dumps(data, indent=2)` changes the JSON character count (indent changes line lengths), shifting the closing fence position. Each successive write compounds the corruption.

### Correct Read/Write Pattern (Python)

```python
import json

def find_json_boundaries(content_bytes):
    """Find JSON start ({) and end (} before closing fence) robustly.
    
    The opening fence is ```json{ (7 chars: 3 backticks + json + brace).
    The closing fence is: }\n}\n```\n...\n%%\n
    """
    fp = content_bytes.find(b'```json{')
    if fp < 0:
        raise ValueError("No ```json{ fence found")
    # { is at fp+6 (0-indexed: backticks at fp,fp+1,fp+2, then j,s,o,n at fp+3..fp+6)
    json_start = fp + 7  # position AFTER the opening { brace
    
    # Find closing fence: }\n}\n```\n (last } of JSON followed by ```)
    for json_end in range(len(content_bytes), json_start, -1):
        try:
            data = json.loads(content_bytes[json_start:json_end])
            return json_start, json_end, data  # boundaries + parsed data
        except json.JSONDecodeError:
            pass
    raise ValueError("Could not find valid JSON boundaries")

# READ
with open(path, 'rb') as f:
    raw = f.read()
json_start, json_end, data = find_json_boundaries(raw)
elements = data['elements']  # modify these

# WRITE (use bytes, preserve prefix/suffix exactly)
data['elements'] = elements
new_json_bytes = json.dumps(data, indent=2).encode('utf-8')

# Verify BEFORE writing
test = json.loads(new_json_bytes)
assert len(test['elements']) == len(elements)

new_raw = raw[:json_start] + new_json_bytes + raw[json_end:]
with open(path, 'wb') as f:
    f.write(new_raw)

# Self-verify
with open(path, 'rb') as f:
    v = f.read()
_, _, vdata = find_json_boundaries(v)
assert len(vdata['elements']) == len(elements)  # must pass
```

### Why Indent Changes Corrupt Boundaries

| Operation | JSON length change |
|-----------|-------------------|
| `json.dumps(data)` (no indent) | single line, compact |
| `json.dumps(data, indent=2)` | ~2-3x larger, multi-line |
| `json.dumps(data, indent=4)` | even larger |

If you replace `raw[json_start:json_end]` with a differently-formatted JSON, the suffix shifts position. The closing fence `}\n``` ` starts at a different absolute position, and subsequent reads fail with "Extra data" or "Unterminated string".

### Critical: Opening Fence Format

**CORRECT**: ` ```json{` (brace directly attached, NO newline after)
**WRONG**: ` ```json\n{` (with newline — this is a different format Obsidian may produce on export)

When searching for the opening fence, use `b'```json{'` not `b'```json\n{'`.

---

## Critical Discovery: Compression Format

The plugin uses **LZString** (not zlib or msgpack5) for `compressed-json` format.

Python's `zlib` CANNOT decompress this data (all modes fail: raw deflate, zlib, gzip). The correct method is `LZString.decompressFromBase64()` via Node.js — confirmed working on actual vault files.

**The `eJz` prefix** in some compressed data is zlib-compressed data (not LZString). The hub-and-spoke.excalidraw.md uses LZString (base64 starts with `N4K`), which works with Node.js `LZString.decompressFromBase64()`.

**Always use uncompressed ` ```json`** to avoid decompression complexity. If you have existing `compressed-json` files, the render script (`render_excalidraw.py`) handles decompression automatically via its bundled lz-string module.

---

## Common Failures

| Symptom | Cause |
|---------|-------|
| Parsing fails completely | Corrupted/incompatible compressed JSON — switch to ` ```json` |
| Text elements not showing | Missing entries in `## Text Elements` section or ID mismatch |
| `%%` shown as text | Wrong position — must be on own line between sections |
| Block ref broken | Text element ID in markdown (`^id`) doesn't match JSON `id` exactly |
| "Extra data" / "Unterminated string" on re-read | JSON boundary corrupted after write — use binary boundary detection + progressive parsing (see Editing section above) |
| Successive writes corrupt file progressively | Indent depth changed between reads/writes — always use `raw[:json_start] + new_json + raw[json_end:]` with bytes, never string concatenation |
| Warning banner shows | View is in raw/source mode — switch to EXCALIDRAW VIEW |

---

## Visual QA with Playwright (Recommended)

After writing a `.excalidraw.md` file, use the render script to verify the diagram renders correctly before opening in Obsidian.

**Prerequisites:**
```bash
python3 -m playwright install chromium
```

**Render to PNG:**
```bash
python3 ~/.hermes/skills/obsidian/obsidian-excalidraw-file-generation/references/render_excalidraw.py \
  ~/my-vault/Excalidraw/your-diagram.excalidraw.md \
  --output /tmp/diagram-render.png --scale 2
```

**Verify in Obsidian:**
```bash
# Copy PNG to vault for side-by-side comparison
cp /tmp/diagram-render.png ~/my-vault/Excalidraw/_renders/
```

The render script:
- Extracts JSON from `.excalidraw.md` (handles both ` ```json ` and ` ```compressed-json ` blocks)
- Computes bounding box from all elements
- Renders via headless Chromium using Excalidraw's `exportToSvg`
- Saves PNG at 2× scale with proper viewport sizing

**Integration with build workflow:** After writing a diagram file, always run the render script before declaring the task done. If rendering fails, the JSON is invalid. If rendering succeeds but Obsidian shows blank/incomplete content, the markdown wrapping is wrong.

**Render script location:**
```
~/.hermes/skills/obsidian/obsidian-excalidraw-file-generation/references/
├── render_excalidraw.py    # Main render script
└── render_template.html     # HTML template with Excalidraw ES module
```

**Quick test (always run after incremental additions):**
```bash
python3 ~/.hermes/skills/obsidian/obsidian-excalidraw-file-generation/references/render_excalidraw.py \
  <file.excalidraw.md> --scale 2 && echo "Render OK" || echo "Render FAILED"
```
