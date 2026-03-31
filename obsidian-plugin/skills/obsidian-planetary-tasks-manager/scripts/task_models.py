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
from typing import Any, Iterable, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
WIKILINK_TOKEN_RE = re.compile(r"(\[\[[^\]]+\]\])")
HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
DATE_LIKE_TARGET_RE = re.compile(r"^\d{4}(?:-\d{2}-\d{2}|-W\d{2})$")
FRONTMATTER_DELIM = "\n---\n"

TASK_FRONTMATTER_ORDER = [
    "task_id",
    "task_kind",
    "task_status",
    "done",
    "planning_system",
    "planning_horizon",
    "timeframe",
    "domain",
    "thread",
    "goal_kind",
    "project_kind",
    "person_kind",
    "company_kind",
    "project",
    "goal",
    "people",
    "companies",
    "source_note",
    "horizon_note",
    "horizon_source_note",
    "source_path",
    "source_line",
    "target_date",
    "due_date",
    "date",
    "week",
    "month",
    "quarter",
    "cycle_12w",
    "context",
    "potential_links",
    "tags",
    "jira_sync",
    "jira_key",
    "jira_url",
    "priority",
    "last_synced",
]

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

DEFAULT_TASK_HUB = "[[Periodic/Periodic Planning and Tasks Hub|Periodic Planning and Tasks Hub]]"
DEFAULT_TASKS_SUMMARY = "[[00 Inbox/Tasks|Tasks]]"
DEFAULT_TASKS_BASE = "[[10 Notes/Planetary Tasks.base|Planetary Tasks Base]]"
DEFAULT_PLANNING_BASE = "[[10 Notes/Planetary Planning.base|Planetary Planning Base]]"
DEFAULT_AUTOGRAB = "[[Companies/Autograb|Autograb]]"
TASK_FILE_GLOB = "Periodic/*/Planetary Tasks/*.md"
TASK_HUB_LINK = DEFAULT_TASK_HUB
TASKS_SUMMARY_LINK = DEFAULT_TASKS_SUMMARY
TASK_BASE_LINK = DEFAULT_TASKS_BASE
PLANNING_BASE_LINK = DEFAULT_PLANNING_BASE


class TaskKind(StrEnum):
    ACTION = "action"
    EXTERNAL_TICKET = "external_ticket"
    CLOSURE_SIGNAL = "closure_signal"


class GoalKind(StrEnum):
    HEALTH_GOAL = "health_goal"
    CAREER_GOAL = "career_goal"
    RELATIONSHIP_GOAL = "relationship_goal"
    CAPABILITY_GOAL = "capability_goal"


class ProjectKind(StrEnum):
    INITIATIVE = "initiative"
    REPORTING_STREAM = "reporting_stream"
    PLATFORM_WORKSTREAM = "platform_workstream"
    DELIVERY_SYSTEM = "delivery_system"


class PersonKind(StrEnum):
    MANAGER = "manager"
    COLLABORATOR = "collaborator"
    STAKEHOLDER = "stakeholder"
    CUSTOMER_CONTACT = "customer_contact"


class CompanyKind(StrEnum):
    EMPLOYER = "employer"
    CUSTOMER = "customer"
    PARTNER = "partner"
    VENDOR = "vendor"


class Timeframe(StrEnum):
    ANYTIME = "anytime"
    SOMEDAY = "someday"
    DATED = "dated"


class DependencyStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"


class ReadBudget(BaseModel):
    max_files: int = 5
    max_chars: int = 22000
    max_snippets: int = 12


class RouteSpec(BaseModel):
    route_id: str
    keywords: list[str]
    selected_skill: str
    required_commands: list[str]


class RoutingResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool = True
    selected_skill: str | None
    required_commands: list[str] = Field(default_factory=list)
    read_budget: ReadBudget = Field(default_factory=ReadBudget)
    dependency_status: DependencyStatus | str
    mode: Literal["plan", "execute"] | None = None
    error: str | None = None
    missing: list[str] | None = None
    fallback_checklist: list[str] | None = None


RouteOutput = RoutingResult


class PlanetaryTaskFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str
    task_kind: Literal["action", "external_ticket", "closure_signal"]
    task_status: Literal["next", "in_progress", "waiting", "completed"]
    done: bool
    planning_system: Literal["planetary"]
    planning_horizon: str
    timeframe: Literal["anytime", "someday", "dated"]
    domain: str
    thread: str
    goal_kind: Literal["health_goal", "career_goal", "relationship_goal", "capability_goal"] | None = None
    project_kind: Literal["initiative", "reporting_stream", "platform_workstream", "delivery_system"] | None = None
    person_kind: Literal["manager", "collaborator", "stakeholder", "customer_contact"] | None = None
    company_kind: Literal["employer", "customer", "partner", "vendor"] | None = None
    source_note: str
    horizon_note: str
    context: list[str]
    potential_links: list[str]
    tags: list[str]
    project: str | None = None
    goal: str | None = None
    people: list[str] | None = None
    companies: list[str] | None = None
    horizon_source_note: str | None = None
    source_path: str | None = None
    source_line: int | None = None
    target_date: str | None = None
    due_date: str | None = None
    date: str | None = None
    week: int | None = None
    month: int | None = None
    quarter: int | None = None
    cycle_12w: str | None = None
    jira_sync: bool | None = None
    jira_key: str | None = None
    jira_url: str | None = None
    priority: str | None = None
    last_synced: str | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "PlanetaryTaskFrontmatter":
        if self.task_status == "completed" and not self.done:
            raise ValueError("`task_status: completed` requires `done: true`.")
        if self.done and self.task_status != "completed":
            raise ValueError("`done: true` requires `task_status: completed`.")
        if self.task_kind == "external_ticket" and not (self.jira_sync and self.jira_key and self.jira_url):
            raise ValueError("`external_ticket` tasks require `jira_sync`, `jira_key`, and `jira_url`.")
        if "type/task" not in self.tags:
            raise ValueError("`tags` must include `type/task`.")
        if "planning/planetary" not in self.tags:
            raise ValueError("`tags` must include `planning/planetary`.")
        if f"task-kind/{self.task_kind}" not in self.tags:
            raise ValueError(f"`tags` must include `task-kind/{self.task_kind}`.")
        if not self.context:
            raise ValueError("`context` must be a non-empty list.")
        if not self.potential_links:
            raise ValueError("`potential_links` must be a non-empty list.")
        return self


@dataclass
class NoteParts:
    path: Path
    frontmatter: dict[str, Any]
    body: str


TaskDocument = NoteParts


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
    body = text[end + len(FRONTMATTER_DELIM) :]
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise ValueError("Frontmatter must deserialize to a mapping.")
    return normalize_jsonable(dict(payload)), body


def load_markdown_note(path: Path) -> NoteParts:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    return NoteParts(path=path, frontmatter=frontmatter, body=body)


def load_task_document(path: str | Path) -> TaskDocument:
    return load_markdown_note(Path(path))


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


def extract_wikilinks(body: str) -> list[str]:
    return extract_body_link_tokens(body)


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


def classify_task_kind(frontmatter: dict[str, Any], body: str, path: Path) -> Literal["action", "external_ticket", "closure_signal"]:
    if frontmatter.get("jira_sync") or frontmatter.get("jira_key"):
        return "external_ticket"
    title = extract_title(body, path.stem).lower()
    if frontmatter.get("planning_horizon") == "maneuver_board":
        return "closure_signal"
    closure_hints = (
        "completion count",
        "todays completion count",
        "today's completion count",
        "main blocker observed",
        "main blocker noticed",
        "first maneuver for tomorrow",
    )
    if any(hint in title or hint in path.stem.lower() or hint in body.lower() for hint in closure_hints):
        return "closure_signal"
    return "action"


def make_task_id(path: Path, frontmatter: dict[str, Any]) -> str:
    if frontmatter.get("task_id"):
        return str(frontmatter["task_id"])
    if frontmatter.get("jira_key"):
        return f"task-{str(frontmatter['jira_key']).lower()}"
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]
    return f"pt-{digest}"


def ensure_task_id(frontmatter: dict[str, Any], path: Path, title_seed: str | None = None) -> str:
    del title_seed
    return make_task_id(path, frontmatter)


def status_from_frontmatter(frontmatter: dict[str, Any]) -> str:
    raw = str(frontmatter.get("task_status", "")).strip() or "next"
    if frontmatter.get("done") is True:
        return "completed"
    return raw


