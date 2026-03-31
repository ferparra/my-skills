#!/usr/bin/env python3
"""Audit an Obsidian vault for health issues.

Scans all markdown notes, detects structural and content issues,
and produces a structured JSON report.

Usage:
    uvx --from python --with pydantic --with pyyaml python \
      .skills/obsidian-vault-health-auditor/scripts/audit_vault.py \
      --vault-root . --output vault_health_report.json

    # Run specific checks only
    uvx --from python --with pydantic --with pyyaml python \
      .skills/obsidian-vault-health-auditor/scripts/audit_vault.py \
      --vault-root . --checks broken_links,orphaned_notes,duplicate_zettel_ids
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from vault_health_models import (
    AuditSummary,
    BrokenLink,
    DuplicateZettelId,
    KIND_DIRECTORY_MAP,
    KNOWN_KINDS,
    load_markdown_note,
    load_report,
    LowConnectionStrength,
    MisplacedNote,
    NoteParts,
    OrphanedNote,
    SchemaDrift,
    StaleNote,
    STALE_THRESHOLD_DAYS,
    VaultHealthReport,
    ZOMBIE_THRESHOLD_DAYS,
    dump_json,
    extract_zettel_id,
    get_expected_directory,
    get_note_age_days,
    infer_kind_field,
    save_report,
    SchemaDrift,
    split_frontmatter,
    ZETTEL_ID_RE,
)

# ── Check functions ────────────────────────────────────────────────────────────

def check_broken_links(
    notes: list[NoteParts],
    all_paths: set[str],
) -> list[BrokenLink]:
    """Find wiki-links whose targets don't exist in the vault."""
    broken = []
    for note in notes:
        for link_target in note.links:
            # link_target may be a full path or just a filename
            candidate = Path(link_target)
            # Check multiple lookup strategies
            found = False
            for search in [
                candidate,
                candidate.with_suffix(".md"),
                Path(".") / candidate,
                Path(".") / candidate.with_suffix(".md"),
            ]:
                resolved = (Path(note.path).parent / search).resolve()
                if resolved.exists():
                    found = True
                    break
            if not found and link_target not in all_paths:
                # Also check without extension
                if not any(p.endswith(link_target) or p.endswith(link_target + ".md") for p in all_paths):
                    broken.append(BrokenLink(
                        file=str(note.path),
                        link=f"[[{link_target}]]",
                        target=link_target,
                        issue="target_not_found",
                    ))
    return broken


def check_orphaned_notes(
    notes: list[NoteParts],
    backlinks: dict[str, int],
) -> list[OrphanedNote]:
    """Find notes with zero incoming and zero outgoing links."""
    orphaned = []
    for note in notes:
        incoming = backlinks.get(str(note.path), 0)
        outgoing = len(note.links)
        if incoming == 0 and outgoing == 0:
            orphaned.append(OrphanedNote(
                path=str(note.path),
                incoming=incoming,
                outgoing=outgoing,
            ))
    return orphaned


def check_low_connection_strength(
    notes: list[NoteParts],
) -> list[LowConnectionStrength]:
    """Find notes with connection_strength below threshold."""
    low = []
    for note in notes:
        cs = note.frontmatter.get("connection_strength")
        if cs is None:
            continue
        try:
            score = float(cs)
        except (TypeError, ValueError):
            continue
        if score < 2.0:
            low.append(LowConnectionStrength(
                path=str(note.path),
                connection_strength=score,
            ))
    return low


def check_schema_drift(
    notes: list[NoteParts],
) -> list[SchemaDrift]:
    """Find notes whose *_kind value is not in the known taxonomy."""
    drifts = []
    for note in notes:
        kind_field, kind_value = infer_kind_field(note.frontmatter)
        if not kind_field or not kind_value:
            continue
        allowed = KNOWN_KINDS.get(kind_field, set())
        if allowed and kind_value not in allowed:
            drifts.append(SchemaDrift(
                path=str(note.path),
                kind_field=kind_field,
                value=kind_value,
                allowed_values=sorted(allowed),
            ))
    return drifts


def check_misplaced_notes(
    notes: list[NoteParts],
) -> list[MisplacedNote]:
    """Find notes whose path doesn't match their kind's expected directory."""
    misplaced = []
    for note in notes:
        kind_field, kind_value = infer_kind_field(note.frontmatter)
        if not kind_field or not kind_value:
            continue
        expected_dir = get_expected_directory(kind_field, kind_value)
        if not expected_dir:
            continue
        path_str = str(note.path)
        if expected_dir not in path_str:
            # Compute the target path
            note_name = Path(path_str).name
            target = expected_dir + note_name
            misplaced.append(MisplacedNote(
                path=path_str,
                expected_dir=expected_dir,
                actual_dir=str(Path(path_str).parent) + "/",
                move_target=target,
            ))
    return misplaced


