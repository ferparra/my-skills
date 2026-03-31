#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import re
from collections import Counter
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

FRONTMATTER_DELIM = "\n---\n"
EXCALIDRAW_DATA_SECTION = re.compile(r"^#+ Excalidraw Data\s*$", re.MULTILINE)
TEXT_ELEMENTS_SECTION = re.compile(r"^##+ Text Elements\s*$", re.MULTILINE)
TEXT_ELEMENT_LINE = re.compile(r"^(.+?)\s+\^([a-zA-Z0-9_-]+)\s*$", re.MULTILINE)
JSON_BLOCK = re.compile(r"```(compressed-)?json\s*(.*?)\n```", re.DOTALL)


class ElementType(StrEnum):
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    DIAMOND = "diamond"
    FRAME = "frame"
    TEXT = "text"
    ARROW = "arrow"
    LINE = "line"
    FREEDRAW = "freedraw"
    IMAGE = "image"


class FillStyle(StrEnum):
    SOLID = "solid"
    HACHURE = "hachure"
    CROSS_HATCH = "cross-hatch"


class StrokeStyle(StrEnum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class TextAlign(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class VerticalAlign(StrEnum):
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class NoteParts(BaseModel):
    """Parsed markdown note parts."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    frontmatter: dict[str, Any]
    body: str


# ============================================================================
# Frontmatter Model
# ============================================================================


class ExcalidrawFrontmatter(BaseModel):
    """Frontmatter for .excalidraw.md files."""

    model_config = ConfigDict(extra="allow")

    excalidraw_plugin: str = Field(alias="excalidraw-plugin")
    tags: list[str] = Field(default_factory=list)

    @field_validator("excalidraw_plugin")
    @classmethod
    def must_be_parsed(cls, v: str) -> str:
        if v != "parsed":
            raise ValueError(f"excalidraw-plugin must be 'parsed', got '{v}'")
        return v

    @model_validator(mode="after")
    def must_have_excalidraw_tag(self) -> "ExcalidrawFrontmatter":
        if "excalidraw" not in self.tags:
            raise ValueError("tags must include 'excalidraw'")
        return self


# ============================================================================
# Element Models
# ============================================================================


class BoundElementRef(BaseModel):
    """Reference to a bound element (text or arrow)."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: str


class Binding(BaseModel):
    """Arrow binding to an element."""

    model_config = ConfigDict(extra="allow")

    elementId: str
    focus: float
    gap: float


class BaseElement(BaseModel):
    """Base element with common properties."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: ElementType
    x: float
    y: float
    width: float
    height: float
    angle: float = 0
    strokeColor: str = "#000000"
    backgroundColor: str = "transparent"
    fillStyle: str = "solid"
    strokeWidth: float = 2
    strokeStyle: str = "solid"
    roughness: int = 1
    opacity: int = 100
    seed: int
    version: int
    versionNonce: int
    isDeleted: bool = False
    groupIds: list[str] = Field(default_factory=list)
    frameId: str | None = None
    boundElements: list[BoundElementRef] | None = None
    link: str | None = None
    locked: bool = False
    roundness: dict | None = None


class RectangleElement(BaseElement):
    """Rectangle shape element."""

    type: Literal[ElementType.RECTANGLE] = ElementType.RECTANGLE


class EllipseElement(BaseElement):
    """Ellipse shape element."""

    type: Literal[ElementType.ELLIPSE] = ElementType.ELLIPSE


class DiamondElement(BaseElement):
    """Diamond shape element."""

    type: Literal[ElementType.DIAMOND] = ElementType.DIAMOND


class FrameElement(BaseElement):
    """Frame element."""

    type: Literal[ElementType.FRAME] = ElementType.FRAME
    name: str | None = None


class TextElement(BaseElement):
    """Text element."""

    type: Literal[ElementType.TEXT] = ElementType.TEXT
    text: str
    originalText: str
    fontSize: float
    fontFamily: int
    textAlign: str
    verticalAlign: str
    lineHeight: float
    baseline: int | None = None
    containerId: str | None = None


class ArrowElement(BaseElement):
    """Arrow element."""

    type: Literal[ElementType.ARROW] = ElementType.ARROW
    points: list[list[float]]
    startBinding: Binding | None = None
    endBinding: Binding | None = None
    startArrowhead: str | None = None
    endArrowhead: str | None = "arrow"
    lastCommittedPoint: list[float] | None = None


class LineElement(BaseElement):
    """Line element."""

    type: Literal[ElementType.LINE] = ElementType.LINE
    points: list[list[float]]
    lastCommittedPoint: list[float] | None = None


class FreedrawElement(BaseElement):
    """Freedraw element."""

    type: Literal[ElementType.FREEDRAW] = ElementType.FREEDRAW
    points: list[list[float]]
    pressures: list[float] | None = None


class ImageElement(BaseElement):
    """Image element."""

    type: Literal[ElementType.IMAGE] = ElementType.IMAGE
    fileId: str | None = None
    status: str | None = None
    scale: list[float] | None = None


# Discriminated union of all element types
ExcalidrawElement = Union[
    RectangleElement,
    EllipseElement,
    DiamondElement,
    FrameElement,
    TextElement,
    ArrowElement,
    LineElement,
    FreedrawElement,
    ImageElement,
]

# Dispatch dict for parsing
MODEL_BY_TYPE: dict[ElementType, type[BaseElement]] = {
    ElementType.RECTANGLE: RectangleElement,
    ElementType.ELLIPSE: EllipseElement,
    ElementType.DIAMOND: DiamondElement,
    ElementType.FRAME: FrameElement,
    ElementType.TEXT: TextElement,
    ElementType.ARROW: ArrowElement,
    ElementType.LINE: LineElement,
    ElementType.FREEDRAW: FreedrawElement,
    ElementType.IMAGE: ImageElement,
}


# ============================================================================
# Drawing Model
# ============================================================================


class AppState(BaseModel):
    """Application state."""

    model_config = ConfigDict(extra="allow")

    theme: str = "light"
    viewBackgroundColor: str = "#ffffff"
    gridSize: int | None = None


class ExcalidrawDrawing(BaseModel):
    """Top-level Excalidraw drawing."""

    model_config = ConfigDict(extra="allow")

    type: Literal["excalidraw"] = "excalidraw"
    version: int
    source: str | None = None
    elements: list[ExcalidrawElement]
    appState: AppState = Field(default_factory=AppState)

    @field_validator("version")
    @classmethod
    def check_version(cls, v: int) -> int:
        if v != 2:
            raise ValueError(f"Only version 2 supported, got {v}")
        return v


# ============================================================================
# Result Models
# ============================================================================


class FileResult(BaseModel):
    """Validation result for a single file."""

    path: str
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    element_count: int = 0
    text_element_count: int = 0


class ValidationOutput(BaseModel):
    """Overall validation output."""

    ok: bool
    count: int
    results: list[FileResult]


# ============================================================================
# Utility Functions
# ============================================================================


def normalize_jsonable(value: Any) -> Any:
    """Recursively normalize a value to JSON-serializable types."""
    if isinstance(value, dict):
        return {str(key): normalize_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return value


def dump_json(payload: Any) -> str:
    """Dump payload as JSON string."""
    return json.dumps(normalize_jsonable(payload), indent=2)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter and body."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find(FRONTMATTER_DELIM, 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len(FRONTMATTER_DELIM) :]
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise ValueError("Frontmatter must deserialize to a mapping.")
    return normalize_jsonable(dict(payload)), body


def load_markdown_note(path: Path) -> NoteParts:
    """Load and parse a markdown note."""
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    return NoteParts(path=path, frontmatter=frontmatter, body=body)


def extract_excalidraw_json(body: str, file_path: Path | None = None) -> dict | None:
    """Extract and parse the Excalidraw JSON from ## Drawing section."""
    match = JSON_BLOCK.search(body)
    if not match:
        return None

    is_compressed = match.group(1) == "compressed-"
    content = match.group(2).strip()

    if is_compressed:
        raise ValueError(
            "compressed-json format detected. Please decompress first:\n"
            "1. Open file in Obsidian\n"
            "2. Command palette → 'Decompress current Excalidraw file'\n"
            "3. Re-run validation\n"
            "\n"
            "The Excalidraw plugin uses pako compression which is not compatible with Python's zlib."
        )
    else:
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}")


def extract_text_element_ids(body: str) -> list[tuple[str, str]]:
    """Extract text element IDs from ## Text Elements section."""
    text_section_match = TEXT_ELEMENTS_SECTION.search(body)
    if not text_section_match:
        return []

    # Find content between ## Text Elements and next ## section or %% marker
    start = text_section_match.end()
    next_section = body.find("\n##", start)
    next_marker = body.find("\n%%", start)
    end = min(next_section if next_section != -1 else len(body), next_marker if next_marker != -1 else len(body))
    text_content = body[start:end]

    return TEXT_ELEMENT_LINE.findall(text_content)


def parse_element(raw: dict[str, Any]) -> BaseElement:
    """Parse a raw element dict into typed element model."""
    element_type = ElementType(raw.get("type"))
    model_cls = MODEL_BY_TYPE[element_type]
    return model_cls.model_validate(raw)


def parse_drawing(raw: dict[str, Any]) -> ExcalidrawDrawing:
    """Parse raw drawing dict into ExcalidrawDrawing model."""
    return ExcalidrawDrawing.model_validate(raw)


def validate_frontmatter(frontmatter: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate frontmatter against ExcalidrawFrontmatter schema."""
    try:
        ExcalidrawFrontmatter.model_validate(frontmatter)
    except ValidationError as exc:
        return False, [error["msg"] for error in exc.errors()]
    except Exception as exc:
        return False, [str(exc)]
    return True, []


# ============================================================================
# Anti-Pattern Checkers
# ============================================================================


def check_duplicate_ids(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check for duplicate element IDs."""
    errors = []
    id_counts = Counter(el.id for el in elements)
    duplicates = [id_ for id_, count in id_counts.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate element IDs found: {', '.join(duplicates)}")
    return errors, []


def check_text_bindings(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check that text element containerIds reference valid elements."""
    errors = []
    element_ids = {el.id for el in elements}

    for el in elements:
        if isinstance(el, TextElement) and el.containerId:
            if el.containerId not in element_ids:
                errors.append(
                    f"Text element '{el.id}' has containerId='{el.containerId}' "
                    f"but no element with that ID exists"
                )
    return errors, []


def check_arrow_bindings(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check that arrow bindings reference valid elements."""
    errors = []
    element_ids = {el.id for el in elements}

    for el in elements:
        if isinstance(el, ArrowElement):
            if el.startBinding and el.startBinding.elementId not in element_ids:
                errors.append(
                    f"Arrow element '{el.id}' startBinding references "
                    f"non-existent element '{el.startBinding.elementId}'"
                )
            if el.endBinding and el.endBinding.elementId not in element_ids:
                errors.append(
                    f"Arrow element '{el.id}' endBinding references "
                    f"non-existent element '{el.endBinding.elementId}'"
                )
    return errors, []


def check_bidirectional_bindings(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check bidirectional consistency between containers and text."""
    errors = []
    element_map = {el.id: el for el in elements}

    # Check: if container lists text in boundElements, text's containerId must point back
    for el in elements:
        if el.boundElements:
            for bound_ref in el.boundElements:
                if bound_ref.type == "text":
                    text_el = element_map.get(bound_ref.id)
                    if isinstance(text_el, TextElement):
                        if text_el.containerId != el.id:
                            errors.append(
                                f"Element '{el.id}' lists text '{text_el.id}' in boundElements, "
                                f"but text's containerId is '{text_el.containerId}' not '{el.id}'"
                            )

    # Check: if text has containerId, container must list it in boundElements
    for el in elements:
        if isinstance(el, TextElement) and el.containerId:
            container = element_map.get(el.containerId)
            if container and container.boundElements:
                if not any(ref.id == el.id and ref.type == "text" for ref in container.boundElements):
                    errors.append(
                        f"Text element '{el.id}' has containerId='{el.containerId}', "
                        f"but container doesn't list it in boundElements"
                    )

    return errors, []


def check_zero_dimensions(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check for zero-dimension shapes (warning only)."""
    warnings = []
    for el in elements:
        # Skip elements where zero dimensions are valid (line, arrow, freedraw)
        if isinstance(el, (LineElement, ArrowElement, FreedrawElement)):
            continue
        if el.width == 0 or el.height == 0:
            warnings.append(f"Element '{el.id}' has zero dimension: width={el.width}, height={el.height}")
    return [], warnings


def check_text_original_text(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check for text/originalText mismatch (warning only)."""
    warnings = []
    for el in elements:
        if isinstance(el, TextElement):
            if el.text != el.originalText:
                warnings.append(
                    f"Text element '{el.id}' has text/originalText mismatch "
                    f"(may be due to line wrapping)"
                )
    return [], warnings


def check_color_values(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check for invalid color values (warning only)."""
    warnings = []
    color_pattern = re.compile(r"^(#[0-9a-fA-F]{3,8}|transparent)$")

    for el in elements:
        if not color_pattern.match(el.strokeColor):
            warnings.append(f"Element '{el.id}' has invalid strokeColor: '{el.strokeColor}'")
        if not color_pattern.match(el.backgroundColor):
            warnings.append(f"Element '{el.id}' has invalid backgroundColor: '{el.backgroundColor}'")
    return [], warnings


def check_orphaned_groups(elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check for groupIds that appear only once (warning only)."""
    warnings = []
    all_group_ids: list[str] = []
    for el in elements:
        all_group_ids.extend(el.groupIds)

    group_counts = Counter(all_group_ids)
    orphaned = [gid for gid, count in group_counts.items() if count == 1]
    if orphaned:
        warnings.append(f"Group IDs appearing on only one element (orphaned): {', '.join(orphaned)}")
    return [], warnings


def check_text_elements_sync(body: str, elements: list[ExcalidrawElement]) -> tuple[list[str], list[str]]:
    """Check that ## Text Elements section is in sync with actual text elements."""
    warnings = []
    markdown_text_ids = {id_ for _, id_ in extract_text_element_ids(body)}
    json_text_ids = {el.id for el in elements if isinstance(el, TextElement)}

    missing_in_markdown = json_text_ids - markdown_text_ids
    extra_in_markdown = markdown_text_ids - json_text_ids

    if missing_in_markdown:
        warnings.append(f"Text elements in JSON but not in ## Text Elements: {', '.join(missing_in_markdown)}")
    if extra_in_markdown:
        warnings.append(f"Text elements in ## Text Elements but not in JSON: {', '.join(extra_in_markdown)}")

    return [], warnings


ALL_CHECKS = [
    check_duplicate_ids,
    check_text_bindings,
    check_arrow_bindings,
    check_bidirectional_bindings,
    check_zero_dimensions,
    check_text_original_text,
    check_color_values,
    check_orphaned_groups,
]


def validate_drawing(drawing: ExcalidrawDrawing, body: str) -> tuple[list[str], list[str]]:
    """Run all anti-pattern checks on a drawing."""
    errors: list[str] = []
    warnings: list[str] = []

    for check in ALL_CHECKS:
        e, w = check(drawing.elements)
        errors.extend(e)
        warnings.extend(w)

    # Check text elements sync separately since it needs the body
    e, w = check_text_elements_sync(body, drawing.elements)
    errors.extend(e)
    warnings.extend(w)

    return errors, warnings
