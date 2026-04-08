#!/usr/bin/env python3
"""Render the Recipe Library Base from validated recipe notes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from recipe_models import (
    RECIPE_FILE_GLOB,
    RECIPE_BASE_PATH,
    RecipeFrontmatter,
    dump_json,
    load_markdown_note,
    validate_frontmatter,
)


def render_base(paths: list[Path]) -> list[dict]:
    """Collect validated recipe frontmatter into a flat table."""
    rows = []
    for path in paths:
        note = load_markdown_note(path)
        fm = note.frontmatter

        result = validate_frontmatter(fm)
        if not result.ok:
            continue

        macros = fm.get("macros", {})
        ingredients = fm.get("ingredients", [])
        equipment = fm.get("equipment", [])

        rows.append({
            "title": fm.get("title", path.stem),
            "recipe_kind": fm.get("recipe_kind"),
            "status": fm.get("status"),
            "servings": fm.get("servings"),
            "prep_time_min": fm.get("prep_time_min"),
            "cook_time_min": fm.get("cook_time_min", 0),
            "calories": macros.get("calories"),
            "protein_g": macros.get("protein_g"),
            "carbs_g": macros.get("carbs_g"),
            "fat_g": macros.get("fat_g"),
            "ingredient_count": len(ingredients),
            "equipment_count": len(equipment),
            "cuisine": fm.get("cuisine"),
            "source": fm.get("source"),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Recipe Library Base")
    parser.add_argument("--glob", default=RECIPE_FILE_GLOB, help="Glob pattern")
    parser.add_argument("--output", default=RECIPE_BASE_PATH, help="Output base path")
    args = parser.parse_args()

    from glob import glob
    paths = sorted(Path(p) for p in glob(args.glob))

    rows = render_base(paths)
    print(dump_json({"total": len(rows), "recipes": rows}))


if __name__ == "__main__":
    main()
