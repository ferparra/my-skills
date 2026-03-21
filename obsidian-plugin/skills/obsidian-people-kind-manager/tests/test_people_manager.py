#!/usr/bin/env python3
"""Tests for obsidian-people-kind-manager scripts.

Run with:
    uvx --from python --with pydantic --with pyyaml --with pytest pytest \
        .skills/obsidian-people-kind-manager/tests/test_people_manager.py -v
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "assets" / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from people_models import (
    InteractionFrequency,
    PersonKind,
    PersonStatus,
    ValidationResult,
    extract_body_dated_headings,
    infer_interaction_frequency,
    infer_person_kind,
    infer_status_from_tags,
    load_markdown_note,
    normalize_person_tags,
    score_connection_strength,
    split_frontmatter,
    validate_frontmatter,
)
from migrate_people import normalize_person


# ── split_frontmatter ────────────────────────────────────────────────────────

def test_split_frontmatter_parses_valid_yaml() -> None:
    text = "---\nperson_kind: manager\nstatus: processed\n---\n\n# Body\n"
    fm, body = split_frontmatter(text)
    assert fm["person_kind"] == "manager"
    assert "# Body" in body


def test_split_frontmatter_returns_empty_for_no_fence() -> None:
    text = "# Just a body\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert "# Just a body" in body


# ── validate_frontmatter ─────────────────────────────────────────────────────

def test_manager_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "manager-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid manager fixture, got errors: {result.errors}"
    assert result.errors == []


def test_collaborator_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "collaborator-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid collaborator fixture, got errors: {result.errors}"


def test_stakeholder_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "stakeholder-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid stakeholder fixture, got errors: {result.errors}"


def test_contact_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "contact-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid customer_contact fixture, got errors: {result.errors}"


def test_author_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "author-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid author fixture, got errors: {result.errors}"


def test_mentor_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "mentor-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid mentor fixture, got errors: {result.errors}"


def test_invalid_fixture_fails_validation() -> None:
    note = load_markdown_note(FIXTURES_DIR / "invalid-missing-kind.md")
    result = validate_frontmatter(note.frontmatter)
    assert not result.ok
    assert len(result.errors) > 0


def test_author_missing_primary_works_fails() -> None:
    fm = {
        "person_kind": "author",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "author",
        "status": "processed",
        "primary_context": "intellectual/alignment",
        "connection_strength": 0.4,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["type/person", "person-kind/author", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("primary_works" in e for e in result.errors)


def test_missing_type_person_tag_fails() -> None:
    fm = {
        "person_kind": "collaborator",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "status": "processed",
        "primary_context": "professional/autograb",
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["person-kind/collaborator", "status/processed"],  # missing type/person
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("type/person" in e for e in result.errors)


def test_missing_person_kind_tag_fails() -> None:
    fm = {
        "person_kind": "collaborator",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "status": "processed",
        "primary_context": "professional/autograb",
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["type/person", "status/processed"],  # missing person-kind/collaborator
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("person-kind" in e for e in result.errors)


def test_empty_potential_links_fails() -> None:
    fm = {
        "person_kind": "collaborator",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "status": "processed",
        "primary_context": "professional/autograb",
        "connection_strength": 0.5,
        "potential_links": [],
        "tags": ["type/person", "person-kind/collaborator", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("potential_links" in e for e in result.errors)


def test_invalid_last_interaction_date_fails() -> None:
    fm = {
        "person_kind": "manager",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "status": "processed",
        "primary_context": "professional/autograb",
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "last_interaction_date": "28-02-2026",  # wrong format
        "tags": ["type/person", "person-kind/manager", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("last_interaction_date" in e for e in result.errors)


# ── infer_person_kind ────────────────────────────────────────────────────────

def test_infer_manager_from_relationship_conditions() -> None:
    fm = {"relationship_conditions": ["line manager in data and analytics"]}
    result = infer_person_kind(fm)
    assert result.kind == PersonKind.MANAGER
    assert not result.is_ambiguous


def test_infer_stakeholder_from_conditions() -> None:
    fm = {"relationship_conditions": ["CTO of the company, key decision maker"]}
    result = infer_person_kind(fm)
    assert result.kind == PersonKind.STAKEHOLDER
    assert not result.is_ambiguous


def test_infer_author_from_tag_no_conditions() -> None:
    fm = {"tags": ["author", "type/person"], "relationship_conditions": []}
    result = infer_person_kind(fm)
    assert result.kind == PersonKind.AUTHOR
    assert not result.is_ambiguous


def test_infer_collaborator_from_colleague_with_no_signals() -> None:
    fm = {"relationship_to_fernando": "colleague", "relationship_conditions": []}
    result = infer_person_kind(fm)
    assert result.kind == PersonKind.COLLABORATOR
    assert not result.is_ambiguous


def test_infer_acquaintance_from_relationship_to() -> None:
    fm = {"relationship_to_fernando": "friend", "relationship_conditions": []}
    result = infer_person_kind(fm)
    assert result.kind == PersonKind.ACQUAINTANCE
    assert not result.is_ambiguous


def test_infer_acquaintance_from_personal_context() -> None:
    fm = {"primary_context": "personal/family", "relationship_conditions": []}
    result = infer_person_kind(fm)
    assert result.kind == PersonKind.ACQUAINTANCE
    assert not result.is_ambiguous


def test_infer_ambiguous_when_multiple_signals() -> None:
    fm = {"relationship_conditions": ["line manager", "also a mentor"]}
    result = infer_person_kind(fm)
    assert result.is_ambiguous


def test_infer_preserves_explicit_kind() -> None:
    fm = {"person_kind": "stakeholder", "relationship_conditions": ["line manager"]}
    result = infer_person_kind(fm)
    assert result.kind == PersonKind.STAKEHOLDER
    assert not result.is_ambiguous


# ── infer_status_from_tags ───────────────────────────────────────────────────

def test_infer_status_processed_from_tag() -> None:
    fm = {"tags": ["status/processed", "type/person"]}
    assert infer_status_from_tags(fm) == PersonStatus.PROCESSED


def test_infer_status_processing_from_tag() -> None:
    fm = {"tags": ["status/processing", "person-kind/manager"]}
    assert infer_status_from_tags(fm) == PersonStatus.PROCESSING


def test_infer_status_defaults_to_fleeting() -> None:
    fm = {"tags": ["type/person"]}
    assert infer_status_from_tags(fm) == PersonStatus.FLEETING


# ── normalize_person_tags ────────────────────────────────────────────────────

def test_normalize_tags_injects_managed() -> None:
    fm: dict = {"tags": ["person", "person/autograb", "role/team-lead"]}
    result = normalize_person_tags(fm, kind="manager", status="processed")
    assert "type/person" in result
    assert "person-kind/manager" in result
    assert "status/processed" in result
    assert "person" in result
    assert "person/autograb" in result
    assert "role/team-lead" in result


def test_normalize_tags_preserves_user_tags() -> None:
    fm: dict = {"tags": ["author", "person/intellectual"]}
    result = normalize_person_tags(fm, kind="author", status="processed")
    assert "author" in result
    assert "person/intellectual" in result


def test_normalize_tags_strips_stale_person_kind_tag() -> None:
    fm: dict = {"tags": ["type/person", "person-kind/collaborator", "status/processing"]}
    result = normalize_person_tags(fm, kind="manager", status="processed")
    assert "person-kind/collaborator" not in result
    assert "person-kind/manager" in result
    assert "status/processing" not in result
    assert "status/processed" in result


# ── score_connection_strength ────────────────────────────────────────────────

def test_score_increases_with_backlinks() -> None:
    path = Path("/vault/People/Foo.md")
    body = "[[10 Notes/Bar|Bar]] [[Companies/Baz|Baz]]"
    fm: dict = {"potential_links": ["[[10 Notes/Qux|Qux]]"]}
    score_0 = score_connection_strength(path, body, fm, backlink_count=0)
    score_4 = score_connection_strength(path, body, fm, backlink_count=4)
    assert score_4 > score_0


def test_score_max_is_one() -> None:
    path = Path("/vault/People/Dense.md")
    body = " ".join(f"[[10 Notes/Note{i}|Note{i}]]" for i in range(20))
    fm: dict = {
        "potential_links": [f"[[10 Notes/PL{i}|PL{i}]]" for i in range(10)],
        "last_interaction_date": "2026-03-20",  # very recent → max recency
    }
    score = score_connection_strength(path, body, fm, backlink_count=100)
    assert score <= 1.0


def test_score_is_zero_for_empty_note() -> None:
    path = Path("/vault/People/Empty.md")
    body = "No links here."
    fm: dict = {"potential_links": []}
    score = score_connection_strength(path, body, fm, backlink_count=0)
    assert score == 0.0


# ── extract_body_dated_headings ──────────────────────────────────────────────

def test_extract_dated_headings_finds_dates() -> None:
    body = "## 2026-02-28 — Meeting\n\nContent.\n\n## 2026-01-15 — Earlier\n\nContent."
    result = extract_body_dated_headings(body)
    assert result == ["2026-01-15", "2026-02-28"]


def test_extract_dated_headings_empty_body() -> None:
    body = "# No dated headings\n\nJust text."
    result = extract_body_dated_headings(body)
    assert result == []


# ── infer_interaction_frequency ──────────────────────────────────────────────

def test_infer_frequency_weekly_from_tight_gaps() -> None:
    dates = ["2026-01-01", "2026-01-08", "2026-01-15", "2026-01-22"]
    result = infer_interaction_frequency(dates)
    assert result == InteractionFrequency.WEEKLY


def test_infer_frequency_monthly_from_medium_gaps() -> None:
    dates = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    result = infer_interaction_frequency(dates)
    assert result == InteractionFrequency.MONTHLY


def test_infer_frequency_returns_none_for_fewer_than_three() -> None:
    dates = ["2026-01-01", "2026-02-01"]
    result = infer_interaction_frequency(dates)
    assert result is None


# ── normalize_person (migrate) ───────────────────────────────────────────────

def test_migrate_injects_person_kind() -> None:
    fm = {
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "primary_context": "professional/autograb",
        "relationship_conditions": ["line manager in data and analytics"],
        "connection_strength": 0.8,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["status/processed", "type/person"],
    }
    result = normalize_person(fm, "# Body")
    assert result["frontmatter"]["person_kind"] == "manager"
    assert "person_kind" in result["changed_fields"]


def test_migrate_preserves_explicit_person_kind() -> None:
    fm = {
        "person_kind": "stakeholder",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "primary_context": "professional/autograb",
        "relationship_conditions": ["line manager in data"],  # would infer manager
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["type/person", "person-kind/stakeholder", "status/processed"],
        "status": "processed",
    }
    result = normalize_person(fm, "# Body")
    assert result["frontmatter"]["person_kind"] == "stakeholder"
    # Should not appear in changed_fields (was already present)
    assert "person_kind" not in result["changed_fields"]


def test_migrate_injects_manager_cadence_placeholder() -> None:
    fm = {
        "person_kind": "manager",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "primary_context": "professional/autograb",
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["type/person", "person-kind/manager", "status/processed"],
        "status": "processed",
    }
    result = normalize_person(fm, "# Body")
    assert "management_cadence" in result["frontmatter"]
    assert "FIXME" in result["frontmatter"]["management_cadence"]
    assert any("management_cadence" in w for w in result["warnings"])


def test_migrate_does_not_overwrite_explicit_management_cadence() -> None:
    fm = {
        "person_kind": "manager",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "primary_context": "professional/autograb",
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "management_cadence": "weekly 1:1",
        "tags": ["type/person", "person-kind/manager", "status/processed"],
        "status": "processed",
    }
    result = normalize_person(fm, "# Body")
    assert result["frontmatter"]["management_cadence"] == "weekly 1:1"
    assert "management_cadence" not in result["changed_fields"]


def test_migrate_injects_author_primary_works_placeholder() -> None:
    fm = {
        "person_kind": "author",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "author",
        "primary_context": "intellectual/alignment",
        "connection_strength": 0.4,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["type/person", "person-kind/author", "status/processed"],
        "status": "processed",
    }
    result = normalize_person(fm, "# Body")
    assert result["frontmatter"]["primary_works"] is not None
    assert any("FIXME" in w for w in result["frontmatter"]["primary_works"])
    assert any("primary_works" in w for w in result["warnings"])


def test_migrate_preserves_user_tags() -> None:
    fm = {
        "person_kind": "collaborator",
        "created": "2025-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00",
        "relationship_to_fernando": "colleague",
        "primary_context": "professional/autograb",
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
        "tags": ["type/person", "person-kind/collaborator", "status/processed",
                 "person", "person/autograb", "role/engineer"],
        "status": "processed",
    }
    result = normalize_person(fm, "# Body")
    tags = result["frontmatter"]["tags"]
    assert "person" in tags
    assert "person/autograb" in tags
    assert "role/engineer" in tags
    assert "type/person" in tags


# ── subprocess: validate_people.py ──────────────────────────────────────────

def run_validate(fixture: str, vault_root: Path | None = None) -> dict:
    import json
    fixture_path = FIXTURES_DIR / fixture
    root = vault_root or FIXTURES_DIR
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "validate_people.py"),
            "--path", str(fixture_path),
            "--vault-root", str(root),
            "--mode", "report",
        ],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_subprocess_manager_fixture_passes() -> None:
    output = run_validate("manager-valid.md")
    assert output["ok"] is True
    assert output["results"][0]["errors"] == []


def test_subprocess_invalid_fixture_fails() -> None:
    output = run_validate("invalid-missing-kind.md")
    assert output["ok"] is False
    assert len(output["results"][0]["errors"]) > 0
