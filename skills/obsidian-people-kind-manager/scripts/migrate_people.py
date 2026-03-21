#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from people_models import (
    PEOPLE_FILE_GLOB,
    MigrateResult,
    PersonKind,
    PersonStatus,
    dedupe_preserve,
    dump_json,
    ensure_string_list,
    infer_person_kind,
    infer_status_from_tags,
    load_markdown_note,
    normalize_person_tags,
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
    """Set key only if absent or empty. Records change."""
    existing = frontmatter.get(key)
    if existing is None or existing == "" or existing == []:
        frontmatter[key] = value
        changed_fields.append(key)


def normalize_person(
    note_frontmatter: dict[str, Any],
    note_body: str,
) -> dict[str, Any]:
    """Return normalized frontmatter dict plus migration metadata."""
    frontmatter = dict(note_frontmatter)
    original_key_order = list(frontmatter.keys())
    warnings: list[str] = []
    errors: list[str] = []
    changed_fields: list[str] = []

    # 1. Determine person_kind
    inference = infer_person_kind(frontmatter)
    kind = inference.kind

    if inference.is_ambiguous:
        warnings.append(
            f"Ambiguous person_kind inference (multiple signals); defaulted to '{kind.value}'. "
            "Confirm and set person_kind manually if incorrect."
        )
    set_if_missing(frontmatter, "person_kind", kind.value, changed_fields)
    # Normalize even if already present
    try:
        kind = PersonKind(str(frontmatter["person_kind"]))
        frontmatter["person_kind"] = kind.value
    except ValueError:
        warnings.append(f"Unknown person_kind '{frontmatter['person_kind']}'; leaving as-is.")

    # 2. Infer status from tags if not set
    if not frontmatter.get("status"):
        inferred_status = infer_status_from_tags(frontmatter)
        frontmatter["status"] = inferred_status.value
        changed_fields.append("status")
    else:
        raw_status = str(frontmatter["status"])
        valid_statuses = {s.value for s in PersonStatus}
        if raw_status not in valid_statuses:
            warnings.append(f"Unknown status '{raw_status}', defaulting to fleeting.")
            frontmatter["status"] = PersonStatus.FLEETING.value
            changed_fields.append("status")

    # 3. Preserve connection_strength; initialise to 0.0 if missing
    set_if_missing(frontmatter, "connection_strength", 0.0, changed_fields)

    # 4. Preserve potential_links; initialise with a placeholder if missing
    if not frontmatter.get("potential_links"):
        frontmatter["potential_links"] = ["[[People/People Hub|People Hub]]"]
        changed_fields.append("potential_links")
        warnings.append("potential_links initialised with placeholder — update with actual wikilinks.")

    # 5. Ensure potential_links is a deduplicated list of strings
    frontmatter["potential_links"] = dedupe_preserve(
        [str(item) for item in frontmatter.get("potential_links") or []]
    )

    # 6. Ensure aliases is a list
    existing_aliases = frontmatter.get("aliases", [])
    if isinstance(existing_aliases, str):
        frontmatter["aliases"] = [existing_aliases]
        changed_fields.append("aliases")
    elif not isinstance(existing_aliases, list):
        frontmatter["aliases"] = []
        changed_fields.append("aliases")

    # 7. Kind-specific field defaults (FIXME placeholders + warnings; never hard errors except author)
    kind_val = str(frontmatter.get("person_kind", ""))
    if kind_val == PersonKind.MANAGER.value and not frontmatter.get("management_cadence"):
        frontmatter["management_cadence"] = "FIXME: e.g. weekly 1:1 / monthly review"
        changed_fields.append("management_cadence")
        warnings.append("`management_cadence` initialised with placeholder — update with actual cadence.")
    if kind_val == PersonKind.STAKEHOLDER.value and not frontmatter.get("influence_domain"):
        frontmatter["influence_domain"] = "FIXME: e.g. data-platform / sales / product"
        changed_fields.append("influence_domain")
        warnings.append("`influence_domain` initialised with placeholder — update with actual domain.")
    if kind_val == PersonKind.CUSTOMER_CONTACT.value and not frontmatter.get("account_context"):
        frontmatter["account_context"] = "FIXME: e.g. [[Companies/Acme|Acme]]"
        changed_fields.append("account_context")
        warnings.append("`account_context` initialised with placeholder — update with actual context.")
    if kind_val == PersonKind.MENTOR.value and not frontmatter.get("domain_of_mentorship"):
        frontmatter["domain_of_mentorship"] = "FIXME: e.g. career / technical / leadership"
        changed_fields.append("domain_of_mentorship")
        warnings.append("`domain_of_mentorship` initialised with placeholder — update with actual domain.")
    if kind_val == PersonKind.AUTHOR.value and not frontmatter.get("primary_works"):
        frontmatter["primary_works"] = ["FIXME: list primary works / wikilinks"]
        changed_fields.append("primary_works")
        warnings.append("`primary_works` initialised with placeholder — required for `author` kind.")
    if kind_val == PersonKind.ACQUAINTANCE.value and not frontmatter.get("personal_context"):
        frontmatter["personal_context"] = "FIXME: e.g. friend / family/sibling / partner"
        changed_fields.append("personal_context")
        warnings.append("`personal_context` initialised with placeholder — update with actual context.")

    # 8. Normalise tags (managed prefixes only; user tags preserved)
    frontmatter["tags"] = normalize_person_tags(
        frontmatter, kind=str(frontmatter["person_kind"]), status=str(frontmatter["status"])
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
        description="Normalize person notes to the canonical person schema."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to migrate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    default_globs = args.glob or ([] if args.path else [PEOPLE_FILE_GLOB])
    paths = expand_paths(root, args.path, default_globs)
    if not paths:
        print(json.dumps({"ok": False, "error": "no_paths"}, indent=2))
        return 1

    results: list[MigrateResult] = []
    overall_ok = True

    for path in paths:
        note = load_markdown_note(path)
        normalized = normalize_person(note.frontmatter, note.body)
        rendered = render_markdown(normalized["frontmatter"], normalized["body"])
        current = path.read_text(encoding="utf-8", errors="replace")
        changed = rendered != current

        has_ambiguity = any("Ambiguous" in w for w in normalized["warnings"])
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
            if has_errors or has_ambiguity:
                result = result.model_copy(
                    update={
                        "skipped": True,
                        "skip_reason": "ambiguous_kind" if has_ambiguity else "validation_errors",
                    }
                )
                if has_ambiguity:
                    result.errors.append(
                        "Skipped write due to ambiguous person_kind inference — confirm kind manually."
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
