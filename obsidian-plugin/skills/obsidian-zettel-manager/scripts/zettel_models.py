#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
WIKILINK_TOKEN_RE = re.compile(r"(\[\[[^\]]+\]\])")
HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
DATE_LIKE_TARGET_RE = re.compile(r"^\d{4}(?:-\d{2}-\d{2}|-W\d{2})$")
ZETTEL_ID_RE = re.compile(r"^zt-[a-f0-9]{10}$")
FRONTMATTER_DELIM = "\n---\n"

CONCEPT_PREFIXES = (
    "10 Notes/",
    "20 Resources/",
    "Projects/",
    "10 Projects/",
    "Companies/",
    "People/",
    "Products/",
)
CONTEXT_PREFIXES = ("Periodic/", "00 Inbox/")

ZETTEL_FILE_GLOB = "10 Notes/**/*.md"
INBOX_FILE_GLOB = "00 Inbox/**/*.md"

ZETTEL_FRONTMATTER_ORDER = [
    "zettel_id",
    "zettel_kind",
    "aliases",
    "status",
    "connection_strength",
    "potential_links",
    "source",
    "source_date",
    "captured_from",
    "hub_for",
    "synthesises",
    "defines",
    "tags",
]


class ZettelKind(StrEnum):
    ATOMIC = "atomic"
    MOC = "moc"
    LITNOTE = "litnote"
    FLEETING_CAPTURE = "fleeting_capture"
    HUB_SYNTHESIS = "hub_synthesis"
    DEFINITION = "definition"


class ZettelStatus(StrEnum):
    FLEETING = "fleeting"
    PROCESSING = "processing"
    PROCESSED = "processed"
    EVERGREEN = "evergreen"


class ZettelFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    zettel_id: str
    zettel_kind: ZettelKind
    aliases: list[str] = Field(default_factory=list)
    status: ZettelStatus
    connection_strength: float = Field(ge=0.0, le=10.0)
    potential_links: list[str] = Field(default_factory=list)

    source: str | None = None
    source_date: str | None = None
    captured_from: str | None = None
    hub_for: list[str] | None = None
    synthesises: list[str] | None = None
    defines: str | None = None

    tags: list[str] = Field(default_factory=list)

    @field_validator("zettel_id")
    @classmethod
    def validate_zettel_id(cls, value: str) -> str:
        if not ZETTEL_ID_RE.match(value):
            raise ValueError(
                f"zettel_id must match 'zt-<10 lowercase hex chars>', got: {value!r}"
            )
        return value

    @field_validator("connection_strength", mode="before")
    @classmethod
    def coerce_connection_strength(cls, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"connection_strength must be numeric, got: {value!r}")

    @model_validator(mode="after")
    def validate_kind_specific_fields(self) -> "ZettelFrontmatter":
        if self.zettel_kind == ZettelKind.LITNOTE and not self.source:
            raise ValueError("`litnote` zettels require a `source` field.")
        if self.zettel_kind == ZettelKind.MOC and not self.hub_for:
            raise ValueError("`moc` zettels require a `hub_for` list.")
        if self.zettel_kind == ZettelKind.HUB_SYNTHESIS and not self.synthesises:
            raise ValueError("`hub_synthesis` zettels require a `synthesises` list.")
        if self.zettel_kind == ZettelKind.DEFINITION and not self.defines:
            raise ValueError("`definition` zettels require a `defines` field.")
        return self

    @model_validator(mode="after")
    def validate_tag_requirements(self) -> "ZettelFrontmatter":
        required = {
            "type/zettel",
            f"zettel-kind/{self.zettel_kind.value}",
            f"status/{self.status.value}",
        }
        missing = required - set(self.tags)
        if missing:
            raise ValueError(
                f"`tags` must include: {sorted(missing)}. Got: {self.tags}"
            )
        return self

    @model_validator(mode="after")
    def validate_potential_links_non_empty(self) -> "ZettelFrontmatter":
        if not self.potential_links:
            raise ValueError("`potential_links` must be a non-empty list.")
        return self


@dataclass
class NoteParts:
    path: Path
    frontmatter: dict[str, Any]
    body: str


def extract_title(body: str, fallback: str) -> str:
    match = HEADING_RE.search(body)
    return match.group(1).strip() if match else fallback


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
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def link_target(link: str) -> str:
    match = WIKILINK_RE.search(link)
    return match.group(1).strip() if match else link.strip()


def extract_body_link_tokens(body: str) -> list[str]:
    return WIKILINK_TOKEN_RE.findall(body)


def extract_body_link_targets(body: str) -> list[str]:
    return [match.group(1).strip() for match in WIKILINK_RE.finditer(body)]


def is_context_target(target: str) -> bool:
    if target.startswith(CONTEXT_PREFIXES):
        return True
    if DATE_LIKE_TARGET_RE.match(target):
        return True
    return False


def is_concept_target(target: str) -> bool:
    if target.startswith(CONCEPT_PREFIXES):
        return True
    if target.startswith(("Goal -", "00 Inbox/Goal -")):
        return True
    if "Project" in target:
        return True
    return not is_context_target(target)


