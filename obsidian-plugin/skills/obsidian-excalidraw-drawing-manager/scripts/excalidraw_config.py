#!/usr/bin/env python3
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ExcalidrawConfig(BaseModel):
    """Configuration for Excalidraw drawing validation."""

    model_config = ConfigDict(extra="forbid")

    vault_root: str = "."
    file_glob: str = "**/*.excalidraw.md"
    excalidraw_plugin_tag: str = "excalidraw"
    required_plugin_field: str = "excalidraw-plugin"
    required_plugin_value: str = "parsed"
    min_schema_version: int = 2
    max_schema_version: int = 2
    allowed_element_types: tuple[str, ...] = (
        "rectangle",
        "text",
        "arrow",
        "ellipse",
        "diamond",
        "line",
        "freedraw",
        "image",
        "frame",
    )
    valid_fill_styles: tuple[str, ...] = ("solid", "hachure", "cross-hatch")
    valid_stroke_styles: tuple[str, ...] = ("solid", "dashed", "dotted")
