#!/usr/bin/env python3
"""Transform an annotated SVG into a valid .excalidraw.md file."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"

# ---------- helpers ----------


def _seed(element_id: str) -> int:
    """Deterministic seed from element ID."""
    return hash(element_id) % (2**31)


def _parse_translate(g: ET.Element) -> tuple[float, float]:
    """Extract (tx, ty) from transform='translate(x, y)' on a <g>."""
    transform = g.get("transform", "")
    m = re.search(r"translate\(\s*([-\d.]+)[,\s]+([-\d.]+)\s*\)", transform)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 0.0, 0.0


def _find_recursive(g: ET.Element, local_names: list[str]) -> ET.Element | None:
    """Walk children recursively to find the first element matching one of the local names."""
    for name in local_names:
        for elem in g.iter(f"{SVG_NS}{name}"):
            return elem
        for elem in g.iter(name):
            return elem
    return None


def _find_text(g: ET.Element) -> str:
    """Find the first <text> child's text content, walking recursively."""
    for t in g.iter(f"{SVG_NS}text"):
        parts = [t.text or ""] + [ts.text or "" for ts in t]
        return " ".join(p.strip() for p in parts if p.strip())
    for t in g.iter("text"):
        parts = [t.text or ""] + [ts.text or "" for ts in t]
        return " ".join(p.strip() for p in parts if p.strip())
    return ""


def _attr_float(elem: ET.Element, attr: str, default: float = 0.0) -> float:
    val = elem.get(attr)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _parse_color(val: str | None, default: str = "transparent") -> str:
    if not val or val == "none":
        return default
    return val


def _parse_path_endpoints(d: str) -> tuple[float, float, float, float]:
    """Extract first and last point from a path d attribute."""
    # Collect all coordinate pairs from M/L/Q/C commands
    points: list[tuple[float, float]] = []
    for m in re.finditer(r"([-\d.]+)[,\s]+([-\d.]+)", d):
        points.append((float(m.group(1)), float(m.group(2))))
    if len(points) >= 2:
        return points[0][0], points[0][1], points[-1][0], points[-1][1]
    if len(points) == 1:
        return points[0][0], points[0][1], points[0][0], points[0][1]
    return 0, 0, 0, 0


# ---------- element builders ----------


def _make_rect_element(eid: str, x: float, y: float, w: float, h: float,
                       fill: str, stroke: str) -> dict[str, object]:
    return {
        "type": "rectangle",
        "id": eid,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "roughness": 0,
        "opacity": 100,
        "seed": _seed(eid),
        "groupIds": [],
        "roundness": {"type": 3},
        "isDeleted": False,
        "boundElements": [],
        "locked": False,
        "link": None,
        "updated": 1,
        "version": 1,
        "versionNonce": _seed(eid + "_v"),
    }


def _make_ellipse_element(eid: str, x: float, y: float, w: float, h: float,
                          fill: str, stroke: str) -> dict[str, object]:
    return {
        "type": "ellipse",
        "id": eid,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "roughness": 0,
        "opacity": 100,
        "seed": _seed(eid),
        "groupIds": [],
        "roundness": {"type": 2},
        "isDeleted": False,
        "boundElements": [],
        "locked": False,
        "link": None,
        "updated": 1,
        "version": 1,
        "versionNonce": _seed(eid + "_v"),
    }


def _make_text_element(eid: str, x: float, y: float, text: str,
                       container_id: str | None = None, font_size: int = 16) -> dict[str, object]:
    return {
        "type": "text",
        "id": eid,
        "x": x,
        "y": y,
        "width": len(text) * font_size * 0.6,
        "height": font_size * 1.4,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "roughness": 0,
        "opacity": 100,
        "seed": _seed(eid),
        "groupIds": [],
        "roundness": None,
        "isDeleted": False,
        "boundElements": None,
        "locked": False,
        "link": None,
        "updated": 1,
        "version": 1,
        "versionNonce": _seed(eid + "_v"),
        "text": text,
        "fontSize": font_size,
        "fontFamily": 5,
        "textAlign": "center",
        "verticalAlign": "middle" if container_id else "top",
        "containerId": container_id,
        "originalText": text,
        "autoResize": True,
        "lineHeight": 1.25,
    }