def classify_body_links(body: str) -> dict[str, list[str]]:
    concept: list[str] = []
    context: list[str] = []
    other: list[str] = []
    for token in extract_body_link_tokens(body):
        target = link_target(token)
        if is_context_target(target):
            context.append(token)
        elif is_concept_target(target):
            concept.append(token)
        else:
            other.append(token)
    return {
        "concept_links": dedupe_preserve(concept),
        "context_links": dedupe_preserve(context),
        "other_links": dedupe_preserve(other),
    }


def has_context_link(body: str) -> bool:
    return bool(classify_body_links(body)["context_links"])


def has_concept_link(body: str) -> bool:
    return bool(classify_body_links(body)["concept_links"])


def count_total_outlinks(body: str, frontmatter: dict[str, Any]) -> int:
    body_targets = {m.group(1).strip() for m in WIKILINK_RE.finditer(body)}
    fm_targets: set[str] = set()
    for item in frontmatter.get("potential_links") or []:
        m = WIKILINK_RE.search(str(item))
        if m:
            fm_targets.add(m.group(1).strip())
    return len(body_targets | fm_targets)


def score_connection_strength(
    path: Path,
    body: str,
    frontmatter: dict[str, Any],
    *,
    backlink_count: int = 0,
) -> float:
    """Score 0.0-10.0 from outlinks (4pts), potential_links (2pts), backlinks (4pts)."""
    outlinks = count_total_outlinks(body, frontmatter)
    out_score = min(outlinks / 6.0, 1.0) * 4.0
    pl_count = len(frontmatter.get("potential_links") or [])
    pl_score = min(pl_count / 4.0, 1.0) * 2.0
    back_score = min(backlink_count / 5.0, 1.0) * 4.0
    return round(out_score + pl_score + back_score, 2)


def make_zettel_id(path: Path, frontmatter: dict[str, Any]) -> str:
    existing = frontmatter.get("zettel_id")
    if existing and ZETTEL_ID_RE.match(str(existing)):
        return str(existing)
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]
    return f"zt-{digest}"


def infer_zettel_kind(frontmatter: dict[str, Any], path: Path) -> tuple[ZettelKind, bool]:
    """Return (inferred_kind, is_ambiguous). Never overwrites an explicit kind."""
    tags = [str(t) for t in frontmatter.get("tags") or []]
    signals: list[ZettelKind] = []

    if "type/moc" in tags or frontmatter.get("hub_for"):
        signals.append(ZettelKind.MOC)
    if "type/resource-litnote" in tags or frontmatter.get("source"):
        signals.append(ZettelKind.LITNOTE)
    if "type/definition" in tags or frontmatter.get("defines"):
        signals.append(ZettelKind.DEFINITION)
    if frontmatter.get("synthesises"):
        signals.append(ZettelKind.HUB_SYNTHESIS)
    if str(path).find("/00 Inbox/") != -1 or str(path).find("00 Inbox" + "/") != -1:
        signals.append(ZettelKind.FLEETING_CAPTURE)

    unique = list(dict.fromkeys(signals))  # dedupe preserving order
    if len(unique) == 0:
        return ZettelKind.ATOMIC, False
    if len(unique) == 1:
        return unique[0], False
    # Multiple signals: ambiguous
    return unique[0], True


def infer_status_from_tags(frontmatter: dict[str, Any]) -> ZettelStatus:
    tags = [str(t) for t in frontmatter.get("tags") or []]
    if "status/evergreen" in tags:
        return ZettelStatus.EVERGREEN
    if "status/processed" in tags:
        return ZettelStatus.PROCESSED
    if "status/processing" in tags:
        return ZettelStatus.PROCESSING
    return ZettelStatus.FLEETING


def normalize_zettel_tags(
    frontmatter: dict[str, Any],
    *,
    kind: str,
    status: str,
) -> list[str]:
    raw = frontmatter.get("tags", [])
    tags: list[str] = []
    if isinstance(raw, str):
        tags.append(raw)
    elif isinstance(raw, list):
        tags.extend(str(item) for item in raw)
    managed_prefixes = ("type/zettel", "zettel-kind/", "status/")
    tags = [t for t in tags if not any(t.startswith(p) for p in managed_prefixes)]
    managed = [
        "type/zettel",
        f"zettel-kind/{kind}",
        f"status/{status}",
    ]
    return dedupe_preserve(managed + tags)


def order_frontmatter(
    frontmatter: dict[str, Any],
    original_key_order: list[str] | None = None,
) -> OrderedDict[str, Any]:
    ordered: OrderedDict[str, Any] = OrderedDict()
    original_key_order = original_key_order or list(frontmatter.keys())

    for key in ZETTEL_FRONTMATTER_ORDER:
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


def validate_frontmatter(frontmatter: dict[str, Any]) -> tuple[bool, list[str]]:
    try:
        ZettelFrontmatter.model_validate(frontmatter)
    except ValidationError as exc:
        return False, [error["msg"] for error in exc.errors()]
    return True, []


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