def derive_done(task_status: str, current_done: Any) -> bool:
    if task_status == "completed":
        return True
    return bool(current_done)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def temporal_fields_for_date(value: str) -> dict[str, Any]:
    dt = parse_iso_date(value)
    iso_year, iso_week, _ = dt.isocalendar()
    quarter = ((dt.month - 1) // 3) + 1
    cycle = f"{dt.year}-Q{quarter}-C{((iso_week - 1) // 12) + 1}"
    week_label = f"{iso_year}-W{iso_week:02d}"
    return {
        "date": dt.isoformat(),
        "week": iso_week,
        "month": dt.month,
        "quarter": quarter,
        "cycle_12w": cycle,
        "horizon_note": f"[[Periodic/{iso_year}/{week_label}|{week_label}]]",
    }


def week_link_for(frontmatter: dict[str, Any], fallback_today: date | None = None) -> str:
    candidates = [
        frontmatter.get("last_synced"),
        frontmatter.get("date"),
        fallback_today.isoformat() if fallback_today else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            fields = temporal_fields_for_date(str(candidate))
            return str(fields["horizon_note"])
        except Exception:
            continue
    today = fallback_today or date.today()
    fields = temporal_fields_for_date(today.isoformat())
    return str(fields["horizon_note"])


def dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    class _NoAliasSafeDumper(yaml.SafeDumper):
        def ignore_aliases(self, data: Any) -> bool:  # pragma: no cover - dumper hook
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


def render_document(frontmatter: dict[str, Any], body: str) -> str:
    return render_markdown(frontmatter, body)


def serialize_model(model: BaseModel) -> dict[str, Any]:
    payload = model.model_dump(mode="python", exclude_none=True)
    return payload


def dump_json(payload: Any) -> str:
    return json.dumps(normalize_jsonable(payload), indent=2)


def order_frontmatter(frontmatter: dict[str, Any], original_key_order: list[str] | None = None) -> OrderedDict[str, Any]:
    ordered: OrderedDict[str, Any] = OrderedDict()
    original_key_order = original_key_order or list(frontmatter.keys())

    for key in TASK_FRONTMATTER_ORDER:
        if key in frontmatter:
            ordered[key] = frontmatter[key]

    for key in original_key_order:
        if key in frontmatter and key not in ordered:
            ordered[key] = frontmatter[key]

    for key, value in frontmatter.items():
        if key not in ordered:
            ordered[key] = value

    return ordered


def parse_frontmatter(frontmatter: dict[str, Any]) -> PlanetaryTaskFrontmatter:
    return PlanetaryTaskFrontmatter.model_validate(frontmatter)


def validate_frontmatter(frontmatter: dict[str, Any]) -> tuple[bool, list[str]]:
    try:
        parse_frontmatter(frontmatter)
    except ValidationError as exc:
        return False, [error["msg"] for error in exc.errors()]
    return True, []


def dedupe_strings(items: Iterable[str]) -> list[str]:
    return dedupe_preserve(items)


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


def normalize_tags(frontmatter: dict[str, Any], *, domain: str, timeframe: str, done: bool) -> list[str]:
    raw = frontmatter.get("tags", [])
    tags: list[str] = []
    if isinstance(raw, str):
        tags.append(raw)
    elif isinstance(raw, list):
        tags.extend(str(item) for item in raw)
    tags = [tag for tag in tags if not tag.startswith("status/") and not tag.startswith("task-kind/")]
    tags.extend(
        [
            "type/task",
            "planning/planetary",
            f"domain/{domain}",
            f"timeframe/{timeframe}",
            f"task-kind/{frontmatter.get('task_kind', TaskKind.ACTION)}",
            "status/completed" if done else "status/actionable",
        ]
    )
    return dedupe_preserve(tags)


def collect_link_candidates(frontmatter: dict[str, Any], body: str) -> list[str]:
    candidates: list[str] = []
    for key in ("project", "goal", "source_note", "horizon_note"):
        value = frontmatter.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    for key in ("people", "companies", "context", "potential_links"):
        value = frontmatter.get(key)
        if isinstance(value, list):
            candidates.extend(str(item).strip() for item in value if str(item).strip())
    candidates.extend(extract_body_link_tokens(body))
    candidates.extend([TASK_HUB_LINK, TASK_BASE_LINK, PLANNING_BASE_LINK])
    return dedupe_preserve(candidates)


def planning_context_lines(frontmatter: dict[str, Any]) -> list[str]:
    lines = [
        f"- Task kind: `{frontmatter['task_kind']}`",
        f"- Status: `{frontmatter['task_status']}`",
        f"- Horizon: `{frontmatter['planning_horizon']}`",
        f"- Timeframe: `{frontmatter['timeframe']}`",
        f"- Thread: `{frontmatter['thread']}`",
        f"- Domain: `{frontmatter['domain']}`",
    ]
    if frontmatter.get("project"):
        lines.append(f"- Project: {frontmatter['project']}")
    if frontmatter.get("goal"):
        lines.append(f"- Goal: {frontmatter['goal']}")
    if frontmatter.get("goal_kind"):
        lines.append(f"- Goal kind: `{frontmatter['goal_kind']}`")
    if frontmatter.get("people"):
        lines.append(f"- People: {', '.join(frontmatter['people'])}")
    if frontmatter.get("companies"):
        lines.append(f"- Companies: {', '.join(frontmatter['companies'])}")
    lines.extend(
        [
            f"- Source: {frontmatter['source_note']}",
            f"- Horizon note: {frontmatter['horizon_note']}",
            f"- Task hub: {TASK_HUB_LINK}",
            f"- Planning base: {PLANNING_BASE_LINK}",
            f"- Task base: {TASK_BASE_LINK}",
        ]
    )
    return lines


def ensure_planning_context_section(body: str, lines: list[str]) -> str:
    marker = "## Planning Context"
    stripped = body.rstrip()
    rendered_section = f"{marker}\n\n" + "\n".join(lines).rstrip() + "\n"
    if marker not in stripped:
        spacer = "\n\n" if stripped else ""
        return f"{stripped}{spacer}{rendered_section}"

    head, tail = stripped.split(marker, 1)
    tail = tail.lstrip("\n")
    next_heading = re.search(r"(?m)^## ", tail)
    if next_heading:
        remainder = tail[next_heading.start() :].lstrip("\n")
        return f"{head.rstrip()}\n\n{rendered_section}\n{remainder.rstrip()}\n"

    return f"{head.rstrip()}\n\n{rendered_section}"
