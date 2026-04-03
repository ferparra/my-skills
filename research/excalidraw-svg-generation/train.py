#!/usr/bin/env python3
"""
SVG generation logic for annotated Excalidraw diagrams.
YES — the agent may modify this file to improve svg_structural_error_rate.

This file generates annotated SVGs from (diagram_type, user_request) pairs.
The agent can improve templates, layout logic, and annotation completeness.
"""
from __future__ import annotations

import sys
from prepare import METRIC_NAME, evaluate


# ── Configurable constants (agent can tune) ──────────────────────────────────

VIEWBOX_W = 1400
VIEWBOX_H = 700
NODE_W = 180
NODE_H = 70
NODE_RX = 12
H_GAP = 80
V_GAP = 100
FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
BG_COLOR = "#fafafa"

# Color palette (Tailwind-inspired)
COLORS = [
    {"fill": "#e0e7ff", "stroke": "#818cf8", "text": "#312e81"},  # indigo
    {"fill": "#d1fae5", "stroke": "#34d399", "text": "#064e3b"},  # emerald
    {"fill": "#ffedd5", "stroke": "#fb923c", "text": "#7c2d12"},  # orange
    {"fill": "#fce7f3", "stroke": "#f472b6", "text": "#831843"},  # pink
    {"fill": "#faf5ff", "stroke": "#e9d5ff", "text": "#581c87"},  # purple
    {"fill": "#ecfdf5", "stroke": "#a7f3d0", "text": "#022c22"},  # green
    {"fill": "#fff7ed", "stroke": "#fed7aa", "text": "#431407"},  # amber
    {"fill": "#f1f5f9", "stroke": "#94a3b8", "text": "#334155"},  # slate
]

EDGE_COLOR = "#94a3b8"


# ── SVG generation ───────────────────────────────────────────────────────────

def _parse_items(request: str) -> list[str]:
    """Extract item names from a user request. Simple heuristic."""
    # Look for patterns like "A, B, C" or "A and B"
    import re
    # Try colon-separated list first
    if ":" in request:
        after_colon = request.split(":")[-1].strip()
        items = [s.strip() for s in re.split(r",\s*|\s+and\s+", after_colon) if s.strip()]
        if len(items) >= 2:
            return items
    # Try comma/and splitting of the whole string for quoted or capitalized items
    items = re.findall(r"[A-Z][a-zA-Z\s]*(?=,|\s+and\s+|$)", request)
    items = [i.strip() for i in items if len(i.strip()) > 1]
    if len(items) >= 2:
        return items
    # Fallback: split on commas
    items = [s.strip() for s in request.split(",") if s.strip()]
    return items if len(items) >= 2 else ["Node A", "Node B", "Node C"]


