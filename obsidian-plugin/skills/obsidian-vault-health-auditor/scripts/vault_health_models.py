#!/usr/bin/env python3
"""Pydantic models for vault health audit results."""
from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vault_health_config import (
    FRONTMATTER_DELIM,
    ISO_DATE_RE,
    KIND_DIRECTORY_MAP,
    KNOWN_KINDS,
    MIN_CONNECTION_STRENGTH,
    STALE_THRESHOLD_DAYS,
    WIKILINK_RE,
    ZETTEL_ID_RE,
    ZOMBIE_THRESHOLD_DAYS,
)


class NoteParts(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    frontmatter: dict[str, Any]
    body: str
    links: list[str] = Field(default_factory=list)


class BrokenLink(BaseModel):
    file: str
    link: str
    target: str
    issue: str = "target_not_found"


class OrphanedNote(BaseModel):
    path: str
    incoming: int = 0
    outgoing: int = 0


class LowConnectionStrength(BaseModel):
    path: str
    connection_strength: float


class SchemaDrift(BaseModel):
    path: str
    kind_field: str
    value: str
    allowed_values: list[str]
    suggestion: str | None = None


class MisplacedNote(BaseModel):
    path: str
    expected_dir: str
    actual_dir: str
    move_target: str | None = None


class DuplicateZettelId(BaseModel):
    zettel_id: str
    paths: list[str]
    primary_path: str | None = None


class StaleNote(BaseModel):
    path: str
    last_modified: str | None = None
    days_since_modified: int | None = None


class AuditSummary(BaseModel):
    total_notes: int = 0
    broken_links: int = 0
    orphaned_notes: int = 0
    low_connection_strength: int = 0
    schema_drift: int = 0
    misplaced_notes: int = 0
    duplicate_zettel_ids: int = 0
    stale_notes: int = 0

    @property
    def total_issues(self) -> int:
        return (
            self.broken_links
            + self.orphaned_notes
            + self.low_connection_strength
            + self.schema_drift
            + self.misplaced_notes
            + self.duplicate_zettel_ids
            + self.stale_notes
        )


class VaultHealthReport(BaseModel):
    ok: bool = True
    summary: AuditSummary = Field(default_factory=AuditSummary)
    broken_links: list[BrokenLink] = Field(default_factory=list)
    orphaned_notes: list[OrphanedNote] = Field(default_factory=list)
    low_connection_strength: list[LowConnectionStrength] = Field(default_factory=list)
    schema_drift: list[SchemaDrift] = Field(default_factory=list)
    misplaced_notes: list[MisplacedNote] = Field(default_factory=list)
    duplicate_zettel_ids: list[DuplicateZettelId] = Field(default_factory=list)
    stale_notes: list[StaleNote] = Field(default_factory=list)
    scanned_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    vault_root: str = ""

    @model_validator(mode="after")
    def compute_ok(self) -> "VaultHealthReport":
        self.ok = self.summary.total_issues == 0
        return self


class FixAction(BaseModel):
    """Single fix action result."""
    action: str  # "keep_primary", "regenerate_id", "move_note", etc.
    path: str
    zettel_id: str | None = None
    new_zettel_id: str | None = None
    backup: str | None = None
    target_path: str | None = None


class FixResult(BaseModel):
    ok: bool = True
    fixed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    changes: list[FixAction] = Field(default_factory=list)


# ── Parsing utilities ──────────────────────────────────────────────────────────

def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find(FRONTMATTER_DELIM, 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len(FRONTMATTER_DELIM):]
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        return {}, text
    return dict(payload), body


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(normalize_jsonable(payload), indent=2)


def load_markdown_note(path: Path) -> NoteParts:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    links = list(set(m.group(1).strip() for m in WIKILINK_RE.finditer(body)))
    return NoteParts(path=path, frontmatter=frontmatter, body=body, links=links)


def extract_zettel_id(frontmatter: dict[str, Any]) -> str | None:
    zettel_id = frontmatter.get("zettel_id") or frontmatter.get("id")
    if zettel_id and ZETTEL_ID_RE.match(str(zettel_id)):
        return str(zettel_id)
    return None


def get_note_age_days(path: Path) -> int | None:
    try:
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        return (datetime.now() - modified).days
    except OSError:
        return None


def infer_kind_field(frontmatter: dict[str, Any]) -> tuple[str | None, str | None]:
    """Detect which kind field is present and its value."""
    for field_name in KIND_DIRECTORY_MAP:
        if field_name in frontmatter:
            return field_name, str(frontmatter[field_name])
    return None, None


def get_expected_directory(kind_field: str, kind_value: str) -> str | None:
    base_dir = KIND_DIRECTORY_MAP.get(kind_field)
    if not base_dir:
        return None
    return base_dir


def check_schema_drift(frontmatter: dict[str, Any]) -> SchemaDrift | None:
    kind_field, kind_value = infer_kind_field(frontmatter)
    if not kind_field or not kind_value:
        return None

    allowed = KNOWN_KINDS.get(kind_field, set())
    if allowed and kind_value not in allowed:
        return SchemaDrift(
            path="",
            kind_field=kind_field,
            value=kind_value,
            allowed_values=sorted(allowed),
        )
    return None


# ── Report I/O ─────────────────────────────────────────────────────────────────

def load_report(path: Path) -> VaultHealthReport:
    data = json.loads(path.read_text(encoding="utf-8"))
    return VaultHealthReport.model_validate(data)


def save_report(report: VaultHealthReport, path: Path) -> None:
    path.write_text(dump_json(report), encoding="utf-8")
