#!/usr/bin/env python3
"""Validate CV entry notes against the canonical cv_entry_kind schema."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from cv_models import (
    CV_NOTE_GLOB,
    AuditResult,
    CvEntryStatus,
    dump_json,
    ensure_string_list,
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

    kind = str(fm.get("cv_entry_kind") or "")
    status_val = str(fm.get("status") or "")

    if not kind:
        warnings.append("Missing `cv_entry_kind`. Run migrate_cv.py to inject.")

    if not status_val:
        warnings.append("Missing `status`. Run migrate_cv.py to inject.")

    # Warn on role entries with unquantified bullets
    if kind == "role":
        bullets = fm.get("bullets")
        if isinstance(bullets, list):
            unquantified = sum(
                1 for b in bullets
                if isinstance(b, dict) and not b.get("quantified", False)
            )
            if unquantified > 0:
                warnings.append(
                    f"{unquantified} bullet(s) not yet quantified — highest-leverage CV improvement."
                )
        elif bullets is None:
            warnings.append("No bullets defined for this role entry.")

    # Warn on missing potential_links
    if not fm.get("potential_links"):
        warnings.append("Missing `potential_links` — run migrate_cv.py to initialise.")

    return AuditResult(
        path=rel,
        ok=result.ok and not errors,
        cv_entry_kind=kind or None,
        status=status_val or None,
        errors=errors,
        warnings=warnings,
        frontmatter_keys=list(fm.keys()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate CV entry notes against the canonical cv_entry_kind schema."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to validate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "report"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [CV_NOTE_GLOB]))
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
