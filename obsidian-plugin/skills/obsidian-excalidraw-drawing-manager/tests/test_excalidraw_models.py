#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from excalidraw_models import (
    ExcalidrawFrontmatter,
    TextElement,
    RectangleElement,
    ArrowElement,
    Binding,
    ExcalidrawDrawing,
    extract_excalidraw_json,
    extract_text_element_ids,
    validate_frontmatter,
    check_duplicate_ids,
    check_text_bindings,
    check_arrow_bindings,
    check_bidirectional_bindings,
)
from pydantic import ValidationError


class TestFrontmatter:
    def test_valid_frontmatter(self):
        """Valid frontmatter passes."""
        fm = {
            "excalidraw-plugin": "parsed",
            "tags": ["excalidraw"],
        }
        ok, errors = validate_frontmatter(fm)
        assert ok
        assert not errors

    def test_missing_plugin_field(self):
        """Missing excalidraw-plugin field fails."""
        fm = {"tags": ["excalidraw"]}
        ok, errors = validate_frontmatter(fm)
        assert not ok
        assert len(errors) > 0

    def test_wrong_plugin_value(self):
        """Wrong plugin value fails."""
        fm = {"excalidraw-plugin": "raw", "tags": ["excalidraw"]}
        ok, errors = validate_frontmatter(fm)
        assert not ok
        assert any("parsed" in str(e) for e in errors)

    def test_missing_tag(self):
        """Missing excalidraw tag fails."""
        fm = {"excalidraw-plugin": "parsed", "tags": []}
        ok, errors = validate_frontmatter(fm)
        assert not ok
        assert any("excalidraw" in str(e) for e in errors)


class TestElements:
    def test_text_element(self):
        """Text element parses correctly."""
        data = {
            "id": "text1",
            "type": "text",
            "x": 100,
            "y": 100,
            "width": 200,
            "height": 50,
            "text": "Hello",
            "originalText": "Hello",
            "fontSize": 20,
            "fontFamily": 1,
            "textAlign": "left",
            "verticalAlign": "top",
            "lineHeight": 1.25,
            "strokeColor": "#000000",
            "backgroundColor": "transparent",
            "seed": 1,
            "version": 1,
            "versionNonce": 1,
        }
        el = TextElement.model_validate(data)
        assert el.id == "text1"
        assert el.text == "Hello"
        assert el.containerId is None

    def test_rectangle_element(self):
        """Rectangle element parses correctly."""
        data = {
            "id": "rect1",
            "type": "rectangle",
            "x": 100,
            "y": 100,
            "width": 200,
            "height": 100,
            "strokeColor": "#000000",
            "backgroundColor": "transparent",
            "seed": 1,
            "version": 1,
            "versionNonce": 1,
        }
        el = RectangleElement.model_validate(data)
        assert el.id == "rect1"
        assert el.type == "rectangle"

    def test_arrow_with_bindings(self):
        """Arrow with bindings parses correctly."""
        data = {
            "id": "arrow1",
            "type": "arrow",
            "x": 100,
            "y": 100,
            "width": 200,
            "height": 50,
            "points": [[0, 0], [200, 50]],
            "startBinding": {"elementId": "rect1", "focus": 0.0, "gap": 10.0},
            "endBinding": {"elementId": "rect2", "focus": 0.0, "gap": 10.0},
            "strokeColor": "#000000",
            "backgroundColor": "transparent",
            "seed": 1,
            "version": 1,
            "versionNonce": 1,
        }
        el = ArrowElement.model_validate(data)
        assert el.startBinding.elementId == "rect1"
        assert el.endBinding.elementId == "rect2"


class TestDrawing:
    def test_valid_drawing(self):
        """Valid drawing parses."""
        data = {
            "type": "excalidraw",
            "version": 2,
            "elements": [],
            "appState": {"theme": "light"},
        }
        drawing = ExcalidrawDrawing.model_validate(data)
        assert drawing.version == 2
        assert drawing.type == "excalidraw"

    def test_wrong_version(self):
        """Wrong version fails."""
        data = {
            "type": "excalidraw",
            "version": 1,
            "elements": [],
        }
        with pytest.raises(ValidationError):
            ExcalidrawDrawing.model_validate(data)


class TestAntiPatterns:
    def test_duplicate_ids(self):
        """Duplicate IDs detected."""
        elements = [
            RectangleElement(
                id="dup",
                type="rectangle",
                x=0,
                y=0,
                width=100,
                height=100,
                seed=1,
                version=1,
                versionNonce=1,
            ),
            RectangleElement(
                id="dup",
                type="rectangle",
                x=200,
                y=0,
                width=100,
                height=100,
                seed=2,
                version=1,
                versionNonce=1,
            ),
        ]
        errors, warnings = check_duplicate_ids(elements)
        assert len(errors) == 1
        assert "dup" in errors[0]

    def test_broken_text_binding(self):
        """Broken text binding detected."""
        elements = [
            TextElement(
                id="text1",
                type="text",
                x=0,
                y=0,
                width=100,
                height=50,
                text="Hello",
                originalText="Hello",
                fontSize=20,
                fontFamily=1,
                textAlign="left",
                verticalAlign="top",
                lineHeight=1.25,
                containerId="nonexistent",
                seed=1,
                version=1,
                versionNonce=1,
            )
        ]
        errors, warnings = check_text_bindings(elements)
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_broken_arrow_binding(self):
        """Broken arrow binding detected."""
        elements = [
            ArrowElement(
                id="arrow1",
                type="arrow",
                x=0,
                y=0,
                width=200,
                height=50,
                points=[[0, 0], [200, 50]],
                startBinding=Binding(elementId="missing", focus=0.0, gap=10.0),
                seed=1,
                version=1,
                versionNonce=1,
            )
        ]
        errors, warnings = check_arrow_bindings(elements)
        assert len(errors) == 1
        assert "missing" in errors[0]


class TestMarkdownParsing:
    def test_extract_json(self):
        """Extract JSON from markdown."""
        body = """
# Excalidraw Data

%%
## Drawing
```json
{"type": "excalidraw", "version": 2, "elements": []}
```
%%
"""
        result = extract_excalidraw_json(body, None)
        assert result is not None
        assert result["type"] == "excalidraw"

    def test_extract_text_elements(self):
        """Extract text element IDs."""
        body = """
## Text Elements
Hello World ^text1
Another line ^text2
"""
        result = extract_text_element_ids(body)
        assert len(result) == 2
        assert ("Hello World", "text1") in result
        assert ("Another line", "text2") in result
