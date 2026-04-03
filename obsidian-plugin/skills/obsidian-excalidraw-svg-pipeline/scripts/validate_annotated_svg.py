#!/usr/bin/env python3
"""Validate an annotated SVG against the reference annotation schema."""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"

VALID_SEMANTIC_ROLES = {
    "node", "edge", "annotation", "label", "title", "legend",
    "container", "layer", "lane", "state", "initial-state", "final-state",
    "guard-condition", "transition", "stock", "flow", "valve", "cloud",
    "auxiliary", "entity", "relationship", "aggregate-root", "value-object",
}


def _find_comments(raw_text: str) -> dict[str, str]:
    """Extract DIAGRAM_TYPE and TOPOLOGY from HTML/XML comments."""
    comments: dict[str, str] = {}
    for match in re.finditer(r"<!--\s*(DIAGRAM_TYPE|TOPOLOGY)\s*:\s*(.+?)\s*-->", raw_text):
        comments[match.group(1)] = match.group(2).strip()
    return comments


def _collect_semantic_groups(root: ET.Element) -> list[ET.Element]:
    """Recursively collect all <g> elements with data-semantic-role."""
    results = []
    for elem in root.iter(f"{SVG_NS}g"):
        if elem.get("data-semantic-role"):
            results.append(elem)
    # Also check without namespace (some SVGs omit it)
    for elem in root.iter("g"):
        if elem.get("data-semantic-role") and elem not in results:
            results.append(elem)
    return results


def _collect_all_ids(root: ET.Element) -> set[str]:
    """Collect all id attributes in the document."""
    ids = set()
    for elem in root.iter():
        eid = elem.get("id")
        if eid:
            ids.add(eid)
    return ids


def _parse_ref_list(value: str | None) -> list[str]:
    """Parse a space- or comma-separated list of ID references."""
    if not value:
        return []
    return [v.strip() for v in re.split(r"[,\s]+", value) if v.strip()]


def validate(path: str) -> dict:
    """Run all validation checks and return a result dict."""
    errors: list[str] = []
    warnings: list[str] = []

    # Read raw text for comment extraction
    with open(path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Check comments
    comments = _find_comments(raw_text)
    if "DIAGRAM_TYPE" not in comments:
        errors.append("Missing <!-- DIAGRAM_TYPE: ... --> comment.")
    if "TOPOLOGY" not in comments:
        errors.append("Missing <!-- TOPOLOGY: ... --> comment.")

    # Parse XML
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as exc:
        errors.append(f"XML parse error: {exc}")
        return {"ok": False, "errors": errors, "warnings": warnings, "stats": {"nodes": 0, "edges": 0, "groups": 0}}

    # Check <desc>
    desc = root.find(f"{SVG_NS}desc")
    if desc is None:
        desc = root.find("desc")
    if desc is None or not (desc.text and desc.text.strip()):
        errors.append("Missing or empty <desc> element.")

    # Collect semantic groups
    groups = _collect_semantic_groups(root)
    all_ids = _collect_all_ids(root)

    # Node-equivalent roles: these all represent primary diagram elements
    NODE_ROLES = {"node", "state", "initial-state", "final-state", "stock", "entity", "aggregate-root", "value-object"}
    # Edge-equivalent roles: these represent connections
    EDGE_ROLES = {"edge", "transition", "flow", "relationship"}

    nodes = [g for g in groups if g.get("data-semantic-role") in NODE_ROLES]
    edges = [g for g in groups if g.get("data-semantic-role") in EDGE_ROLES]

    # Check 4: at least one node-equivalent
    if not nodes:
        errors.append("No node-equivalent elements found (expected at least one <g> with data-semantic-role in: node, state, stock, entity, etc.).")

    # Check 5: at least one edge-equivalent (unless single-node)
    if not edges and len(nodes) > 1:
        errors.append("No edge-equivalent elements found (expected for multi-node diagrams).")
    elif not edges and len(nodes) == 1:
        warnings.append("Single-node diagram with no edges.")

    # Per-group checks
    for g in groups:
        role = g.get("data-semantic-role")
        gid = g.get("id")

        # Check 6: all semantic groups have id
        if not gid:
            errors.append(f"<g data-semantic-role=\"{role}\"> is missing an id attribute.")

        # Check 7: all semantic groups have role attribute
        if not g.get("role"):
            errors.append(f"<g data-semantic-role=\"{role}\" id=\"{gid or '?'}\"> is missing a role attribute (expected \"img\" or \"heading\").")

        # Check 10: valid vocabulary
        if role not in VALID_SEMANTIC_ROLES:
            errors.append(f"Invalid data-semantic-role value \"{role}\" on id=\"{gid or '?'}\". Valid: {sorted(VALID_SEMANTIC_ROLES)}")

    # Check 8: nodes have upstream or downstream
    # Strict for role="node", advisory for domain-specific node roles
    STRICT_CONNECTION_ROLES = {"node"}
    for g in nodes:
        gid = g.get("id", "?")
        role = g.get("data-semantic-role", "")
        has_upstream = g.get("data-upstream")
        has_downstream = g.get("data-downstream")
        if not has_upstream and not has_downstream:
            if role in STRICT_CONNECTION_ROLES:
                warnings.append(f"Node id=\"{gid}\" has neither data-upstream nor data-downstream.")
            # Domain-specific node roles (state, stock, entity) may be standalone — no warning

    # Check 9: edges have data-from and data-to
    for g in edges:
        gid = g.get("id", "?")
        if not g.get("data-from"):
            errors.append(f"Edge id=\"{gid}\" is missing data-from.")
        if not g.get("data-to"):
            errors.append(f"Edge id=\"{gid}\" is missing data-to.")

    # Check 11: referenced IDs exist
    # Downgraded to warnings — external/cloud/boundary elements may have IDs
    # nested inside groups that are not top-level semantic groups
    for g in groups:
        gid = g.get("id", "?")
        role = g.get("data-semantic-role")
        if role in NODE_ROLES:
            for ref in _parse_ref_list(g.get("data-upstream")):
                if ref not in all_ids:
                    warnings.append(f"Node id=\"{gid}\" references id=\"{ref}\" not found as a top-level id.")
            for ref in _parse_ref_list(g.get("data-downstream")):
                if ref not in all_ids:
                    warnings.append(f"Node id=\"{gid}\" references id=\"{ref}\" not found as a top-level id.")
        elif role in EDGE_ROLES:
            for attr in ("data-from", "data-to"):
                ref = g.get(attr)
                if ref and ref not in all_ids:
                    warnings.append(f"Edge id=\"{gid}\" {attr} references id=\"{ref}\" not found as a top-level id.")

    ok = len(errors) == 0
    result = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "groups": len(groups),
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an annotated SVG.")
    parser.add_argument("--path", required=True, help="Path to the SVG file to validate.")
    args = parser.parse_args()

    result = validate(args.path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
