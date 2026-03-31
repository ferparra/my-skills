#!/usr/bin/env python3
"""Tests for obsidian-vault-health-auditor.

Run with:
    uvx --from python --with pydantic --with pyyaml --with pytest pytest \
        .skills/obsidian-vault-health-auditor/tests/test_vault_health.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "assets" / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from vault_health_models import (
    DuplicateZettelId,
    extract_zettel_id,
    KNOWN_KINDS,
    load_markdown_note,
    MIN_CONNECTION_STRENGTH,
    NoteParts,
    split_frontmatter,
    STALE_THRESHOLD_DAYS,
    VaultHealthReport,
    AuditSummary,
)
from audit_vault import (
    check_duplicate_zettel_ids,
    check_low_connection_strength,
    check_misplaced_notes,
    check_orphaned_notes,
    check_schema_drift,
    check_stale_notes,
)


# ── split_frontmatter ──────────────────────────────────────────────────────────

def test_split_frontmatter_parses_valid_yaml() -> None:
    text = "---\nperson_kind: manager\nstatus: processed\n---\n\n# Body\n"
    fm, body = split_frontmatter(text)
    assert fm["person_kind"] == "manager"
    assert "# Body" in body


def test_split_frontmatter_no_fence() -> None:
    text = "# Just a body\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert "# Just a body" in body


# ── load_markdown_note ─────────────────────────────────────────────────────────

def test_load_note_extracts_wikilinks() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("---\nperson_kind: manager\n---\n\nBody with [[Some/Note]] and [[Another/Note|Alias]].\n")
        f.flush()
        path = Path(f.name)
        note = load_markdown_note(path)
        assert note.path == path
        assert note.frontmatter["person_kind"] == "manager"
        assert "Some/Note" in note.links
        assert "Another/Note" in note.links
        path.unlink()


def test_load_note_deduplicates_links() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("---\nperson_kind: manager\n---\n\n[[Same/Note]] and [[Same/Note]] again.\n")
        f.flush()
        path = Path(f.name)
        note = load_markdown_note(path)
        assert note.links.count("Same/Note") == 1
        path.unlink()


# ── extract_zettel_id ───────────────────────────────────────────────────────────

def test_extract_zettel_id_valid() -> None:
    assert extract_zettel_id({"zettel_id": "20260228143022"}) == "20260228143022"
    assert extract_zettel_id({"id": "20260228143022"}) == "20260228143022"


def test_extract_zettel_id_invalid() -> None:
    assert extract_zettel_id({"zettel_id": "not-a-timestamp"}) is None
    assert extract_zettel_id({}) is None
    assert extract_zettel_id({"zettel_id": "20260228"}) is None  # too short


# ── check_schema_drift ─────────────────────────────────────────────────────────

def test_schema_drift_detected() -> None:
    note = NoteParts(
        path=Path("/vault/People/Test.md"),
        frontmatter={"person_kind": "unknown_type", "status": "processed"},
        body="",
        links=[],
    )
    drifts = check_schema_drift([note])
    assert len(drifts) == 1
    assert drifts[0].kind_field == "person_kind"
    assert drifts[0].value == "unknown_type"
    assert "manager" in drifts[0].allowed_values


def test_schema_drift_not_detected_for_valid_kind() -> None:
    note = NoteParts(
        path=Path("/vault/People/Test.md"),
        frontmatter={"person_kind": "manager", "status": "processed"},
        body="",
        links=[],
    )
    drifts = check_schema_drift([note])
    assert len(drifts) == 0


def test_schema_drift_not_detected_when_no_kind_field() -> None:
    note = NoteParts(
        path=Path("/vault/Notes/Random.md"),
        frontmatter={"status": "processed"},
        body="",
        links=[],
    )
    drifts = check_schema_drift([note])
    assert len(drifts) == 0


# ── check_low_connection_strength ──────────────────────────────────────────────

def test_low_connection_strength_detected() -> None:
    note = NoteParts(
        path=Path("/vault/People/Test.md"),
        frontmatter={"person_kind": "manager", "connection_strength": 0.5},
        body="",
        links=[],
    )
    low = check_low_connection_strength([note])
    assert len(low) == 1
    assert low[0].connection_strength == 0.5


def test_high_connection_strength_ok() -> None:
    note = NoteParts(
        path=Path("/vault/People/Test.md"),
        frontmatter={"person_kind": "manager", "connection_strength": 3.0},
        body="",
        links=[],
    )
    low = check_low_connection_strength([note])
    assert len(low) == 0


def test_missing_connection_strength_skipped() -> None:
    note = NoteParts(
        path=Path("/vault/People/Test.md"),
        frontmatter={"person_kind": "manager"},
        body="",
        links=[],
    )
    low = check_low_connection_strength([note])
    assert len(low) == 0


# ── check_misplaced_notes ───────────────────────────────────────────────────────

def test_misplaced_note_detected() -> None:
    note = NoteParts(
        path=Path("/vault/Notes/Misplaced.md"),
        frontmatter={"person_kind": "manager"},  # Should be in People/
        body="",
        links=[],
    )
    misplaced = check_misplaced_notes([note])
    assert len(misplaced) == 1
    assert "People/" in misplaced[0].expected_dir


def test_correctly_placed_note_ok() -> None:
    note = NoteParts(
        path=Path("/vault/People/Correct.md"),
        frontmatter={"person_kind": "manager"},
        body="",
        links=[],
    )
    misplaced = check_misplaced_notes([note])
    assert len(misplaced) == 0


# ── check_duplicate_zettel_ids ─────────────────────────────────────────────────

def test_duplicate_zettel_ids_detected() -> None:
    notes = [
        NoteParts(
            path=Path("/vault/zettel1.md"),
            frontmatter={"zettel_id": "20260228143022", "created": "2026-01-01"},
            body="",
            links=[],
        ),
        NoteParts(
            path=Path("/vault/zettel2.md"),
            frontmatter={"zettel_id": "20260228143022", "created": "2026-02-01"},
            body="",
            links=[],
        ),
    ]
    dups = check_duplicate_zettel_ids(notes)
    assert len(dups) == 1
    assert dups[0].zettel_id == "20260228143022"
    assert len(dups[0].paths) == 2


def test_no_duplicates_when_all_unique() -> None:
    notes = [
        NoteParts(
            path=Path("/vault/zettel1.md"),
            frontmatter={"zettel_id": "20260228143021"},
            body="",
            links=[],
        ),
        NoteParts(
            path=Path("/vault/zettel2.md"),
            frontmatter={"zettel_id": "20260228143022"},
            body="",
            links=[],
        ),
    ]
    dups = check_duplicate_zettel_ids(notes)
    assert len(dups) == 0


# ── check_orphaned_notes ───────────────────────────────────────────────────────

def test_orphaned_note_detected() -> None:
    note = NoteParts(
        path=Path("/vault/Orphan.md"),
        frontmatter={},
        body="No links here.",
        links=[],
    )
    orphaned = check_orphaned_notes([note], {})
    assert len(orphaned) == 1
    assert orphaned[0].incoming == 0
    assert orphaned[0].outgoing == 0


def test_note_with_incoming_links_not_orphaned() -> None:
    note = NoteParts(
        path=Path("/vault/HasBacklinks.md"),
        frontmatter={},
        body="",
        links=[],
    )
    orphaned = check_orphaned_notes([note], {"HasBacklinks.md": 3})
    assert len(orphaned) == 0


def test_note_with_outgoing_links_not_orphaned() -> None:
    note = NoteParts(
        path=Path("/vault/HasOutlinks.md"),
        frontmatter={},
        body="[[Some/Other]]",
        links=["Some/Other"],
    )
    orphaned = check_orphaned_notes([note], {})
    assert len(orphaned) == 0


# ── VaultHealthReport ──────────────────────────────────────────────────────────

def test_report_ok_when_no_issues() -> None:
    report = VaultHealthReport(
        summary=AuditSummary(
            total_notes=10,
            broken_links=0,
            orphaned_notes=0,
            low_connection_strength=0,
            schema_drift=0,
            misplaced_notes=0,
            duplicate_zettel_ids=0,
            stale_notes=0,
        )
    )
    assert report.ok is True


def test_report_not_ok_when_issues_present() -> None:
    report = VaultHealthReport(
        summary=AuditSummary(
            total_notes=10,
            broken_links=2,
            orphaned_notes=0,
            low_connection_strength=0,
            schema_drift=0,
            misplaced_notes=0,
            duplicate_zettel_ids=0,
            stale_notes=0,
        )
    )
    assert report.ok is False


# ── subprocess: audit_vault.py ─────────────────────────────────────────────────

def test_audit_vault_script_runs(tmp_path: Path) -> None:
    """Test that audit_vault.py executes without error on a clean vault."""
    # Create minimal vault structure
    (tmp_path / "People").mkdir()
    (tmp_path / "People" / "Test.md").write_text(
        "---\nperson_kind: manager\nstatus: processed\nconnection_strength: 3.0\n---\n\nTest note.\n",
        encoding="utf-8",
    )
    (tmp_path / "20 Resources").mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "audit_vault.py"),
            "--vault-root", str(tmp_path),
            "--output", "health_report.json",
            "--checks", "broken_links,orphaned_notes,schema_drift",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["summary"]["total_notes"] == 1


def test_audit_vault_detects_schema_drift(tmp_path: Path) -> None:
    (tmp_path / "People").mkdir()
    (tmp_path / "People" / "BadKind.md").write_text(
        "---\nperson_kind: bad_type\nstatus: processed\n---\n\nBad kind.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "audit_vault.py"),
            "--vault-root", str(tmp_path),
            "--output", "health_report.json",
            "--checks", "schema_drift",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["summary"]["schema_drift"] == 1
    assert data["schema_drift"][0]["kind_field"] == "person_kind"
    assert data["schema_drift"][0]["value"] == "bad_type"


def test_audit_vault_detects_duplicate_zettel_ids(tmp_path: Path) -> None:
    (tmp_path / "zettel1.md").write_text(
        "---\ncreated: 2026-01-01\nzettel_id: 20260228143022\n---\n\nFirst.\n",
        encoding="utf-8",
    )
    (tmp_path / "zettel2.md").write_text(
        "---\ncreated: 2026-02-01\nzettel_id: 20260228143022\n---\n\nSecond.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "audit_vault.py"),
            "--vault-root", str(tmp_path),
            "--output", "health_report.json",
            "--checks", "duplicate_zettel_ids",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["summary"]["duplicate_zettel_ids"] == 1
    assert data["duplicate_zettel_ids"][0]["zettel_id"] == "20260228143022"
    assert len(data["duplicate_zettel_ids"][0]["paths"]) == 2


# ── subprocess: fix_issues.py ─────────────────────────────────────────────────

def test_fix_issues_check_mode(tmp_path: Path) -> None:
    (tmp_path / "People").mkdir()
    (tmp_path / "People" / "BadKind.md").write_text(
        "---\nperson_kind: bad_type\nstatus: processed\ntags: [type/person]\n---\n\nBad kind.\n",
        encoding="utf-8",
    )

    # First run audit
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "audit_vault.py"),
            "--vault-root", str(tmp_path),
            "--output", "health_report.json",
            "--checks", "schema_drift",
        ],
        capture_output=True,
        text=True,
    )

    # Then run fix in check mode
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "fix_issues.py"),
            "--vault-root", str(tmp_path),
            "--report", "health_report.json",
            "--mode", "check",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["mode"] == "check"
    assert data["skipped"] == 1  # Would fix but in check mode
    assert "would_inject_fixme_tag" in data["changes"][0]["action"]


def test_fix_issues_fix_mode_adds_fixme_tag(tmp_path: Path) -> None:
    (tmp_path / "People").mkdir()
    (tmp_path / "People" / "BadKind.md").write_text(
        "---\nperson_kind: bad_type\nstatus: processed\ntags: [type/person]\n---\n\nBad kind.\n",
        encoding="utf-8",
    )

    # First run audit
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "audit_vault.py"),
            "--vault-root", str(tmp_path),
            "--output", "health_report.json",
            "--checks", "schema_drift",
        ],
        capture_output=True,
        text=True,
    )

    # Then run fix in fix mode
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "fix_issues.py"),
            "--vault-root", str(tmp_path),
            "--report", "health_report.json",
            "--mode", "fix",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["fixed"] == 1

    # Verify the FIXME tag was added
    content = (tmp_path / "People" / "BadKind.md").read_text(encoding="utf-8")
    assert "FIXME_review_required" in content


def test_fix_issues_regenerates_duplicate_zettel_ids(tmp_path: Path) -> None:
    (tmp_path / "zettel1.md").write_text(
        "---\ncreated: 2026-01-01\nzettel_id: 20260228143022\n---\n\nFirst.\n",
        encoding="utf-8",
    )
    (tmp_path / "zettel2.md").write_text(
        "---\ncreated: 2026-02-01\nzettel_id: 20260228143022\n---\n\nSecond.\n",
        encoding="utf-8",
    )

    # First run audit
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "audit_vault.py"),
            "--vault-root", str(tmp_path),
            "--output", "health_report.json",
            "--checks", "duplicate_zettel_ids",
        ],
        capture_output=True,
        text=True,
    )

    # Then run fix in fix mode
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "fix_issues.py"),
            "--vault-root", str(tmp_path),
            "--report", "health_report.json",
            "--mode", "fix",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["fixed"] == 1  # One was regenerated

    # Verify zettel2 now has a different ID
    content2 = (tmp_path / "zettel2.md").read_text(encoding="utf-8")
    assert "20260228143022" not in content2 or "zettel_id" not in content2.split("---\n")[1]