def _make_arrow_element(eid: str, x: float, y: float, points: list[list[float]],
                        from_id: str | None, to_id: str | None,
                        stroke: str = "#1e1e1e") -> dict[str, object]:
    start_binding = None
    end_binding = None
    if from_id:
        start_binding = {"elementId": from_id, "focus": 0, "gap": 5, "fixedPoint": None}
    if to_id:
        end_binding = {"elementId": to_id, "focus": 0, "gap": 5, "fixedPoint": None}

    return {
        "type": "arrow",
        "id": eid,
        "x": x,
        "y": y,
        "width": abs(points[-1][0]) if points else 0,
        "height": abs(points[-1][1]) if points else 0,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "roughness": 0,
        "opacity": 100,
        "seed": _seed(eid),
        "groupIds": [],
        "roundness": {"type": 2},
        "isDeleted": False,
        "boundElements": None,
        "locked": False,
        "link": None,
        "updated": 1,
        "version": 1,
        "versionNonce": _seed(eid + "_v"),
        "points": points,
        "startBinding": start_binding,
        "endBinding": end_binding,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "lastCommittedPoint": None,
    }


# ---------- main transform ----------


def transform(input_path: str, output_path: str) -> dict[str, object]:
    """Parse annotated SVG and write .excalidraw.md."""
    tree = ET.parse(input_path)
    root = tree.getroot()

    elements: list[dict[str, object]] = []
    text_sections: list[str] = []
    bound_element_refs: dict[str, list[dict[str, str]]] = {}  # container_id -> [{id, type}]

    # Collect all semantic groups
    groups: list[ET.Element] = []
    for elem in root.iter(f"{SVG_NS}g"):
        if elem.get("data-semantic-role"):
            groups.append(elem)
    for elem in root.iter("g"):
        if elem.get("data-semantic-role") and elem not in groups:
            groups.append(elem)

    # Process nodes
    for g in groups:
        role = g.get("data-semantic-role")
        gid = g.get("id", "unknown")
        tx, ty = _parse_translate(g)

        if role == "node":
            shape_elem = _find_recursive(g, ["rect", "rectangle"])
            is_ellipse = False
            if shape_elem is None:
                shape_elem = _find_recursive(g, ["ellipse", "circle"])
                is_ellipse = True

            if shape_elem is not None:
                if is_ellipse:
                    cx = _attr_float(shape_elem, "cx")
                    cy = _attr_float(shape_elem, "cy")
                    rx = _attr_float(shape_elem, "rx", 40)
                    ry = _attr_float(shape_elem, "ry", rx)
                    # circle uses r
                    r = _attr_float(shape_elem, "r", 0)
                    if r > 0:
                        rx = ry = r
                    w, h = rx * 2, ry * 2
                    x, y = tx + cx - rx, ty + cy - ry
                else:
                    x = tx + _attr_float(shape_elem, "x")
                    y = ty + _attr_float(shape_elem, "y")
                    w = _attr_float(shape_elem, "width", 120)
                    h = _attr_float(shape_elem, "height", 60)

                fill = _parse_color(shape_elem.get("fill"), "transparent")
                stroke = _parse_color(shape_elem.get("stroke"), "#1e1e1e")
            else:
                # No shape found; place a default rectangle
                x, y, w, h = tx, ty, 120, 60
                fill, stroke = "transparent", "#1e1e1e"
                is_ellipse = False

            if is_ellipse:
                shape = _make_ellipse_element(gid, x, y, w, h, fill, stroke)
            else:
                shape = _make_rect_element(gid, x, y, w, h, fill, stroke)

            elements.append(shape)

            label = _find_text(g)
            if label:
                text_id = f"{gid}-label"
                text_el = _make_text_element(text_id, x + w / 2, y + h / 2, label, container_id=gid)
                elements.append(text_el)
                text_sections.append(f"{label} ^{text_id}")

                bound_element_refs.setdefault(gid, []).append({"id": text_id, "type": "text"})

        elif role == "title":
            label = _find_text(g)
            if label:
                text_id = gid or "title-text"
                text_el = _make_text_element(text_id, tx + 20, ty + 20, label, font_size=28)
                elements.append(text_el)
                text_sections.append(f"{label} ^{text_id}")

    # Process edges
    for g in groups:
        role = g.get("data-semantic-role")
        if role != "edge":
            continue

        gid = g.get("id", "unknown-edge")
        tx, ty = _parse_translate(g)
        from_id = g.get("data-from")
        to_id = g.get("data-to")

        path_elem = _find_recursive(g, ["path"])
        line_elem = _find_recursive(g, ["line"])

        if path_elem is not None:
            d = path_elem.get("d", "")
            x1, y1, x2, y2 = _parse_path_endpoints(d)
            stroke = _parse_color(path_elem.get("stroke"), "#1e1e1e")
        elif line_elem is not None:
            x1 = _attr_float(line_elem, "x1")
            y1 = _attr_float(line_elem, "y1")
            x2 = _attr_float(line_elem, "x2")
            y2 = _attr_float(line_elem, "y2")
            stroke = _parse_color(line_elem.get("stroke"), "#1e1e1e")
        else:
            x1, y1, x2, y2 = tx, ty, tx + 100, ty
            stroke = "#1e1e1e"

        ax = tx + x1
        ay = ty + y1
        dx = (x2 - x1)
        dy = (y2 - y1)

        arrow = _make_arrow_element(gid, ax, ay, [[0, 0], [dx, dy]], from_id, to_id, stroke)
        elements.append(arrow)

        # Wire bindings into the target shapes
        if from_id:
            bound_element_refs.setdefault(from_id, []).append({"id": gid, "type": "arrow"})
        if to_id:
            bound_element_refs.setdefault(to_id, []).append({"id": gid, "type": "arrow"})

        label = _find_text(g)
        if label:
            text_id = f"{gid}-label"
            mid_x = ax + dx / 2
            mid_y = ay + dy / 2
            text_el = _make_text_element(text_id, mid_x, mid_y - 12, label, container_id=gid)
            elements.append(text_el)
            text_sections.append(f"{label} ^{text_id}")

            arrow["boundElements"] = [{"id": text_id, "type": "text"}]

    # Patch boundElements on containers
    for el in elements:
        eid = str(el.get("id", ""))
        if eid and eid in bound_element_refs:
            raw_existing = el.get("boundElements")
            existing_list: list[dict[str, str]] = raw_existing if isinstance(raw_existing, list) else []
            el["boundElements"] = existing_list + bound_element_refs[eid]

    # Build scene JSON
    scene = {
        "type": "excalidraw",
        "version": 2,
        "source": "svg-to-excalidraw-pipeline",
        "elements": elements,
        "appState": {
            "gridSize": None,
            "viewBackgroundColor": "#ffffff",
        },
        "files": {},
    }

    # Build .excalidraw.md content
    text_block = "\n".join(text_sections)
    scene_json = json.dumps(scene, indent=2)

    md_content = f"""---
tags:
  - excalidraw
excalidraw-plugin: parsed
---
> [!warning] Do not edit this file directly.
> This file was generated by the SVG-to-Excalidraw pipeline.

## Text Elements
{text_block}

## Drawing
```json
{scene_json}
```
%%
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {
        "ok": True,
        "output_path": output_path,
        "element_count": len(elements),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform annotated SVG to .excalidraw.md.")
    parser.add_argument("--input", required=True, help="Path to the annotated SVG.")
    parser.add_argument("--output", required=True, help="Output path for the .excalidraw.md file.")
    args = parser.parse_args()

    try:
        result = transform(args.input, args.output)
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