def _node_id(name: str) -> str:
    """Convert name to kebab-case node ID."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"node-{slug}"


def _edge_id(from_id: str, to_id: str) -> str:
    return f"edge-{from_id.replace('node-', '')}-to-{to_id.replace('node-', '')}"


def generate_annotated_svg(diagram_type: str, user_request: str) -> str:
    """Generate an annotated SVG from a diagram type and user request."""
    items = _parse_items(user_request)
    n = len(items)

    # Build node list with IDs and positions
    nodes: list[dict] = []
    for i, name in enumerate(items):
        nid = _node_id(name)
        color = COLORS[i % len(COLORS)]
        nodes.append({
            "id": nid,
            "name": name,
            "x": 100 + i * (NODE_W + H_GAP),
            "y": 250,
            "w": NODE_W,
            "h": NODE_H,
            "color": color,
        })

    # Build edges based on diagram type
    edges: list[dict] = []

    if diagram_type in ("pipeline", "sequence", "process_level_flow"):
        # Linear chain
        for i in range(n - 1):
            edges.append({
                "from": nodes[i]["id"],
                "to": nodes[i + 1]["id"],
                "from_x": nodes[i]["x"] + NODE_W,
                "from_y": nodes[i]["y"] + NODE_H // 2,
                "to_x": nodes[i + 1]["x"],
                "to_y": nodes[i + 1]["y"] + NODE_H // 2,
            })

    elif diagram_type in ("hub_spoke", "fan_out"):
        # Hub is first, spokes radiate
        hub = nodes[0]
        hub["y"] = 300  # center
        hub["x"] = VIEWBOX_W // 2 - NODE_W // 2
        angle_step = 360 / max(n - 1, 1)
        import math
        for i, spoke in enumerate(nodes[1:]):
            angle = math.radians(-90 + i * angle_step)
            spoke["x"] = int(hub["x"] + 280 * math.cos(angle))
            spoke["y"] = int(hub["y"] + 200 * math.sin(angle))
            edges.append({
                "from": hub["id"],
                "to": spoke["id"],
                "from_x": hub["x"] + NODE_W // 2,
                "from_y": hub["y"] + NODE_H // 2,
                "to_x": spoke["x"] + NODE_W // 2,
                "to_y": spoke["y"] + NODE_H // 2,
            })

    elif diagram_type in ("convergence",):
        # All sources converge to last node
        target = nodes[-1]
        target["x"] = VIEWBOX_W // 2 - NODE_W // 2
        target["y"] = 450
        for i, src in enumerate(nodes[:-1]):
            src["x"] = 80 + i * (NODE_W + 40)
            src["y"] = 150
            edges.append({
                "from": src["id"],
                "to": target["id"],
                "from_x": src["x"] + NODE_W // 2,
                "from_y": src["y"] + NODE_H,
                "to_x": target["x"] + NODE_W // 2,
                "to_y": target["y"],
            })

    elif diagram_type in ("tree",):
        # First is root, rest are children
        root = nodes[0]
        root["x"] = VIEWBOX_W // 2 - NODE_W // 2
        root["y"] = 100
        child_count = n - 1
        total_w = child_count * NODE_W + (child_count - 1) * H_GAP
        start_x = VIEWBOX_W // 2 - total_w // 2
        for i, child in enumerate(nodes[1:]):
            child["x"] = start_x + i * (NODE_W + H_GAP)
            child["y"] = 300
            edges.append({
                "from": root["id"],
                "to": child["id"],
                "from_x": root["x"] + NODE_W // 2,
                "from_y": root["y"] + NODE_H,
                "to_x": child["x"] + NODE_W // 2,
                "to_y": child["y"],
            })

    elif diagram_type in ("concept_map", "mind_map"):
        # First is central, rest branch out
        center = nodes[0]
        center["x"] = VIEWBOX_W // 2 - NODE_W // 2
        center["y"] = 250
        import math
        for i, leaf in enumerate(nodes[1:]):
            angle = math.radians(-90 + i * (360 / max(n - 1, 1)))
            leaf["x"] = int(center["x"] + 300 * math.cos(angle))
            leaf["y"] = int(center["y"] + 200 * math.sin(angle))
            edges.append({
                "from": center["id"],
                "to": leaf["id"],
                "from_x": center["x"] + NODE_W // 2,
                "from_y": center["y"] + NODE_H // 2,
                "to_x": leaf["x"] + NODE_W // 2,
                "to_y": leaf["y"] + NODE_H // 2,
            })

    elif diagram_type in ("iterative_cycle",):
        # Circular layout with edges forming a cycle
        import math
        cx, cy = VIEWBOX_W // 2, VIEWBOX_H // 2
        radius = 220
        for i, node in enumerate(nodes):
            angle = math.radians(-90 + i * (360 / n))
            node["x"] = int(cx + radius * math.cos(angle) - NODE_W // 2)
            node["y"] = int(cy + radius * math.sin(angle) - NODE_H // 2)
        for i in range(n):
            j = (i + 1) % n
            edges.append({
                "from": nodes[i]["id"],
                "to": nodes[j]["id"],
                "from_x": nodes[i]["x"] + NODE_W // 2,
                "from_y": nodes[i]["y"] + NODE_H // 2,
                "to_x": nodes[j]["x"] + NODE_W // 2,
                "to_y": nodes[j]["y"] + NODE_H // 2,
            })

    elif diagram_type in ("systems_thinking",):
        # Two nodes with bidirectional edges (reinforcing loop)
        if n >= 2:
            nodes[0]["x"] = 300
            nodes[0]["y"] = 300
            nodes[1]["x"] = 800
            nodes[1]["y"] = 300
            edges.append({
                "from": nodes[0]["id"],
                "to": nodes[1]["id"],
                "from_x": nodes[0]["x"] + NODE_W,
                "from_y": nodes[0]["y"] + 10,
                "to_x": nodes[1]["x"],
                "to_y": nodes[1]["y"] + 10,
            })
            edges.append({
                "from": nodes[1]["id"],
                "to": nodes[0]["id"],
                "from_x": nodes[1]["x"],
                "from_y": nodes[1]["y"] + NODE_H - 10,
                "to_x": nodes[0]["x"] + NODE_W,
                "to_y": nodes[0]["y"] + NODE_H - 10,
            })

    else:
        # Default: linear chain
        for i in range(n - 1):
            edges.append({
                "from": nodes[i]["id"],
                "to": nodes[i + 1]["id"],
                "from_x": nodes[i]["x"] + NODE_W,
                "from_y": nodes[i]["y"] + NODE_H // 2,
                "to_x": nodes[i + 1]["x"],
                "to_y": nodes[i + 1]["y"] + NODE_H // 2,
            })

    # Build upstream/downstream maps
    downstream: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    upstream: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        downstream[e["from"]].append(e["to"])
        upstream[e["to"]].append(e["from"])

    # Compute viewBox bounds
    all_x = [n["x"] for n in nodes]
    all_y = [n["y"] for n in nodes]
    vb_w = max(max(n["x"] + n["w"] for n in nodes) + 100, VIEWBOX_W)
    vb_h = max(max(n["y"] + n["h"] for n in nodes) + 150, VIEWBOX_H)

    # Build SVG
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w} {vb_h}" '
        f'style="background-color: {BG_COLOR}; font-family: {FONT_FAMILY};">'
    )
    parts.append(f"  <!-- DIAGRAM_TYPE: {diagram_type} -->")
    parts.append(
        f"  <!-- TOPOLOGY: {len(nodes)} nodes, {len(edges)} edges, "
        f"{'linear' if diagram_type in ('pipeline', 'sequence') else 'graph'} layout -->"
    )
    parts.append(f"  <desc>{user_request}</desc>")

    # Defs for arrow markers
    parts.append('  <defs>')
    parts.append(
        '    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
    )
    parts.append(f'      <path d="M 0 0 L 10 5 L 0 10 z" fill="{EDGE_COLOR}" />')
    parts.append("    </marker>")
    parts.append("  </defs>")

    # Title
    parts.append(f'  <g id="diagram-title" role="heading" data-semantic-role="title">')
    parts.append(
        f'    <text x="{vb_w // 2}" y="60" text-anchor="middle" '
        f'font-weight="700" font-size="22" fill="#1e293b">'
        f"{diagram_type.upper().replace('_', ' ')}</text>"
    )
    parts.append("  </g>")

    # Edges (render before nodes so nodes appear on top)
    for e in edges:
        eid = _edge_id(e["from"], e["to"])
        parts.append(
            f'  <g id="{eid}" role="img" '
            f'aria-label="Edge from {e["from"]} to {e["to"]}" '
            f'data-semantic-role="edge" '
            f'data-from="{e["from"]}" data-to="{e["to"]}">'
        )
        parts.append(
            f'    <path d="M {e["from_x"]} {e["from_y"]} L {e["to_x"]} {e["to_y"]}" '
            f'stroke="{EDGE_COLOR}" stroke-width="2" fill="none" marker-end="url(#arrow)" />'
        )
        parts.append("  </g>")

    # Nodes
    for node in nodes:
        nid = node["id"]
        up_str = ",".join(upstream[nid]) if upstream[nid] else ""
        down_str = ",".join(downstream[nid]) if downstream[nid] else ""
        up_attr = f' data-upstream="{up_str}"' if up_str else ""
        down_attr = f' data-downstream="{down_str}"' if down_str else ""
        c = node["color"]

        parts.append(
            f'  <g id="{nid}" role="img" '
            f'aria-label="{node["name"]}" '
            f'data-semantic-role="node"'
            f"{up_attr}{down_attr}>"
        )
        parts.append(
            f'    <rect x="{node["x"]}" y="{node["y"]}" '
            f'width="{node["w"]}" height="{node["h"]}" rx="{NODE_RX}" '
            f'fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="2" />'
        )
        parts.append(
            f'    <text x="{node["x"] + node["w"] // 2}" '
            f'y="{node["y"] + node["h"] // 2 + 5}" '
            f'text-anchor="middle" font-weight="600" font-size="14" '
            f'fill="{c["text"]}">{node["name"]}</text>'
        )
        parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    score = evaluate(generate_annotated_svg, verbose=True)
    print(f"\n{METRIC_NAME}: {score:.6f}")
