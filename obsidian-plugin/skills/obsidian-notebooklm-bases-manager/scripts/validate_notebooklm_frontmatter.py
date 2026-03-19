#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from jsonschema import Draft202012Validator

from notebooklm_frontmatter_utils import load_note, load_schema


def semantic_checks(frontmatter: dict[str, Any], derived: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    note_kind = frontmatter.get("notebooklm_note_kind")
    note_type = frontmatter.get("type")

    if note_kind == "map" and note_type != "moc":
        errors.append('`notebooklm_note_kind: map` requires `type: moc`.')

    if note_kind == "notebook":
        if note_type not in {"note", "resource"}:
            warnings.append("Notebook records usually use `type: note` or `type: resource`.")
        if frontmatter.get("para_type") not in {None, "resource", "project", "area"}:
            warnings.append("`para_type` should normally be one of resource, project, or area.")

    if not derived["has_status_tag"]:
        errors.append("`tags` must include at least one `status/...` tag.")

    return errors, warnings


def validate_note(path: str, schema: dict[str, Any]) -> dict[str, Any]:
    note = load_note(path)
    validator = Draft202012Validator(schema)
    schema_errors = sorted(
        validator.iter_errors(note["frontmatter"]),
        key=lambda error: list(error.path),
    )

    errors = [
        error.message if not error.path else f'{".".join(str(part) for part in error.path)}: {error.message}'
        for error in schema_errors
    ]
    semantic_errors, warnings = semantic_checks(note["frontmatter"], note["derived"])
    errors.extend(semantic_errors)

    recommended_missing = []
    if note["frontmatter"].get("notebooklm_note_kind") == "notebook":
        for field in [
            "notebooklm_professional_track",
            "notebooklm_life_track",
            "notebooklm_review_due",
            "notebooklm_source_note",
        ]:
            if field not in note["frontmatter"]:
                recommended_missing.append(field)

    return {
        "path": note["path"],
        "ok": len(errors) == 0,
        "note_kind": note["derived"]["note_kind"],
        "errors": errors,
        "warnings": warnings,
        "recommended_missing": recommended_missing,
        "frontmatter_keys": sorted(note["frontmatter"].keys()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate NotebookLM note frontmatter against the canonical schema.",
    )
    parser.add_argument(
        "--path",
        action="append",
        required=True,
        help="NotebookLM note path. Repeat for multiple notes.",
    )
    parser.add_argument(
        "--schema",
        help="Optional override for the NotebookLM frontmatter schema JSON file.",
    )
    args = parser.parse_args()

    schema = load_schema(args.schema)
    results = [validate_note(path, schema) for path in args.path]
    ok = all(result["ok"] for result in results)
    payload = {"ok": ok, "count": len(results), "results": results}
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
