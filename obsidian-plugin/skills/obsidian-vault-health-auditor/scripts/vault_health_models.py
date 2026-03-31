#!/usr/bin/env python3
"""Pydantic models for vault health audit results."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FRONTMATTER_DELIM = "\n---\n"
ZETTEL_ID_RE = re.compile(r"^(\d{14})$")

# Kind field to expected directory mapping
KIND_DIRECTORY_MAP: dict[str, str] = {
    "person_kind": "People/",
    "exercise_kind": "20 Resources/Exercises/",
    "brokerage_activity_kind": "20 Resources/Investments/Brokerage Activity/",
    "portfolio_holding_kind": "20 Resources/Investments/Portfolio Holdings/",
    "cv_entry_kind": "20 Resources/Career/",
    "zettel_kind": "30 Zettelkasten/",
    "key_date_kind": "20 Resources/Key Dates/",
    "planetary_task_kind": "20 Resources/Planetary Tasks/",
}

# Known kind taxonomies
KNOWN_KINDS: dict[str, set[str]] = {
    "person_kind": {
        "manager", "collaborator", "stakeholder", "customer_contact",
        "mentor", "author", "acquaintance",
    },
    "exercise_kind": {
        "hypertrophy", "strength", "mobility_drill", "warmup_flow", "exercise_brief",
    },
    "brokerage_activity_kind": {
        "trade_buy", "trade_sell", "distribution", "distribution_reinvestment",
        "cash_deposit", "cash_withdrawal", "fee", "tax", "fx", "adjustment", "cash_interest",
    },
    "cv_entry_kind": {
        "role", "education", "certification", "award", "community",
    },
    "zettel_kind": {
        "atomic", "literature", "project", "archive",
    },
    "key_date_kind": {
        "birthday", "anniversary", "deadline", "milestone", "holiday",
    },
    "planetary_task_kind": {
        "habit", "chore", "deep_work", "review", "meeting",
    },
    "portfolio_holding_kind": {
        "current_position", "closed_position", "watchlist",
    },
}

STALE_THRESHOLD_DAYS = 90
ZOMBIE_THRESHOLD_DAYS = 180
MIN_CONNECTION_STRENGTH = 2.0


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


class FixResult(BaseModel):
    ok: bool = True
    fixed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)


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
