#!/usr/bin/env python3
"""
Evaluation harness for SVG generation quality.
READ-ONLY — the agent must never modify this file.

Loads reference annotated SVGs, defines test specs (simplified diagram requests),
and scores generated SVGs against the annotation schema.
"""
from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

# ── Contract constants ───────────────────────────────────────────────────────
TIME_BUDGET = 30
METRIC_NAME = "svg_structural_error_rate"

SVG_NS = "{http://www.w3.org/2000/svg}"
REFERENCE_DIR = Path(__file__).parent / ".." / "excalidraw-svg-references" / "annotated"

VALID_SEMANTIC_ROLES = {
    "node", "edge", "annotation", "label", "title", "legend", "container",
    "layer", "lane", "state", "initial-state", "final-state", "guard-condition",
    "transition", "stock", "flow", "valve", "cloud", "auxiliary", "entity",
    "relationship", "aggregate-root", "value-object",
}


# ── Schema validation ────────────────────────────────────────────────────────

def validate_svg_schema(svg_text: str) -> tuple[list[str], dict[str, int]]:
    """Validate an annotated SVG against the schema. Returns (errors, stats)."""
    errors: list[str] = []
    stats: dict[str, int] = {"nodes": 0, "edges": 0, "groups": 0}

    # Check comments (ET doesn't parse comments, use raw text)
    if not re.search(r"<!--\s*DIAGRAM_TYPE:", svg_text):
        errors.append("Missing <!-- DIAGRAM_TYPE: ... --> comment")
    if not re.search(r"<!--\s*TOPOLOGY:", svg_text):
        errors.append("Missing <!-- TOPOLOGY: ... --> comment")

    # Parse XML
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        errors.append(f"Invalid XML: {e}")
        return errors, stats

    # Check <desc>
    desc = root.find(f"{SVG_NS}desc")
    if desc is None:
        desc = root.find("desc")
    if desc is None or not (desc.text and desc.text.strip()):
        errors.append("Missing or empty <desc> element")

    # Collect all groups with data-semantic-role
    all_groups: list[ET.Element] = []
    all_ids: set[str] = set()

    for g in root.iter(f"{SVG_NS}g"):
        role = g.get("data-semantic-role")
        if role is not None:
            all_groups.append(g)
            gid = g.get("id")
            if gid:
                all_ids.add(gid)

    # Also check without namespace
    for g in root.iter("g"):
        role = g.get("data-semantic-role")
        if role is not None and g not in all_groups:
            all_groups.append(g)
            gid = g.get("id")
            if gid:
                all_ids.add(gid)

    stats["groups"] = len(all_groups)

    # Validate each group
    for g in all_groups:
        role = g.get("data-semantic-role", "")
        gid = g.get("id")

        # Must have id
        if not gid:
            errors.append(f"Group with role '{role}' missing id attribute")

        # Must have role attribute
        if not g.get("role"):
            errors.append(f"Group '{gid or '?'}' missing role attribute (should be 'img' or 'heading')")

        # Validate vocabulary
        if role not in VALID_SEMANTIC_ROLES:
            errors.append(f"Invalid data-semantic-role '{role}' on '{gid or '?'}'")

        # Node-specific checks
        if role == "node":
            stats["nodes"] += 1
            has_up = g.get("data-upstream")
            has_down = g.get("data-downstream")
            if not has_up and not has_down:
                errors.append(f"Node '{gid or '?'}' has neither data-upstream nor data-downstream")

        # Edge-specific checks
        if role in ("edge", "transition", "flow"):
            stats["edges"] += 1
            if not g.get("data-from"):
                errors.append(f"Edge '{gid or '?'}' missing data-from")
            if not g.get("data-to"):
                errors.append(f"Edge '{gid or '?'}' missing data-to")

    # Also count domain-specific node/edge roles
    NODE_ROLES = {"node", "state", "initial-state", "final-state", "stock", "entity", "aggregate-root", "value-object"}
    EDGE_ROLES = {"node": False, "edge": True, "transition": True, "flow": True}
    for g in all_groups:
        role = g.get("data-semantic-role", "")
        if role in NODE_ROLES and role != "node":
            stats["nodes"] += 1
        if role in ("transition", "flow"):
            stats["edges"] += 1

    # Check minimum content
    if stats["nodes"] == 0:
        errors.append("No node-equivalent elements found")
    if stats["nodes"] > 1 and stats["edges"] == 0:
        errors.append("Multiple nodes but no edges found")

    # Check ID references
    for g in all_groups:
        for attr in ("data-upstream", "data-downstream", "data-from", "data-to"):
            val = g.get(attr)
            if val:
                for ref_id in val.split(","):
                    ref_id = ref_id.strip()
                    if ref_id and ref_id not in all_ids:
                        errors.append(
                            f"'{g.get('id', '?')}' references non-existent id '{ref_id}' in {attr}"
                        )

    return errors, stats


