#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from exercise_models import (
    EXERCISE_FILE_GLOB,
    ExerciseKind,
    dump_json,
    extract_training_metrics,
    infer_component_exercises,
    infer_exercise_kind,
    infer_fatigue_cost,
    infer_progression_mode,
    infer_strong_exercise_names,
    infer_strong_weight_unit,
    infer_stability_profile,
    infer_volume_tracking,
    load_markdown_note,
    normalize_equipment_list,
    normalize_exercise_tags,
    order_frontmatter,
    render_markdown,
    validate_frontmatter,
    volume_credits_for,
    derive_secondary_muscles,
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


def normalize_note(path: Path) -> dict[str, Any]:
    note = load_markdown_note(path)
    original = dict(note.frontmatter)
    original_order = list(original.keys())
    updated = dict(original)
    warnings: list[str] = []
    errors: list[str] = []
    changed_fields: list[str] = []

    kind, ambiguous = infer_exercise_kind(updated, note.body, path)
    if ambiguous:
        warnings.append("Kind inference is low confidence; defaulting to exercise_brief.")

    def set_if_changed(key: str, value: Any, *, only_if_missing: bool = False) -> None:
        nonlocal updated
        if only_if_missing and key in updated and updated.get(key) not in (None, "", [], {}):
            return
        if updated.get(key) != value:
            updated[key] = value
            changed_fields.append(key)

    set_if_changed("exercise_kind", kind.value, only_if_missing=True)
    set_if_changed("tags", normalize_exercise_tags(updated, kind=kind))

    normalized_equipment = normalize_equipment_list(updated.get("equipment"))
    if normalized_equipment:
        set_if_changed("equipment", normalized_equipment)

    progression_mode = infer_progression_mode(kind, updated)
    set_if_changed("progression_mode", progression_mode.value, only_if_missing=True)

    volume_tracking = infer_volume_tracking(kind, updated)
    set_if_changed("volume_tracking", volume_tracking.value, only_if_missing=True)
    primary_credit, secondary_credit = volume_credits_for(volume_tracking)
    set_if_changed("volume_primary_credit", primary_credit)
    set_if_changed("volume_secondary_credit", secondary_credit)
    set_if_changed("strong_exercise_names", infer_strong_exercise_names(updated, path), only_if_missing=True)

    strong_weight_unit = infer_strong_weight_unit(updated, kind)
    if strong_weight_unit is not None:
        set_if_changed("strong_weight_unit", strong_weight_unit.value, only_if_missing=True)

    if kind.value in {"hypertrophy", "mobility_drill"} and updated.get("muscle_group") and updated.get("primary_muscle"):
        set_if_changed("secondary_muscles", derive_secondary_muscles(updated))
        set_if_changed("stability_profile", infer_stability_profile(updated, kind, path).value, only_if_missing=True)
        set_if_changed("fatigue_cost", infer_fatigue_cost(updated, kind, path).value, only_if_missing=True)

    if kind.value == "warmup_flow":
        components = infer_component_exercises(note.body)
        if components:
            set_if_changed("component_exercises", components)

    metrics = extract_training_metrics(note.body)
    for key, value in metrics.as_updates().items():
        if key == "last_performed":
            set_if_changed(key, value, only_if_missing=True)
        else:
            set_if_changed(key, value)

    ordered = order_frontmatter(updated, original_order)
    ok, validation_errors = validate_frontmatter(ordered)
    if not ok:
        errors.extend(validation_errors)

    changed = changed_fields or (original_order != list(ordered.keys()))
    return {
        "path": str(path),
        "changed": bool(changed),
        "changed_fields": changed_fields,
        "warnings": warnings,
        "errors": errors,
        "frontmatter": ordered,
        "body": note.body,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate exercise notes to the canonical exercise_kind schema.")
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to migrate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to the vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [EXERCISE_FILE_GLOB]))
    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results = [normalize_note(path) for path in paths]
    overall_ok = all(not result["errors"] for result in results)

    if args.mode == "fix" and overall_ok:
        for result in results:
            if not result["changed"]:
                continue
            path = Path(result["path"])
            path.write_text(render_markdown(result["frontmatter"], result["body"]), encoding="utf-8")

    payload = {
        "ok": overall_ok,
        "count": len(results),
        "mode": args.mode,
        "results": [
            {
                "path": str(Path(result["path"]).relative_to(root)),
                "changed": result["changed"],
                "changed_fields": result["changed_fields"],
                "warnings": result["warnings"],
                "errors": result["errors"],
            }
            for result in results
        ],
    }
    print(dump_json(payload))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
