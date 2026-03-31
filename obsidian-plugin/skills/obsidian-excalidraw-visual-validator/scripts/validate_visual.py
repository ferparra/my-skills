#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from visual_validator_config import VisualValidatorConfig
from visual_validator_models import (
    VisualAuditResult,
    dump_json,
    extract_excalidraw_json,
    load_markdown_note,
    parse_drawing,
    validate_visual,
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


def audit_path(
    path: Path, root: Path, config: VisualValidatorConfig, do_render: bool, output_dir: Path
) -> dict[str, Any]:
    """Audit a single .excalidraw.md file for visual quality."""
    errors: list[str] = []
    warnings: list[str] = []
    render_path: str | None = None

    try:
        # Load and parse
        note = load_markdown_note(path)
        drawing_json = extract_excalidraw_json(note.body, path)

        if drawing_json is None:
            errors.append("Could not extract JSON from markdown")
            return {
                "path": str(path.relative_to(root)),
                "ok": False,
                "errors": errors,
                "warnings": warnings,
                "element_count": 0,
                "render_path": None,
            }

        drawing = parse_drawing(drawing_json)

        # Filter out deleted elements
        active_elements = [
            el for el in drawing.elements if not getattr(el, "isDeleted", False)
        ]

        # Run visual validation checks
        check_errors, check_warnings = validate_visual(active_elements, config)
        errors.extend(check_errors)
        warnings.extend(check_warnings)

        # Optional: render to PNG
        if do_render:
            from render_excalidraw import render_to_png

            output_png = output_dir / f"{path.stem}.png"
            render_result = render_to_png(path, output_png, config)

            if render_result["ok"]:
                render_path = render_result["render_path"]
            else:
                warnings.append(f"Render failed: {render_result.get('error', 'unknown')}")

        return {
            "path": str(path.relative_to(root)),
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "element_count": len(active_elements),
            "render_path": render_path,
        }

    except Exception as e:
        errors.append(f"Validation failed: {e}")
        return {
            "path": str(path.relative_to(root)),
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "element_count": 0,
            "render_path": None,
        }


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Excalidraw drawings for visual quality."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "report"], default="check")
    parser.add_argument("--render", action="store_true", help="Also render to PNG (requires Playwright).")
    parser.add_argument(
        "--output-dir",
        default=".skills/excalidraw-renders",
        help="Output directory for PNG renders.",
    )

    args = parser.parse_args()

    config = VisualValidatorConfig(vault_root=args.vault_root)
    root = Path(args.vault_root).resolve()
    output_dir = root / args.output_dir

    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [config.file_glob]))

    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results = [audit_path(path, root, config, args.render, output_dir) for path in paths]
    overall_ok = all(result["ok"] for result in results)

    print(dump_json({"ok": overall_ok, "count": len(results), "results": results}))

    return 0 if overall_ok or args.mode == "report" else 1


if __name__ == "__main__":
    raise SystemExit(main())
