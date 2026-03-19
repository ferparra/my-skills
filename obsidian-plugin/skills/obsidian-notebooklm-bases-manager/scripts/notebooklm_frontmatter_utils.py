#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "notebooklm_frontmatter_schema.json"
)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text

    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text

    frontmatter_text, body = parts
    parsed = yaml.safe_load(frontmatter_text[4:]) or {}
    if not isinstance(parsed, dict):
        raise ValueError("Frontmatter must deserialize to a YAML mapping.")
    return {str(key): normalize_jsonable(value) for key, value in parsed.items()}, body


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def normalize_tags(frontmatter: dict[str, Any]) -> list[str]:
    raw = frontmatter.get("tags", [])
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def load_note(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    normalized_frontmatter = {
        str(key): normalize_jsonable(value) for key, value in frontmatter.items()
    }
    tags = normalize_tags(normalized_frontmatter)
    potential_links = normalized_frontmatter.get("potential_links", [])
    if not isinstance(potential_links, list):
        potential_links = []

    return {
        "path": str(path),
        "has_frontmatter": bool(frontmatter),
        "frontmatter": normalized_frontmatter,
        "body": body,
        "derived": {
            "tags": tags,
            "has_status_tag": any(tag.startswith("status/") for tag in tags),
            "potential_links_count": len(potential_links),
            "note_kind": normalized_frontmatter.get("notebooklm_note_kind"),
            "lane": normalized_frontmatter.get("notebooklm_lane"),
            "title": normalized_frontmatter.get("notebooklm_title"),
            "url": normalized_frontmatter.get("notebooklm_url"),
        },
    }


def load_schema(schema_path: str | None = None) -> dict[str, Any]:
    target = Path(schema_path) if schema_path else SCHEMA_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("NotebookLM schema must deserialize to a JSON object.")
    return {str(key): normalize_jsonable(value) for key, value in payload.items()}
