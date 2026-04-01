#!/usr/bin/env python3
"""Tests for obsidian-zettel-manager scripts.

Run with:
    uvx --from python --with pydantic --with pyyaml --with pytest pytest \
        .skills/obsidian-zettel-manager/tests/test_zettel_manager.py -v
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "assets" / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from zettel_models import (
    ZETTEL_ID_RE,
    ZettelFrontmatter,
    ZettelKind,
    ZettelStatus,
    classify_body_links,
    infer_zettel_kind,
    load_markdown_note,
    make_zettel_id,
    normalize_zettel_tags,
    score_connection_strength,
    split_frontmatter,
    validate_frontmatter,
)
from migrate_zettels import normalize_zettel


# ── split_frontmatter ────────────────────────────────────────────────────────

def test_split_frontmatter_parses_valid_yaml() -> None:
    text = "---\nzettel_kind: atomic\nstatus: fleeting\n---\n\n# Body\n"
    fm, body = split_frontmatter(text)
    assert fm["zettel_kind"] == "atomic"
    assert "# Body" in body


def test_split_frontmatter_returns_empty_for_no_fence() -> None:
    text = "# Just a body\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert "# Just a body" in body


# ── validate_frontmatter ─────────────────────────────────────────────────────

def test_atomic_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "atomic-valid.md")
    ok, errors = validate_frontmatter(note.frontmatter)
    assert ok, f"Expected valid atomic fixture, got errors: {errors}"
    assert errors == []


def test_moc_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "moc-valid.md")
    ok, errors = validate_frontmatter(note.frontmatter)
    assert ok, f"Expected valid moc fixture, got errors: {errors}"


def test_litnote_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "litnote-valid.md")
    ok, errors = validate_frontmatter(note.frontmatter)
    assert ok, f"Expected valid litnote fixture, got errors: {errors}"


def test_hub_synthesis_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "hub-synthesis-valid.md")
    ok, errors = validate_frontmatter(note.frontmatter)
    assert ok, f"Expected valid hub_synthesis fixture, got errors: {errors}"


def test_definition_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "definition-valid.md")
    ok, errors = validate_frontmatter(note.frontmatter)
    assert ok, f"Expected valid definition fixture, got errors: {errors}"


def test_invalid_fixture_fails_validation() -> None:
    note = load_markdown_note(FIXTURES_DIR / "invalid-missing-kind.md")
    ok, errors = validate_frontmatter(note.frontmatter)
    assert not ok
    assert len(errors) > 0


def test_litnote_missing_source_fails() -> None:
    fm = {
        "zettel_id": "zt-a1b2c3d4e5",
        "zettel_kind": "litnote",
        "status": "fleeting",
        "connection_strength": 0.0,
        "potential_links": ["[[10 Notes/Foo|Foo]]"],
        "tags": ["type/zettel", "zettel-kind/litnote", "status/fleeting"],
    }
    ok, errors = validate_frontmatter(fm)
    assert not ok
    assert any("source" in e for e in errors)


def test_moc_missing_hub_for_fails() -> None:
    fm = {
        "zettel_id": "zt-a1b2c3d4e5",
        "zettel_kind": "moc",
        "status": "evergreen",
        "connection_strength": 5.0,
        "potential_links": ["[[10 Notes/Foo|Foo]]"],
        "tags": ["type/zettel", "zettel-kind/moc", "status/evergreen"],
    }
    ok, errors = validate_frontmatter(fm)
    assert not ok
    assert any("hub_for" in e for e in errors)


def test_definition_missing_defines_fails() -> None:
    fm = {
        "zettel_id": "zt-a1b2c3d4e5",
        "zettel_kind": "definition",
        "status": "evergreen",
        "connection_strength": 5.0,
        "potential_links": ["[[10 Notes/Foo|Foo]]"],
        "tags": ["type/zettel", "zettel-kind/definition", "status/evergreen"],
    }
    ok, errors = validate_frontmatter(fm)
    assert not ok
    assert any("defines" in e for e in errors)


def test_hub_synthesis_missing_synthesises_fails() -> None:
    fm = {
        "zettel_id": "zt-a1b2c3d4e5",
        "zettel_kind": "hub_synthesis",
        "status": "processed",
        "connection_strength": 5.0,
        "potential_links": ["[[10 Notes/Foo|Foo]]"],
        "tags": ["type/zettel", "zettel-kind/hub_synthesis", "status/processed"],
    }
    ok, errors = validate_frontmatter(fm)
    assert not ok
    assert any("synthesises" in e for e in errors)


def test_missing_type_zettel_tag_fails() -> None:
    fm = {
        "zettel_id": "zt-a1b2c3d4e5",
        "zettel_kind": "atomic",
        "status": "fleeting",
        "connection_strength": 0.0,
        "potential_links": ["[[10 Notes/Foo|Foo]]"],
        "tags": ["zettel-kind/atomic", "status/fleeting"],  # missing type/zettel
    }
    ok, errors = validate_frontmatter(fm)
    assert not ok
    assert any("type/zettel" in e for e in errors)


def test_empty_potential_links_fails() -> None:
    fm = {
        "zettel_id": "zt-a1b2c3d4e5",
        "zettel_kind": "atomic",
        "status": "fleeting",
        "connection_strength": 0.0,
        "potential_links": [],
        "tags": ["type/zettel", "zettel-kind/atomic", "status/fleeting"],
    }
    ok, errors = validate_frontmatter(fm)
    assert not ok
    assert any("potential_links" in e for e in errors)


# ── make_zettel_id ───────────────────────────────────────────────────────────

def test_make_zettel_id_preserves_existing() -> None:
    path = Path("/vault/10 Notes/Foo.md")
    fm = {"zettel_id": "zt-a1b2c3d4e5"}
    result = make_zettel_id(path, fm)
    assert result == "zt-a1b2c3d4e5"


def test_make_zettel_id_generates_from_path() -> None:
    path = Path("/vault/10 Notes/New Note.md")
    fm: dict[str, object] = {}
    result = make_zettel_id(path, fm)
    assert ZETTEL_ID_RE.match(result), f"Generated ID {result!r} does not match expected pattern"


def test_make_zettel_id_is_stable() -> None:
    path = Path("/vault/10 Notes/New Note.md")
    fm: dict[str, object] = {}
    assert make_zettel_id(path, fm) == make_zettel_id(path, fm)


# ── infer_zettel_kind ────────────────────────────────────────────────────────

def test_infer_kind_moc_from_tag() -> None:
    path = Path("/vault/10 Notes/Something.md")
    fm = {"tags": ["type/moc", "concept/architecture"]}
    kind, ambiguous = infer_zettel_kind(fm, path)
    assert kind == ZettelKind.MOC
    assert not ambiguous


def test_infer_kind_litnote_from_source() -> None:
    path = Path("/vault/10 Notes/Newport.md")
    fm = {"source": "Newport - Deep Work"}
    kind, ambiguous = infer_zettel_kind(fm, path)
    assert kind == ZettelKind.LITNOTE
    assert not ambiguous


def test_infer_kind_definition_from_tag() -> None:
    path = Path("/vault/10 Notes/Zettelkasten.md")
    fm = {"tags": ["type/definition"]}
    kind, ambiguous = infer_zettel_kind(fm, path)
    assert kind == ZettelKind.DEFINITION
    assert not ambiguous


def test_infer_kind_defaults_to_atomic() -> None:
    path = Path("/vault/10 Notes/Random Thought.md")
    fm = {"tags": ["concept/random"]}
    kind, ambiguous = infer_zettel_kind(fm, path)
    assert kind == ZettelKind.ATOMIC
    assert not ambiguous


def test_infer_kind_ambiguous_when_multiple_signals() -> None:
    path = Path("/vault/10 Notes/Mixed.md")
    fm = {"tags": ["type/moc", "type/definition"]}
    kind, ambiguous = infer_zettel_kind(fm, path)
    assert ambiguous


# ── classify_body_links ──────────────────────────────────────────────────────

def test_classify_body_links_concept() -> None:
    body = "See [[10 Notes/Agent Loop|Agent Loop]] for details."
    result = classify_body_links(body)
    assert len(result["concept_links"]) == 1
    assert result["context_links"] == []


def test_classify_body_links_context() -> None:
    body = "Captured during [[Periodic/2026/2026-W10|2026-W10]]."
    result = classify_body_links(body)
    assert len(result["context_links"]) == 1
    assert result["concept_links"] == []


def test_classify_body_links_both() -> None:
    body = "[[10 Notes/Agent Loop|Agent Loop]] — see [[Periodic/2026/2026-W10|2026-W10]]."
    result = classify_body_links(body)
    assert len(result["concept_links"]) == 1
    assert len(result["context_links"]) == 1


# ── normalize_zettel_tags ────────────────────────────────────────────────────

def test_normalize_tags_injects_managed() -> None:
    fm: dict[str, object] = {"tags": ["tech/ai/agent-engineering"]}
    result = normalize_zettel_tags(fm, kind="atomic", status="processed")
    assert "type/zettel" in result
    assert "zettel-kind/atomic" in result
    assert "status/processed" in result
    assert "tech/ai/agent-engineering" in result


def test_normalize_tags_preserves_user_tags() -> None:
    fm: dict[str, object] = {"tags": ["resource/topic/pkm", "concept/method"]}
    result = normalize_zettel_tags(fm, kind="definition", status="evergreen")
    assert "resource/topic/pkm" in result
    assert "concept/method" in result


def test_normalize_tags_strips_stale_status_tags() -> None:
    fm: dict[str, object] = {"tags": ["status/fleeting", "tech/ai"]}
    result = normalize_zettel_tags(fm, kind="atomic", status="processed")
    assert "status/fleeting" not in result
    assert "status/processed" in result


# ── score_connection_strength ────────────────────────────────────────────────

def test_score_increases_with_backlinks() -> None:
    path = Path("/vault/10 Notes/Foo.md")
    body = "[[10 Notes/Bar|Bar]] [[10 Notes/Baz|Baz]]"
    fm: dict[str, object] = {"potential_links": ["[[10 Notes/Qux|Qux]]"]}
    score_0 = score_connection_strength(path, body, fm, backlink_count=0)
    score_5 = score_connection_strength(path, body, fm, backlink_count=5)
    assert score_5 > score_0


def test_score_max_is_ten() -> None:
    path = Path("/vault/10 Notes/Foo.md")
    body = " ".join(f"[[10 Notes/Note{i}|Note{i}]]" for i in range(20))
    fm: dict[str, object] = {"potential_links": [f"[[10 Notes/PL{i}|PL{i}]]" for i in range(10)]}
    score = score_connection_strength(path, body, fm, backlink_count=100)
    assert score <= 10.0


def test_score_is_zero_for_empty_note() -> None:
    path = Path("/vault/10 Notes/Empty.md")
    body = "No links here."
    fm: dict[str, object] = {"potential_links": []}
    score = score_connection_strength(path, body, fm, backlink_count=0)
    assert score == 0.0


# ── normalize_zettel (migrate) ───────────────────────────────────────────────

def test_migrate_assigns_zettel_id() -> None:
    note = load_markdown_note(FIXTURES_DIR / "fleeting-capture.md")
    assert "zettel_id" not in note.frontmatter or not note.frontmatter.get("zettel_id")
    root = FIXTURES_DIR.parent.parent.parent  # vault root for tests
    result = normalize_zettel(note, root)
    assert ZETTEL_ID_RE.match(result["frontmatter"]["zettel_id"])


def test_migrate_infers_kind_from_moc_tag(tmp_path: Path) -> None:
    md = tmp_path / "Hub.md"
    md.write_text(
        "---\naliases: []\ntags:\n  - type/moc\n---\n\n"
        "# Hub\n\n[[10 Notes/Foo|Foo]] [[Periodic/2026/2026-W10|2026-W10]]\n"
    )
    note = load_markdown_note(md)
    result = normalize_zettel(note, tmp_path)
    assert result["frontmatter"]["zettel_kind"] == "moc"


def test_migrate_status_inferred_from_tags(tmp_path: Path) -> None:
    md = tmp_path / "Evergreen.md"
    md.write_text(
        "---\naliases: []\ntags:\n  - status/evergreen\n  - concept/foo\n---\n\n"
        "# Evergreen\n\n[[10 Notes/Foo|Foo]] [[Periodic/2026/2026-W10|W10]]\n"
    )
    note = load_markdown_note(md)
    result = normalize_zettel(note, tmp_path)
    assert result["frontmatter"]["status"] == "evergreen"


def test_migrate_definition_infers_defines_from_filename(tmp_path: Path) -> None:
    md = tmp_path / "Zettelkasten.md"
    md.write_text(
        "---\nzettel_kind: definition\naliases: []\ntags:\n  - type/definition\n---\n\n"
        "# Zettelkasten\n\n[[10 Notes/PKM Hub|PKM Hub]] [[Periodic/2026/2026-W10|W10]]\n"
    )
    note = load_markdown_note(md)
    result = normalize_zettel(note, tmp_path)
    assert result["frontmatter"].get("defines") == "Zettelkasten"
    assert any("defines" in w for w in result["warnings"])


def test_migrate_preserves_user_tags(tmp_path: Path) -> None:
    md = tmp_path / "Note.md"
    md.write_text(
        "---\nzettel_kind: atomic\nstatus: processed\ntags:\n  - resource/topic/pkm\n  - concept/method\n---\n\n"
        "# Note\n\n[[10 Notes/Foo|Foo]] [[Periodic/2026/2026-W10|W10]]\n"
    )
    note = load_markdown_note(md)
    result = normalize_zettel(note, tmp_path)
    tags = result["frontmatter"]["tags"]
    assert "resource/topic/pkm" in tags
    assert "concept/method" in tags
    assert "type/zettel" in tags


# ── subprocess: validate_zettels.py ─────────────────────────────────────────

def run_validate(fixture: str, vault_root: Path | None = None) -> dict[str, Any]:
    import json

    fixture_path = FIXTURES_DIR / fixture
    root = vault_root or FIXTURES_DIR
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "validate_zettels.py"),
            "--path", str(fixture_path),
            "--vault-root", str(root),
            "--mode", "report",
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def test_subprocess_atomic_fixture_passes() -> None:
    output = run_validate("atomic-valid.md")
    assert output["ok"] is True
    assert output["results"][0]["errors"] == []


def test_subprocess_invalid_fixture_fails() -> None:
    output = run_validate("invalid-missing-kind.md")
    assert output["ok"] is False
    assert len(output["results"][0]["errors"]) > 0
