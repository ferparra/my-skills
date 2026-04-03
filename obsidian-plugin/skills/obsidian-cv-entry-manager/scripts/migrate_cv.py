#!/usr/bin/env python3
"""Normalize CV entry notes to the canonical cv_entry_kind schema."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cv_models import (
    CV_NOTE_GLOB,
    CvEntryKind,
    CvEntryStatus,
    MigrateResult,
    dedupe_preserve,
    dump_json,
    ensure_string_list,
    load_markdown_note,
    normalize_cv_tags,
    order_frontmatter,
    render_markdown,
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


def set_if_missing(
    frontmatter: dict[str, Any],
    key: str,
    value: Any,
    changed_fields: list[str],
) -> None:
    existing = frontmatter.get(key)
    if existing is None or existing == "" or existing == []:
        frontmatter[key] = value
        changed_fields.append(key)


def infer_kind_from_path(path: Path) -> str | None:
    parts = [p.lower() for p in path.parts]
    if "roles" in parts:
        return CvEntryKind.ROLE.value
    if "education" in parts:
        return CvEntryKind.EDUCATION.value
    if "credentials" in parts:
        fm_keys_hint = None  # can't infer cert vs award from path alone
        return None
    if "community" in parts:
        return CvEntryKind.COMMUNITY.value
    return None


def infer_kind_from_frontmatter(fm: dict[str, Any]) -> str | None:
    if fm.get("company_name") and fm.get("role_title"):
        return CvEntryKind.ROLE.value
    if fm.get("institution") and fm.get("qualification"):
        return CvEntryKind.EDUCATION.value
    if fm.get("certification_name"):
        return CvEntryKind.CERTIFICATION.value
    if fm.get("award_name"):
        return CvEntryKind.AWARD.value
    if fm.get("activity_name"):
        return CvEntryKind.COMMUNITY.value
    return None


def normalize_cv_entry(
    note_frontmatter: dict[str, Any],
    note_body: str,
    *,
    inferred_kind: str | None = None,
) -> dict[str, Any]:
    frontmatter = dict(note_frontmatter)
    original_key_order = list(frontmatter.keys())
    warnings: list[str] = []
    errors: list[str] = []
    changed_fields: list[str] = []

    # 1. Determine cv_entry_kind
    if not frontmatter.get("cv_entry_kind"):
        kind = inferred_kind or infer_kind_from_frontmatter(frontmatter)
        if kind:
            frontmatter["cv_entry_kind"] = kind
            changed_fields.append("cv_entry_kind")
        else:
            warnings.append(
                "Cannot infer cv_entry_kind — set it manually."
            )
            frontmatter.setdefault("cv_entry_kind", "role")
            changed_fields.append("cv_entry_kind")

    kind_val = str(frontmatter.get("cv_entry_kind", "role"))

    # 2. Inject status if missing
    if not frontmatter.get("status"):
        # Infer from tags
        tags = ensure_string_list(frontmatter.get("tags"))
        if "status/processed" in tags:
            frontmatter["status"] = CvEntryStatus.PROCESSED.value
        elif "status/processing" in tags:
            frontmatter["status"] = CvEntryStatus.PROCESSING.value
        else:
            frontmatter["status"] = CvEntryStatus.PROCESSING.value
        changed_fields.append("status")
    else:
        raw_status = str(frontmatter["status"])
        valid_statuses = {s.value for s in CvEntryStatus}
        if raw_status not in valid_statuses:
            warnings.append(f"Unknown status '{raw_status}', defaulting to processing.")
            frontmatter["status"] = CvEntryStatus.PROCESSING.value
            changed_fields.append("status")

    status_val = str(frontmatter["status"])

    # 3. Initialise connection_strength if missing
    set_if_missing(frontmatter, "connection_strength", 0.0, changed_fields)

    # 4. Initialise potential_links if missing
    if not frontmatter.get("potential_links"):
        frontmatter["potential_links"] = ["[[10 Notes/Fernando|Fernando]]"]
        changed_fields.append("potential_links")
        warnings.append("potential_links initialised with placeholder.")

    # 5. Initialise recency_weight if missing
    set_if_missing(frontmatter, "recency_weight", "low", changed_fields)

    # 6. Initialise pillars if missing
    set_if_missing(frontmatter, "pillars", [], changed_fields)

    # 7. Kind-specific FIXME placeholders
    if kind_val == CvEntryKind.ROLE.value:
        if not frontmatter.get("company_name"):
            frontmatter["company_name"] = "FIXME: company name"
            changed_fields.append("company_name")
            warnings.append("`company_name` initialised with placeholder.")
        if not frontmatter.get("role_title"):
            frontmatter["role_title"] = "FIXME: role title"
            changed_fields.append("role_title")
            warnings.append("`role_title` initialised with placeholder.")
        if not frontmatter.get("start_date"):
            frontmatter["start_date"] = "FIXME"
            changed_fields.append("start_date")
            warnings.append("`start_date` initialised with placeholder.")
    elif kind_val == CvEntryKind.EDUCATION.value:
        if not frontmatter.get("institution"):
            frontmatter["institution"] = "FIXME: institution name"
            changed_fields.append("institution")
            warnings.append("`institution` initialised with placeholder.")
        if not frontmatter.get("qualification"):
            frontmatter["qualification"] = "FIXME: qualification"
            changed_fields.append("qualification")
            warnings.append("`qualification` initialised with placeholder.")
    elif kind_val == CvEntryKind.CERTIFICATION.value:
        if not frontmatter.get("certification_name"):
            frontmatter["certification_name"] = "FIXME: certification name"
            changed_fields.append("certification_name")
            warnings.append("`certification_name` initialised with placeholder.")
    elif kind_val == CvEntryKind.AWARD.value:
        if not frontmatter.get("award_name"):
            frontmatter["award_name"] = "FIXME: award name"
            changed_fields.append("award_name")
            warnings.append("`award_name` initialised with placeholder.")
    elif kind_val == CvEntryKind.COMMUNITY.value:
        if not frontmatter.get("activity_name"):
            frontmatter["activity_name"] = "FIXME: activity name"
            changed_fields.append("activity_name")
            warnings.append("`activity_name` initialised with placeholder.")

    # 8. Normalise tags
    frontmatter["tags"] = normalize_cv_tags(
        frontmatter, kind=kind_val, status=status_val
    )

    # 9. Order frontmatter canonically
    normalized = order_frontmatter(frontmatter, original_key_order)

    # 10. Validate after normalisation
    validation = validate_frontmatter(dict(normalized))
    if not validation.ok:
        errors.extend(validation.errors)

    return {
        "frontmatter": dict(normalized),
        "body": note_body,
        "warnings": warnings,
        "errors": errors,
        "changed_fields": changed_fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize CV entry notes to the canonical cv_entry_kind schema."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to migrate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    default_globs = args.glob or ([] if args.path else [CV_NOTE_GLOB])
    paths = expand_paths(root, args.path, default_globs)
    if not paths:
        print(json.dumps({"ok": False, "error": "no_paths"}, indent=2))
        return 1

    results: list[MigrateResult] = []
    overall_ok = True

    for path in paths:
        note = load_markdown_note(path)
        inferred = infer_kind_from_path(path)
        normalized = normalize_cv_entry(note.frontmatter, note.body, inferred_kind=inferred)
        rendered = render_markdown(normalized["frontmatter"], normalized["body"])
        current = path.read_text(encoding="utf-8", errors="replace")
        changed = rendered != current

        has_errors = bool(normalized["errors"])

        result = MigrateResult(
            path=str(path.relative_to(root)),
            changed=changed,
            changed_fields=normalized["changed_fields"],
            warnings=normalized["warnings"],
            errors=normalized["errors"],
        )

        if has_errors:
            overall_ok = False

        if args.mode == "check" and changed:
            overall_ok = False

        if args.mode == "fix":
            if has_errors:
                result = result.model_copy(
                    update={
                        "skipped": True,
                        "skip_reason": "validation_errors",
                    }
                )
            elif changed:
                path.write_text(rendered, encoding="utf-8")

        results.append(result)

    payload = {
        "ok": overall_ok,
        "count": len(results),
        "results": [r.model_dump() for r in results],
    }
    print(dump_json(payload))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
