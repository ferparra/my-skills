#!/usr/bin/env python3
"""
Evaluation harness for Excalidraw validation optimization.
READ-ONLY — the agent must never modify this file.
"""
from __future__ import annotations

from typing import Callable

# ── Contract constants ───────────────────────────────────────────────────────
TIME_BUDGET = 30  # seconds
METRIC_NAME = "validation_error_rate"  # lower is better (0.0 = perfect)

# ── Element factory helpers ──────────────────────────────────────────────────

_NEXT_SEED = 0


def _seed() -> int:
    """Generate monotonic seed values."""
    global _NEXT_SEED
    _NEXT_SEED += 1
    return _NEXT_SEED


def make_rect(id: str, x: float, y: float, w: float, h: float, **overrides) -> dict:
    """Create a rectangle element with sensible defaults."""
    return {
        "id": id,
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#1E1E1E",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "boundElements": [],
        "seed": _seed(),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        **overrides,
    }


def make_text(
    id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    container_id: str | None = None,
    **overrides,
) -> dict:
    """Create a text element with sensible defaults."""
    return {
        "id": id,
        "type": "text",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#1E1E1E",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "boundElements": [],
        "text": text,
        "originalText": text,
        "fontSize": 20,
        "fontFamily": 3,
        "textAlign": "center",
        "verticalAlign": "middle",
        "lineHeight": 1.25,
        "baseline": 18,
        "containerId": container_id,
        "seed": _seed(),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        **overrides,
    }


def make_arrow(
    id: str,
    x: float,
    y: float,
    points: list,
    start_binding: dict | None = None,
    end_binding: dict | None = None,
    **overrides,
) -> dict:
    """Create an arrow element with sensible defaults."""
    return {
        "id": id,
        "type": "arrow",
        "x": x,
        "y": y,
        "width": 0,  # Computed from points
        "height": 0,
        "angle": 0,
        "strokeColor": "#1E1E1E",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "boundElements": [],
        "points": points,
        "startBinding": start_binding,
        "endBinding": end_binding,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "lastCommittedPoint": None,
        "seed": _seed(),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        **overrides,
    }


# ── Ground-truth test suite ──────────────────────────────────────────────────
# Each entry: (name, elements, expected_error_substrings, expected_warning_substrings)

