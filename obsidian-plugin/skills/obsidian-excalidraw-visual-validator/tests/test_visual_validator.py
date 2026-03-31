#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from visual_validator_config import VisualValidatorConfig
from visual_validator_models import (
    BBox,
    ElementType,
    RectangleElement,
    TextElement,
    ArrowElement,
    Binding,
    check_arrow_accuracy,
    check_composition,
    check_overlaps,
    check_size_hierarchy,
    check_spacing,
    check_text_overflow,
    compute_bbox,
)


class TestBBox:
    def test_bbox_properties(self) -> None:
        """BBox computed properties work correctly."""
        bb = BBox(x=100, y=200, width=150, height=80)
        assert bb.x2 == 250
        assert bb.y2 == 280
        assert bb.center == (175.0, 240.0)
        assert bb.area == 12000

    def test_bbox_intersection(self) -> None:
        """BBox intersection detection."""
        bb1 = BBox(x=0, y=0, width=100, height=100)
        bb2 = BBox(x=50, y=50, width=100, height=100)
        bb3 = BBox(x=200, y=200, width=50, height=50)

        assert bb1.intersects(bb2)
        assert bb2.intersects(bb1)
        assert not bb1.intersects(bb3)
        assert bb1.intersection_area(bb2) == 2500  # 50x50 overlap


class TestComputeBBox:
    def test_compute_bbox_rectangle(self) -> None:
        """Compute bbox for simple rectangle."""
        rect = RectangleElement(
            id="r1",
            type=ElementType.RECTANGLE,
            x=100,
            y=200,
            width=150,
            height=80,
            seed=1,
            version=1,
            versionNonce=1,
        )
        bb = compute_bbox(rect)
        assert bb.x == 100
        assert bb.y == 200
        assert bb.width == 150
        assert bb.height == 80

    def test_compute_bbox_arrow(self) -> None:
        """Compute bbox for arrow with points array."""
        arrow = ArrowElement(
            id="a1",
            type=ElementType.ARROW,
            x=100,
            y=100,
            width=200,
            height=50,
            points=[[0, 0], [100, 25], [200, 50]],
            seed=1,
            version=1,
            versionNonce=1,
        )
        bb = compute_bbox(arrow)
        # Points are relative to (x, y)
        assert bb.x == 100  # min x: 100 + 0
        assert bb.y == 100  # min y: 100 + 0
        assert bb.width == 200  # 300 - 100
        assert bb.height == 50  # 150 - 100


class TestOverlapDetection:
    def test_no_overlap(self) -> None:
        """Non-overlapping elements pass."""
        config = VisualValidatorConfig()
        elements = [
            RectangleElement(
                id="r1",
                type=ElementType.RECTANGLE,
                x=0,
                y=0,
                width=100,
                height=100,
                seed=1,
                version=1,
                versionNonce=1,
            ),
            RectangleElement(
                id="r2",
                type=ElementType.RECTANGLE,
                x=150,
                y=0,
                width=100,
                height=100,
                seed=2,
                version=1,
                versionNonce=1,
            ),
        ]
        errors, warnings = check_overlaps(elements, config)
        assert not errors
        assert not warnings

    def test_overlap_detected(self) -> None:
        """Overlapping elements are detected."""
        config = VisualValidatorConfig(max_overlap_ratio=0.15, overlap_is_error=False)
        elements = [
            RectangleElement(
                id="r1",
                type=ElementType.RECTANGLE,
                x=0,
                y=0,
                width=100,
                height=100,
                seed=1,
                version=1,
                versionNonce=1,
            ),
            RectangleElement(
                id="r2",
                type=ElementType.RECTANGLE,
                x=50,
                y=0,
                width=100,
                height=100,
                seed=2,
                version=1,
                versionNonce=1,
            ),
        ]
        errors, warnings = check_overlaps(elements, config)
        # Overlap is 50x100 = 5000 out of 10000 = 50% > 15%
        assert not errors  # overlap_is_error=False
        assert len(warnings) == 1
        assert "r1" in warnings[0] and "r2" in warnings[0]


