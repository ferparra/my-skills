#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from zettel_models import (
    ZETTEL_FILE_GLOB,
    classify_body_links,
    dump_json,
    load_markdown_note,
    validate_frontmatter,
)


def expand_paths(root: Path, paths: list[str], globs: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if path.exists():
            resolved.append(path)
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


def audit_path(path: Path, root: Path) -> dict[str, Any]:
    note = load_markdown_note(path)
    ok_frontmatter, frontmatter_errors = validate_frontmatter(note.frontmatter)
    body_links = classify_body_links(note.body)
    errors = list(frontmatter_errors)
    warnings: list[str] = []

    if not body_links["concept_links"]:
        errors.append("Zettel body must contain at least one concept link (10 Notes/, 20 Resources/, etc.).")
    if not body_links["context_links"]:
        errors.append("Zettel body must contain at least one context link (Periodic/, 00 Inbox/, or date-like target).")

    fm = note.frontmatter
    cs = fm.get("connection_strength")
    if cs is not None:
        try:
            if float(cs) == 0.0 and (body_links["concept_links"] or body_links["context_links"]):
                warnings.append("connection_strength is 0.0 but note has body links — run score_zettels.py to update.")
        except (TypeError, ValueError):
            pass

    status = str(fm.get("status") or "")
    if status == "fleeting" and str(path).find("/10 Notes/") != -1:
        warnings.append("Note has status=fleeting but lives in 10 Notes/ — consider promoting status to processing/processed.")

    kind = str(fm.get("zettel_kind") or "")
    if kind == "fleeting_capture" and str(path).find("/10 Notes/") != -1:
        warnings.append("fleeting_capture kind should live in 00 Inbox/ before promotion to 10 Notes/.")

    return {
        "path": str(path.relative_to(root)),
        "ok": ok_frontmatter and not errors,
        "zettel_kind": fm.get("zettel_kind"),
        "errors": errors,
        "warnings": warnings,
        "concept_links": body_links["concept_links"],
        "context_links": body_links["context_links"],
        "frontmatter_keys": list(fm.keys()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate zettel notes against the canonical zettel schema.")
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to validate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to the vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "report"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [ZETTEL_FILE_GLOB]))
    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results = [audit_path(path, root) for path in paths]
    overall_ok = all(result["ok"] for result in results)
    print(dump_json({"ok": overall_ok, "count": len(results), "results": results}))
    return 0 if overall_ok or args.mode == "report" else 1


if __name__ == "__main__":
    raise SystemExit(main())
