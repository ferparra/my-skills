#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from zettel_models import (
    INBOX_FILE_GLOB,
    ZETTEL_FILE_GLOB,
    NoteParts,
    ZettelKind,
    classify_body_links,
    dedupe_preserve,
    dump_json,
    infer_status_from_tags,
    infer_zettel_kind,
    load_markdown_note,
    make_zettel_id,
    normalize_zettel_tags,
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


def normalize_zettel(note: NoteParts, root: Path) -> dict[str, Any]:
    frontmatter = dict(note.frontmatter)
    original_key_order = list(frontmatter.keys())
    warnings: list[str] = []
    errors: list[str] = []

    # 1. Determine zettel_kind
    if frontmatter.get("zettel_kind"):
        kind_str = str(frontmatter["zettel_kind"])
        try:
            kind = ZettelKind(kind_str)
        except ValueError:
            warnings.append(f"Unknown zettel_kind '{kind_str}', defaulting to atomic.")
            kind = ZettelKind.ATOMIC
        frontmatter["zettel_kind"] = kind.value
    else:
        kind, is_ambiguous = infer_zettel_kind(frontmatter, note.path)
        frontmatter["zettel_kind"] = kind.value
        if is_ambiguous:
            warnings.append(
                f"Ambiguous zettel_kind inference (multiple signals); defaulted to '{kind.value}'. "
                "Confirm and set zettel_kind manually if incorrect."
            )

    # 2. Generate zettel_id if missing
    frontmatter["zettel_id"] = make_zettel_id(note.path, frontmatter)

    # 3. Infer status from existing status/ tags if not set
    if not frontmatter.get("status"):
        inferred_status = infer_status_from_tags(frontmatter)
        frontmatter["status"] = inferred_status.value
    else:
        raw_status = str(frontmatter["status"])
        valid_statuses = {"fleeting", "processing", "processed", "evergreen"}
        if raw_status not in valid_statuses:
            warnings.append(f"Unknown status '{raw_status}', defaulting to fleeting.")
            frontmatter["status"] = "fleeting"

    # 4. Preserve connection_strength; initialise to 0.0 if missing
    if "connection_strength" not in frontmatter:
        frontmatter["connection_strength"] = 0.0

    # 5. Preserve potential_links; initialise to hub if missing
    if not frontmatter.get("potential_links"):
        frontmatter["potential_links"] = ["[[10 Notes/Notes Infrastructure Hub|Notes Infrastructure Hub]]"]

    # 6. Ensure aliases is a list
    existing_aliases = frontmatter.get("aliases", [])
    if isinstance(existing_aliases, str):
        frontmatter["aliases"] = [existing_aliases]
    elif not isinstance(existing_aliases, list):
        frontmatter["aliases"] = []

    # 7. Kind-specific field defaults
    kind_val = frontmatter["zettel_kind"]
    if kind_val == ZettelKind.LITNOTE.value and not frontmatter.get("source"):
        warnings.append(
            "litnote zettel is missing required `source` field. Set `source` manually."
        )
    if kind_val == ZettelKind.MOC.value and not frontmatter.get("hub_for"):
        frontmatter["hub_for"] = ["FIXME: list the concept notes this MOC curates"]
        warnings.append(
            "moc `hub_for` initialised with placeholder — update with actual linked concept notes."
        )
    if kind_val == ZettelKind.HUB_SYNTHESIS.value and not frontmatter.get("synthesises"):
        frontmatter["synthesises"] = ["FIXME: list the zettel_ids this note synthesises"]
        warnings.append(
            "hub_synthesis `synthesises` initialised with placeholder — update with actual zettel IDs."
        )
    if kind_val == ZettelKind.DEFINITION.value and not frontmatter.get("defines"):
        term = note.path.stem
        frontmatter["defines"] = term
        warnings.append(f"definition zettel missing `defines`; inferred from filename: '{term}'.")

    # 8. Normalise tags
    frontmatter["tags"] = normalize_zettel_tags(
        frontmatter, kind=frontmatter["zettel_kind"], status=frontmatter["status"]
    )

    # 9. Ensure potential_links is deduplicated list of strings
    frontmatter["potential_links"] = dedupe_preserve(
        [str(item) for item in frontmatter.get("potential_links") or []]
    )

    # 10. Order frontmatter canonically
    normalized = order_frontmatter(frontmatter, original_key_order)

    # 11. Validate after normalisation
    ok_frontmatter, frontmatter_errors = validate_frontmatter(dict(normalized))
    if not ok_frontmatter:
        errors.extend(frontmatter_errors)

    # 12. Body link audit (warnings only — migrate.py owns frontmatter; body belongs to interweave-engine)
    body_links = classify_body_links(note.body)
    if not body_links["concept_links"]:
        warnings.append("No concept links in body; run obsidian-interweave-engine to enrich.")
    if not body_links["context_links"]:
        warnings.append("No context links in body; add a Periodic/ or 00 Inbox/ wikilink.")

    return {
        "frontmatter": dict(normalized),
        "body": note.body,
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize zettel notes to the canonical zettel schema."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to migrate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    default_globs = args.glob or ([] if args.path else [ZETTEL_FILE_GLOB])
    paths = expand_paths(root, args.path, default_globs)
    if not paths:
        print(json.dumps({"ok": False, "error": "no_paths"}, indent=2))
        return 1

    results: list[dict[str, Any]] = []
    overall_ok = True

    for path in paths:
        note = load_markdown_note(path)
        normalized = normalize_zettel(note, root)
        rendered = render_markdown(normalized["frontmatter"], normalized["body"])
        current = path.read_text(encoding="utf-8", errors="replace")
        changed = rendered != current
        result = {
            "path": str(path.relative_to(root)),
            "changed": changed,
            "warnings": normalized["warnings"],
            "errors": normalized["errors"],
        }
        has_ambiguity = any("Ambiguous" in w for w in normalized["warnings"])
        if normalized["errors"]:
            overall_ok = False
        if args.mode == "check" and changed:
            overall_ok = False
            result["errors"] = result["errors"] + ["Note does not match canonical zettel schema."]
        if args.mode == "fix" and not normalized["errors"] and not has_ambiguity and changed:
            path.write_text(rendered, encoding="utf-8")
        elif args.mode == "fix" and has_ambiguity:
            result["errors"] = result["errors"] + [
                "Skipped write due to ambiguous zettel_kind inference — confirm kind manually."
            ]
        results.append(result)

    print(json.dumps({"ok": overall_ok, "count": len(results), "results": results}, indent=2))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
