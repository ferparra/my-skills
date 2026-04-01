#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from visual_validator_config import VisualValidatorConfig
from visual_validator_models import (
    compute_global_bbox,
    dump_json,
    extract_excalidraw_json,
    load_markdown_note,
    parse_drawing,
)

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { margin: 0; padding: 0; }
    #root { display: flex; align-items: center; justify-content: center; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="module">
    import { exportToSvg } from "https://esm.sh/@excalidraw/excalidraw?bundle";

    window.renderDiagram = async (data) => {
      try {
        const svg = await exportToSvg({
          elements: data.elements,
          appState: data.appState || { theme: "light" },
          files: {}
        });
        const root = document.getElementById("root");
        root.innerHTML = "";
        root.appendChild(svg);
        return { ok: true };
      } catch (error) {
        return { ok: false, error: error.message };
      }
    };

    window.ready = true;
  </script>
</body>
</html>
"""


def _extract_json_flexible(body: str, file_path: Path) -> dict:
    """Extract JSON, handling both plain and compressed formats."""
    from visual_validator_models import extract_excalidraw_json
    try:
        return extract_excalidraw_json(body, file_path)
    except ValueError as e:
        if "compressed-json" not in str(e):
            raise
        # Decompress with LZString
        import subprocess, os, json, re
        match = re.search(r'```compressed-json\s+([\s\S]+?)\n```', body)
        if not match:
            raise ValueError("No compressed-json block found") from e
        cleaned = match.group(1).strip().replace('\n\n', '').replace('\n', '')
        lz_path = os.path.join(os.path.dirname(__file__), "..", "node_modules", "lz-string", "libs", "lz-string.js")
        if not os.path.exists(lz_path):
            lz_path = "/tmp/node_modules/lz-string/libs/lz-string.js"
        result = subprocess.run(
            ["node", "-e",
             f"const LZ=require('{lz_path}');"
             f"const d=LZ.decompressFromBase64('{cleaned}');"
             f"if(d){console.log(d)}else{process.exit(1)}"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise ValueError(f"LZString decompression failed: {result.stderr[:200]}") from e
        return json.loads(result.stdout)



def render_to_png(
    input_path: Path, output_path: Path, config: VisualValidatorConfig
) -> dict[str, Any]:
    """Render .excalidraw.md file to PNG using Playwright."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError:
        return {
            "ok": False,
            "error": "Playwright not installed. Run: python -m playwright install chromium",
        }

    # Load and parse the drawing
    note = load_markdown_note(input_path)
    drawing_json = _extract_json_flexible(note.body, input_path)
    if drawing_json is None:
        return {"ok": False, "error": "Could not extract JSON from markdown"}

    drawing = parse_drawing(drawing_json)

    # Filter out deleted elements
    active_elements = [el for el in drawing.elements if not getattr(el, "isDeleted", False)]

    # Compute bounding box
    global_bbox = compute_global_bbox(active_elements)

    # Set viewport size
    viewport_width = min(
        int(global_bbox.width + 2 * config.render_padding_px),
        config.render_max_width_px,
    )
    viewport_height = max(
        int(global_bbox.height + 2 * config.render_padding_px),
        config.render_min_height_px,
    )

    # Prepare data for Playwright
    render_data = {
        "elements": [el.model_dump(exclude_none=True) for el in active_elements],
        "appState": drawing.appState.model_dump(exclude_none=True)
        if drawing.appState
        else {"theme": "light"},
    }

    # Launch browser and render
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": viewport_width, "height": viewport_height})

            # Load HTML template
            page.set_content(HTML_TEMPLATE)

            # Wait for window.ready
            page.wait_for_function("window.ready === true", timeout=10000)

            # Call renderDiagram
            result = page.evaluate(f"window.renderDiagram({json.dumps(render_data)})")

            if not result.get("ok"):
                browser.close()
                return {"ok": False, "error": f"Render failed: {result.get('error', 'unknown')}"}

            # Wait for SVG to appear
            page.wait_for_selector("svg", timeout=10000)

            # Screenshot
            output_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output_path), full_page=True)

            browser.close()

        return {
            "ok": True,
            "render_path": str(output_path),
            "width": viewport_width,
            "height": viewport_height,
            "element_count": len(active_elements),
        }

    except Exception as e:
        return {"ok": False, "error": f"Playwright error: {e}"}


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Render Excalidraw drawing to PNG")
    parser.add_argument("--input", required=True, help=".excalidraw.md file path")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument(
        "--padding", type=int, default=80, help="Padding around diagram (px)"
    )
    parser.add_argument("--max-width", type=int, default=1920, help="Max viewport width (px)")
    parser.add_argument("--min-height", type=int, default=600, help="Min viewport height (px)")

    args = parser.parse_args()

    config = VisualValidatorConfig(
        render_padding_px=args.padding,
        render_max_width_px=args.max_width,
        render_min_height_px=args.min_height,
    )

    result = render_to_png(Path(args.input), Path(args.output), config)
    print(dump_json(result))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
