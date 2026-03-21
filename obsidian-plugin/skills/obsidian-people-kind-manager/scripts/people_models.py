#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATED_HEADING_RE = re.compile(r"^#{1,3}\s+(\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
FRONTMATTER_DELIM = "\n---\n"

PEOPLE_FILE_GLOB = "People/**/*.md"

PERSON_FRONTMATTER_ORDER = [
    "person_kind",
    "aliases",
    "created",
    "modified",
    "relationship_to_fernando",
    "status",
    "primary_context",
    "relationship_conditions",
    "organizations",
    "connection_strength",
    "potential_links",
    "last_interaction_date",
    "interaction_frequency",
    "management_cadence",
    "influence_domain",
    "account_context",
    "domain_of_mentorship",
    "primary_works",
    "personal_context",
    "unique_attributes",
    "tags",
]


class PersonKind(StrEnum):
    MANAGER = "manager"
    COLLABORATOR = "collaborator"
    STAKEHOLDER = "stakeholder"
    CUSTOMER_CONTACT = "customer_contact"
    MENTOR = "mentor"
    AUTHOR = "author"
    ACQUAINTANCE = "acquaintance"


class PersonStatus(StrEnum):
    FLEETING = "fleeting"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DORMANT = "dormant"


class InteractionFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    RARELY = "rarely"
    NEVER = "never"


class PersonFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Required for all kinds
    person_kind: PersonKind
    created: str
    modified: str
    relationship_to_fernando: str
    status: PersonStatus
    primary_context: str
    connection_strength: float = Field(ge=0.0, le=1.0)
    potential_links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Optional for all kinds
    aliases: list[str] = Field(default_factory=list)
    relationship_conditions: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    last_interaction_date: str | None = None
    interaction_frequency: InteractionFrequency | None = None
    unique_attributes: list[dict[str, Any]] | None = None

    # Kind-specific optional fields
    management_cadence: str | None = None       # manager
    influence_domain: str | None = None         # stakeholder
    account_context: str | None = None          # customer_contact
    domain_of_mentorship: str | None = None     # mentor
    primary_works: list[str] | None = None      # author (hard error if absent)
    personal_context: str | None = None         # acquaintance

    @field_validator("connection_strength", mode="before")
    @classmethod
    def coerce_connection_strength(cls, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"connection_strength must be numeric, got: {value!r}")

    @field_validator("potential_links", "organizations", "aliases",
                     "relationship_conditions", "tags")
    @classmethod
    def validate_string_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Expected a YAML list.")
        return [str(item) for item in value]

    @field_validator("organizations")
    @classmethod
    def validate_organization_links(cls, value: list[str]) -> list[str]:
        for item in value:
            if not is_wikilink(item):
                raise ValueError(
                    f"`organizations` entries should be wikilinks, got: {item!r}"
                )
        return value

    @field_validator("last_interaction_date")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ISO_DATE_RE.match(str(value)):
            raise ValueError(
                f"`last_interaction_date` must be YYYY-MM-DD, got: {value!r}"
            )
        return value

    @model_validator(mode="after")
    def validate_kind_specific_fields(self) -> "PersonFrontmatter":
        if self.person_kind == PersonKind.AUTHOR and not self.primary_works:
            raise ValueError("`author` persons require a non-empty `primary_works` list.")
        return self

    @model_validator(mode="after")
    def validate_tag_requirements(self) -> "PersonFrontmatter":
        required = {
            "type/person",
            f"person-kind/{self.person_kind.value}",
            f"status/{self.status.value}",
        }
        missing = required - set(self.tags)
        if missing:
            raise ValueError(
                f"`tags` must include: {sorted(missing)}. Got: {self.tags}"
            )
        return self

    @model_validator(mode="after")
    def validate_potential_links_non_empty(self) -> "PersonFrontmatter":
        if not self.potential_links:
            raise ValueError("`potential_links` must be a non-empty list.")
        return self


class NoteParts(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    frontmatter: dict[str, Any]
    body: str


class InferenceResult(BaseModel):
    kind: PersonKind
    is_ambiguous: bool


class ValidationResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)


class AuditResult(BaseModel):
    path: str
    ok: bool
    person_kind: str | None = None
    inferred_person_kind: str | None = None
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


class ScoreResult(BaseModel):
    path: str
    old_score: float
    new_score: float
    changed: bool
    backlinks: int
    warning: str | None = None


class EnrichResult(BaseModel):
    path: str
    proposed_last_interaction_date: str | None = None
    proposed_interaction_frequency: str | None = None
    changed: bool = False
    warnings: list[str] = Field(default_factory=list)


def is_wikilink(value: str) -> bool:
    return bool(WIKILINK_RE.fullmatch(str(value).strip()))


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(normalize_jsonable(payload), indent=2)


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
        raise ValueError("Frontmatter must deserialize to a mapping.")
    return normalize_jsonable(dict(payload)), body


def load_markdown_note(path: Path) -> NoteParts:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    return NoteParts(path=path, frontmatter=frontmatter, body=body)


def dedupe_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def ensure_string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def order_frontmatter(
    frontmatter: dict[str, Any],
    original_key_order: list[str] | None = None,
) -> OrderedDict[str, Any]:
    ordered: OrderedDict[str, Any] = OrderedDict()
    original_key_order = original_key_order or list(frontmatter.keys())
    for key in PERSON_FRONTMATTER_ORDER:
        if key in frontmatter:
            ordered[key] = frontmatter[key]
    for key in original_key_order:
        if key in frontmatter and key not in ordered:
            ordered[key] = frontmatter[key]
    for key, value in frontmatter.items():
        if key not in ordered:
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
        PersonFrontmatter.model_validate(frontmatter)
    except ValidationError as exc:
        return ValidationResult(ok=False, errors=[error["msg"] for error in exc.errors()])
    except Exception as exc:
        return ValidationResult(ok=False, errors=[str(exc)])
    return ValidationResult(ok=True)


