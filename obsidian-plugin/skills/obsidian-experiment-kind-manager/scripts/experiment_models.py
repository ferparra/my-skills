#!/usr/bin/env python3
"""Pydantic v2 models for the obsidian-experiment-kind-manager skill.

This file is the single source of truth for all experiment frontmatter schemas,
enums, validation logic, and shared utilities.

Inspired by Tana's supertag concept: `experiment_kind` is the supertag that
selects the strict schema contract for each experiment note.
"""
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

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPERIMENT_ID_RE = re.compile(r"^exp-\d{4}-\d{3,}$")
FRONTMATTER_DELIM = "\n---\n"

EXPERIMENTS_FILE_GLOB = "10 Notes/Productivity/Experiments/**/*.md"

# ---------------------------------------------------------------------------
# Canonical frontmatter field order
# ---------------------------------------------------------------------------

EXPERIMENT_FRONTMATTER_ORDER = [
    "experiment_kind",
    "experiment_id",
    "aliases",
    "created",
    "modified",
    "status",
    "council_owner",
    "domain_tag",
    # Question frame
    "question",
    "hypothesis",
    # Design
    "method",
    "metrics",
    "duration_days",
    "start_date",
    "end_date",
    # Execution
    "interventions",
    "controls",
    "confounders",
    # Outcome
    "outcome",
    "findings",
    "confidence",
    "next_experiments",
    # Vault graph
    "connection_strength",
    "related",
    "potential_links",
    "tags",
]

# ---------------------------------------------------------------------------
# Council and domain routing
# ---------------------------------------------------------------------------

