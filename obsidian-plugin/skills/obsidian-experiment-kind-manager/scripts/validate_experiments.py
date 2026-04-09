#!/usr/bin/env python3
"""Validate experiment notes against the ExperimentFrontmatter Pydantic v2 schema.

Usage:
    uvx --from python --with pydantic --with pyyaml python validate_experiments.py \
        --glob "10 Notes/Productivity/Experiments/**/*.md" --mode check

    uvx --from python --with pydantic --with pyyaml python validate_experiments.py \
        --path "10 Notes/Productivity/Experiments/My Experiment.md"

Exit code: 0 if all notes pass, 1 if any errors are found.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

from experiment_models import (
    AuditResult,
    ExperimentFrontmatter,
    dump_json,
    infer_experiment_kind,
    load_markdown_note,
    validate_frontmatter,
)


def resolve_notes(glob: str | None, path: str | None, vault_root: Path) -> list[Path]:
    if path:
        p = Path(path) if Path(path).is_absolute() else vault_root / path
        return [p] if p.exists() else []
    pattern = glob or "10 Notes/Productivity/Experiments/**/*.md"
    return [
        p for p in vault_root.rglob("*.md")
        if fnmatch.fnmatch(str(p.relative_to(vault_root)), pattern)
        and p.stem != "_hub"
    ]


def audit_note(path: Path) -> AuditResult:
    try:
        note = load_markdown_note(path)
    except Exception as exc:
        return AuditResult(path=str(path), ok=False, errors=[f"Failed to read note: {exc}"])

    fm = note.frontmatter
    warnings: list[str] = []

    kind_value = str(fm.get("experiment_kind") or "").strip()
    inferred_kind, is_ambiguous = infer_experiment_kind(fm, path)

    if not kind_value:
        if is_ambiguous:
            warnings.append(
                f"experiment_kind is missing and ambiguous — inferred: {inferred_kind!r}. "
                "Manual confirmation required."
            )
        else:
            warnings.append(f"experiment_kind is missing — inferred: {inferred_kind!r}")

    result = validate_frontmatter(fm)

    return AuditResult(
        path=str(path),
        ok=result.ok,
        experiment_kind=kind_value or inferred_kind,
        experiment_id=str(fm.get("experiment_id") or ""),
        status=str(fm.get("status") or ""),
        outcome=str(fm.get("outcome") or ""),
        council_owner=str(fm.get("council_owner") or ""),
        errors=result.errors,
        warnings=warnings,
        frontmatter_keys=list(fm.keys()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate experiment notes.")
    parser.add_argument("--glob", help="Glob pattern relative to vault root.")
    parser.add_argument("--path", help="Single note path.")
    parser.add_argument("--mode", default="check", choices=["check"], help="Only check is supported.")
    parser.add_argument("--vault", default=str(Path.home() / "my-vault"), help="Vault root path.")
    args = parser.parse_args()

    vault_root = Path(args.vault)
    notes = resolve_notes(args.glob, args.path, vault_root)

    if not notes:
        print(dump_json({"ok": True, "message": "No experiment notes found.", "results": []}))
        return 0

    results = [audit_note(p) for p in notes]
    all_ok = all(r.ok for r in results)
    error_count = sum(len(r.errors) for r in results)
    warning_count = sum(len(r.warnings) for r in results)

    summary = {
        "ok": all_ok,
        "total": len(results),
        "passed": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "error_count": error_count,
        "warning_count": warning_count,
        "results": [r.model_dump() for r in results],
    }

    print(dump_json(summary))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
