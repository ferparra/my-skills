#!/usr/bin/env python3
"""
Validation solution — the ONLY file the agent may edit.
Baseline: ported schema + visual checks with known gaps for the agent to fix.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from math import sqrt
from statistics import mean, stdev

from prepare import TIME_BUDGET, METRIC_NAME, evaluate

# ── Threshold constants (agent-tunable) ──────────────────────────────────────

MAX_OVERLAP_RATIO = 0.15
MIN_ELEMENT_GAP_PX = 20.0
MAX_SPACING_CV = 0.5
TEXT_PADDING_PX = 10.0
ARROW_SNAP_TOLERANCE_PX = 15.0
MAX_QUADRANT_SKEW = 0.7
MAX_CENTER_OF_MASS_OFFSET = 0.3
MIN_SIZE_TIERS = 2

# ── Geometry helpers ─────────────────────────────────────────────────────────


def compute_bbox(el: dict) -> dict:
    """Compute bounding box for an element. Returns dict with x, y, w, h, x2, y2, cx, cy, area."""
    # For arrows, lines, freedraw, use points array
    if "points" in el and el["points"]:
        xs = [el["x"] + p[0] for p in el["points"]]
        ys = [el["y"] + p[1] for p in el["points"]]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x
        h = max_y - min_y
        return {
            "x": min_x,
            "y": min_y,
            "w": w,
            "h": h,
            "x2": max_x,
            "y2": max_y,
            "cx": (min_x + max_x) / 2,
            "cy": (min_y + max_y) / 2,
            "area": w * h,
        }

    # For other elements, use x, y, width, height
    x, y = el["x"], el["y"]
    w, h = el["width"], el["height"]
    return {
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "x2": x + w,
        "y2": y + h,
        "cx": x + w / 2,
        "cy": y + h / 2,
        "area": w * h,
    }


def bbox_intersects(a: dict, b: dict) -> bool:
    """Check if two bboxes intersect."""
    return not (a["x2"] < b["x"] or a["x"] > b["x2"] or a["y2"] < b["y"] or a["y"] > b["y2"])


def intersection_area(a: dict, b: dict) -> float:
    """Compute intersection area."""
    if not bbox_intersects(a, b):
        return 0.0
    x_overlap = min(a["x2"], b["x2"]) - max(a["x"], b["x"])
    y_overlap = min(a["y2"], b["y2"]) - max(a["y"], b["y"])
    return x_overlap * y_overlap


def point_to_bbox_distance(px: float, py: float, bbox: dict) -> float:
    """Distance from point to bbox (0 if inside)."""
    dx = max(bbox["x"] - px, 0, px - bbox["x2"])
    dy = max(bbox["y"] - py, 0, py - bbox["y2"])
    return sqrt(dx**2 + dy**2)


# ── Schema check functions ───────────────────────────────────────────────────


def check_duplicate_ids(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for duplicate element IDs."""
    errors = []
    id_counts = Counter(el["id"] for el in elements)
    duplicates = [id_ for id_, count in id_counts.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate element IDs found: {', '.join(duplicates)}")
    return errors, []


def check_text_bindings(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check that text element containerIds reference valid elements."""
    errors = []
    element_ids = {el["id"] for el in elements}

    for el in elements:
        if el["type"] == "text" and el.get("containerId"):
            if el["containerId"] not in element_ids:
                errors.append(
                    f"Text element '{el['id']}' has containerId='{el['containerId']}' "
                    f"but no element with that ID exists"
                )
    return errors, []


def check_arrow_bindings(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check that arrow bindings reference valid elements."""
    errors = []
    element_ids = {el["id"] for el in elements}

    for el in elements:
        if el["type"] == "arrow":
            start_binding = el.get("startBinding")
            end_binding = el.get("endBinding")
            if start_binding and start_binding.get("elementId") not in element_ids:
                errors.append(
                    f"Arrow element '{el['id']}' startBinding references "
                    f"non-existent element '{start_binding['elementId']}'"
                )
            if end_binding and end_binding.get("elementId") not in element_ids:
                errors.append(
                    f"Arrow element '{el['id']}' endBinding references "
                    f"non-existent element '{end_binding['elementId']}'"
                )
    return errors, []


def check_bidirectional_bindings(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check bidirectional consistency between containers and text."""
    errors = []
    element_map = {el["id"]: el for el in elements}

    # Check: if container lists text in boundElements, text's containerId must point back
    for el in elements:
        if el.get("boundElements"):
            for bound_ref in el["boundElements"]:
                if bound_ref.get("type") == "text":
                    text_el = element_map.get(bound_ref["id"])
                    if text_el and text_el["type"] == "text":
                        if text_el.get("containerId") != el["id"]:
                            errors.append(
                                f"Element '{el['id']}' lists text '{text_el['id']}' in boundElements, "
                                f"but text's containerId is '{text_el.get('containerId')}' not '{el['id']}'"
                            )

    # Check: if text has containerId, container must list it in boundElements
    for el in elements:
        if el["type"] == "text" and el.get("containerId"):
            container = element_map.get(el["containerId"])
            if container and container.get("boundElements"):
                if not any(
                    ref["id"] == el["id"] and ref.get("type") == "text"
                    for ref in container["boundElements"]
                ):
                    errors.append(
                        f"Text element '{el['id']}' has containerId='{el['containerId']}', "
                        f"but container doesn't list it in boundElements"
                    )

    return errors, []


def check_zero_dimensions(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for zero-dimension shapes (warning only)."""
    warnings = []
    for el in elements:
        # Skip elements where zero dimensions are valid
        if el["type"] in ("line", "arrow", "freedraw"):
            continue
        if el["width"] == 0 or el["height"] == 0:
            warnings.append(
                f"Element '{el['id']}' has zero dimension: width={el['width']}, height={el['height']}"
            )
    return [], warnings


def check_text_original_text(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for text/originalText mismatch (warning only)."""
    warnings = []
    for el in elements:
        if el["type"] == "text":
            if el.get("text") != el.get("originalText"):
                warnings.append(
                    f"Text element '{el['id']}' has text/originalText mismatch (may be due to line wrapping)"
                )
    return [], warnings


def check_color_values(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for invalid color values (warning only)."""
    warnings = []
    color_pattern = re.compile(r"^(#[0-9a-fA-F]{3,8}|transparent)$")

    for el in elements:
        if not color_pattern.match(el.get("strokeColor", "")):
            warnings.append(f"Element '{el['id']}' has invalid strokeColor: '{el.get('strokeColor')}'")
        if not color_pattern.match(el.get("backgroundColor", "")):
            warnings.append(
                f"Element '{el['id']}' has invalid backgroundColor: '{el.get('backgroundColor')}'"
            )
    return [], warnings


def check_orphaned_groups(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for groupIds that appear only once (warning only)."""
    warnings = []
    all_group_ids: list[str] = []
    for el in elements:
        all_group_ids.extend(el.get("groupIds", []))

    group_counts = Counter(all_group_ids)
    orphaned = [gid for gid, count in group_counts.items() if count == 1]
    if orphaned:
        warnings.append(f"Group IDs appearing on only one element (orphaned): {', '.join(orphaned)}")
    return [], warnings


# ── Visual check functions ───────────────────────────────────────────────────


def check_overlaps(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for overlapping elements."""
    # NOTE: Baseline intentionally does NOT filter container-child pairs
    errors: list[str] = []
    warnings: list[str] = []

    # Compute bboxes
    bboxes_with_ids: list[tuple[str, dict]] = [(el["id"], compute_bbox(el)) for el in elements]

    # Pairwise overlap check
    for i, (id_a, bb_a) in enumerate(bboxes_with_ids):
        for id_b, bb_b in bboxes_with_ids[i + 1 :]:
            if bbox_intersects(bb_a, bb_b):
                overlap_area = intersection_area(bb_a, bb_b)
                smaller_area = min(bb_a["area"], bb_b["area"])
                overlap_ratio = overlap_area / smaller_area if smaller_area > 0 else 0

                if overlap_ratio > MAX_OVERLAP_RATIO:
                    warnings.append(
                        f"Elements {id_a} and {id_b} overlap by {overlap_ratio:.1%} "
                        f"(threshold: {MAX_OVERLAP_RATIO:.1%})"
                    )

    return errors, warnings


def check_spacing(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check spacing consistency between elements."""
    errors: list[str] = []
    warnings: list[str] = []

    if len(elements) < 2:
        return errors, warnings

    bboxes_with_ids: list[tuple[str, dict]] = [(el["id"], compute_bbox(el)) for el in elements]

    # Compute nearest neighbor distances
    gaps: list[float] = []
    close_pairs: list[tuple[str, str, float]] = []

    for i, (id_a, bb_a) in enumerate(bboxes_with_ids):
        min_gap = float("inf")
        for j, (id_b, bb_b) in enumerate(bboxes_with_ids):
            if i == j:
                continue
            # Compute gap
            dx = max(0, max(bb_a["x"], bb_b["x"]) - min(bb_a["x2"], bb_b["x2"]))
            dy = max(0, max(bb_a["y"], bb_b["y"]) - min(bb_a["y2"], bb_b["y2"]))
            gap = sqrt(dx**2 + dy**2)
            if gap < min_gap:
                min_gap = gap

        gaps.append(min_gap)

        if min_gap < MIN_ELEMENT_GAP_PX:
            # Find which neighbor it was
            for id_b, bb_b in bboxes_with_ids:
                if id_a == id_b:
                    continue
                dx = max(0, max(bb_a["x"], bb_b["x"]) - min(bb_a["x2"], bb_b["x2"]))
                dy = max(0, max(bb_a["y"], bb_b["y"]) - min(bb_a["y2"], bb_b["y2"]))
                gap = sqrt(dx**2 + dy**2)
                if abs(gap - min_gap) < 1e-6:
                    close_pairs.append((id_a, id_b, min_gap))
                    break

    # Compute coefficient of variation
    if len(gaps) >= 2:
        mean_gap = mean(gaps)
        std_gap = stdev(gaps)
        cv = std_gap / mean_gap if mean_gap > 0 else 0

        if cv > MAX_SPACING_CV:
            warnings.append(
                f"Spacing consistency poor: CV={cv:.2f} (threshold: {MAX_SPACING_CV:.2f}). "
                f"Mean gap: {mean_gap:.1f}px, StdDev: {std_gap:.1f}px"
            )

    # Report close pairs
    for id_a, id_b, gap in close_pairs:
        warnings.append(
            f"Elements {id_a} and {id_b} are very close: {gap:.1f}px (min: {MIN_ELEMENT_GAP_PX:.1f}px)"
        )

    return errors, warnings


def check_text_overflow(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for text overflow in containers."""
    errors: list[str] = []
    warnings: list[str] = []

    # Build element index
    element_index = {el["id"]: el for el in elements}

    # Check each text element with a containerId
    for el in elements:
        if el["type"] != "text":
            continue
        if not el.get("containerId"):
            continue

        container = element_index.get(el["containerId"])
        if not container:
            continue  # Broken binding, caught by schema check

        # Text element's width is the rendered width
        text_width = el["width"]
        container_width = container["width"]
        available_width = container_width - 2 * TEXT_PADDING_PX

        if text_width > available_width:
            overflow = text_width - available_width
            errors.append(
                f"Text element {el['id']} overflows container {el['containerId']} by {overflow:.1f}px "
                f"(text width: {text_width:.1f}px, available: {available_width:.1f}px)"
            )

    return errors, warnings


def check_arrow_accuracy(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check arrow endpoint accuracy (do arrows land on target bboxes?)."""
    errors: list[str] = []
    warnings: list[str] = []

    # Build element index with bboxes
    element_bboxes = {el["id"]: compute_bbox(el) for el in elements}

    # Check each arrow
    for el in elements:
        if el["type"] != "arrow":
            continue
        if not el.get("points") or len(el["points"]) < 2:
            continue

        # Check start binding
        start_binding = el.get("startBinding")
        if start_binding:
            target_bbox = element_bboxes.get(start_binding.get("elementId"))
            if target_bbox:
                # Arrow start point is (x + points[0][0], y + points[0][1])
                arrow_x = el["x"] + el["points"][0][0]
                arrow_y = el["y"] + el["points"][0][1]
                distance = point_to_bbox_distance(arrow_x, arrow_y, target_bbox)

                if distance > ARROW_SNAP_TOLERANCE_PX:
                    errors.append(
                        f"Arrow {el['id']} start point is {distance:.1f}px from target {start_binding['elementId']} "
                        f"(tolerance: {ARROW_SNAP_TOLERANCE_PX:.1f}px)"
                    )

        # Check end binding
        end_binding = el.get("endBinding")
        if end_binding:
            target_bbox = element_bboxes.get(end_binding.get("elementId"))
            if target_bbox:
                # Arrow end point is (x + points[-1][0], y + points[-1][1])
                arrow_x = el["x"] + el["points"][-1][0]
                arrow_y = el["y"] + el["points"][-1][1]
                distance = point_to_bbox_distance(arrow_x, arrow_y, target_bbox)

                if distance > ARROW_SNAP_TOLERANCE_PX:
                    errors.append(
                        f"Arrow {el['id']} end point is {distance:.1f}px from target {end_binding['elementId']} "
                        f"(tolerance: {ARROW_SNAP_TOLERANCE_PX:.1f}px)"
                    )

    return errors, warnings


def check_composition(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check composition balance (center of mass, quadrant distribution)."""
    errors: list[str] = []
    warnings: list[str] = []

    if len(elements) < 4:
        return errors, warnings  # Too few elements

    # Compute global bbox
    if not elements:
        return errors, warnings
    bboxes = [compute_bbox(el) for el in elements]
    min_x = min(bb["x"] for bb in bboxes)
    min_y = min(bb["y"] for bb in bboxes)
    max_x = max(bb["x2"] for bb in bboxes)
    max_y = max(bb["y2"] for bb in bboxes)
    canvas_center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    canvas_width = max_x - min_x
    canvas_height = max_y - min_y

    # Compute center of mass
    total_area = 0.0
    weighted_x = 0.0
    weighted_y = 0.0

    for el in elements:
        bbox = compute_bbox(el)
        area = bbox["area"]
        cx, cy = bbox["cx"], bbox["cy"]
        total_area += area
        weighted_x += cx * area
        weighted_y += cy * area

    if total_area > 0:
        center_of_mass = (weighted_x / total_area, weighted_y / total_area)
    else:
        center_of_mass = canvas_center

    # Compute center offset
    com_offset_x = abs(center_of_mass[0] - canvas_center[0]) / (canvas_width / 2) if canvas_width > 0 else 0
    com_offset_y = abs(center_of_mass[1] - canvas_center[1]) / (canvas_height / 2) if canvas_height > 0 else 0
    max_offset = max(com_offset_x, com_offset_y)

    if max_offset > MAX_CENTER_OF_MASS_OFFSET:
        warnings.append(
            f"Composition unbalanced: center of mass offset {max_offset:.1%} "
            f"(threshold: {MAX_CENTER_OF_MASS_OFFSET:.1%})"
        )

    # Quadrant distribution
    quadrants = {"NW": 0, "NE": 0, "SW": 0, "SE": 0}
    for el in elements:
        bbox = compute_bbox(el)
        cx, cy = bbox["cx"], bbox["cy"]
        quad_x = "W" if cx < canvas_center[0] else "E"
        quad_y = "N" if cy < canvas_center[1] else "S"
        quadrants[quad_y + quad_x] += 1

    total_elements = len(elements)
    max_quadrant_count = max(quadrants.values())
    max_quadrant_fraction = max_quadrant_count / total_elements

    if max_quadrant_fraction > MAX_QUADRANT_SKEW:
        warnings.append(
            f"Composition skewed: {max_quadrant_fraction:.1%} of elements in one quadrant "
            f"(threshold: {MAX_QUADRANT_SKEW:.1%})"
        )

    return errors, warnings


def check_size_hierarchy(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Check for size hierarchy (distinct size tiers)."""
    errors: list[str] = []
    warnings: list[str] = []

    if len(elements) < 3:
        return errors, warnings

    # Compute areas
    areas = [compute_bbox(el)["area"] for el in elements]

    # Cluster into tiers
    tier_counts = {"hero": 0, "primary": 0, "secondary": 0, "small": 0}

    for area in areas:
        if area >= 40000:
            tier_counts["hero"] += 1
        elif area >= 15000:
            tier_counts["primary"] += 1
        elif area >= 6000:
            tier_counts["secondary"] += 1
        else:
            tier_counts["small"] += 1

    distinct_tiers = sum(1 for count in tier_counts.values() if count > 0)

    if distinct_tiers < MIN_SIZE_TIERS:
        warnings.append(
            f"Size hierarchy weak: only {distinct_tiers} distinct tier(s) "
            f"(min: {MIN_SIZE_TIERS}). All elements similar size."
        )

    return errors, warnings


# ── Main entry point ─────────────────────────────────────────────────────────

ALL_CHECKS = [
    check_duplicate_ids,
    check_text_bindings,
    check_arrow_bindings,
    check_bidirectional_bindings,
    check_zero_dimensions,
    check_text_original_text,
    check_color_values,
    check_orphaned_groups,
    check_overlaps,
    check_spacing,
    check_text_overflow,
    check_arrow_accuracy,
    check_composition,
    check_size_hierarchy,
]


def validate_all(elements: list[dict]) -> tuple[list[str], list[str]]:
    """Run all checks on elements. Returns (errors, warnings)."""
    # Baseline: NO isDeleted filtering (agent should add this)
    all_errors: list[str] = []
    all_warnings: list[str] = []

    for check_fn in ALL_CHECKS:
        e, w = check_fn(elements)
        all_errors.extend(e)
        all_warnings.extend(w)

    return all_errors, all_warnings


def main():
    """Evaluate the validator and print the metric."""
    t0 = time.monotonic()
    score = evaluate(validate_all, verbose=True)
    elapsed = time.monotonic() - t0
    assert elapsed < TIME_BUDGET, f"Exceeded time budget: {elapsed:.1f}s > {TIME_BUDGET}s"
    print(f"\n{METRIC_NAME}: {score:.6f}")


if __name__ == "__main__":
    main()
