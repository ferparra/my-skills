#!/usr/bin/env python3
"""
Render an Obsidian .excalidraw.md file to PNG using Playwright + headless Chromium.

Usage:
  python3 render_excalidraw.py <path-to-file.excalidraw.md> [--output path.png] [--scale 2] [--width 1920]

First-time setup:
  python3 -m playwright install chromium
  npm install lz-string  # dependency for decompressing existing compressed-json files
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from pathlib import Path
from base64 import b64decode
from typing import Any, cast


def extract_json_from_excalidraw_md(raw: str) -> dict[str, Any]:
    """Extract and decompress JSON from an .excalidraw.md file."""
    # Try ```json block first
    json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if json_match:
        json_text = json_match.group(1).strip()
        try:
            return cast(dict[str, Any], json.loads(json_text))
        except json.JSONDecodeError as e:
            print(f"WARNING: ```json block found but invalid JSON: {e}", file=sys.stderr)

    # Try ```compressed-json block
    compressed_match = re.search(
        r"```compressed-json\s*(.*?)\s*```", raw, re.DOTALL
    )
    if compressed_match:
        compressed_text = compressed_match.group(1).strip()
        # Remove any chunking (double newlines every 256 chars)
        compressed_text = compressed_text.replace("\n\n", "").replace("\n", "")
        try:
            decoded = b64decode(compressed_text)
            # Try zlib decompress first
            try:
                decompressed = zlib.decompress(decoded)
                return cast(dict[str, Any], json.loads(decompressed))
            except zlib.error:
                # Try raw decompress (no header)
                try:
                    decompressed = zlib.decompress(decoded, -15)
                    return cast(dict[str, Any], json.loads(decompressed))
                except zlib.error:
                    pass
            # Last resort: try LZString decompress via Node.js
            # NOTE: zlib CANNOT decompress this data — Excalidraw uses LZString, not zlib.
            # We need the full path to lz-string since it may not be globally installed.
            import subprocess, os
            lz_path = os.path.join(os.path.dirname(__file__), "..", "node_modules", "lz-string", "libs", "lz-string.js")
            if not os.path.exists(lz_path):
                lz_path = "/tmp/node_modules/lz-string/libs/lz-string.js"
            # Plain string (no f-string) to prevent mypy treating JS identifiers as Python names
            node_script = (
                "const LZString=require('%s');"
                "const d=LZString.decompressFromBase64('%s');"
                "if(d){console.log(d)}else{process.exit(1)}"
            ) % (lz_path, compressed_text)
            result = subprocess.run(
                ["node", "-e", node_script],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return cast(dict[str, Any], json.loads(result.stdout))
            else:
                print(f"WARNING: LZString decompress failed: {result.stderr[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: compressed-json decompression failed: {e}", file=sys.stderr)

    raise ValueError(
        "Could not extract JSON from ## Drawing section. "
        "File must contain a ```json or ```compressed-json code block."
    )


def validate_excalidraw(data: dict[str, Any]) -> list[str]:
    """Validate Excalidraw JSON structure. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    if data.get("type") != "excalidraw":
        errors.append(f"Expected type 'excalidraw', got '{data.get('type')}'")
    if "elements" not in data:
        errors.append("Missing 'elements' array")
    elif not isinstance(data["elements"], list):
        errors.append("'elements' must be an array")
    elif len(data["elements"]) == 0:
        errors.append("'elements' array is empty — nothing to render")
    return errors


def compute_bounding_box(elements: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    """Compute bounding box (min_x, min_y, max_x, max_y) across all elements."""
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    for el in elements:
        if el.get("isDeleted"):
            continue
        x = el.get("x", 0)
        y = el.get("y", 0)
        w = el.get("width", 0)
        h = el.get("height", 0)

        # For arrows/lines, points array defines the shape relative to x,y
        if el.get("type") in ("arrow", "line") and "points" in el:
            for px, py in el["points"]:
                min_x = min(min_x, x + px)
                min_y = min(min_y, y + py)
                max_x = max(max_x, x + px)
                max_y = max(max_y, y + py)
        else:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + abs(w))
            max_y = max(max_y, y + abs(h))

    if min_x == float("inf"):
        return (0, 0, 800, 600)
    return (min_x, min_y, max_x, max_y)


def render(
    excalidraw_path: Path,
    output_path: Path | None = None,
    scale: int = 2,
    max_width: int = 1920,
    headless: bool = True,
) -> Path:
    """Render an .excalidraw.md file to PNG. Returns the output PNG path."""
    # Import playwright here so validation errors show before import errors
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError:
        print("ERROR: playwright not installed.", file=sys.stderr)
        print("Run: python3 -m playwright install chromium", file=sys.stderr)
        sys.exit(1)

    # Read and validate
    raw = excalidraw_path.read_text(encoding="utf-8")

    try:
        data = extract_json_from_excalidraw_md(raw)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_excalidraw(data)
    if errors:
        print(f"ERROR: Invalid Excalidraw file:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Compute viewport size from element bounding box
    elements = [e for e in data["elements"] if not e.get("isDeleted")]
    min_x, min_y, max_x, max_y = compute_bounding_box(elements)
    padding = 80
    diagram_w = max_x - min_x + padding * 2
    diagram_h = max_y - min_y + padding * 2

    # Cap viewport width, let height be natural
    vp_width = min(int(diagram_w), max_width)
    vp_height = max(int(diagram_h), 600)

    # Output path
    if output_path is None:
        output_path = excalidraw_path.with_suffix(".png")

    # Template path (same directory as this script)
    template_path = Path(__file__).parent / "render_template.html"
    if not template_path.exists():
        print(f"ERROR: Template not found at {template_path}", file=sys.stderr)
        sys.exit(1)
    template_url = template_path.as_uri()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as e:
            if "Executable doesn't exist" in str(e) or "browserType.launch" in str(e):
                print("ERROR: Chromium not installed for Playwright.", file=sys.stderr)
                print("Run: python3 -m playwright install chromium", file=sys.stderr)
                sys.exit(1)
            raise

        page = browser.new_page(
            viewport={"width": vp_width, "height": vp_height},
            device_scale_factor=scale,
        )

        # Load the template
        page.goto(template_url)

        # Wait for the ES module to load (imports from esm.sh)
        page.wait_for_function("window.__moduleReady === true", timeout=30000)

        # Inject the diagram data and render
        json_str = json.dumps(data)
        result = page.evaluate(f"window.renderDiagram({json_str})")

        if not result or not result.get("success"):
            error_msg = result.get("error", "Unknown render error") if result else "renderDiagram returned null"
            print(f"ERROR: Render failed: {error_msg}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        # Wait for render completion signal
        page.wait_for_function("window.__renderComplete === true", timeout=15000)

        # Screenshot the SVG element
        svg_el = page.query_selector("#root svg")
        if svg_el is None:
            print("ERROR: No SVG element found after render.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        svg_el.screenshot(path=str(output_path))
        browser.close()

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Obsidian .excalidraw.md to PNG")
    parser.add_argument("input", type=Path, help="Path to .excalidraw.md file")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output PNG path (default: same name with .png)")
    parser.add_argument("--scale", "-s", type=int, default=2, help="Device scale factor (default: 2)")
    parser.add_argument("--width", "-w", type=int, default=1920, help="Max viewport width (default: 1920)")
    parser.add_argument("--visible", action="store_true", help="Show browser window (not headless)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    png_path = render(
        args.input,
        args.output,
        args.scale,
        args.width,
        headless=not args.visible,
    )
    print(str(png_path))


if __name__ == "__main__":
    main()