class TestSpacingConsistency:
    def test_spacing_uniform(self) -> None:
        """Uniformly spaced elements pass."""
        config = VisualValidatorConfig(max_spacing_cv=0.5, min_element_gap_px=20.0)
        # 3 elements with consistent 50px gaps
        elements = [
            RectangleElement(
                id=f"r{i}",
                type=ElementType.RECTANGLE,
                x=i * 150,
                y=0,
                width=100,
                height=100,
                seed=i,
                version=1,
                versionNonce=1,
            )
            for i in range(3)
        ]
        errors, warnings = check_spacing(elements, config)
        assert not errors
        # May have warnings if gaps < 20px, but our 50px gaps are fine

    def test_spacing_poor(self) -> None:
        """Inconsistent spacing is flagged."""
        config = VisualValidatorConfig(max_spacing_cv=0.3, min_element_gap_px=20.0)
        # Very inconsistent: 10px, 100px gaps
        elements = [
            RectangleElement(
                id="r1",
                type=ElementType.RECTANGLE,
                x=0,
                y=0,
                width=100,
                height=100,
                seed=1,
                version=1,
                versionNonce=1,
            ),
            RectangleElement(
                id="r2",
                type=ElementType.RECTANGLE,
                x=110,  # 10px gap
                y=0,
                width=100,
                height=100,
                seed=2,
                version=1,
                versionNonce=1,
            ),
            RectangleElement(
                id="r3",
                type=ElementType.RECTANGLE,
                x=310,  # 100px gap
                y=0,
                width=100,
                height=100,
                seed=3,
                version=1,
                versionNonce=1,
            ),
        ]
        errors, warnings = check_spacing(elements, config)
        # High CV expected
        assert warnings  # Should flag spacing inconsistency


class TestTextOverflow:
    def test_text_overflow_ok(self) -> None:
        """Text fits in container."""
        config = VisualValidatorConfig(text_padding_px=10.0)
        container = RectangleElement(
            id="c1",
            type=ElementType.RECTANGLE,
            x=100,
            y=100,
            width=200,
            height=60,
            seed=1,
            version=1,
            versionNonce=1,
            boundElements=[{"id": "t1", "type": "text"}],
        )
        text = TextElement(
            id="t1",
            type=ElementType.TEXT,
            x=110,
            y=120,
            width=100,  # 200 - 2*10 = 180 available, so 100 fits
            height=25,
            text="Short",
            originalText="Short",
            fontSize=20,
            fontFamily=3,
            textAlign="left",
            verticalAlign="top",
            lineHeight=1.25,
            containerId="c1",
            seed=2,
            version=1,
            versionNonce=1,
        )
        errors, warnings = check_text_overflow([container, text], config)
        assert not errors
        assert not warnings

    def test_text_overflow_detected(self) -> None:
        """Text overflow is detected."""
        config = VisualValidatorConfig(text_padding_px=10.0, text_overflow_is_error=True)
        container = RectangleElement(
            id="c1",
            type=ElementType.RECTANGLE,
            x=100,
            y=100,
            width=100,
            height=60,
            seed=1,
            version=1,
            versionNonce=1,
            boundElements=[{"id": "t1", "type": "text"}],
        )
        text = TextElement(
            id="t1",
            type=ElementType.TEXT,
            x=110,
            y=120,
            width=150,  # 100 - 2*10 = 80 available, so 150 overflows by 70px
            height=25,
            text="Very long text",
            originalText="Very long text",
            fontSize=20,
            fontFamily=3,
            textAlign="left",
            verticalAlign="top",
            lineHeight=1.25,
            containerId="c1",
            seed=2,
            version=1,
            versionNonce=1,
        )
        errors, warnings = check_text_overflow([container, text], config)
        assert len(errors) == 1
        assert "overflows" in errors[0]


