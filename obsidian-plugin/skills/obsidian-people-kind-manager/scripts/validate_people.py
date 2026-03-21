#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from people_models import (
    PEOPLE_FILE_GLOB,
    AuditResult,
    PersonStatus,
    dump_json,
    ensure_string_list,
    infer_person_kind,
    infer_status_from_tags,
    load_markdown_note,
    validate_frontmatter,
)


def expand_paths(root: Path, paths: list[str], globs: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if candidate.exists():
            resolved.append(candidate)
    for pattern in globs:
        resolved.extend(sorted(root.glob(pattern)))
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in resolved:
        if path.suffix != ".md" or path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def audit_path(path: Path, root: Path) -> AuditResult:
    note = load_markdown_note(path)
    result = validate_frontmatter(note.frontmatter)
    errors = list(result.errors)
    warnings: list[str] = []

    fm = note.frontmatter
    rel = str(path.relative_to(root))

    # Infer kind for reporting even if explicit kind is set
    inference = infer_person_kind(fm)
    inferred_kind = inference.kind.value if inference.is_ambiguous else None

    # Warn on missing person_kind (not yet an error — migrate will inject it)
    if not fm.get("person_kind"):
        warnings.append("Missing `person_kind`. Run migrate_people.py to inject.")

    # Warn on missing last_interaction_date for non-author, non-dormant persons
    person_kind = str(fm.get("person_kind") or "")
    status_val = str(fm.get("status") or "")
    if person_kind != "author" and status_val != "dormant" and not fm.get("last_interaction_date"):
        warnings.append("Missing `last_interaction_date`. Run enrich_people.py to derive from body.")

    # Warn on stale status/processing with no recent interaction
    if status_val == PersonStatus.PROCESSING.value:
        lid = fm.get("last_interaction_date")
        if not lid:
            warnings.append("Status is `processing` but `last_interaction_date` is unset.")

    # Warn on connection_strength at 0.0 with potential_links present
    cs = fm.get("connection_strength")
    if cs is not None:
        try:
            if float(cs) == 0.0 and fm.get("potential_links"):
                warnings.append("connection_strength is 0.0 but potential_links exist — run score_people.py.")
        except (TypeError, ValueError):
            pass

    return AuditResult(
        path=rel,
        ok=result.ok and not errors,
        person_kind=person_kind or None,
        inferred_person_kind=inferred_kind,
        status=status_val or None,
        errors=errors,
        warnings=warnings,
        frontmatter_keys=list(fm.keys()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate person notes against the canonical person schema."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to validate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "report"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [PEOPLE_FILE_GLOB]))
    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results = [audit_path(path, root) for path in paths]
    overall_ok = all(r.ok for r in results)
    payload: dict[str, Any] = {
        "ok": overall_ok,
        "count": len(results),
        "results": [r.model_dump() for r in results],
    }
    print(dump_json(payload))
    return 0 if overall_ok or args.mode == "report" else 1


if __name__ == "__main__":
    raise SystemExit(main())