TEST_CASES: list[tuple[str, list[dict], list[str], list[str]]] = [
    # ── Schema validation group ──────────────────────────────────────────────
    (
        "valid_drawing",
        [
            make_rect("rect1", 100, 100, 200, 100, boundElements=[{"id": "text1", "type": "text"}]),
            make_text("text1", 150, 120, 100, 60, "Box 1", container_id="rect1"),
            make_rect("rect2", 400, 100, 200, 100),
            make_arrow(
                "arrow1",
                310,
                150,
                [[0, 0], [80, 0]],
                start_binding={"elementId": "rect1", "focus": 0, "gap": 10},
                end_binding={"elementId": "rect2", "focus": 0, "gap": 10},
            ),
        ],
        [],  # no errors
        [],  # no warnings
    ),
    (
        "duplicate_ids",
        [
            make_rect("dup", 100, 100, 100, 100),
            make_rect("dup", 300, 100, 100, 100),
        ],
        ["Duplicate"],
        [],
    ),
    (
        "text_broken_container",
        [
            make_rect("rect1", 100, 100, 200, 100),
            make_text("text1", 150, 120, 100, 60, "Orphan text", container_id="nonexistent"),
        ],
        ["containerId"],
        [],
    ),
    (
        "arrow_broken_start",
        [
            make_rect("rect1", 100, 100, 100, 100),
            make_arrow(
                "arrow1",
                210,
                150,
                [[0, 0], [100, 0]],
                start_binding={"elementId": "nonexistent", "focus": 0, "gap": 10},
                end_binding={"elementId": "rect1", "focus": 0, "gap": 10},
            ),
        ],
        ["startBinding"],
        [],
    ),
    (
        "bidirectional_mismatch",
        [
            make_rect("rect1", 100, 100, 200, 100, boundElements=[{"id": "text1", "type": "text"}]),
            make_text("text1", 150, 120, 100, 60, "Wrong link", container_id="rect2"),
            make_rect("rect2", 400, 100, 200, 100),
        ],
        ["bidirectional"],
        [],
    ),
    (
        "zero_dimension",
        [
            make_rect("rect1", 100, 100, 0, 100),
        ],
        [],
        ["zero"],
    ),
    (
        "text_original_mismatch",
        [
            make_text("text1", 100, 100, 150, 40, "Wrapped text", originalText="Original different text"),
        ],
        [],
        ["originalText"],
    ),
    (
        "invalid_color",
        [
            make_rect("rect1", 100, 100, 100, 100, strokeColor="rgb(255,0,0)"),
        ],
        [],
        ["color"],
    ),
    (
        "orphaned_group",
        [
            make_rect("rect1", 100, 100, 100, 100, groupIds=["g1"]),
        ],
        [],
        ["orphan"],
    ),
    (
        "valid_colors",
        [
            make_rect("rect1", 100, 100, 100, 100, strokeColor="#FF0000", backgroundColor="#00FF00"),
            make_rect("rect2", 400, 100, 100, 100, strokeColor="#0000FF", backgroundColor="transparent"),
        ],
        [],
        [],
    ),
    (
        "invalid_fill_style",
        [
            make_rect("rect1", 100, 100, 100, 100, fillStyle="zigzag"),
        ],
        ["fillStyle"],
        [],
    ),
    (
        "invalid_stroke_style",
        [
            make_rect("rect1", 100, 100, 100, 100, strokeStyle="wavy"),
        ],
        ["strokeStyle"],
        [],
    ),
    (
        "opacity_out_of_range",
        [
            make_rect("rect1", 100, 100, 100, 100, opacity=150),
        ],
        ["opacity"],
        [],
    ),
    (
        "roughness_out_of_range",
        [
            make_rect("rect1", 100, 100, 100, 100, roughness=5),
        ],
        ["roughness"],
        [],
    ),
    (
        "invalid_font_family",
        [
            make_text("text1", 100, 100, 150, 40, "Bad font", fontFamily=99),
        ],
        ["fontFamily"],
        [],
    ),
    (
        "arrow_points_bad",
        [
            make_rect("rect1", 100, 100, 100, 100),
            make_arrow("arrow1", 100, 100, [[0, 0, 7], [100, 50, 3]]),
        ],
        ["points"],
        [],
    ),
    (
        "deleted_broken_binding",
        [
            make_rect("rect1", 100, 100, 200, 100),
            make_text("text1", 150, 120, 100, 60, "Deleted", container_id="nonexistent", isDeleted=True),
        ],
        [],  # No errors — isDeleted elements should be filtered
        [],
    ),
    # ── Visual validation group ──────────────────────────────────────────────
    (
        "well_spaced",
        [
            make_rect("rect1", 100, 100, 100, 100),
            make_rect("rect2", 700, 100, 100, 100),
            make_rect("rect3", 400, 500, 100, 100),
        ],
        [],
        [],
    ),
    (
        "elements_overlap",
        [
            make_rect("rect1", 100, 100, 200, 100),  # x: 100-300
            make_rect("rect2", 200, 100, 200, 100),  # x: 200-400 → 100px overlap = 50%
        ],
        [],
        ["overlap"],
    ),
    (
        "text_in_container_no_overlap",
        [
            make_rect("rect1", 100, 100, 200, 100, boundElements=[{"id": "text1", "type": "text"}]),
            make_text("text1", 150, 120, 100, 60, "Inside", container_id="rect1"),
        ],
        [],
        [],  # Should NOT flag overlap
    ),
    (
        "text_overflows",
        [
            make_rect("rect1", 100, 100, 100, 60, boundElements=[{"id": "text1", "type": "text"}]),
            make_text("text1", 110, 110, 150, 40, "Too wide", container_id="rect1"),
        ],
        ["overflow"],
        [],
    ),
    (
        "text_fits",
        [
            make_rect("rect1", 100, 100, 100, 60, boundElements=[{"id": "text1", "type": "text"}]),
            make_text("text1", 110, 110, 60, 40, "Fits", container_id="rect1"),
        ],
        [],
        [],
    ),
    (
        "arrow_far_from_target",
        [
            make_rect("rect1", 100, 100, 100, 100),
            make_arrow(
                "arrow1",
                250,
                150,
                [[0, 0], [100, 0]],
                start_binding={"elementId": "rect1", "focus": 0, "gap": 10},
            ),
        ],
        ["arrow"],
        [],
    ),
    (
        "arrow_on_target",
        [
            make_rect("rect1", 100, 100, 100, 100),
            make_arrow(
                "arrow1",
                200,
                150,
                [[0, 0], [100, 0]],
                start_binding={"elementId": "rect1", "focus": 0, "gap": 10},
            ),
        ],
        [],
        [],
    ),
    (
        "poor_spacing",
        [
            make_rect("rect1", 100, 100, 100, 100),
            make_rect("rect2", 220, 100, 100, 100),  # 20px gap
            make_rect("rect3", 500, 100, 100, 100),  # 180px gap
            make_rect("rect4", 750, 100, 100, 100),  # 150px gap
        ],
        [],
        ["spacing", "CV"],  # Either substring acceptable
    ),
    (
        "balanced_composition",
        [
            make_rect("rect1", 100, 100, 100, 100),  # NW
            make_rect("rect2", 500, 100, 100, 100),  # NE
            make_rect("rect3", 100, 400, 100, 100),  # SW
            make_rect("rect4", 500, 400, 100, 100),  # SE
        ],
        [],
        [],
    ),
    (
        "skewed_composition",
        [
            make_rect("rect1", 100, 100, 50, 50),
            make_rect("rect2", 170, 100, 50, 50),
            make_rect("rect3", 100, 170, 50, 50),
            make_rect("rect4", 170, 170, 50, 50),
            make_rect("rect5", 240, 100, 50, 50),
        ],
        [],
        ["quadrant", "skew"],  # Either substring
    ),
    (
        "single_size_tier",
        [
            make_rect("rect1", 100, 100, 100, 100),  # 10000 area
            make_rect("rect2", 400, 100, 100, 100),
            make_rect("rect3", 100, 400, 100, 100),
            make_rect("rect4", 400, 400, 100, 100),
        ],
        [],
        ["tier"],
    ),
    (
        "multiple_size_tiers",
        [
            make_rect("hero", 100, 100, 300, 150),  # 45000 area (hero)
            make_rect("small1", 500, 100, 60, 40),  # 2400 area (small)
            make_rect("small2", 600, 100, 60, 40),
            make_rect("small3", 700, 100, 60, 40),
        ],
        [],
        [],
    ),
    (
        "dangling_arrow",
        [
            make_arrow("arrow1", 100, 100, [[0, 0], [100, 0]]),  # No bindings
        ],
        [],
        ["dangling", "no binding"],  # Either substring
    ),
    (
        "arrow_crosses_element",
        [
            make_rect("rect1", 100, 100, 100, 100),
            make_rect("rect2", 500, 100, 100, 100),
            make_rect("obstacle", 280, 130, 80, 40),  # In the path between rect1 and rect2
            make_arrow(
                "arrow1",
                200,
                150,
                [[0, 0], [300, 0]],
                start_binding={"elementId": "rect1", "focus": 0, "gap": 10},
                end_binding={"elementId": "rect2", "focus": 0, "gap": 10},
            ),
        ],
        [],
        ["cross"],
    ),
]


