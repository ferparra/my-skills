#!/usr/bin/env python3
"""Auto-fix correctable vault health issues.

Reads a vault_health_report.json and applies safe fixes:
- Adds missing frontmatter kind fields
- Moves misplaced notes to correct directories
- Removes duplicate zettel IDs (keeps oldest, regenerates others)
- Injects FIXME placeholders for schema drift

Usage:
    uvx --from python --with pydantic --with pyyaml python \
      .skills/obsidian-vault-health-auditor/scripts/fix_issues.py \
      --vault-root . --report vault_health_report.json --mode check

    uvx --from python --with pydantic --with pyyaml python \
      .skills/obsidian-vault-health-auditor/scripts/fix_issues.py \
      --vault-root . --report vault_health_report.json --mode fix
"""
from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from vault_health_models import (
    DuplicateZettelId,
    FixResult,
    load_report,
    MisplacedNote,
    save_report,
    VaultHealthReport,
    dump_json,
    KNOWN_KINDS,
    split_frontmatter,
)

import yaml


def generate_zettel_id() -> str:
    """Generate a new Zettel ID based on current timestamp."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def fix_missing_frontmatter(
    path: Path,
    kind_field: str,
    kind_value: str,
) -> dict[str, Any]:
    """Add missing kind field to frontmatter."""
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)

    if kind_field not in frontmatter:
        frontmatter[kind_field] = kind_value

    # Ensure tags include FIXME marker for drift
    tags = frontmatter.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags]
    if "FIXME_review_required" not in tags:
        tags = tags + ["FIXME_review_required"]
    frontmatter["tags"] = tags

    # Serialize back
    return {"path": str(path), "action": "add_frontmatter", "field": kind_field}


def fix_schema_drift(
    path: Path,
    kind_field: str,
    kind_value: str,
    allowed_values: list[str],
) -> dict[str, Any]:
    """Add FIXME tag for schema drift requiring manual review."""
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)

    tags = frontmatter.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags]
    if "FIXME_review_required" not in tags:
        tags = tags + ["FIXME_review_required"]
    frontmatter["tags"] = tags

    # Write back
    output = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, width=4096) + "---\n" + body
    backup = path.with_suffix(path.suffix + ".b4_fix")
    shutil.copy2(path, backup)
    path.write_text(output, encoding="utf-8")

    return {
        "path": str(path),
        "action": "inject_fixme_tag",
        "kind_field": kind_field,
        "kind_value": kind_value,
        "allowed_values": allowed_values,
        "backup": str(backup),
    }


def fix_misplaced_note(
    report: MisplacedNote,
    vault_root: Path,
) -> dict[str, Any]:
    """Move a misplaced note to its expected directory and update backlinks."""
    source = vault_root / report.path
    if not report.move_target:
        return {"path": str(source), "action": "skip", "reason": "no_move_target"}
    target = vault_root / report.move_target

    # Ensure target directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    # Get all notes to update wiki-links
    all_notes: list[tuple[Path, str]] = []
    for md_file in vault_root.rglob("*.md"):
        if md_file == source:
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
            all_notes.append((md_file, text))
        except Exception:
            continue

    # Update wiki-links in other notes that point to the old path
    old_name = source.name
    new_name = target.name
    changes = []

    for md_file, text in all_notes:
        if old_name in text or f"[[{old_name}]]" in text:
            updated = text.replace(f"[[{old_name}]]", f"[[{new_name}]]")
            updated = updated.replace(f"[[{old_name}|", f"[[{new_name}|")
            if updated != text:
                backup = md_file.with_suffix(md_file.suffix + ".b4_fix")
                shutil.copy2(md_file, backup)
                md_file.write_text(updated, encoding="utf-8")
                changes.append(str(md_file.relative_to(vault_root)))

    # Move the file
    backup = source.with_suffix(source.suffix + ".b4_fix")
    shutil.copy2(source, backup)
    shutil.move(str(source), str(target))

    return {
        "action": "move_and_update_links",
        "source": str(source.relative_to(vault_root)),
        "target": str(target.relative_to(vault_root)),
        "backlinks_updated": len(changes),
        "backlinks_updated_files": changes,
        "backup": str(backup),
    }


def fix_duplicate_zettel_ids(
    dup: DuplicateZettelId,
    vault_root: Path,
) -> list[dict[str, Any]]:
    """Remove duplicate zettel IDs, keeping oldest, regenerating others."""
    results: list[dict] = []
    paths = dup.paths
    if not paths or len(paths) <= 1:
        return results

    primary = dup.primary_path or paths[0]

    for i, path_str in enumerate(paths):
        path = vault_root / path_str
        if not path.exists():
            continue

        if i == 0:
            # Primary - keep but ensure zettel_id is canonical
            text = path.read_text(encoding="utf-8", errors="replace")
            frontmatter, body = split_frontmatter(text)
            zid_field = "zettel_id" if "zettel_id" in frontmatter else "id"
            frontmatter[zid_field] = dup.zettel_id
            output = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, width=4096) + "---\n" + body
            backup = path.with_suffix(path.suffix + ".b4_fix")
            shutil.copy2(path, backup)
            path.write_text(output, encoding="utf-8")
            results.append({
                "action": "keep_primary",
                "path": path_str,
                "zettel_id": dup.zettel_id,
                "backup": str(backup),
            })
        else:
            # Others - regenerate zettel_id
            text = path.read_text(encoding="utf-8", errors="replace")
            frontmatter, body = split_frontmatter(text)
            new_id = generate_zettel_id()
            zid_field = "zettel_id" if "zettel_id" in frontmatter else "id"
            frontmatter[zid_field] = new_id
            output = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, width=4096) + "---\n" + body
            backup = path.with_suffix(path.suffix + ".b4_fix")
            shutil.copy2(path, backup)
            path.write_text(output, encoding="utf-8")
            results.append({
                "action": "regenerate_id",
                "path": path_str,
                "old_id": dup.zettel_id,
                "new_id": new_id,
                "backup": str(backup),
            })

    return results


def apply_fixes(
    report: VaultHealthReport,
    vault_root: Path,
    mode: str = "check",
) -> FixResult:
    """Apply fixes from a health report."""
    result = FixResult()

    # Schema drift - inject FIXME tags
    for drift in report.schema_drift:
        path = vault_root / drift.path
        if not path.exists():
            result.skipped += 1
            result.errors.append(f"Schema drift file not found: {drift.path}")
            continue

        if mode == "check":
            result.changes.append({
                "path": str(path),
                "action": "would_inject_fixme_tag",
                "kind_field": drift.kind_field,
                "kind_value": drift.value,
            })
            result.skipped += 1
        else:
            change = fix_schema_drift(path, drift.kind_field, drift.value, drift.allowed_values)
            result.changes.append(change)
            result.fixed += 1

    # Misplaced notes
    for misplaced in report.misplaced_notes:
        if mode == "check":
            result.changes.append({
                "path": misplaced.path,
                "action": "would_move",
                "expected": misplaced.expected_dir,
                "actual": misplaced.actual_dir,
            })
            result.skipped += 1
        else:
            change = fix_misplaced_note(misplaced, vault_root)
            result.changes.append(change)
            if change.get("action") == "move_and_update_links":
                result.fixed += 1

    # Duplicate zettel IDs
    for dup in report.duplicate_zettel_ids:
        if mode == "check":
            result.changes.append({
                "action": "would_fix_duplicates",
                "zettel_id": dup.zettel_id,
                "paths": dup.paths,
                "primary": dup.primary_path,
            })
            result.skipped += len(dup.paths) - 1
        else:
            changes = fix_duplicate_zettel_ids(dup, vault_root)
            for c in changes:
                result.changes.append(c)
                if c["action"] == "regenerate_id":
                    result.fixed += 1

    result.ok = len(result.errors) == 0
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix correctable vault health issues.",
    )
    parser.add_argument(
        "--vault-root",
        default=".",
        help="Root of the Obsidian vault.",
    )
    parser.add_argument(
        "--report",
        default="vault_health_report.json",
        help="Path to the health report JSON.",
    )
    parser.add_argument(
        "--mode",
        default="check",
        choices=["check", "fix"],
        help="check: show what would be fixed. fix: apply fixes.",
    )
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    report_path = root / args.report

    if not report_path.exists():
        print(dump_json({"ok": False, "error": f"Report not found: {report_path}"}))
        return 1

    try:
        report = load_report(report_path)
    except Exception as exc:
        print(dump_json({"ok": False, "error": f"Failed to load report: {exc}"}))
        return 1

    result = apply_fixes(report, root, mode=args.mode)

    print(dump_json({
        "ok": result.ok,
        "mode": args.mode,
        "fixed": result.fixed,
        "skipped": result.skipped,
        "errors": result.errors,
        "changes": result.changes,
    }))

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
