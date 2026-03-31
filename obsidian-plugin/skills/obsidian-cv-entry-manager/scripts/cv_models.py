#!/usr/bin/env python3
"""Pydantic v2 models and utilities for the CV entry manager skill.

This module is the source of truth for the ``cv_entry_kind`` schema.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# ── Constants ────────────────────────────────────────────────────────────────

FRONTMATTER_DELIM = "\n---\n"
CV_ENTRY_ID_RE = re.compile(r"^ce-[a-f0-9]{12}$")
YEAR_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

CV_NOTES_DIR = Path("20 Resources/Career")
CV_ROLES_DIR = CV_NOTES_DIR / "Roles"
CV_EDUCATION_DIR = CV_NOTES_DIR / "Education"
CV_CREDENTIALS_DIR = CV_NOTES_DIR / "Credentials"
CV_COMMUNITY_DIR = CV_NOTES_DIR / "Community"
CV_NOTE_GLOB = "20 Resources/Career/**/*.md"
CV_BASE_PATH = CV_NOTES_DIR / "CV Entries.base"

CV_FRONTMATTER_ORDER = [
    "cv_entry_id",
    "cv_entry_kind",
    "status",
    "company",
    "company_name",
    "role_title",
    "start_date",
    "end_date",
    "location",
    "reporting_to",
    "industry",
    "pillars",
    "recency_weight",
    "bullets",
    "institution",
    "qualification",
    "start_year",
    "end_year",
    "certification_name",
    "issuing_body",
    "year_obtained",
    "award_name",
    "event",
    "year",
    "activity_name",
    "duration",
    "description",
    "connection_strength",
    "potential_links",
    "tags",
]


# ── Enums ────────────────────────────────────────────────────────────────────


class CvEntryKind(StrEnum):
    ROLE = "role"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    AWARD = "award"
    COMMUNITY = "community"


class CvPillar(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class CvEntryStatus(StrEnum):
    FLEETING = "fleeting"
    PROCESSING = "processing"
    PROCESSED = "processed"


class RecencyWeight(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Nested Models ────────────────────────────────────────────────────────────


class CvBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    pillars: list[CvPillar] = Field(default_factory=list)
    quantified: bool = False

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Bullet text must not be empty.")
        return stripped

    @field_validator("pillars", mode="before")
    @classmethod
    def coerce_pillars(cls, value: Any) -> list[CvPillar]:
        if value is None:
            return []
        if isinstance(value, str):
            return [CvPillar(value)]
        return [CvPillar(str(item)) for item in value]


# ── Main Frontmatter Model ──────────────────────────────────────────────────


class CvEntryFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Common fields
    cv_entry_id: str
    cv_entry_kind: CvEntryKind
    status: CvEntryStatus = CvEntryStatus.PROCESSING
    pillars: list[CvPillar] = Field(default_factory=list)
    recency_weight: RecencyWeight = RecencyWeight.LOW
    connection_strength: float = Field(ge=0.0, le=1.0, default=0.0)
    potential_links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Role-specific
    company: str | None = None
    company_name: str | None = None
    role_title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    reporting_to: str | None = None
    industry: str | None = None
    bullets: list[CvBullet] | None = None

    # Education-specific
    institution: str | None = None
    qualification: str | None = None
    start_year: int | None = None
    end_year: int | None = None

    # Certification-specific
    certification_name: str | None = None
    issuing_body: str | None = None
    year_obtained: int | None = None

    # Award-specific
    award_name: str | None = None
    event: str | None = None
    year: int | None = None

    # Community-specific
    activity_name: str | None = None
    duration: str | None = None
    description: str | None = None

    # ── Field validators ─────────────────────────────────────────────────

    @field_validator("cv_entry_id")
    @classmethod
    def validate_entry_id(cls, value: str) -> str:
        text = str(value).strip()
        if not CV_ENTRY_ID_RE.match(text):
            raise ValueError(
                "cv_entry_id must match 'ce-<12 lowercase hex chars>'"
            )
        return text

    @field_validator("connection_strength", mode="before")
    @classmethod
    def coerce_connection_strength(cls, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"connection_strength must be numeric, got: {value!r}")

    @field_validator("pillars", mode="before")
    @classmethod
    def coerce_pillars_list(cls, value: Any) -> list[CvPillar]:
        if value is None:
            return []
        if isinstance(value, str):
            return [CvPillar(value)]
        return [CvPillar(str(item)) for item in value]

    @field_validator("potential_links", "tags", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_year_month(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not YEAR_MONTH_RE.match(text):
            raise ValueError(f"Date must be YYYY-MM format, got: {text!r}")
        return text

    @field_validator("start_year", "end_year", "year_obtained", "year", mode="before")
    @classmethod
    def coerce_optional_int(cls, value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    @field_validator("bullets", mode="before")
    @classmethod
    def coerce_bullets(cls, value: Any) -> list[CvBullet] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("bullets must be a list")
        result: list[CvBullet] = []
        for item in value:
            if isinstance(item, CvBullet):
                result.append(item)
            elif isinstance(item, dict):
                result.append(CvBullet.model_validate(item))
            else:
                raise ValueError(f"Invalid bullet entry: {item!r}")
        return result

    # ── Model validators ─────────────────────────────────────────────────

    @model_validator(mode="after")
    def validate_kind_specific_fields(self) -> "CvEntryFrontmatter":
        kind = self.cv_entry_kind
        if kind == CvEntryKind.ROLE:
            missing: list[str] = []
            if not self.company_name:
                missing.append("company_name")
            if not self.role_title:
                missing.append("role_title")
            if not self.start_date:
                missing.append("start_date")
            if missing:
                raise ValueError(
                    f"Role entries require: {', '.join(missing)}"
                )
        elif kind == CvEntryKind.EDUCATION:
            if not self.institution:
                raise ValueError("Education entries require: institution")
            if not self.qualification:
                raise ValueError("Education entries require: qualification")
        elif kind == CvEntryKind.CERTIFICATION:
            if not self.certification_name:
                raise ValueError("Certification entries require: certification_name")
        elif kind == CvEntryKind.AWARD:
            if not self.award_name:
                raise ValueError("Award entries require: award_name")
        elif kind == CvEntryKind.COMMUNITY:
            if not self.activity_name:
                raise ValueError("Community entries require: activity_name")
        return self

    @model_validator(mode="after")
    def validate_required_tags(self) -> "CvEntryFrontmatter":
        required = required_tags_for(self.cv_entry_kind, self.status)
        missing = set(required) - set(self.tags)
        if missing:
            raise ValueError(f"tags must include {sorted(missing)}")
        return self

    @model_validator(mode="after")
    def validate_date_ordering(self) -> "CvEntryFrontmatter":
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError(
                    f"start_date {self.start_date} must be <= end_date {self.end_date}"
                )
        return self


# ── Result Models ────────────────────────────────────────────────────────────


class NoteParts(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    frontmatter: dict[str, Any]
    body: str


class ValidationResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)


class AuditResult(BaseModel):
    path: str
    ok: bool
    cv_entry_kind: str | None = None
    status: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    frontmatter_keys: list[str] = Field(default_factory=list)


class MigrateResult(BaseModel):
    path: str
    changed: bool
    changed_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


# ── Utility Functions ────────────────────────────────────────────────────────


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return normalize_jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): normalize_jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(normalize_jsonable(payload), indent=2)


def stable_hash(payload: Any, *, prefix: str | None = None, length: int = 12) -> str:
    raw = json.dumps(
        normalize_jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}" if prefix else digest


def make_cv_entry_id(kind: str, key: str) -> str:
    return stable_hash({"cv_entry_kind": kind, "key": key}, prefix="ce", length=12)


def dedupe_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def ensure_string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def required_tags_for(kind: CvEntryKind | str, status: CvEntryStatus | str) -> list[str]:
    kind_value = CvEntryKind(str(kind)).value
    status_value = CvEntryStatus(str(status)).value
    return [
        "type/cv-entry",
        f"cv-entry-kind/{kind_value}",
        f"status/{status_value}",
    ]


def normalize_cv_tags(
    frontmatter: dict[str, Any],
    *,
    kind: str,
    status: str,
) -> list[str]:
    raw = ensure_string_list(frontmatter.get("tags"))
    managed_prefixes = ("type/cv-entry", "cv-entry-kind/", "status/")
    user_tags = [
        t for t in raw
        if not any(t == p or t.startswith(p) for p in managed_prefixes)
    ]
    managed = required_tags_for(kind, status)
    return dedupe_preserve(managed + user_tags)


# ── Frontmatter I/O ─────────────────────────────────────────────────────────


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find(FRONTMATTER_DELIM, 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len(FRONTMATTER_DELIM) :]
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise ValueError("Frontmatter must deserialize to a mapping.")
    return normalize_jsonable(dict(payload)), body


def load_markdown_note(path: Path) -> NoteParts:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    return NoteParts(path=path, frontmatter=frontmatter, body=body)


def order_frontmatter(
    frontmatter: dict[str, Any],
    original_key_order: list[str] | None = None,
) -> OrderedDict[str, Any]:
    ordered: OrderedDict[str, Any] = OrderedDict()
    original_key_order = original_key_order or list(frontmatter.keys())
    for key in CV_FRONTMATTER_ORDER:
        if key in frontmatter and frontmatter[key] not in (None, [], {}):
            ordered[key] = frontmatter[key]
    for key in original_key_order:
        if key in frontmatter and key not in ordered and frontmatter[key] not in (None, [], {}):
            ordered[key] = frontmatter[key]
    for key, value in frontmatter.items():
        if key not in ordered and value not in (None, [], {}):
            ordered[key] = value
    return ordered


def dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    class _NoAliasSafeDumper(yaml.SafeDumper):
        def ignore_aliases(self, data: Any) -> bool:
            return True

    payload = yaml.dump(
        normalize_jsonable(frontmatter),
        Dumper=_NoAliasSafeDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    ).strip()
    return f"---\n{payload}\n---\n"


def render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    normalized_body = body.lstrip("\n").rstrip() + "\n"
    return dump_frontmatter(frontmatter) + "\n" + normalized_body


def validate_frontmatter(frontmatter: dict[str, Any]) -> ValidationResult:
    try:
        CvEntryFrontmatter.model_validate(frontmatter)
    except ValidationError as exc:
        return ValidationResult(ok=False, errors=[error["msg"] for error in exc.errors()])
    except Exception as exc:
        return ValidationResult(ok=False, errors=[str(exc)])
    return ValidationResult(ok=True)


# ── Path helpers ─────────────────────────────────────────────────────────────


def safe_note_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._\- ]+", "", value).strip()
    return re.sub(r"\s+", " ", cleaned) or "unknown"


def role_relative_path(frontmatter: dict[str, Any]) -> Path:
    start = str(frontmatter.get("start_date", "0000-00"))
    company = safe_note_component(str(frontmatter.get("company_name", "Unknown")))
    title = safe_note_component(str(frontmatter.get("role_title", "Unknown")))
    return CV_ROLES_DIR / f"{start} {company} {title}.md"


def education_relative_path(frontmatter: dict[str, Any]) -> Path:
    institution = safe_note_component(str(frontmatter.get("institution", "Unknown")))
    qualification = safe_note_component(str(frontmatter.get("qualification", "Unknown")))
    return CV_EDUCATION_DIR / f"{institution} {qualification}.md"


def credential_relative_path(frontmatter: dict[str, Any]) -> Path:
    kind = frontmatter.get("cv_entry_kind", "")
    if kind == CvEntryKind.CERTIFICATION.value:
        name = safe_note_component(str(frontmatter.get("certification_name", "Unknown")))
    elif kind == CvEntryKind.AWARD.value:
        name = safe_note_component(str(frontmatter.get("award_name", "Unknown")))
    else:
        name = "Unknown"
    return CV_CREDENTIALS_DIR / f"{name}.md"


def community_relative_path(frontmatter: dict[str, Any]) -> Path:
    name = safe_note_component(str(frontmatter.get("activity_name", "Unknown")))
    return CV_COMMUNITY_DIR / f"{name}.md"


def note_relative_path(frontmatter: dict[str, Any]) -> Path:
    kind = frontmatter.get("cv_entry_kind", "")
    if kind == CvEntryKind.ROLE.value:
        return role_relative_path(frontmatter)
    if kind == CvEntryKind.EDUCATION.value:
        return education_relative_path(frontmatter)
    if kind in (CvEntryKind.CERTIFICATION.value, CvEntryKind.AWARD.value):
        return credential_relative_path(frontmatter)
    if kind == CvEntryKind.COMMUNITY.value:
        return community_relative_path(frontmatter)
    return CV_NOTES_DIR / "Unknown.md"


def kind_dir(kind: CvEntryKind | str) -> Path:
    kind_value = CvEntryKind(str(kind))
    mapping: dict[CvEntryKind, Path] = {
        CvEntryKind.ROLE: CV_ROLES_DIR,
        CvEntryKind.EDUCATION: CV_EDUCATION_DIR,
        CvEntryKind.CERTIFICATION: CV_CREDENTIALS_DIR,
        CvEntryKind.AWARD: CV_CREDENTIALS_DIR,
        CvEntryKind.COMMUNITY: CV_COMMUNITY_DIR,
    }
    return mapping.get(kind_value, CV_NOTES_DIR)
