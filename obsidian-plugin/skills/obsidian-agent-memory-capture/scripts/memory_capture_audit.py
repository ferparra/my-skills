#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import TypeAlias

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
STATUS_RE = re.compile(r"#status/[a-z0-9-]+")
H1_RE = re.compile(r"(?m)^# ")

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
            "Verify tools: obsidian --help && qmd status && uvx --version",
            "Re-run memory audit before promoting note status.",
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


def classify_links(text: str) -> tuple[int, int, int]:
    links = [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]
    concept = sum(1 for l in links if l.startswith(CONCEPT_PREFIXES))
    context = sum(1 for l in links if l.startswith(CONTEXT_PREFIXES))
    return len(links), concept, context


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit zettel memory compliance for knowledge notes.")
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

    is_knowledge_note = any(seg in str(path) for seg in ["00 Inbox/", "10 Notes/", "20 Resources/"])

    issues = []
    recommendations = []

    if is_knowledge_note:
        if "potential_links" not in frontmatter:
            issues.append("missing_potential_links")
            recommendations.append("Add potential_links YAML list with candidate [[wikilinks]].")
        if "connection_strength" not in frontmatter:
            issues.append("missing_connection_strength")
            recommendations.append("Add connection_strength (0.0-1.0) for materially edited knowledge notes.")

    if "connection_strength" in frontmatter:
        try:
            value = float(str(frontmatter["connection_strength"]).strip())
            if value < 0.0 or value > 1.0:
                issues.append("invalid_connection_strength_range")
                recommendations.append("Keep connection_strength between 0.0 and 1.0.")
        except ValueError:
            issues.append("invalid_connection_strength_type")
            recommendations.append("Set connection_strength to a numeric value.")

    status_tags = sorted(set(STATUS_RE.findall(text)))
    if not status_tags:
        issues.append("missing_status_tag")
        recommendations.append("Add lifecycle tag like #status/processing or #status/processed.")

    total_links, concept_count, context_count = classify_links(body)
    if concept_count < 1:
        issues.append("missing_concept_link")
        recommendations.append("Add at least one concept link (usually 10 Notes/*).")
    if context_count < 1:
        issues.append("missing_context_link")
        recommendations.append("Add at least one context link (Periodic/Projects/00 Inbox/10 Projects).")
    if total_links < 2:
        issues.append("insufficient_total_links")
        recommendations.append("Maintain at least two meaningful links in body text.")

    if len(H1_RE.findall(text)) > 1:
        issues.append("multiple_h1_headers")
        recommendations.append("Keep one core idea per note; avoid multiple H1 sections.")

    payload = {
        "ok": len(issues) == 0,
        "path": str(path),
        "is_knowledge_note": is_knowledge_note,
        "status_tags": status_tags,
        "link_counts": {
            "total_body_wikilinks": total_links,
            "concept_links": concept_count,
            "context_links": context_count,
        },
        "issues": issues,
        "recommendations": recommendations,
    }

    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
