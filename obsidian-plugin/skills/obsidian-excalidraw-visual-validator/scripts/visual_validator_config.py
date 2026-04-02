#!/usr/bin/env python3
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VisualValidatorConfig(BaseModel):
    """Configuration for Excalidraw visual validation."""

    model_config = ConfigDict(extra="forbid")

    # File selection
    vault_root: str = "."
    file_glob: str = "**/*.excalidraw.md"
    render_output_dir: str = ".skills/excalidraw-renders"

    # Overlap detection
    max_overlap_ratio: float = 0.15  # Max allowed bbox overlap fraction
    min_element_gap_px: float = 20.0  # Minimum gap between elements

    # Spacing consistency
    max_spacing_cv: float = 0.5  # Max coefficient of variation for gaps

    # Text overflow
    text_padding_px: float = 10.0  # Container padding for text fit check

    # Arrow accuracy
    arrow_snap_tolerance_px: float = 15.0  # Max distance from arrow endpoint to target

    # Composition balance
    max_quadrant_skew: float = 0.7  # Max fraction of elements in one quadrant
    max_center_of_mass_offset: float = 0.3  # Max CoM distance from center (normalized)

    # Size hierarchy
    min_size_tiers: int = 2  # At least 2 distinct size tiers

    # Render settings
    render_padding_px: int = 80
    render_max_width_px: int = 1920
    render_min_height_px: int = 600

    # Severity levels
    overlap_is_error: bool = False
    spacing_is_error: bool = False
    text_overflow_is_error: bool = True
    arrow_accuracy_is_error: bool = True
