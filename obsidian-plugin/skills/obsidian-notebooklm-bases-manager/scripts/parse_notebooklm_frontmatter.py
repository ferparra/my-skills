#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from notebooklm_frontmatter_utils import load_note


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse NotebookLM note frontmatter and emit a normalized JSON payload.",
    )
    parser.add_argument(
        "--path",
        action="append",
        required=True,
        help="NotebookLM note path. Repeat for multiple notes.",
    )
    args = parser.parse_args()

    results = []
    for path in args.path:
        note = load_note(path)
        results.append(
            {
                "path": note["path"],
                "has_frontmatter": note["has_frontmatter"],
                "frontmatter": note["frontmatter"],
                "derived": note["derived"],
            }
        )

    payload = {"ok": True, "count": len(results), "notes": results}
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
