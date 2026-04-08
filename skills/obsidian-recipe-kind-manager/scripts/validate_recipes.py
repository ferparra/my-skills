#!/usr/bin/env python3
"""Validate recipe notes against the RecipeFrontmatter schema."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from recipe_models import (
    RECIPE_FILE_GLOB,
    AuditResult,
    RecipeFrontmatter,
    ValidationError,
    dump_json,
    infer_recipe_kind,
    infer_status_from_tags,
    load_markdown_note,
    validate_frontmatter,
)


def audit_note(path: Path) -> AuditResult:
    note = load_markdown_note(path)
    fm = note.frontmatter

    inferred_kind = infer_recipe_kind(fm)
    inferred_status = infer_status_from_tags(fm)

    result = validate_frontmatter(fm)

    return AuditResult(
        path=str(path),
        ok=result.ok,
        recipe_kind=fm.get("recipe_kind"),
        inferred_recipe_kind=inferred_kind.value if inferred_kind else None,
        status=fm.get("status") or inferred_status.value,
        errors=result.errors,
        warnings=[],
        frontmatter_keys=list(fm.keys()),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate recipe notes")
    parser.add_argument("--glob", default=RECIPE_FILE_GLOB, help="Glob pattern")
    parser.add_argument("--path", help="Single note path")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    if args.path:
        paths = [Path(args.path)]
    else:
        from glob import glob
        paths = sorted(Path(p) for p in glob(args.glob))

    results = [audit_note(p) for p in paths]
    overall_ok = all(r.ok for r in results)

    report = {
        "ok": overall_ok,
        "total": len(results),
        "passed": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "notes": [json.loads(r.model_dump_json()) for r in results],
    }

    print(dump_json(report))

    if not overall_ok and args.mode == "check":
        sys.exit(1)


if __name__ == "__main__":
    main()
