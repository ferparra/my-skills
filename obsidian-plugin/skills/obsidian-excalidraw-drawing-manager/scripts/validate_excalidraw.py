#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from excalidraw_config import ExcalidrawConfig
from models import (
    dump_json,
    extract_excalidraw_json,
    load_markdown_note,
    parse_drawing,
    validate_drawing,
    validate_frontmatter,
)


def expand_paths(root: Path, paths: list[str], globs: list[str]) -> list[Path]:
    """Expand paths and globs to a list of unique .md files."""
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


def audit_path(path: Path, root: Path, config: ExcalidrawConfig) -> dict[str, Any]:
    """Audit a single .excalidraw.md file."""
    note = load_markdown_note(path)
    errors: list[str] = []
    warnings: list[str] = []

    # Validate frontmatter
    ok_frontmatter, frontmatter_errors = validate_frontmatter(note.frontmatter)
    errors.extend(frontmatter_errors)

    # Check for required sections
    if "# Excalidraw Data" not in note.body:
        errors.append("Missing '# Excalidraw Data' section")

    # Extract and validate drawing JSON
    drawing_json = None
    element_count = 0
    text_element_count = 0

    try:
        # Pass the full path for decompression if needed
        drawing_json = extract_excalidraw_json(note.body, path)
        if drawing_json is None:
            errors.append("Could not find JSON or compressed-json code block in ## Drawing section")
        else:
            # Parse drawing
            try:
                drawing = parse_drawing(drawing_json)
                element_count = len(drawing.elements)
                text_element_count = sum(1 for el in drawing.elements if el.type == "text")

                # Run anti-pattern checks
                drawing_errors, drawing_warnings = validate_drawing(drawing, note.body)
                errors.extend(drawing_errors)
                warnings.extend(drawing_warnings)

            except Exception as e:
                errors.append(f"Failed to parse drawing: {e}")

    except Exception as e:
        errors.append(f"Failed to extract JSON: {e}")

    return {
        "path": str(path.relative_to(root)),
        "ok": ok_frontmatter and not errors,
        "errors": errors,
        "warnings": warnings,
        "element_count": element_count,
        "text_element_count": text_element_count,
    }


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Excalidraw drawings against the canonical schema."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to validate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "report"], default="check")
    args = parser.parse_args()

    config = ExcalidrawConfig(vault_root=args.vault_root)
    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [config.file_glob]))

    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results = [audit_path(path, root, config) for path in paths]
    overall_ok = all(result["ok"] for result in results)
    print(dump_json({"ok": overall_ok, "count": len(results), "results": results}))
    return 0 if overall_ok or args.mode == "report" else 1


if __name__ == "__main__":
    raise SystemExit(main())
