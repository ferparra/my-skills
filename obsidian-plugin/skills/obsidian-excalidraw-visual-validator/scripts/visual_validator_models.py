#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from visual_validator_config import VisualValidatorConfig

# Import from drawing-manager skill using importlib (same pattern as router_models.py)
DRAWING_MANAGER_MODELS_PATH = (
    Path(__file__).parent.parent.parent
    / "obsidian-excalidraw-drawing-manager"
    / "scripts"
    / "excalidraw_models.py"
)


def _import_drawing_manager_models() -> Any:
    """Import excalidraw_models from drawing-manager skill."""
    import importlib.util
    import sys

    existing_module = sys.modules.get("_excalidraw_models")
    if existing_module is not None:
        return existing_module

    spec = importlib.util.spec_from_file_location(
        "_excalidraw_models", DRAWING_MANAGER_MODELS_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load drawing manager models from {DRAWING_MANAGER_MODELS_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Load the actual module
_dm = _import_drawing_manager_models()

# Export classes and functions directly from drawing manager
# Note: mypy cannot see these types through the dynamic import, so type: ignore where needed
BaseElement: Any = _dm.BaseElement
TextElement: Any = _dm.TextElement
ArrowElement: Any = _dm.ArrowElement
LineElement: Any = _dm.LineElement
FreedrawElement: Any = _dm.FreedrawElement
RectangleElement: Any = _dm.RectangleElement
ExcalidrawElement: Any = _dm.ExcalidrawElement
ElementType: Any = _dm.ElementType
Binding: Any = _dm.Binding

extract_excalidraw_json = _dm.extract_excalidraw_json
load_markdown_note = _dm.load_markdown_note
parse_drawing = _dm.parse_drawing
dump_json = _dm.dump_json


# Geometry models


class BBox(BaseModel):
    """Axis-aligned bounding box."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def area(self) -> float:
        return abs(self.width * self.height)

    def intersects(self, other: BBox) -> bool:
        """Check if this bbox intersects another."""
        return not (
            self.x2 < other.x
            or self.x > other.x2
            or self.y2 < other.y
            or self.y > other.y2
        )

    def intersection_area(self, other: BBox) -> float:
        """Compute intersection area with another bbox."""
        if not self.intersects(other):
            return 0.0
        x_overlap = min(self.x2, other.x2) - max(self.x, other.x)
        y_overlap = min(self.y2, other.y2) - max(self.y, other.y)
        return x_overlap * y_overlap


class VisualAuditResult(BaseModel):
    """Result of visual validation for a single file."""

    model_config = ConfigDict(extra="forbid")

    path: str
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    element_count: int = 0
    render_path: str | None = None


# Geometry computation


def compute_bbox(element: BaseElement) -> BBox:
    """Compute bounding box for an element, handling points arrays for arrows/lines."""
    # For arrows, lines, and freedraw, use points array
    if hasattr(element, "points") and element.points:
        xs = [element.x + p[0] for p in element.points]
        ys = [element.y + p[1] for p in element.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)

    # For other elements, use x, y, width, height
    return BBox(x=element.x, y=element.y, width=element.width, height=element.height)


def compute_global_bbox(elements: Sequence[ExcalidrawElement]) -> BBox:
    """Compute global bounding box spanning all elements."""
    if not elements:
        return BBox(x=0, y=0, width=800, height=600)

    bboxes = [compute_bbox(el) for el in elements if not getattr(el, "isDeleted", False)]
    if not bboxes:
        return BBox(x=0, y=0, width=800, height=600)

    min_x = min(bb.x for bb in bboxes)
    min_y = min(bb.y for bb in bboxes)
    max_x = max(bb.x2 for bb in bboxes)
    max_y = max(bb.y2 for bb in bboxes)

    return BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)


# Geometric checks


def check_overlaps(
    elements: Sequence[ExcalidrawElement], config: VisualValidatorConfig
) -> tuple[list[str], list[str]]:
    """Check for overlapping elements."""
    errors: list[str] = []
    warnings: list[str] = []

    # Filter non-deleted elements
    active_elements = [el for el in elements if not getattr(el, "isDeleted", False)]

    # Compute bboxes
    bboxes_with_ids: list[tuple[str, BBox]] = [
        (el.id, compute_bbox(el)) for el in active_elements
    ]

    # Pairwise overlap check
    for i, (id_a, bb_a) in enumerate(bboxes_with_ids):
        for id_b, bb_b in bboxes_with_ids[i + 1 :]:
            if bb_a.intersects(bb_b):
                overlap_area = bb_a.intersection_area(bb_b)
                smaller_area = min(bb_a.area, bb_b.area)
                overlap_ratio = overlap_area / smaller_area if smaller_area > 0 else 0

                if overlap_ratio > config.max_overlap_ratio:
                    msg = (
                        f"Elements {id_a} and {id_b} overlap by {overlap_ratio:.1%} "
                        f"(threshold: {config.max_overlap_ratio:.1%})"
                    )
                    if config.overlap_is_error:
                        errors.append(msg)
                    else:
                        warnings.append(msg)

    return errors, warnings


def check_spacing(
    elements: Sequence[ExcalidrawElement], config: VisualValidatorConfig
) -> tuple[list[str], list[str]]:
    """Check spacing consistency between elements."""
    errors: list[str] = []
    warnings: list[str] = []

    active_elements = [el for el in elements if not getattr(el, "isDeleted", False)]
    if len(active_elements) < 2:
        return errors, warnings

    bboxes_with_ids: list[tuple[str, BBox]] = [
        (el.id, compute_bbox(el)) for el in active_elements
    ]

    # Compute nearest neighbor distances
    gaps: list[float] = []
    close_pairs: list[tuple[str, str, float]] = []

    for i, (id_a, bb_a) in enumerate(bboxes_with_ids):
        min_gap = float("inf")
        for j, (id_b, bb_b) in enumerate(bboxes_with_ids):
            if i == j:
                continue
            # Compute gap (negative if overlapping)
            dx = max(0, max(bb_a.x, bb_b.x) - min(bb_a.x2, bb_b.x2))
            dy = max(0, max(bb_a.y, bb_b.y) - min(bb_a.y2, bb_b.y2))
            gap = sqrt(dx**2 + dy**2)
            if gap < min_gap:
                min_gap = gap

        gaps.append(min_gap)

        if min_gap < config.min_element_gap_px:
            # Find which neighbor it was
            for id_b, bb_b in bboxes_with_ids:
                if id_a == id_b:
                    continue
                dx = max(0, max(bb_a.x, bb_b.x) - min(bb_a.x2, bb_b.x2))
                dy = max(0, max(bb_a.y, bb_b.y) - min(bb_a.y2, bb_b.y2))
                gap = sqrt(dx**2 + dy**2)
                if abs(gap - min_gap) < 1e-6:
                    close_pairs.append((id_a, id_b, min_gap))
                    break

    # Compute coefficient of variation
    if len(gaps) >= 2:
        mean_gap = mean(gaps)
        std_gap = stdev(gaps)
        cv = std_gap / mean_gap if mean_gap > 0 else 0

        if cv > config.max_spacing_cv:
            msg = (
                f"Spacing consistency poor: CV={cv:.2f} (threshold: {config.max_spacing_cv:.2f}). "
                f"Mean gap: {mean_gap:.1f}px, StdDev: {std_gap:.1f}px"
            )
            if config.spacing_is_error:
                errors.append(msg)
            else:
                warnings.append(msg)

    # Report close pairs
    for id_a, id_b, gap in close_pairs:
        msg = f"Elements {id_a} and {id_b} are very close: {gap:.1f}px (min: {config.min_element_gap_px:.1f}px)"
        warnings.append(msg)

    return errors, warnings


def check_text_overflow(
    elements: Sequence[ExcalidrawElement], config: VisualValidatorConfig
) -> tuple[list[str], list[str]]:
    """Check for text overflow in containers."""
    errors: list[str] = []
    warnings: list[str] = []

    # Build element index
    element_index = {el.id: el for el in elements if not getattr(el, "isDeleted", False)}

    # Check each text element with a containerId
    for el in elements:
        if not isinstance(el, TextElement):
            continue
        if getattr(el, "isDeleted", False):
            continue
        if not el.containerId:
            continue

        container = element_index.get(el.containerId)
        if not container:
            continue  # Broken binding, caught by drawing-manager

        # Text element's width is the rendered width
        text_width = el.width
        container_width = container.width
        available_width = container_width - 2 * config.text_padding_px

        if text_width > available_width:
            overflow = text_width - available_width
            msg = (
                f"Text element {el.id} overflows container {el.containerId} by {overflow:.1f}px "
                f"(text width: {text_width:.1f}px, available: {available_width:.1f}px)"
            )
            if config.text_overflow_is_error:
                errors.append(msg)
            else:
                warnings.append(msg)

    return errors, warnings


def check_arrow_accuracy(
    elements: Sequence[ExcalidrawElement], config: VisualValidatorConfig
) -> tuple[list[str], list[str]]:
    """Check arrow endpoint accuracy (do arrows land on target bboxes?)."""
    errors: list[str] = []
    warnings: list[str] = []

    # Build element index with bboxes
    element_bboxes = {
        el.id: compute_bbox(el)
        for el in elements
        if not getattr(el, "isDeleted", False)
    }

    # Check each arrow
    for el in elements:
        if not isinstance(el, ArrowElement):
            continue
        if getattr(el, "isDeleted", False):
            continue
        if not el.points or len(el.points) < 2:
            continue

        # Check start binding
        if el.startBinding:
            target_bbox = element_bboxes.get(el.startBinding.elementId)
            if target_bbox:
                # Arrow start point is (x + points[0][0], y + points[0][1])
                arrow_x = el.x + el.points[0][0]
                arrow_y = el.y + el.points[0][1]
                distance = _point_to_bbox_distance(arrow_x, arrow_y, target_bbox)

                if distance > config.arrow_snap_tolerance_px:
                    msg = (
                        f"Arrow {el.id} start point is {distance:.1f}px from target {el.startBinding.elementId} "
                        f"(tolerance: {config.arrow_snap_tolerance_px:.1f}px)"
                    )
                    if config.arrow_accuracy_is_error:
                        errors.append(msg)
                    else:
                        warnings.append(msg)

        # Check end binding
        if el.endBinding:
            target_bbox = element_bboxes.get(el.endBinding.elementId)
            if target_bbox:
                # Arrow end point is (x + points[-1][0], y + points[-1][1])
                arrow_x = el.x + el.points[-1][0]
                arrow_y = el.y + el.points[-1][1]
                distance = _point_to_bbox_distance(arrow_x, arrow_y, target_bbox)

                if distance > config.arrow_snap_tolerance_px:
                    msg = (
                        f"Arrow {el.id} end point is {distance:.1f}px from target {el.endBinding.elementId} "
                        f"(tolerance: {config.arrow_snap_tolerance_px:.1f}px)"
                    )
                    if config.arrow_accuracy_is_error:
                        errors.append(msg)
                    else:
                        warnings.append(msg)

    return errors, warnings


def _point_to_bbox_distance(px: float, py: float, bbox: BBox) -> float:
    """Compute distance from point to bbox (0 if inside)."""
    dx = max(bbox.x - px, 0, px - bbox.x2)
    dy = max(bbox.y - py, 0, py - bbox.y2)
    return sqrt(dx**2 + dy**2)


def check_composition(
    elements: Sequence[ExcalidrawElement], config: VisualValidatorConfig
) -> tuple[list[str], list[str]]:
    """Check composition balance (center of mass, quadrant distribution)."""
    errors: list[str] = []
    warnings: list[str] = []

    active_elements = [el for el in elements if not getattr(el, "isDeleted", False)]
    if len(active_elements) < 4:
        return errors, warnings  # Too few elements to judge composition

    # Compute global bbox
    global_bbox = compute_global_bbox(active_elements)
    canvas_center = global_bbox.center

    # Compute center of mass
    total_area = 0.0
    weighted_x = 0.0
    weighted_y = 0.0

    for el in active_elements:
        bbox = compute_bbox(el)
        area = bbox.area
        cx, cy = bbox.center
        total_area += area
        weighted_x += cx * area
        weighted_y += cy * area

    if total_area > 0:
        center_of_mass = (weighted_x / total_area, weighted_y / total_area)
    else:
        center_of_mass = canvas_center

    # Compute center offset (normalized by canvas size)
    com_offset_x = abs(center_of_mass[0] - canvas_center[0]) / (global_bbox.width / 2)
    com_offset_y = abs(center_of_mass[1] - canvas_center[1]) / (global_bbox.height / 2)
    max_offset = max(com_offset_x, com_offset_y)

    if max_offset > config.max_center_of_mass_offset:
        warnings.append(
            f"Composition unbalanced: center of mass offset {max_offset:.1%} "
            f"(threshold: {config.max_center_of_mass_offset:.1%})"
        )

    # Quadrant distribution
    quadrants = {"NW": 0, "NE": 0, "SW": 0, "SE": 0}
    for el in active_elements:
        bbox = compute_bbox(el)
        cx, cy = bbox.center
        if cx < canvas_center[0]:
            quad_x = "W"
        else:
            quad_x = "E"
        if cy < canvas_center[1]:
            quad_y = "N"
        else:
            quad_y = "S"
        quadrants[quad_y + quad_x] += 1

    total_elements = len(active_elements)
    max_quadrant_count = max(quadrants.values())
    max_quadrant_fraction = max_quadrant_count / total_elements

    if max_quadrant_fraction > config.max_quadrant_skew:
        warnings.append(
            f"Composition skewed: {max_quadrant_fraction:.1%} of elements in one quadrant "
            f"(threshold: {config.max_quadrant_skew:.1%})"
        )

    return errors, warnings


def check_size_hierarchy(
    elements: Sequence[ExcalidrawElement], config: VisualValidatorConfig
) -> tuple[list[str], list[str]]:
    """Check for size hierarchy (distinct size tiers)."""
    errors: list[str] = []
    warnings: list[str] = []

    active_elements = [el for el in elements if not getattr(el, "isDeleted", False)]
    if len(active_elements) < 3:
        return errors, warnings

    # Compute areas
    areas = [compute_bbox(el).area for el in active_elements]
    unique_areas = set(areas)

    # Cluster into tiers using simple thresholds (from coleam00)
    # Hero: 300x150 = 45000, Primary: 180x90 = 16200, Secondary: 120x60 = 7200, Small: 60x40 = 2400
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

    if distinct_tiers < config.min_size_tiers:
        warnings.append(
            f"Size hierarchy weak: only {distinct_tiers} distinct tier(s) "
            f"(min: {config.min_size_tiers}). All elements similar size."
        )

    return errors, warnings


# All checks registry
ALL_CHECKS = [
    check_overlaps,
    check_spacing,
    check_text_overflow,
    check_arrow_accuracy,
    check_composition,
    check_size_hierarchy,
]


def validate_visual(
    elements: Sequence[ExcalidrawElement], config: VisualValidatorConfig
) -> tuple[list[str], list[str]]:
    """Run all visual validation checks."""
    all_errors: list[str] = []
    all_warnings: list[str] = []

    for check_fn in ALL_CHECKS:
        errors, warnings = check_fn(elements, config)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    return all_errors, all_warnings
