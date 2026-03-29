#!/usr/bin/env python3
"""Tests for obsidian-cv-entry-manager scripts.

Run with:
    uvx --from python --with pydantic --with pyyaml --with pytest pytest \
        .skills/obsidian-cv-entry-manager/tests/test_cv_entry_manager.py -v
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

from cv_models import (
    CvBullet,
    CvEntryFrontmatter,
    CvEntryKind,
    CvEntryStatus,
    CvPillar,
    RecencyWeight,
    ValidationResult,
    load_markdown_note,
    make_cv_entry_id,
    normalize_cv_tags,
    split_frontmatter,
    validate_frontmatter,
)
from migrate_cv import normalize_cv_entry


# ── split_frontmatter ────────────────────────────────────────────────────────


def test_split_frontmatter_parses_valid_yaml() -> None:
    text = "---\ncv_entry_kind: role\nstatus: processed\n---\n\n# Body\n"
    fm, body = split_frontmatter(text)
    assert fm["cv_entry_kind"] == "role"
    assert "# Body" in body


def test_split_frontmatter_returns_empty_for_no_fence() -> None:
    text = "# Just a body\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert "# Just a body" in body


# ── validate_frontmatter — fixtures ─────────────────────────────────────────


def test_role_current_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "role-current-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid role fixture, got errors: {result.errors}"


def test_role_past_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "role-past-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid role fixture, got errors: {result.errors}"


def test_education_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "education-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid education fixture, got errors: {result.errors}"


def test_certification_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "certification-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid certification fixture, got errors: {result.errors}"


def test_award_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "award-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid award fixture, got errors: {result.errors}"


def test_community_fixture_validates_clean() -> None:
    note = load_markdown_note(FIXTURES_DIR / "community-valid.md")
    result = validate_frontmatter(note.frontmatter)
    assert result.ok, f"Expected valid community fixture, got errors: {result.errors}"


def test_invalid_fixture_fails_validation() -> None:
    note = load_markdown_note(FIXTURES_DIR / "invalid-missing-kind.md")
    result = validate_frontmatter(note.frontmatter)
    assert not result.ok
    assert len(result.errors) > 0


# ── validate_frontmatter — kind-specific ────────────────────────────────────


def test_role_missing_company_name_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("company_name" in e for e in result.errors)


def test_role_missing_start_date_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("start_date" in e for e in result.errors)


def test_education_missing_institution_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "education",
        "status": "processed",
        "qualification": "BSc",
        "tags": ["type/cv-entry", "cv-entry-kind/education", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("institution" in e for e in result.errors)


def test_education_missing_qualification_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "education",
        "status": "processed",
        "institution": "MIT",
        "tags": ["type/cv-entry", "cv-entry-kind/education", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("qualification" in e for e in result.errors)


def test_certification_missing_name_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "certification",
        "status": "processed",
        "tags": ["type/cv-entry", "cv-entry-kind/certification", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("certification_name" in e for e in result.errors)


def test_award_missing_name_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "award",
        "status": "processed",
        "tags": ["type/cv-entry", "cv-entry-kind/award", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("award_name" in e for e in result.errors)


def test_community_missing_activity_name_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "community",
        "status": "processed",
        "tags": ["type/cv-entry", "cv-entry-kind/community", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("activity_name" in e for e in result.errors)


# ── validate_frontmatter — tags ─────────────────────────────────────────────


def test_missing_type_cv_entry_tag_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "tags": ["cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("type/cv-entry" in e for e in result.errors)


def test_missing_kind_tag_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "tags": ["type/cv-entry", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("cv-entry-kind" in e for e in result.errors)


# ── validate_frontmatter — ID ───────────────────────────────────────────────


def test_invalid_cv_entry_id_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "bad-id",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("ce-" in e for e in result.errors)


# ── validate_frontmatter — dates ────────────────────────────────────────────


def test_invalid_start_date_format_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "January 2024",
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("YYYY-MM" in e for e in result.errors)


def test_start_date_after_end_date_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-06",
        "end_date": "2024-01",
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok
    assert any("start_date" in e for e in result.errors)


# ── validate_frontmatter — bullets ──────────────────────────────────────────


def test_bullet_with_invalid_pillar_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "bullets": [{"text": "Did something", "pillars": ["P4"]}],
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok


def test_bullet_with_empty_text_fails() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "bullets": [{"text": "", "pillars": ["P1"]}],
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert not result.ok


def test_valid_bullets_pass() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "bullets": [
            {"text": "Built X", "pillars": ["P1", "P2"], "quantified": True},
            {"text": "Led Y", "pillars": ["P2"]},
        ],
        "tags": ["type/cv-entry", "cv-entry-kind/role", "status/processed"],
    }
    result = validate_frontmatter(fm)
    assert result.ok, f"Expected valid, got errors: {result.errors}"


# ── normalize_cv_tags ────────────────────────────────────────────────────────


def test_normalize_tags_injects_managed() -> None:
    fm: dict[str, Any] = {"tags": ["area/career", "project/job-search-2026"]}
    result = normalize_cv_tags(fm, kind="role", status="processed")
    assert "type/cv-entry" in result
    assert "cv-entry-kind/role" in result
    assert "status/processed" in result
    assert "area/career" in result
    assert "project/job-search-2026" in result


def test_normalize_tags_strips_stale_kind_tag() -> None:
    fm: dict[str, Any] = {
        "tags": ["type/cv-entry", "cv-entry-kind/education", "status/processing"]
    }
    result = normalize_cv_tags(fm, kind="role", status="processed")
    assert "cv-entry-kind/education" not in result
    assert "cv-entry-kind/role" in result
    assert "status/processing" not in result
    assert "status/processed" in result


# ── make_cv_entry_id ─────────────────────────────────────────────────────────


def test_make_cv_entry_id_produces_stable_hash() -> None:
    id1 = make_cv_entry_id("role", "AutoGrab-Senior Analytics Engineer")
    id2 = make_cv_entry_id("role", "AutoGrab-Senior Analytics Engineer")
    assert id1 == id2
    assert id1.startswith("ce-")
    assert len(id1) == 15  # ce- + 12 hex


def test_make_cv_entry_id_different_inputs_differ() -> None:
    id1 = make_cv_entry_id("role", "AutoGrab-Senior Analytics Engineer")
    id2 = make_cv_entry_id("role", "Freely-Product Manager")
    assert id1 != id2


# ── CvBullet model ──────────────────────────────────────────────────────────


def test_cv_bullet_validates_valid() -> None:
    bullet = CvBullet(text="Built pipelines", pillars=["P1"], quantified=False)
    assert bullet.text == "Built pipelines"
    assert bullet.pillars == [CvPillar.P1]


def test_cv_bullet_rejects_empty_text() -> None:
    with pytest.raises(Exception):
        CvBullet(text="   ", pillars=["P1"])


# ── normalize_cv_entry (migrate) ────────────────────────────────────────────


def test_migrate_injects_cv_entry_kind_for_role() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "tags": ["area/career"],
    }
    result = normalize_cv_entry(fm, "# Body", inferred_kind="role")
    assert result["frontmatter"]["cv_entry_kind"] == "role"
    assert "cv_entry_kind" in result["changed_fields"]


def test_migrate_preserves_explicit_kind() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "education",
        "status": "processed",
        "institution": "MIT",
        "qualification": "BSc CS",
        "tags": ["type/cv-entry", "cv-entry-kind/education", "status/processed"],
    }
    result = normalize_cv_entry(fm, "# Body")
    assert result["frontmatter"]["cv_entry_kind"] == "education"
    assert "cv_entry_kind" not in result["changed_fields"]


def test_migrate_injects_status() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "tags": ["area/career"],
    }
    result = normalize_cv_entry(fm, "# Body")
    assert result["frontmatter"]["status"] == "processing"
    assert "status" in result["changed_fields"]


def test_migrate_normalizes_tags() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processed",
        "company_name": "Acme",
        "role_title": "Engineer",
        "start_date": "2024-01",
        "tags": ["area/career"],
    }
    result = normalize_cv_entry(fm, "# Body")
    tags = result["frontmatter"]["tags"]
    assert "type/cv-entry" in tags
    assert "cv-entry-kind/role" in tags
    assert "status/processed" in tags
    assert "area/career" in tags


def test_migrate_injects_fixme_for_missing_role_fields() -> None:
    fm: dict[str, Any] = {
        "cv_entry_id": "ce-aaaaaaaaaaaa",
        "cv_entry_kind": "role",
        "status": "processing",
        "tags": ["area/career"],
    }
    result = normalize_cv_entry(fm, "# Body")
    assert "FIXME" in result["frontmatter"].get("company_name", "")
    assert "FIXME" in result["frontmatter"].get("role_title", "")
    assert "FIXME" in result["frontmatter"].get("start_date", "")
    assert len(result["warnings"]) > 0


# ── subprocess: validate_cv.py ───────────────────────────────────────────────


def run_validate(fixture: str) -> dict[str, Any]:
    import json

    fixture_path = FIXTURES_DIR / fixture
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "validate_cv.py"),
            "--path",
            str(fixture_path),
            "--vault-root",
            str(FIXTURES_DIR),
            "--mode",
            "report",
        ],
        capture_output=True,
        text=True,
    )
    data: dict[str, Any] = json.loads(result.stdout)
    return data


def test_subprocess_role_fixture_passes() -> None:
    output = run_validate("role-current-valid.md")
    assert output["ok"] is True
    assert output["results"][0]["errors"] == []


def test_subprocess_invalid_fixture_fails() -> None:
    output = run_validate("invalid-missing-kind.md")
    assert output["ok"] is False
    assert len(output["results"][0]["errors"]) > 0