# ── Evaluation function ──────────────────────────────────────────────────────


def evaluate(
    validate_fn: Callable[[list[dict]], tuple[list[str], list[str]]],
    verbose: bool = False,
) -> float:
    """
    Run validate_fn on all test cases and return error rate.

    A test case is correct if:
    - All expected error substrings found in actual errors
    - No unexpected actual errors
    - All expected warning substrings found in actual warnings
    - No unexpected actual warnings

    Returns:
        validation_error_rate: 1 - (correct / total)
    """
    correct = 0
    total = len(TEST_CASES)

    for name, elements, expected_errors, expected_warnings in TEST_CASES:
        actual_errors, actual_warnings = validate_fn(elements)

        # Check errors
        errors_match = _check_matches(expected_errors, actual_errors)
        warnings_match = _check_matches(expected_warnings, actual_warnings)

        is_correct = errors_match and warnings_match

        if is_correct:
            correct += 1

        if verbose:
            status = "PASS" if is_correct else "FAIL"
            print(f"[{status}] {name}")
            if not is_correct:
                if not errors_match:
                    print(f"  Expected errors: {expected_errors}")
                    print(f"  Actual errors:   {actual_errors}")
                if not warnings_match:
                    print(f"  Expected warnings: {expected_warnings}")
                    print(f"  Actual warnings:   {actual_warnings}")

    if verbose:
        print(f"\n=== Validation evaluation ({correct}/{total} correct) ===")

    return 1 - (correct / total)


def _check_matches(expected_substrings: list[str], actual_messages: list[str]) -> bool:
    """
    Check if expected substrings match actual messages.

    A match means:
    - Every expected substring appears in at least one actual message
    - Every actual message contains at least one expected substring (or expected is empty)
    """
    # If no expectations, actual must be empty
    if not expected_substrings:
        return len(actual_messages) == 0

    # Every expected substring must match at least one actual
    for expected in expected_substrings:
        if not any(expected in actual for actual in actual_messages):
            return False

    # Every actual must match at least one expected
    for actual in actual_messages:
        if not any(expected in actual for expected in expected_substrings):
            return False

    return True
