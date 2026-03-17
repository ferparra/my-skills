#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from exercise_models import (
    EXERCISE_FILE_GLOB,
    dump_json,
    infer_exercise_kind,
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
    inferred_kind, ambiguous = infer_exercise_kind(note.frontmatter, note.body, path)
    ok_frontmatter, frontmatter_errors = validate_frontmatter(note.frontmatter)
    errors = list(frontmatter_errors)
    warnings: list[str] = []

    if not note.frontmatter.get("exercise_kind"):
        warnings.append(f"Missing `exercise_kind`; inferred `{inferred_kind.value}`.")
    if ambiguous:
        warnings.append("Kind inference is low confidence; review before fixing.")

    return {
        "path": str(path.relative_to(root)),
        "ok": ok_frontmatter,
        "exercise_kind": note.frontmatter.get("exercise_kind"),
        "inferred_exercise_kind": inferred_kind.value,
        "errors": errors,
        "warnings": warnings,
        "frontmatter_keys": list(note.frontmatter.keys()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exercise notes against the canonical exercise_kind schema.")
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to validate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to the vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "report"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [EXERCISE_FILE_GLOB]))
    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results = [audit_path(path, root) for path in paths]
    overall_ok = all(result["ok"] for result in results)
    print(dump_json({"ok": overall_ok, "count": len(results), "results": results}))
    return 0 if overall_ok or args.mode == "report" else 1


if __name__ == "__main__":
    raise SystemExit(main())