# Maps experiment_kind → (council_owner, domain_tag)
COUNCIL_DOMAIN_MAP: dict[str, tuple[str, str]] = {
    "health":        ("sentinel",    "health-and-performance"),
    "cognitive":     ("philosopher", "philosophy-and-psychology"),
    "technical":     ("architect",   "agentic-systems"),
    "social":        ("steward",     "relationships"),
    "financial":     ("sentinel",    "financial-stewardship"),
    "creative":      ("philosopher", "philosophy-and-psychology"),
    "philosophical": ("philosopher", "philosophy-and-psychology"),
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExperimentKind(StrEnum):
    HEALTH        = "health"         # body, supplements, sleep, diet, physiology
    COGNITIVE     = "cognitive"      # learning, focus, memory, productivity systems
    TECHNICAL     = "technical"      # engineering, tooling, workflow, agentic systems
    SOCIAL        = "social"         # relationships, communication, influence
    FINANCIAL     = "financial"      # investing, spending, financial behaviour
    CREATIVE      = "creative"       # writing, art, music, creative output
    PHILOSOPHICAL = "philosophical"  # beliefs, values, mindset, identity


class ExperimentStatus(StrEnum):
    HYPOTHESIS = "hypothesis"  # idea not yet designed — default entry point
    DESIGN     = "design"      # actively designing protocol and metrics
    RUNNING    = "running"     # intervention is active and data is being collected
    PAUSED     = "paused"      # temporarily halted (external blocker or re-design)
    CONCLUDED  = "concluded"   # completed; findings recorded
    ARCHIVED   = "archived"    # historical record; no further action expected


class ExperimentOutcome(StrEnum):
    CONFIRMED    = "confirmed"    # primary hypothesis supported by evidence
    REFUTED      = "refuted"      # primary hypothesis rejected by evidence
    INCONCLUSIVE = "inconclusive" # insufficient signal to determine
    ABANDONED    = "abandoned"    # stopped early without collecting sufficient data
    ONGOING      = "ongoing"      # experiment still running; no outcome yet


class ConfidenceLevel(StrEnum):
    LOW    = "low"    # anecdotal / n=1 with confounders
    MEDIUM = "medium" # repeated observation with partial controls
    HIGH   = "high"   # robust protocol, tracked metrics, replicated signal


# ---------------------------------------------------------------------------
# Core frontmatter schema
# ---------------------------------------------------------------------------

class ExperimentFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    # ---- Identity ----
    experiment_kind: ExperimentKind
    experiment_id: str                          # e.g. "exp-2026-001"
    created: str
    modified: str
    status: ExperimentStatus
    council_owner: str                          # sentinel | architect | strategist | steward | philosopher
    domain_tag: str                             # e.g. "health-and-performance"

    # ---- Question frame ----
    question: str                               # "What is the effect of X on Y?"
    hypothesis: str                             # "I believe X will cause Y because Z"

    # ---- Design ----
    method: str                                 # protocol / intervention description
    metrics: list[str] = Field(default_factory=list)  # what will be measured
    duration_days: int | None = None
    start_date: str | None = None
    end_date: str | None = None

    # ---- Execution ----
    interventions: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    confounders: list[str] = Field(default_factory=list)

    # ---- Outcome ----
    outcome: ExperimentOutcome = ExperimentOutcome.ONGOING
    findings: str | None = None
    confidence: ConfidenceLevel | None = None
    next_experiments: list[str] = Field(default_factory=list)  # wikilinks

    # ---- Vault graph ----
    aliases: list[str] = Field(default_factory=list)
    connection_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    related: list[str] = Field(default_factory=list)        # wikilinks
    potential_links: list[str] = Field(default_factory=list)  # wikilinks
    tags: list[str] = Field(default_factory=list)

    # ---- Validators ----

    @field_validator("experiment_id")
    @classmethod
    def validate_experiment_id(cls, value: Any) -> str:
        if not EXPERIMENT_ID_RE.match(str(value)):
            raise ValueError(
                f"`experiment_id` must match exp-YYYY-NNN, got: {value!r}"
            )
        return str(value)

    @field_validator("connection_strength", mode="before")
    @classmethod
    def coerce_connection_strength(cls, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"connection_strength must be numeric, got: {value!r}")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_iso_dates(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ISO_DATE_RE.match(str(value)):
            raise ValueError(f"Date fields must be YYYY-MM-DD, got: {value!r}")
        return value

    @field_validator(
        "metrics", "interventions", "controls", "confounders",
        "aliases", "related", "potential_links", "tags", "next_experiments",
    )
    @classmethod
    def validate_string_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Expected a YAML list.")
        return [str(item) for item in value]

    @field_validator("next_experiments", "related", "potential_links")
    @classmethod
    def validate_wikilink_lists(cls, value: list[str]) -> list[str]:
        for item in value:
            if item and not is_wikilink(item):
                raise ValueError(
                    f"Entries must be wikilinks (e.g. [[Note Name]]), got: {item!r}"
                )
        return value

    @field_validator("duration_days")
    @classmethod
    def validate_duration(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("`duration_days` must be a positive integer.")
        return value

    @model_validator(mode="after")
    def validate_council_owner(self) -> "ExperimentFrontmatter":
        expected_owner, expected_domain = COUNCIL_DOMAIN_MAP[self.experiment_kind.value]
        if self.council_owner != expected_owner:
            raise ValueError(
                f"`council_owner` for kind={self.experiment_kind!r} must be "
                f"{expected_owner!r}, got: {self.council_owner!r}"
            )
        if self.domain_tag != expected_domain:
            raise ValueError(
                f"`domain_tag` for kind={self.experiment_kind!r} must be "
                f"{expected_domain!r}, got: {self.domain_tag!r}"
            )
        return self

    @model_validator(mode="after")
    def validate_concluded_has_findings(self) -> "ExperimentFrontmatter":
        if self.status == ExperimentStatus.CONCLUDED:
            if not self.findings:
                raise ValueError(
                    "Concluded experiments must have a non-empty `findings` field."
                )
            if self.outcome == ExperimentOutcome.ONGOING:
                raise ValueError(
                    "Concluded experiments cannot have outcome=ongoing."
                )
        return self

    @model_validator(mode="after")
    def validate_running_has_metrics(self) -> "ExperimentFrontmatter":
        if self.status in (ExperimentStatus.RUNNING, ExperimentStatus.DESIGN):
            if not self.metrics:
                raise ValueError(
                    f"Experiments with status={self.status!r} must define at least one metric."
                )
        return self

    @model_validator(mode="after")
    def validate_tag_requirements(self) -> "ExperimentFrontmatter":
        required = {
            "type/experiment",
            f"experiment-kind/{self.experiment_kind.value}",
            f"status/{self.status.value}",
        }
        missing = required - set(self.tags)
        if missing:
            raise ValueError(
                f"`tags` must include: {sorted(missing)}. Got: {self.tags}"
            )
        return self

    @model_validator(mode="after")
    def validate_date_window(self) -> "ExperimentFrontmatter":
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError(
                    f"`start_date` ({self.start_date}) must be before `end_date` ({self.end_date})."
                )
        return self


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

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
    experiment_kind: str | None = None
    experiment_id: str | None = None
    status: str | None = None
    outcome: str | None = None
    council_owner: str | None = None
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


class ScaffoldResult(BaseModel):
    path: str
    ok: bool
    experiment_id: str
    experiment_kind: str
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

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


def order_frontmatter(frontmatter: dict[str, Any]) -> OrderedDict[str, Any]:
    ordered: OrderedDict[str, Any] = OrderedDict()
    for key in EXPERIMENT_FRONTMATTER_ORDER:
        if key in frontmatter:
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
        ExperimentFrontmatter.model_validate(frontmatter)
    except ValidationError as exc:
        return ValidationResult(ok=False, errors=[error["msg"] for error in exc.errors()])
    except Exception as exc:
        return ValidationResult(ok=False, errors=[str(exc)])
    return ValidationResult(ok=True)


def normalize_experiment_tags(
    frontmatter: dict[str, Any],
    *,
    kind: str,
    status: str,
) -> list[str]:
    raw = ensure_string_list(frontmatter.get("tags"))
    managed_prefixes = ("type/experiment", "experiment-kind/", "status/")
    user_tags = [
        t for t in raw
        if not any(t == p or t.startswith(p) for p in managed_prefixes)
    ]
    managed = [
        "type/experiment",
        f"experiment-kind/{kind}",
        f"status/{status}",
    ]
    return dedupe_preserve(managed + user_tags)


def infer_council_and_domain(kind: str) -> tuple[str, str]:
    """Return (council_owner, domain_tag) for a given experiment_kind value."""
    entry = COUNCIL_DOMAIN_MAP.get(kind)
    if entry is None:
        raise ValueError(f"Unknown experiment_kind: {kind!r}")
    return entry


def next_experiment_id(existing_notes: list[Path]) -> str:
    """Generate the next sequential experiment_id in exp-YYYY-NNN format."""
    year = date.today().year
    existing_ids: list[int] = []
    prefix = f"exp-{year}-"
    for path in existing_notes:
        try:
            note = load_markdown_note(path)
            eid = str(note.frontmatter.get("experiment_id", ""))
            if eid.startswith(prefix):
                seq = int(eid[len(prefix):])
                existing_ids.append(seq)
        except Exception:
            continue
    next_seq = max(existing_ids, default=0) + 1
    return f"{prefix}{next_seq:03d}"


def infer_experiment_kind(frontmatter: dict[str, Any], path: Path) -> tuple[str | None, bool]:
    """Infer kind from tags, folder structure, or explicit field.

    Returns (kind_value, is_ambiguous).
    Never overwrites an explicit experiment_kind.
    """
    raw_kind = str(frontmatter.get("experiment_kind") or "").strip()
    if raw_kind:
        try:
            return ExperimentKind(raw_kind).value, False
        except ValueError:
            pass  # fall through to heuristic

    tags = set(ensure_string_list(frontmatter.get("tags")))
    for kind in ExperimentKind:
        if f"experiment-kind/{kind.value}" in tags:
            return kind.value, False

    # Folder name heuristic
    folder_lower = str(path.parent).lower()
    for kind in ExperimentKind:
        if kind.value in folder_lower:
            return kind.value, False

    # Question/hypothesis keyword heuristic
    text = " ".join([
        str(frontmatter.get("question") or ""),
        str(frontmatter.get("hypothesis") or ""),
        str(frontmatter.get("method") or ""),
    ]).lower()

    health_kw = ("supplement", "sleep", "diet", "exercise", "biomarker", "hrv",
                 "glucose", "cortisol", "nutrition", "recovery", "fasting")
    technical_kw = ("workflow", "tool", "agent", "automation", "code", "api",
                    "pipeline", "script", "framework", "deploy")
    cognitive_kw = ("learning", "focus", "memory", "recall", "attention",
                    "reading", "study", "retention", "pomodoro", "zettelkasten")
    financial_kw = ("invest", "spend", "saving", "budget", "portfolio",
                    "return", "allocation", "compound")
    social_kw = ("relationship", "communication", "network", "conversation",
                 "habit", "accountability", "feedback", "collaboration")

    signals: list[str] = []
    if any(kw in text for kw in health_kw):
        signals.append(ExperimentKind.HEALTH.value)
    if any(kw in text for kw in technical_kw):
        signals.append(ExperimentKind.TECHNICAL.value)
    if any(kw in text for kw in cognitive_kw):
        signals.append(ExperimentKind.COGNITIVE.value)
    if any(kw in text for kw in financial_kw):
        signals.append(ExperimentKind.FINANCIAL.value)
    if any(kw in text for kw in social_kw):
        signals.append(ExperimentKind.SOCIAL.value)

    unique = list(dict.fromkeys(signals))
    if len(unique) == 1:
        return unique[0], False
    if len(unique) > 1:
        return unique[0], True  # ambiguous
    return None, True  # completely unknown
