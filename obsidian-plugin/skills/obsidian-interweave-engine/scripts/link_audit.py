#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TypeAlias

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
STATUS_RE = re.compile(r"#status/[a-z0-9-]+")


CONCEPT_PREFIXES = ("10 Notes/",)
CONTEXT_PREFIXES = ("00 Inbox/", "Projects/", "10 Projects/", "Periodic/")
FrontmatterValue: TypeAlias = str | list[str]


def dependency_error(missing: list[str]) -> int:
    payload = {
        "ok": False,
        "error": "missing_dependencies",
        "missing": missing,
        "fallback_checklist": [
            "Install/repair Obsidian CLI and qmd, and ensure uvx is available.",
            "Verify tools: obsidian help && qmd status && uvx --version",
            "Run audit again before editing links.",
        ],
    }
    print(json.dumps(payload, indent=2))
    return 2


def split_frontmatter(text: str) -> tuple[dict[str, FrontmatterValue], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text

    fm_text, body = parts
    fm_lines = fm_text.splitlines()[1:]
    frontmatter: dict[str, FrontmatterValue] = {}
    current_key: str | None = None

    for line in fm_lines:
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                frontmatter[key] = value.strip('"')
                current_key = None
            else:
                frontmatter[key] = []
                current_key = key
        elif current_key and line.strip().startswith("- "):
            current_value = frontmatter.get(current_key)
            if isinstance(current_value, list):
                current_value.append(line.strip()[2:].strip().strip('"'))
        elif current_key and line.startswith("  - "):
            current_value = frontmatter.get(current_key)
            if isinstance(current_value, list):
                current_value.append(line.strip()[2:].strip().strip('"'))

    return frontmatter, body


def classify_links(text: str) -> tuple[list[str], list[str], list[str]]:
    links = [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]
    concept = [l for l in links if l.startswith(CONCEPT_PREFIXES)]
    context = [l for l in links if l.startswith(CONTEXT_PREFIXES)]
    other = [l for l in links if l not in concept and l not in context]
    return concept, context, other


def unresolved_via_obsidian(path: Path) -> list[str]:
    try:
        cmd = ["obsidian", "links", f'path={str(path)}']
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        unresolved = []
        for line in result.stdout.splitlines():
            if "(unresolved)" in line:
                unresolved.append(line.strip())
        return unresolved
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit concept/context weaving, frontmatter fields, and unresolved link risk.")
    parser.add_argument("--path", required=True, help="Path to markdown note")
    args = parser.parse_args()

    missing = [cmd for cmd in ["obsidian", "qmd", "uvx"] if shutil.which(cmd) is None]
    if missing:
        return dependency_error(missing)

    path = Path(args.path)
    if not path.exists():
        payload = {"ok": False, "error": "missing_file", "path": str(path)}
        print(json.dumps(payload, indent=2))
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    concept_links, context_links, other_links = classify_links(text)

    missing_fields: list[str] = []
    for required in ["connection_strength", "potential_links"]:
        if required not in frontmatter:
            missing_fields.append(required)

    status_tags = sorted(set(STATUS_RE.findall(text)))
    if not status_tags:
        missing_fields.append("status_tag")

    unresolved = unresolved_via_obsidian(path)
    pattern_unresolved = [l for l in other_links if l.lower() == "unknown"]

    payload = {
        "ok": len(missing_fields) == 0 and len(concept_links) >= 1 and len(context_links) >= 1 and len(unresolved) == 0,
        "path": str(path),
        "concept_links": concept_links,
        "context_links": context_links,
        "other_links": other_links,
        "counts": {
            "concept_links": len(concept_links),
            "context_links": len(context_links),
            "other_links": len(other_links),
        },
        "missing_fields": missing_fields,
        "status_tags": status_tags,
        "unresolved_links": unresolved,
        "pattern_unresolved_candidates": pattern_unresolved,
    }

    if len(concept_links) < 1:
        missing_fields.append("concept_link_in_body")
    if len(context_links) < 1:
        missing_fields.append("context_link_in_body")

    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
