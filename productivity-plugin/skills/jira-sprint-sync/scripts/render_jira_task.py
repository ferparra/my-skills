#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_MODEL_DIR = SCRIPT_DIR.parents[1] / "obsidian-planetary-tasks-manager" / "scripts"
if str(TASK_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_MODEL_DIR))

from task_models import (  # noqa: E402
    DEFAULT_AUTOGRAB,
    DEFAULT_PLANNING_BASE,
    DEFAULT_TASKS_BASE,
    DEFAULT_TASKS_SUMMARY,
    DEFAULT_TASK_HUB,
    classify_body_links,
    dedupe_preserve,
    dump_json,
    ensure_planning_context_section,
    order_frontmatter,
    planning_context_lines,
    render_markdown,
    temporal_fields_for_date,
    validate_frontmatter,
)


STATUS_CATEGORY_TO_TASK_STATUS = {
    "new": "next",
    "indeterminate": "in_progress",
    "done": "completed",
}

TASK_STATUS_LABELS = {
    "next": "To Do",
    "in_progress": "In Progress",
    "waiting": "Waiting",
    "completed": "Done",
}


def parse_timestamp(value: str) -> datetime:
    candidate = value.strip()
    if len(candidate) == 10:
        return datetime.combine(date.fromisoformat(candidate), time.min)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    return datetime.fromisoformat(candidate)


def normalize_link(value: str, prefix: str | None = None) -> str:
    target = value.strip()
    if target.startswith("[[") and target.endswith("]]"):
        return target
    if prefix and not target.startswith(prefix):
        target = f"{prefix}/{target}"
    return f"[[{target}]]"


def sanitize_summary(summary: str) -> str:
    cleaned = summary.replace("/", " - ").replace(":", " - ")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def primary_concept_link(frontmatter: dict[str, object]) -> str:
    for key in ("project", "goal"):
        value = frontmatter.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("people", "companies"):
        values = frontmatter.get(key)
        if isinstance(values, list) and values:
            return str(values[0])
    return DEFAULT_AUTOGRAB


def build_frontmatter(args: argparse.Namespace) -> tuple[dict[str, object], Path]:
    synced_at = parse_timestamp(args.last_synced)
    temporal = temporal_fields_for_date(synced_at.date().isoformat())
    task_status = STATUS_CATEGORY_TO_TASK_STATUS[args.status_category]
    task_id = f"task-{args.key.lower()}"
    summary = sanitize_summary(args.summary)
    relative_path = Path(
        args.path
        or f"Periodic/{synced_at.year}/Planetary Tasks/{args.key} - {summary}.md"
    )

    project = normalize_link(args.project) if args.project else None
    goal = normalize_link(args.goal) if args.goal else None
    people = [normalize_link(value, "People") for value in args.person]
    companies = [normalize_link(value, "Companies") for value in args.company]
    if not companies:
        companies = [DEFAULT_AUTOGRAB]

    frontmatter: dict[str, object] = {
        "task_id": task_id,
        "task_kind": "external_ticket",
        "task_status": task_status,
        "done": task_status == "completed",
        "planning_system": "planetary",
        "planning_horizon": "maneuver",
        "timeframe": "dated" if args.target_date or args.due_date else "anytime",
        "domain": "work",
        "thread": args.thread,
        "project": project,
        "goal": goal,
        "people": people or None,
        "companies": companies,
        "source_note": DEFAULT_TASKS_SUMMARY,
        "horizon_note": temporal["horizon_note"],
        "source_path": "00 Inbox/Tasks.md",
        "target_date": args.target_date,
        "due_date": args.due_date,
        "date": temporal["date"],
        "week": temporal["week"],
        "month": temporal["month"],
        "quarter": temporal["quarter"],
        "cycle_12w": temporal["cycle_12w"],
        "context": dedupe_preserve([DEFAULT_TASKS_SUMMARY, temporal["horizon_note"], DEFAULT_TASK_HUB]),
        "potential_links": dedupe_preserve(
            [
                *(item for item in [project, goal] if item),
                *people,
                *companies,
                DEFAULT_PLANNING_BASE,
                DEFAULT_TASKS_BASE,
                DEFAULT_TASK_HUB,
            ]
        ),
        "tags": [
            "type/task",
            "status/completed" if task_status == "completed" else "status/actionable",
            "planning/planetary",
            "domain/work",
            f"timeframe/{'dated' if args.target_date or args.due_date else 'anytime'}",
            "task-kind/external_ticket",
        ],
        "jira_sync": True,
        "jira_key": args.key,
        "jira_url": args.jira_url,
        "priority": args.priority,
        "last_synced": synced_at.isoformat(),
    }

    frontmatter = {key: value for key, value in frontmatter.items() if value is not None}
    return dict(order_frontmatter(frontmatter)), relative_path