# ── Test specs ────────────────────────────────────────────────────────────────
# Each spec: (name, diagram_type, user_request, min_nodes, min_edges)
# The generator in train.py receives (diagram_type, user_request) and must
# produce a valid annotated SVG.

TEST_SPECS: list[tuple[str, str, str, int, int]] = [
    (
        "simple_pipeline",
        "pipeline",
        "A 3-stage data pipeline: Ingest, Transform, Load",
        3, 2,
    ),
    (
        "concept_map_learning",
        "concept_map",
        "A concept map about Machine Learning with 4 concepts: ML, Supervised, Unsupervised, Reinforcement",
        4, 3,
    ),
    (
        "hub_spoke_team",
        "hub_spoke",
        "A hub-and-spoke diagram with a Team Lead connected to 3 team members: Alice, Bob, Carol",
        4, 3,
    ),
    (
        "simple_tree",
        "tree",
        "A 2-level tree: Company at root, Engineering and Marketing as children",
        3, 2,
    ),
    (
        "simple_sequence",
        "sequence",
        "A sequence diagram with Client sending Request to Server, Server returning Response",
        2, 2,
    ),
    (
        "causal_loop",
        "systems_thinking",
        "A reinforcing loop between Practice and Skill Level",
        2, 2,
    ),
    (
        "fan_out_events",
        "fan_out",
        "An event bus broadcasting to 3 consumers: Logger, Analytics, Notification",
        4, 3,
    ),
    (
        "iterative_sprint",
        "iterative_cycle",
        "A 4-phase sprint cycle: Plan, Build, Test, Review",
        4, 4,
    ),
]


# ── Evaluation function ─────────────────────────────────────────────────────

def evaluate(
    generate_fn: Callable[[str, str], str],
    *,
    verbose: bool = False,
) -> float:
    """
    Run generate_fn over all TEST_SPECS.
    Returns svg_structural_error_rate (lower is better; 0.0 = all pass).

    generate_fn(diagram_type, user_request) → svg_text: str
    """
    total = len(TEST_SPECS)
    correct = 0
    failures: list[tuple[str, list[str]]] = []

    for name, dtype, request, min_nodes, min_edges in TEST_SPECS:
        try:
            svg_text = generate_fn(dtype, request)
        except Exception as e:
            failures.append((name, [f"Generation crashed: {e}"]))
            continue

        if not svg_text or not svg_text.strip():
            failures.append((name, ["Empty SVG output"]))
            continue

        errs, stats = validate_svg_schema(svg_text)

        # Check minimum topology
        if stats["nodes"] < min_nodes:
            errs.append(f"Expected >= {min_nodes} nodes, got {stats['nodes']}")
        if stats["edges"] < min_edges:
            errs.append(f"Expected >= {min_edges} edges, got {stats['edges']}")

        if errs:
            failures.append((name, errs))
        else:
            correct += 1

    error_rate = 1.0 - correct / total if total > 0 else 1.0

    if verbose:
        print(f"\n=== SVG generation evaluation ({correct}/{total} correct) ===")
        if failures:
            print("\n--- Failures ---")
            for name, errs in failures:
                print(f"  [{name}]")
                for e in errs:
                    print(f"    - {e}")

    return error_rate


if __name__ == "__main__":
    print(f"Test suite: {len(TEST_SPECS)} specs")
    print(f"Reference dir: {REFERENCE_DIR}")
    if REFERENCE_DIR.exists():
        refs = list(REFERENCE_DIR.glob("*.svg"))
        print(f"Reference SVGs found: {len(refs)}")
    else:
        print("WARNING: Reference directory not found")
    print(f"Import evaluate(generate_fn) from this module in train.py")
    sys.exit(0)
