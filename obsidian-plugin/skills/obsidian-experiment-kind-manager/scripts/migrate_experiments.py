#!/usr/bin/env python3
"""Migrate experiment notes to the canonical ExperimentFrontmatter schema.

Usage:
    # Dry-run (check mode — no writes):
    uvx --from python --with pydantic --with pyyaml python migrate_experiments.py \
        --glob "10 Notes/Productivity/Experiments/**/*.md" --mode check

    # Apply (fix mode — writes normalised frontmatter):
    uvx --from python --with pydantic --with pyyaml python migrate_experiments.py \
        --glob "10 Notes/Productivity/Experiments/**/*.md" --mode fix

    # Single note:
    uvx --from python --with pydantic --with pyyaml python migrate_experiments.py \
        --path "10 Notes/Productivity/Experiments/My Experiment.md" --mode fix

Exit code: 0 on success, 1 if any unrecoverable errors occur.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from experiment_models import (
    COUNCIL_DOMAIN_MAP,
    ExperimentKind,
    ExperimentOutcome,
    ExperimentStatus,
    MigrateResult,
    dump_json,
    ensure_string_list,
    infer_experiment_kind,
    load_markdown_note,
    next_experiment_id,
    normalize_experiment_tags,
    order_frontmatter,
    render_markdown,
    validate_frontmatter,
)


def resolve_notes(glob: str | None, path: str | None, vault_root: Path) -> list[Path]:
    if path:
        p = Path(path) if Path(path).is_absolute() else vault_root / path
        return [p] if p.exists() else []
    pattern = glob or "10 Notes/Productivity/Experiments/**/*.md"
    return [
        p for p in vault_root.rglob("*.md")
        if fnmatch.fnmatch(str(p.relative_to(vault_root)), pattern)
        and p.stem != "_hub"
    ]


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return date.today().isoformat()


def inject_missing(
    fm: dict[str, Any],
    key: str,
    value: Any,
    changed: list[str],
) -> None:
    """Set `key` to `value` only if it is absent or empty. Record the change."""
    existing = fm.get(key)
    if existing is None or existing == "" or existing == [] or existing == {}:
        fm[key] = value
        changed.append(key)


def migrate_note(
    path: Path,
    all_notes: list[Path],
    *,
    mode: str,
) -> MigrateResult:
    try:
        note = load_markdown_note(path)
    except Exception as exc:
        return MigrateResult(
            path=str(path),
            changed=False,
            errors=[f"Failed to read note: {exc}"],
        )

    fm = dict(note.frontmatter)
    body = note.body
    changed_fields: list[str] = []
    warnings: list[str] = []

    # ---- 1. Infer / confirm experiment_kind ----
    kind_value, is_ambiguous = infer_experiment_kind(fm, path)
    if not fm.get("experiment_kind"):
        if is_ambiguous or kind_value is None:
            warnings.append(
                "experiment_kind is ambiguous — skipping note. "
                f"Inferred candidates: {kind_value!r}. Manual confirmation required."
            )
            return MigrateResult(
                path=str(path), changed=False, warnings=warnings, skipped=True,
                skip_reason="ambiguous_kind",
            )
        inject_missing(fm, "experiment_kind", kind_value, changed_fields)
    else:
        kind_value = fm["experiment_kind"]

    try:
        kind_enum = ExperimentKind(kind_value)
    except ValueError:
        return MigrateResult(
            path=str(path), changed=False,
            errors=[f"Invalid experiment_kind: {kind_value!r}"],
        )

    # ---- 2. experiment_id — stable once set ----
    if not fm.get("experiment_id"):
        new_id = next_experiment_id(all_notes)
        inject_missing(fm, "experiment_id", new_id, changed_fields)

    # ---- 3. Timestamps ----
    inject_missing(fm, "created", today_iso(), changed_fields)
    fm["modified"] = now_iso()
    if "modified" not in changed_fields:
        changed_fields.append("modified")

    # ---- 4. Status ----
    if not fm.get("status"):
        inject_missing(fm, "status", ExperimentStatus.HYPOTHESIS.value, changed_fields)

    # ---- 5. Council owner + domain_tag ----
    council_owner, domain_tag = COUNCIL_DOMAIN_MAP[kind_enum.value]
    inject_missing(fm, "council_owner", council_owner, changed_fields)
    inject_missing(fm, "domain_tag", domain_tag, changed_fields)

    # ---- 6. Outcome default ----
    inject_missing(fm, "outcome", ExperimentOutcome.ONGOING.value, changed_fields)

    # ---- 7. Empty lists ----
    for list_field in ("metrics", "interventions", "controls", "confounders",
                       "next_experiments", "related", "potential_links", "aliases"):
        if fm.get(list_field) is None:
            inject_missing(fm, list_field, [], changed_fields)

    # ---- 8. connection_strength default ----
    inject_missing(fm, "connection_strength", 0.5, changed_fields)

    # ---- 9. Tags ----
    current_status = str(fm.get("status", ExperimentStatus.HYPOTHESIS.value))
    normalised_tags = normalize_experiment_tags(fm, kind=kind_enum.value, status=current_status)
    if set(normalised_tags) != set(ensure_string_list(fm.get("tags"))):
        fm["tags"] = normalised_tags
        changed_fields.append("tags")

    # ---- 10. Placeholder fields (require user input) ----
    for required_text_field in ("question", "hypothesis", "method"):
        if not fm.get(required_text_field):
            fm[required_text_field] = f"<!-- TODO: fill in {required_text_field} -->"
            changed_fields.append(required_text_field)
            warnings.append(f"`{required_text_field}` is missing — placeholder inserted.")

    # ---- 11. Order and validate ----
    ordered = dict(order_frontmatter(fm))
    validation = validate_frontmatter(ordered)

    errors: list[str] = []
    if not validation.ok:
        # Only report errors that prevent schema conformance; still write if
        # only warnings-level issues remain (e.g. empty potential_links).
        non_blocking = {"potential_links", "findings"}
        blocking_errors = [
            e for e in validation.errors
            if not any(nb in e for nb in non_blocking)
        ]
        if blocking_errors:
            errors = blocking_errors

    changed = bool(changed_fields)

    if mode == "fix" and changed and not errors:
        markdown = render_markdown(ordered, body)
        try:
            path.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            return MigrateResult(
                path=str(path), changed=False,
                errors=[f"Failed to write note: {exc}"],
            )

    return MigrateResult(
        path=str(path),
        changed=changed,
        changed_fields=changed_fields,
        warnings=warnings,
        errors=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate experiment notes to canonical schema.")
    parser.add_argument("--glob", help="Glob pattern relative to vault root.")
    parser.add_argument("--path", help="Single note path.")
    parser.add_argument("--mode", default="check", choices=["check", "fix"])
    parser.add_argument("--vault", default=str(Path.home() / "my-vault"), help="Vault root path.")
    args = parser.parse_args()

    vault_root = Path(args.vault)
    notes = resolve_notes(args.glob, args.path, vault_root)

    if not notes:
        print(dump_json({"ok": True, "message": "No experiment notes found.", "results": []}))
        return 0

    results = [migrate_note(p, notes, mode=args.mode) for p in notes]
    all_ok = all(not r.errors for r in results)

    summary = {
        "ok": all_ok,
        "mode": args.mode,
        "total": len(results),
        "changed": sum(1 for r in results if r.changed),
        "skipped": sum(1 for r in results if r.skipped),
        "errors": sum(1 for r in results if r.errors),
        "results": [r.model_dump() for r in results],
    }

    print(dump_json(summary))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
