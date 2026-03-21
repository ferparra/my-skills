#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from people_models import (
    PEOPLE_FILE_GLOB,
    EnrichResult,
    dump_frontmatter,
    dump_json,
    extract_body_dated_headings,
    infer_interaction_frequency,
    load_markdown_note,
    normalize_jsonable,
    split_frontmatter,
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


def enrich_note(path: Path, root: Path) -> EnrichResult:
    note = load_markdown_note(path)
    rel = str(path.relative_to(root))
    warnings: list[str] = []
    changed = False

    fm = note.frontmatter
    dated_headings = extract_body_dated_headings(note.body)

    proposed_lid: str | None = None
    proposed_freq: str | None = None

    # Derive last_interaction_date from latest dated heading
    if dated_headings:
        proposed_lid = dated_headings[-1]

    # Derive interaction_frequency from heading gap distribution
    if len(dated_headings) >= 3:
        freq = infer_interaction_frequency(dated_headings)
        if freq:
            proposed_freq = freq.value

    # Only mark changed if the field is missing and we have a proposal
    existing_lid = fm.get("last_interaction_date")
    existing_freq = fm.get("interaction_frequency")

    if proposed_lid and not existing_lid:
        changed = True
    elif proposed_freq and not existing_freq:
        changed = True

    if not dated_headings:
        warnings.append("No dated headings (## YYYY-MM-DD) found in body; cannot derive last_interaction_date.")

    return EnrichResult(
        path=rel,
        proposed_last_interaction_date=proposed_lid,
        proposed_interaction_frequency=proposed_freq,
        changed=changed,
        warnings=warnings,
    )


def apply_enrich(path: Path, result: EnrichResult) -> None:
    """Write proposed enrichment fields only if missing in frontmatter."""
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)

    updated = False
    if result.proposed_last_interaction_date and not frontmatter.get("last_interaction_date"):
        frontmatter["last_interaction_date"] = result.proposed_last_interaction_date
        updated = True
    if result.proposed_interaction_frequency and not frontmatter.get("interaction_frequency"):
        frontmatter["interaction_frequency"] = result.proposed_interaction_frequency
        updated = True

    if updated:
        rendered = dump_frontmatter(normalize_jsonable(frontmatter)) + "\n" + body.lstrip("\n").rstrip() + "\n"
        path.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich person notes with last_interaction_date and interaction_frequency from body."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to enrich.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [PEOPLE_FILE_GLOB]))
    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results: list[EnrichResult] = []
    for path in paths:
        result = enrich_note(path, root)
        results.append(result)
        if args.mode == "fix" and result.changed:
            apply_enrich(path, result)

    changed_count = sum(1 for r in results if r.changed)
    print(dump_json({
        "ok": True,
        "count": len(results),
        "changed": changed_count,
        "results": [r.model_dump() for r in results],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
