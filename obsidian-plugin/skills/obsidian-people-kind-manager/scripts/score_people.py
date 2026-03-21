#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from people_models import (
    PEOPLE_FILE_GLOB,
    ScoreResult,
    dump_frontmatter,
    dump_json,
    load_markdown_note,
    normalize_jsonable,
    score_connection_strength,
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


def query_backlink_count(path: Path, root: Path) -> tuple[int, str | None]:
    """Return (count, warning_or_none). Falls back to 0 if obsidian CLI unavailable."""
    rel = str(path.relative_to(root))
    try:
        result = subprocess.run(
            ["obsidian", "backlinks", f"path={rel}", "counts", "total"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for token in result.stdout.strip().split():
                try:
                    return int(token), None
                except ValueError:
                    continue
            return 0, f"Could not parse backlink count from obsidian output: {result.stdout.strip()!r}"
    except FileNotFoundError:
        return 0, "obsidian CLI not found; backlink count defaulted to 0."
    except subprocess.TimeoutExpired:
        return 0, f"obsidian CLI timed out for {rel}; backlink count defaulted to 0."
    except Exception as exc:
        return 0, f"obsidian CLI error for {rel}: {exc}; backlink count defaulted to 0."
    return 0, None


def score_note(path: Path, root: Path) -> ScoreResult:
    note = load_markdown_note(path)
    backlinks, backlink_warning = query_backlink_count(path, root)
    new_score = score_connection_strength(path, note.body, note.frontmatter, backlink_count=backlinks)
    try:
        old_score = float(note.frontmatter.get("connection_strength") or 0.0)
    except (TypeError, ValueError):
        old_score = 0.0
    return ScoreResult(
        path=str(path.relative_to(root)),
        old_score=old_score,
        new_score=new_score,
        changed=abs(old_score - new_score) > 0.01,
        backlinks=backlinks,
        warning=backlink_warning,
    )


def apply_score(path: Path, new_score: float) -> None:
    """Write updated connection_strength into frontmatter without disturbing other fields."""
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    frontmatter["connection_strength"] = new_score
    rendered = dump_frontmatter(normalize_jsonable(frontmatter)) + "\n" + body.lstrip("\n").rstrip() + "\n"
    path.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score connection_strength for person notes from link graph and backlinks."
    )
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to score.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    parser.add_argument(
        "--force-rescore",
        action="store_true",
        help="Rewrite all scores even if unchanged.",
    )
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    paths = expand_paths(root, args.path, args.glob or ([] if args.path else [PEOPLE_FILE_GLOB]))
    if not paths:
        print(dump_json({"ok": False, "error": "no_paths"}))
        return 1

    results: list[ScoreResult] = []
    for path in paths:
        result = score_note(path, root)
        results.append(result)
        if args.mode == "fix" and (result.changed or args.force_rescore):
            apply_score(path, result.new_score)

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