def build_body(frontmatter: dict[str, object], summary: str) -> str:
    task_status = str(frontmatter["task_status"])
    title = f"{frontmatter['jira_key']} · {summary}"
    checkbox = "[x]" if frontmatter["done"] else "[ ]"
    concept_link = primary_concept_link(frontmatter)
    context_link = str(frontmatter["horizon_note"])
    status_label = TASK_STATUS_LABELS[task_status]
    body = (
        f"# {title}\n\n"
        f"> [View in Jira]({frontmatter['jira_url']}) · `{frontmatter['priority']}` · {status_label}\n\n"
        f"- {checkbox} Sync Jira issue into the planetary task system. {concept_link} {context_link} "
        f"[thread::{frontmatter['thread']}] [horizon::{frontmatter['planning_horizon']}] [jira::{frontmatter['jira_key']}]\n"
    )
    return ensure_planning_context_section(body, planning_context_lines(frontmatter))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a canonical Jira-backed planetary task note.")
    parser.add_argument("--key", required=True, help="Jira key, for example AG-7218")
    parser.add_argument("--summary", required=True, help="Jira issue summary")
    parser.add_argument(
        "--status-category",
        required=True,
        choices=sorted(STATUS_CATEGORY_TO_TASK_STATUS),
        help="Jira status category key",
    )
    parser.add_argument("--priority", required=True, help="Jira priority label")
    parser.add_argument("--jira-url", required=True, help="Jira issue URL")
    parser.add_argument("--last-synced", required=True, help="Sync timestamp in ISO-8601 format")
    parser.add_argument("--thread", default="unassigned", help="Planetary thread id")
    parser.add_argument("--project", help="Project link target or wikilink")
    parser.add_argument("--goal", help="Goal link target or wikilink")
    parser.add_argument("--person", action="append", default=[], help="Person link target or wikilink")
    parser.add_argument("--company", action="append", default=[], help="Company link target or wikilink")
    parser.add_argument("--target-date", help="Target date as YYYY-MM-DD")
    parser.add_argument("--due-date", help="Due date as YYYY-MM-DD")
    parser.add_argument("--path", help="Optional output path relative to the vault root")
    parser.add_argument("--vault-root", default=".", help="Vault root directory")
    parser.add_argument("--mode", choices=["check", "write"], default="check")
    parser.add_argument("--include-markdown", action="store_true", help="Include rendered markdown in JSON output")
    args = parser.parse_args()

    vault_root = Path(args.vault_root).resolve()
    frontmatter, relative_path = build_frontmatter(args)
    body = build_body(frontmatter, args.summary)

    errors: list[str] = []
    ok_frontmatter, frontmatter_errors = validate_frontmatter(frontmatter)
    errors.extend(frontmatter_errors)
    body_links = classify_body_links(body)
    if not body_links["concept_links"]:
        errors.append("Task body must contain at least one concept link.")
    if not body_links["context_links"]:
        errors.append("Task body must contain at least one context link.")

    output_path = vault_root / relative_path
    rendered = render_markdown(frontmatter, body)

    payload: dict[str, object] = {
        "ok": ok_frontmatter and not errors,
        "mode": args.mode,
        "path": str(relative_path),
        "task_id": frontmatter["task_id"],
        "task_kind": frontmatter["task_kind"],
        "task_status": frontmatter["task_status"],
        "errors": errors,
        "warnings": [] if args.thread != "unassigned" else ["thread defaulted to unassigned"],
    }
    if args.include_markdown:
        payload["markdown"] = rendered

    if args.mode == "write" and payload["ok"]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")

    print(dump_json(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