def normalize_person_tags(
    frontmatter: dict[str, Any],
    *,
    kind: str,
    status: str,
) -> list[str]:
    raw = ensure_string_list(frontmatter.get("tags"))
    managed_prefixes = ("type/person", "person-kind/", "status/")
    user_tags = [t for t in raw if not any(t == p or t.startswith(p) for p in managed_prefixes)]
    managed = [
        "type/person",
        f"person-kind/{kind}",
        f"status/{status}",
    ]
    return dedupe_preserve(managed + user_tags)


def infer_status_from_tags(frontmatter: dict[str, Any]) -> PersonStatus:
    tags = [str(t) for t in ensure_string_list(frontmatter.get("tags"))]
    if "status/processed" in tags:
        return PersonStatus.PROCESSED
    if "status/processing" in tags:
        return PersonStatus.PROCESSING
    if "status/dormant" in tags:
        return PersonStatus.DORMANT
    return PersonStatus.FLEETING


def infer_person_kind(frontmatter: dict[str, Any]) -> InferenceResult:
    """Infer kind from existing signals. Never overwrites an explicit kind."""
    raw_kind = str(frontmatter.get("person_kind") or "").strip()
    if raw_kind:
        try:
            return InferenceResult(kind=PersonKind(raw_kind), is_ambiguous=False)
        except ValueError:
            pass  # fall through to heuristic inference

    conditions = " ".join(ensure_string_list(frontmatter.get("relationship_conditions"))).lower()
    tags = set(ensure_string_list(frontmatter.get("tags")))
    rel_to = str(frontmatter.get("relationship_to_fernando") or "").lower()
    context = str(frontmatter.get("primary_context") or "").lower()

    signals: list[PersonKind] = []

    if any(kw in conditions for kw in ("line manager", "reports to", "manager", "managing")):
        signals.append(PersonKind.MANAGER)
    if any(kw in conditions for kw in ("stakeholder", "cto", "head of", "director", "decision")):
        signals.append(PersonKind.STAKEHOLDER)
    if any(kw in conditions for kw in ("customer", "account", "client", "dealer")):
        signals.append(PersonKind.CUSTOMER_CONTACT)
    if any(kw in conditions for kw in ("mentor", "advisory", "coach")):
        signals.append(PersonKind.MENTOR)
    if "author" in tags and not conditions.strip():
        signals.append(PersonKind.AUTHOR)
    if rel_to in ("friend", "family", "partner", "sibling") or context.startswith("personal"):
        signals.append(PersonKind.ACQUAINTANCE)
    if rel_to == "colleague" and not signals:
        return InferenceResult(kind=PersonKind.COLLABORATOR, is_ambiguous=False)

    unique = list(dict.fromkeys(signals))
    if not unique:
        return InferenceResult(kind=PersonKind.COLLABORATOR, is_ambiguous=True)
    return InferenceResult(kind=unique[0], is_ambiguous=len(unique) > 1)


def extract_body_dated_headings(body: str) -> list[str]:
    """Return all YYYY-MM-DD dates found in body headings, sorted ascending."""
    return sorted(set(DATED_HEADING_RE.findall(body)))


def infer_interaction_frequency(dates: list[str]) -> InteractionFrequency | None:
    """Infer frequency from gap distribution if 3+ dated entries exist."""
    if len(dates) < 3:
        return None
    parsed = [date.fromisoformat(d) for d in dates]
    gaps = [(parsed[i + 1] - parsed[i]).days for i in range(len(parsed) - 1)]
    avg_gap = sum(gaps) / len(gaps)
    if avg_gap <= 2:
        return InteractionFrequency.DAILY
    if avg_gap <= 10:
        return InteractionFrequency.WEEKLY
    if avg_gap <= 45:
        return InteractionFrequency.MONTHLY
    if avg_gap <= 120:
        return InteractionFrequency.QUARTERLY
    return InteractionFrequency.RARELY


def recency_bonus(last_interaction_date: str | None) -> float:
    """Return recency contribution to connection_strength (0.0–0.15)."""
    if not last_interaction_date:
        return 0.0
    try:
        delta = (date.today() - date.fromisoformat(str(last_interaction_date))).days
    except ValueError:
        return 0.0
    if delta <= 30:
        return 0.15
    if delta <= 90:
        return 0.10
    if delta <= 180:
        return 0.05
    return 0.0


def count_body_outlinks(body: str) -> int:
    return len(set(m.group(1).strip() for m in WIKILINK_RE.finditer(body)))


def score_connection_strength(
    path: Path,
    body: str,
    frontmatter: dict[str, Any],
    *,
    backlink_count: int = 0,
) -> float:
    """Score 0.0–1.0 for person relationship depth.

    outlink_score  = min(body_outlinks / 8,  1.0) × 0.35
    pl_score       = min(potential_links / 6, 1.0) × 0.25
    backlink_score = min(backlinks / 4, 1.0) × 0.25
    recency_score  = recency_bonus(last_interaction_date)  (0.0–0.15)
    """
    out_score = min(count_body_outlinks(body) / 8.0, 1.0) * 0.35
    pl_score = min(len(frontmatter.get("potential_links") or []) / 6.0, 1.0) * 0.25
    back_score = min(backlink_count / 4.0, 1.0) * 0.25
    rec_score = recency_bonus(frontmatter.get("last_interaction_date"))
    return round(out_score + pl_score + back_score + rec_score, 2)
