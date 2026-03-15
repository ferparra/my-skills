#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from brokerage_models import dump_json, load_markdown_note, validate_frontmatter


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate brokerage activity ledger notes.")
    parser.add_argument(
        "--glob",
        default="20 Resources/Investments/Brokerage Activity/**/*.md",
        help="Glob of ledger notes to validate",
    )
    args = parser.parse_args()

    root = Path.cwd()
    invalid: list[dict[str, object]] = []
    signatures: dict[str, list[str]] = defaultdict(list)
    paths = sorted(root.glob(args.glob))

    for path in paths:
        note = load_markdown_note(path)
        ok, errors = validate_frontmatter(note.frontmatter)
        relative = str(path.relative_to(root))
        signature = str(note.frontmatter.get("source_signature") or "").strip()
        if signature:
            signatures[signature].append(relative)
        if not ok:
            invalid.append({"path": relative, "errors": errors})

    collisions = {
        signature: items
        for signature, items in signatures.items()
        if len(items) > 1
    }
    payload = {
        "ok": not invalid and not collisions,
        "checked": len(paths),
        "invalid": invalid,
        "duplicate_source_signatures": collisions,
    }
    print(dump_json(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
