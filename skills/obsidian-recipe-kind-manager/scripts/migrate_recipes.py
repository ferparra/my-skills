#!/usr/bin/env python3
"""Migrate free-form recipe notes to the RecipeFrontmatter schema."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from recipe_models import (
    INGREDIENTS_PATH,
    KITCHEN_EQUIPMENT_PATH,
    RECIPE_FILE_GLOB,
    IngredientRef,
    Macros,
    MigrateResult,
    RecipeFrontmatter,
    RecipeKind,
    RecipeStatus,
    dump_json,
    dump_frontmatter,
    ensure_string_list,
    infer_recipe_kind,
    infer_status_from_tags,
    is_wikilink,
    load_markdown_note,
    normalize_jsonable,
    normalize_recipe_tags,
    order_frontmatter,
    render_markdown,
    validate_frontmatter,
)

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
INGREDIENT_LINE_RE = re.compile(
    r"^-\s+(?P<qty>.+?)\s*(?:->|→)\s*(?P<link>\[\[.+?\]\])",
    re.MULTILINE,
)
EQUIPMENT_LINE_RE = re.compile(r"^-\s+(\[\[.+?\]\])", re.MULTILINE)
STEP_LINE_RE = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)


def parse_ingredients_from_body(body: str) -> list[dict]:
    """Parse ingredient lines with wikilinks from the body."""
    ingredients = []
    for m in INGREDIENT_LINE_RE.finditer(body):
        ref = m.group("link").strip()
        qty = m.group("qty").strip()
        if is_wikilink(ref):
            ingredients.append({"ref": ref, "quantity": qty})
    return ingredients


def parse_equipment_from_body(body: str) -> list[str]:
    """Parse equipment wikilinks from the body."""
    equipment = []
    for m in EQUIPMENT_LINE_RE.finditer(body):
        link = m.group(1).strip()
        if is_wikilink(link):
            equipment.append(link)
    return equipment


def parse_steps_from_body(body: str) -> list[str]:
    """Parse numbered preparation steps from the body."""
    steps = []
    for m in STEP_LINE_RE.finditer(body):
        step = m.group(1).strip()
        if step:
            steps.append(step)
    return steps


def extract_description(body: str) -> str:
    """Extract the first non-heading, non-tag paragraph as description."""
    lines = body.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("::"):
            continue
        # Skip tag-only lines
        if re.match(r"^#[\w/-]+$", stripped):
            continue
        if re.match(r"^#[\w/-]+(\s+#[\w/-]+)*$", stripped):
            continue
        return stripped
    return "FIXME"


def migrate_note(path: Path, *, mode: str = "check") -> MigrateResult:
    note = load_markdown_note(path)
    fm = note.frontmatter

    # Infer kind
    inferred_kind = infer_recipe_kind(fm)
    if inferred_kind is None:
        return MigrateResult(
            path=str(path),
            changed=False,
            skipped=True,
            skip_reason="Could not infer recipe_kind",
        )

    inferred_status = infer_status_from_tags(fm)

    # Build new frontmatter
    new_fm: dict = dict(fm)

    # Set recipe_kind
    if "recipe_kind" not in new_fm:
        new_fm["recipe_kind"] = inferred_kind.value
    else:
        try:
            RecipeKind(new_fm["recipe_kind"])
        except ValueError:
            new_fm["recipe_kind"] = inferred_kind.value

    # Set title from filename
    if "title" not in new_fm:
        new_fm["title"] = path.stem

    # Set description
    if "description" not in new_fm:
        new_fm["description"] = extract_description(note.body)

    # Set status
    if "status" not in new_fm or not isinstance(new_fm["status"], str):
        new_fm["status"] = inferred_status.value

    # Set para_type
    if "para_type" not in new_fm:
        new_fm["para_type"] = "resource"

    # Build macros from existing scalar fields
    if "macros" not in new_fm:
        calories = fm.get("calories")
        protein = fm.get("protein")
        carbs = fm.get("carbs")
        fat = fm.get("fat")
        if calories is not None and protein is not None and carbs is not None and fat is not None:
            new_fm["macros"] = {
                "calories": int(float(calories)),
                "protein_g": float(protein),
                "carbs_g": float(carbs),
                "fat_g": float(fat),
            }
        else:
            new_fm["macros"] = {
                "calories": 0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
            }

    # Map prep_time -> prep_time_min
    if "prep_time_min" not in new_fm and "prep_time" in fm:
        new_fm["prep_time_min"] = int(float(fm["prep_time"]))

    # Set cook_time_min
    if "cook_time_min" not in new_fm:
        new_fm["cook_time_min"] = 0

    # Parse ingredients from body if not in frontmatter
    if "ingredients" not in new_fm:
        parsed = parse_ingredients_from_body(note.body)
        if parsed:
            new_fm["ingredients"] = parsed
        else:
            new_fm["ingredients"] = [{"ref": "[[FIXME]]", "quantity": "FIXME"}]

    # Parse equipment from body if not in frontmatter
    if "equipment" not in new_fm:
        new_fm["equipment"] = parse_equipment_from_body(note.body)

    # Parse steps from body if not in frontmatter
    if "steps" not in new_fm:
        new_fm["steps"] = parse_steps_from_body(note.body)
        if not new_fm["steps"]:
            new_fm["steps"] = ["FIXME: add preparation steps"]

    # Normalize tags
    new_fm["tags"] = normalize_recipe_tags(
        new_fm, kind=new_fm["recipe_kind"], status=new_fm["status"]
    )

    # Determine what changed
    changed_fields = sorted(set(new_fm.keys()) - set(fm.keys()))

    if mode == "fix":
        # Order frontmatter and write
        ordered = order_frontmatter(new_fm)
        new_content = render_markdown(dict(ordered), note.body)
        path.write_text(new_content, encoding="utf-8")

    return MigrateResult(
        path=str(path),
        changed=bool(changed_fields),
        changed_fields=changed_fields,
        warnings=[],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate recipe notes")
    parser.add_argument("--glob", default=RECIPE_FILE_GLOB, help="Glob pattern")
    parser.add_argument("--path", help="Single note path")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    if args.path:
        paths = [Path(args.path)]
    else:
        from glob import glob
        paths = sorted(Path(p) for p in glob(args.glob))

    results = [migrate_note(p, mode=args.mode) for p in paths]

    report = {
        "total": len(results),
        "changed": sum(1 for r in results if r.changed),
        "skipped": sum(1 for r in results if r.skipped),
        "notes": [json.loads(r.model_dump_json()) for r in results],
    }

    print(dump_json(report))


if __name__ == "__main__":
    main()
