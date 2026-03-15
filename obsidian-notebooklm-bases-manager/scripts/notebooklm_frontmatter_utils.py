#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "notebooklm_frontmatter_schema.json"
)


def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text

    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text

    frontmatter_text, body = parts
    parsed = yaml.safe_load(frontmatter_text[4:]) or {}
    if not isinstance(parsed, dict):
        raise ValueError("Frontmatter must deserialize to a YAML mapping.")
    return parsed, body


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def normalize_tags(frontmatter: Dict[str, Any]) -> List[str]:
    raw = frontmatter.get("tags", [])
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def load_note(path_str: str) -> Dict[str, Any]:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    normalized = normalize_jsonable(frontmatter)
    tags = normalize_tags(normalized)
    potential_links = normalized.get("potential_links", [])
    if not isinstance(potential_links, list):
        potential_links = []

    return {
        "path": str(path),
        "has_frontmatter": bool(frontmatter),
        "frontmatter": normalized,
        "body": body,
        "derived": {
            "tags": tags,
            "has_status_tag": any(tag.startswith("status/") for tag in tags),
            "potential_links_count": len(potential_links),
            "note_kind": normalized.get("notebooklm_note_kind"),
            "lane": normalized.get("notebooklm_lane"),
            "title": normalized.get("notebooklm_title"),
            "url": normalized.get("notebooklm_url"),
        },
    }


def load_schema(schema_path: str | None = None) -> Dict[str, Any]:
    target = Path(schema_path) if schema_path else SCHEMA_PATH
    return json.loads(target.read_text(encoding="utf-8"))