def check_duplicate_zettel_ids(
    notes: list[NoteParts],
) -> list[DuplicateZettelId]:
    """Find notes sharing the same zettel_id."""
    id_to_paths: dict[str, list[str]] = defaultdict(list)
    for note in notes:
        zid = extract_zettel_id(note.frontmatter)
        if zid:
            id_to_paths[zid].append(str(note.path))

    duplicates = []
    for zid, paths in id_to_paths.items():
        if len(paths) > 1:
            # Sort by created date - oldest first
            def get_created(p: str) -> str:
                try:
                    fm, _ = split_frontmatter(Path(p).read_text(encoding="utf-8", errors="replace"))
                    return str(fm.get("created", "0"))
                except Exception:
                    return "0"
            sorted_paths = sorted(paths, key=get_created)
            duplicates.append(DuplicateZettelId(
                zettel_id=zid,
                paths=sorted_paths,
                primary_path=sorted_paths[0],
            ))
    return duplicates


def check_stale_notes(
    notes: list[NoteParts],
) -> list[StaleNote]:
    """Find notes not modified in >90 days."""
    stale = []
    for note in notes:
        days = get_note_age_days(note.path)
        if days is not None and days > STALE_THRESHOLD_DAYS:
            # Format the last modified date
            try:
                stat = note.path.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
            except OSError:
                modified = None
            stale.append(StaleNote(
                path=str(note.path),
                last_modified=modified,
                days_since_modified=days,
            ))
    return stale


# ── Main audit logic ───────────────────────────────────────────────────────────

def scan_vault(root: Path, checks: list[str] | None = None) -> VaultHealthReport:
    """Scan the vault and build a health report."""
    all_checks = {
        "broken_links",
        "orphaned_notes",
        "low_connection_strength",
        "schema_drift",
        "misplaced_notes",
        "duplicate_zettel_ids",
        "stale_notes",
    }
    active = set(checks) if checks else all_checks

    # Collect all markdown files
    notes: list[NoteParts] = []
    all_paths: set[str] = set()

    for md_file in root.rglob("*.md"):
        # Skip hidden directories
        if any(part.startswith(".") for part in md_file.parts):
            continue
        try:
            note = load_markdown_note(md_file)
            notes.append(note)
            all_paths.add(str(md_file.relative_to(root)))
            # Also add without extension for link matching
            all_paths.add(str(md_file.stem))
        except Exception:
            continue

    # Build backlink index
    backlinks: dict[str, int] = defaultdict(int)
    for note in notes:
        for link in note.links:
            # Try to resolve link to a file path
            link_str = link.strip()
            for ext in ["", ".md"]:
                candidate = link_str + ext
                for note_path in all_paths:
                    if note_path.endswith(candidate) or note_path == candidate:
                        backlinks[note_path] += 1
                        break

    # Run checks
    report = VaultHealthReport(vault_root=str(root))

    if "broken_links" in active:
        report.broken_links = check_broken_links(notes, all_paths)
        report.summary.broken_links = len(report.broken_links)

    if "orphaned_notes" in active:
        report.orphaned_notes = check_orphaned_notes(notes, backlinks)
        report.summary.orphaned_notes = len(report.orphaned_notes)

    if "low_connection_strength" in active:
        report.low_connection_strength = check_low_connection_strength(notes)
        report.summary.low_connection_strength = len(report.low_connection_strength)

    if "schema_drift" in active:
        report.schema_drift = check_schema_drift(notes)
        report.summary.schema_drift = len(report.schema_drift)

    if "misplaced_notes" in active:
        report.misplaced_notes = check_misplaced_notes(notes)
        report.summary.misplaced_notes = len(report.misplaced_notes)

    if "duplicate_zettel_ids" in active:
        report.duplicate_zettel_ids = check_duplicate_zettel_ids(notes)
        report.summary.duplicate_zettel_ids = len(report.duplicate_zettel_ids)

    if "stale_notes" in active:
        report.stale_notes = check_stale_notes(notes)
        report.summary.stale_notes = len(report.stale_notes)

    report.summary.total_notes = len(notes)
    report.ok = report.summary.total_issues == 0

    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

def dependency_error(missing: list[str]) -> int:
    payload = {
        "ok": False,
        "error": "missing_dependencies",
        "missing": missing,
        "fallback_checklist": [
            "Install/repair Obsidian CLI and ensure uvx is available.",
            "Install qmd: npm install -g @tobilu/qmd",
            "Re-index if needed: qmd update && qmd embed",
            "Re-run this guard command before any broad reads.",
        ],
    }
    print(dump_json(payload))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit an Obsidian vault for health issues.",
    )
    parser.add_argument(
        "--vault-root",
        default=".",
        help="Root of the Obsidian vault.",
    )
    parser.add_argument(
        "--output",
        default="vault_health_report.json",
        help="Output path for the JSON report.",
    )
    parser.add_argument(
        "--checks",
        default=None,
        help="Comma-separated list of checks to run (default: all).",
    )
    args = parser.parse_args()

    # Check dependencies
    missing = [cmd for cmd in ["obsidian", "qmd", "uvx"] if shutil.which(cmd) is None]
    if missing:
        return dependency_error(missing)

    root = Path(args.vault_root).resolve()
    if not root.exists():
        print(dump_json({"ok": False, "error": f"Vault root not found: {root}"}))
        return 1

    checks = [c.strip() for c in args.checks.split(",")] if args.checks else None

    try:
        report = scan_vault(root, checks=checks)
    except Exception as exc:
        print(dump_json({"ok": False, "error": str(exc)}))
        return 1

    output_path = root / args.output
    save_report(report, output_path)

    # Always print summary
    print(dump_json(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