class TestArrowAccuracy:
    def test_arrow_accuracy_good(self) -> None:
        """Arrow endpoint within tolerance of target."""
        config = VisualValidatorConfig(arrow_snap_tolerance_px=15.0)
        target = RectangleElement(
            id="target",
            type=ElementType.RECTANGLE,
            x=200,
            y=100,
            width=100,
            height=100,
            seed=1,
            version=1,
            versionNonce=1,
        )
        arrow = ArrowElement(
            id="arrow1",
            type=ElementType.ARROW,
            x=100,
            y=150,
            width=100,
            height=0,
            points=[[0, 0], [100, 0]],  # End at (200, 150), which is on target's left edge
            endBinding=Binding(elementId="target", focus=0.0, gap=10.0),
            seed=2,
            version=1,
            versionNonce=1,
        )
        errors, warnings = check_arrow_accuracy([target, arrow], config)
        assert not errors  # Endpoint (200, 150) is on target bbox

    def test_arrow_accuracy_bad(self) -> None:
        """Arrow endpoint far from target."""
        config = VisualValidatorConfig(
            arrow_snap_tolerance_px=15.0, arrow_accuracy_is_error=True
        )
        target = RectangleElement(
            id="target",
            type=ElementType.RECTANGLE,
            x=300,
            y=100,
            width=100,
            height=100,
            seed=1,
            version=1,
            versionNonce=1,
        )
        arrow = ArrowElement(
            id="arrow1",
            type=ElementType.ARROW,
            x=100,
            y=150,
            width=150,
            height=0,
            points=[[0, 0], [150, 0]],  # End at (250, 150), 50px from target
            endBinding=Binding(elementId="target", focus=0.0, gap=10.0),
            seed=2,
            version=1,
            versionNonce=1,
        )
        errors, warnings = check_arrow_accuracy([target, arrow], config)
        assert len(errors) == 1
        assert "50.0px" in errors[0]


class TestComposition:
    def test_composition_balanced(self) -> None:
        """Balanced composition passes."""
        config = VisualValidatorConfig(
            max_quadrant_skew=0.7, max_center_of_mass_offset=0.3
        )
        # 4 elements in each quadrant
        elements = [
            RectangleElement(
                id=f"r{i}",
                type=ElementType.RECTANGLE,
                x=100 * (i % 2),
                y=100 * (i // 2),
                width=50,
                height=50,
                seed=i,
                version=1,
                versionNonce=1,
            )
            for i in range(4)
        ]
        errors, warnings = check_composition(elements, config)
        assert not errors
        # Should be balanced

    def test_composition_skewed(self) -> None:
        """Skewed composition is flagged."""
        config = VisualValidatorConfig(max_quadrant_skew=0.5)
        # All 5 elements in one area
        elements = [
            RectangleElement(
                id=f"r{i}",
                type=ElementType.RECTANGLE,
                x=i * 60,
                y=0,
                width=50,
                height=50,
                seed=i,
                version=1,
                versionNonce=1,
            )
            for i in range(5)
        ]
        errors, warnings = check_composition(elements, config)
        assert warnings  # Should flag quadrant skew


class TestSizeHierarchy:
    def test_size_hierarchy_varied(self) -> None:
        """Multiple size tiers present."""
        config = VisualValidatorConfig(min_size_tiers=2)
        elements = [
            RectangleElement(
                id="hero",
                type=ElementType.RECTANGLE,
                x=0,
                y=0,
                width=300,
                height=150,  # 45000 area
                seed=1,
                version=1,
                versionNonce=1,
            ),
            RectangleElement(
                id="small",
                type=ElementType.RECTANGLE,
                x=400,
                y=0,
                width=60,
                height=40,  # 2400 area
                seed=2,
                version=1,
                versionNonce=1,
            ),
        ]
        errors, warnings = check_size_hierarchy(elements, config)
        assert not warnings  # 2 tiers present

    def test_size_hierarchy_uniform(self) -> None:
        """All same size triggers warning."""
        config = VisualValidatorConfig(min_size_tiers=2)
        elements = [
            RectangleElement(
                id=f"r{i}",
                type=ElementType.RECTANGLE,
                x=i * 120,
                y=0,
                width=100,
                height=100,
                seed=i,
                version=1,
                versionNonce=1,
            )
            for i in range(3)
        ]
        errors, warnings = check_size_hierarchy(elements, config)
        assert warnings  # Only 1 tier (all same size)
