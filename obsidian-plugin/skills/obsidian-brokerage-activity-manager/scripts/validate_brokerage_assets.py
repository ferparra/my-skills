#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from brokerage_models import dump_json, load_markdown_note, validate_asset_frontmatter


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate brokerage asset notes.")
    parser.add_argument(
        "--glob",
        default="20 Resources/Investments/Brokerage Assets/*.md",
        help="Glob of brokerage asset notes to validate",
    )
    args = parser.parse_args()

    root = Path.cwd()
    invalid: list[dict[str, object]] = []
    symbols: dict[str, list[str]] = defaultdict(list)
    paths = sorted(root.glob(args.glob))

    for path in paths:
        note = load_markdown_note(path)
        ok, errors = validate_asset_frontmatter(note.frontmatter)
        relative = str(path.relative_to(root))
        symbol = str(note.frontmatter.get("instrument_symbol") or "").strip().upper()
        if symbol:
            symbols[symbol].append(relative)
        if not ok:
            invalid.append({"path": relative, "errors": errors})

    collisions = {
        symbol: items
        for symbol, items in symbols.items()
        if len(items) > 1
    }
    payload = {
        "ok": not invalid and not collisions,
        "checked": len(paths),
        "invalid": invalid,
        "duplicate_symbols": collisions,
    }
    print(dump_json(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
