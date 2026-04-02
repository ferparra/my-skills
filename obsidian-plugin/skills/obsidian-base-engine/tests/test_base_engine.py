#!/usr/bin/env python3
"""Tests for obsidian-base-engine.

Run with:
    uvx --from python --with pydantic --with pyyaml --with pytest pytest \
        .skills/obsidian-base-engine/tests/test_base_engine.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from base_renderer import (
    BASE_REGISTRY,
    BaseRenderer,
    compose_views,
    merge_properties,
)
from formula_parser import (
    FormulaParser,
    extract_field_references,
    FormulaParseError,
)


# ── BaseRenderer tests ─────────────────────────────────────────────────────────

def test_base_renderer_from_registry_exercise() -> None:
    renderer = BaseRenderer.from_registry("exercise")
    assert renderer.base_name == "exercise"
    assert renderer.kind_field == "exercise_kind"
    assert "primary_label" in renderer.formulas
    assert len(renderer.views) > 0


def test_base_renderer_from_registry_people() -> None:
    renderer = BaseRenderer.from_registry("people")
    assert renderer.base_name == "people"
    assert renderer.kind_field == "person_kind"


def test_base_renderer_from_registry_brokerage_activity() -> None:
    renderer = BaseRenderer.from_registry("brokerage_activity")
    assert renderer.base_name == "brokerage_activity"
    assert renderer.kind_field == "brokerage_activity_kind"


def test_base_renderer_from_registry_cv_entry() -> None:
    renderer = BaseRenderer.from_registry("cv_entry")
    assert renderer.base_name == "cv_entry"
    assert renderer.kind_field == "cv_entry_kind"


def test_base_renderer_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown base type"):
        BaseRenderer.from_registry("nonexistent")


def test_base_renderer_build_config() -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
        formulas={"foo": 'if(bar, bar, "default")'},
        properties={"bar": {"displayName": "Bar"}},
        views=[{"type": "table", "name": "Test View"}],
    )
    config = renderer.build_config()
    assert "filters" in config
    assert "formulas" in config
    assert "properties" in config
    assert "views" in config
    assert config["formulas"]["foo"] == 'if(bar, bar, "default")'


def test_base_renderer_build_config_has_filter() -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
    )
    config = renderer.build_config()
    assert 'file.ext == "md"' in config["filters"]["and"]
    assert 'file.inFolder("Test/**/*.md")' in config["filters"]["and"]
    assert 'test_kind != ""' in config["filters"]["and"]


def test_base_renderer_validate_ok() -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
        formulas={"foo": 'if(bar, bar, "default")'},
        properties={"bar": {"displayName": "Bar"}},
        views=[{"type": "table", "name": "Test View"}],
    )
    issues = renderer.validate()
    assert issues == []


def test_base_renderer_validate_missing_formulas() -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
        properties={"bar": {"displayName": "Bar"}},
        views=[{"type": "table", "name": "Test View"}],
    )
    issues = renderer.validate()
    assert "No formulas defined" in issues


def test_base_renderer_validate_missing_views() -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
        formulas={"foo": 'if(bar, bar, "default")'},
        properties={"bar": {"displayName": "Bar"}},
    )
    issues = renderer.validate()
    assert "No views defined" in issues


def test_base_renderer_validate_view_missing_name() -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
        formulas={"foo": 'if(bar, bar, "default")'},
        properties={"bar": {"displayName": "Bar"}},
        views=[{"type": "table"}],
    )
    issues = renderer.validate()
    assert any("missing 'name'" in i for i in issues)


def test_base_renderer_render_creates_file(tmp_path: Path) -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
        formulas={"foo": 'if(bar, bar, "default")'},
        properties={"bar": {"displayName": "Bar"}},
        views=[{"type": "table", "name": "Test View"}],
    )
    output = tmp_path / "Test.base"
    result = renderer.render(output)
    assert result["ok"] is True
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "filters" in content
    assert "formulas" in content
    assert "Test View" in content


def test_base_renderer_custom_overrides_merge() -> None:
    renderer = BaseRenderer(
        base_name="test",
        kind_field="test_kind",
        folder_glob="Test/**/*.md",
        formulas={"original": '"original"'},
        custom_formulas={"original": '"modified"', "added": '"new"'},
    )
    assert renderer.formulas["original"] == '"modified"'
    assert renderer.formulas["added"] == '"new"'


# ── View composition tests ─────────────────────────────────────────────────────

def test_compose_views_adds_prefix() -> None:
    views = [
        {"type": "table", "name": "Test View"},
    ]
    composed = compose_views([("prefix", views)])
    assert composed[0]["name"] == "[prefix] Test View"


def test_compose_views_multiple_collections() -> None:
    views1 = [{"type": "table", "name": "View A"}]
    views2 = [{"type": "table", "name": "View B"}]
    composed = compose_views([("A", views1), ("B", views2)])
    assert len(composed) == 2
    assert composed[0]["name"] == "[A] View A"
    assert composed[1]["name"] == "[B] View B"


# ── Property merge tests ───────────────────────────────────────────────────────

def test_merge_properties_override() -> None:
    pd1 = {"foo": {"displayName": "Foo 1"}}
    pd2 = {"foo": {"displayName": "Foo 2"}, "bar": {"displayName": "Bar"}}
    merged = merge_properties(pd1, pd2)
    assert merged["foo"]["displayName"] == "Foo 2"
    assert "bar" in merged


# ── FormulaParser tests ────────────────────────────────────────────────────────

def test_formula_parser_valid_if() -> None:
    parser = FormulaParser()
    result = parser.parse('if(bar, bar, "default")')
    assert result["valid"] is True
    assert result["issues"] == []


def test_formula_parser_valid_nested_if() -> None:
    parser = FormulaParser()
    result = parser.parse('if(a, if(b, c, d), e)')
    assert result["valid"] is True


def test_formula_parser_valid_method_chain() -> None:
    parser = FormulaParser()
    result = parser.parse('field.toString().replace("[[", "").replace("]]", "")')
    assert result["valid"] is True


def test_formula_parser_valid_function_call() -> None:
    parser = FormulaParser()
    result = parser.parse('join(", ", list)')
    assert result["valid"] is True


def test_formula_parser_invalid_unclosed_paren() -> None:
    parser = FormulaParser()
    result = parser.parse("if(a, b")
    assert result["valid"] is False
    assert any("Unclosed" in i for i in result["issues"])


def test_formula_parser_invalid_unclosed_bracket() -> None:
    parser = FormulaParser()
    result = parser.parse("arr[1, 2")
    assert result["valid"] is False
    assert any("Unclosed" in i for i in result["issues"])


def test_formula_parser_empty() -> None:
    parser = FormulaParser()
    result = parser.parse("")
    assert result["valid"] is False


def test_formula_parser_whitespace() -> None:
    parser = FormulaParser()
    result = parser.parse("   ")
    assert result["valid"] is False


def test_formula_parser_complex_expression() -> None:
    parser = FormulaParser()
    formula = 'if(exercise_kind == "hypertrophy", if(force_profile == "lengthened", 2, if(force_profile == "mid-range", 1, 0)) + if(stability_profile == "high", 2, if(stability_profile == "medium", 1, 0)) + if(fatigue_cost == "low", 2, if(fatigue_cost == "moderate", 1, 0)) + if(volume_tracking == "primary_only", 1, if(volume_tracking == "secondary_half", 0.5, 0)), "")'
    result = parser.parse(formula)
    assert result["valid"] is True, f"Issues: {result['issues']}"


def test_formula_parser_validate_formula() -> None:
    parser = FormulaParser()
    valid, issues = parser.validate_formula('if(a, b, "c")')
    assert valid is True
    assert issues == []


def test_formula_parser_validate_formula_dict() -> None:
    parser = FormulaParser()
    formulas = {
        "foo": 'if(bar, bar, "default")',
        "baz": "arr.join(\", \")",
    }
    results = parser.validate_formula_dict(formulas)
    assert results["foo"]["valid"] is True
    assert results["baz"]["valid"] is True


def test_extract_field_references() -> None:
    fields = extract_field_references('if(primary_muscle, primary_muscle.toString(), "")')
    assert "primary_muscle" in fields


def test_extract_field_references_complex() -> None:
    formula = 'if(exercise_kind == "hypertrophy", if(force_profile == "lengthened", 2, 0), "")'
    fields = extract_field_references(formula)
    assert "exercise_kind" in fields
    assert "force_profile" in fields


# ── BASE_REGISTRY tests ────────────────────────────────────────────────────────

def test_registry_has_all_expected_types() -> None:
    expected = {"brokerage_activity", "exercise", "people", "cv_entry"}
    assert expected.issubset(BASE_REGISTRY.keys())


def test_registry_exercise_has_required_keys() -> None:
    spec = BASE_REGISTRY["exercise"]
    assert "kind_field" in spec
    assert "folder_glob" in spec
    assert "formulas" in spec
    assert "properties" in spec
    assert "views" in spec
    assert len(spec["views"]) > 0


def test_registry_brokerage_activity_has_required_keys() -> None:
    spec = BASE_REGISTRY["brokerage_activity"]
    assert "kind_field" in spec
    assert spec["kind_field"] == "brokerage_activity_kind"


def test_registry_people_has_required_keys() -> None:
    spec = BASE_REGISTRY["people"]
    assert "kind_field" in spec
    assert spec["kind_field"] == "person_kind"
    assert "folder_glob" in spec
    assert "People" in spec["folder_glob"]


# ── CLI tests ──────────────────────────────────────────────────────────────────

def test_cli_base_renderer_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "base_renderer.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_render_exercise_base(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "base_renderer.py"),
            "--base", "exercise",
            "--output", "Exercise.base",
            "--vault-root", str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["ok"] is True

    output_file = tmp_path / "Exercise.base"
    assert output_file.exists()


def test_cli_invalid_base_type(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "base_renderer.py"),
            "--base", "nonexistent",
            "--output", "Test.base",
            "--vault-root", str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert "error" in data
