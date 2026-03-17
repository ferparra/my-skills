#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from task_models import (
    DEFAULT_AUTOGRAB,
    DEFAULT_PLANNING_BASE,
    DEFAULT_TASKS_BASE,
    DEFAULT_TASKS_SUMMARY,
    DEFAULT_TASK_HUB,
    NoteParts,
    classify_body_links,
    classify_task_kind,
    dedupe_preserve,
    ensure_planning_context_section,
    extract_body_link_tokens,
    link_target,
    load_markdown_note,
    make_task_id,
    order_frontmatter,
    planning_context_lines,
    render_markdown,
    temporal_fields_for_date,
    validate_frontmatter,
)

THREAD_ROW_RE = re.compile(r"^\|\s*(T\d+)\s*\|\s*\[(AG-\d+)\]", re.MULTILINE)


def expand_paths(root: Path, paths: list[str], globs: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if candidate.exists():
            resolved.append(candidate)
    for pattern in globs:
        resolved.extend(sorted(root.glob(pattern)))
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in resolved:
        if path.suffix != ".md" or path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def resolve_task_link(root: Path, link: str) -> Path | None:
    target = link_target(link)
    if target.startswith("Periodic/"):
        candidate = root / f"{target}.md"
        return candidate if candidate.exists() else None
    for candidate in root.glob(f"Periodic/*/Planetary Tasks/{target}.md"):
        return candidate
    return None


def infer_thread_from_related_tasks(root: Path, body: str) -> str | None:
    threads: list[str] = []
    for token in extract_body_link_tokens(body):
        task_path = resolve_task_link(root, token)
        if not task_path:
            continue
        note = load_markdown_note(task_path)
        thread = note.frontmatter.get("thread")
        if thread:
            threads.append(str(thread))
    if not threads:
        return None
    [(thread, _count)] = Counter(threads).most_common(1)
    return thread


def infer_project_from_related_tasks(root: Path, body: str) -> str | None:
    projects: list[str] = []
    for token in extract_body_link_tokens(body):
        task_path = resolve_task_link(root, token)
        if not task_path:
            continue
        note = load_markdown_note(task_path)
        project = note.frontmatter.get("project")
        if project:
            projects.append(str(project))
    if not projects:
        return None
    [(project, _count)] = Counter(projects).most_common(1)
    return project


def infer_thread_from_periodic_notes(root: Path, jira_key: str) -> str | None:
    for weekly_note in sorted(root.glob("Periodic/**/*.md")):
        text = weekly_note.read_text(encoding="utf-8", errors="replace")
        for thread, key in THREAD_ROW_RE.findall(text):
            if key == jira_key:
                return thread
    return None


def infer_relation_fields(frontmatter: dict[str, Any], body: str) -> None:
    people = list(frontmatter.get("people") or [])
    companies = list(frontmatter.get("companies") or [])
    goal = frontmatter.get("goal")

    for token in extract_body_link_tokens(body):
        target = link_target(token)
        if target.startswith("People/"):
            people.append(token)
        elif target.startswith("Companies/"):
            companies.append(token)
        elif not goal and (target.startswith(("Goal -", "00 Inbox/Goal -"))):
            goal = token

    if people:
        frontmatter["people"] = dedupe_preserve(people)
    if companies:
        frontmatter["companies"] = dedupe_preserve(companies)
    if goal:
        frontmatter["goal"] = goal


def managed_tags(frontmatter: dict[str, Any]) -> list[str]:
    existing = [str(tag) for tag in frontmatter.get("tags") or []]
    existing = [
        tag
        for tag in existing
        if not (
            tag == "type/task"
            or tag == "planning/planetary"
            or tag.startswith("domain/")
            or tag.startswith("timeframe/")
            or tag.startswith("task-kind/")
            or tag in {"status/actionable", "status/completed"}
        )
    ]
    managed = [
        "type/task",
        "status/completed" if frontmatter.get("done") else "status/actionable",
        "planning/planetary",
        f"domain/{frontmatter['domain']}",
        f"timeframe/{frontmatter['timeframe']}",
        f"task-kind/{frontmatter['task_kind']}",
    ]
    return dedupe_preserve(managed + existing)


def ensure_lists(frontmatter: dict[str, Any]) -> None:
    frontmatter["context"] = dedupe_preserve([str(item) for item in frontmatter.get("context") or []])
    frontmatter["potential_links"] = dedupe_preserve([str(item) for item in frontmatter.get("potential_links") or []])
    frontmatter["tags"] = [str(item) for item in frontmatter.get("tags") or []]
    if frontmatter.get("people"):
        frontmatter["people"] = dedupe_preserve([str(item) for item in frontmatter["people"]])
    if frontmatter.get("companies"):
        frontmatter["companies"] = dedupe_preserve([str(item) for item in frontmatter["companies"]])


def append_planning_context(body: str, frontmatter: dict[str, Any]) -> str:
    lines = planning_context_lines(frontmatter)
    if not frontmatter.get("project") and not frontmatter.get("goal") and not frontmatter.get("people") and not frontmatter.get("companies"):
        lines.insert(3, f"- Company: {DEFAULT_AUTOGRAB}")
    return ensure_planning_context_section(body, lines)


def normalize_task(note: NoteParts, root: Path) -> dict[str, Any]:
    frontmatter = dict(note.frontmatter)
    original_key_order = list(frontmatter.keys())
    warnings: list[str] = []

    frontmatter["task_kind"] = classify_task_kind(frontmatter, note.body, note.path)
    frontmatter["task_id"] = make_task_id(note.path, frontmatter)
    frontmatter["planning_system"] = "planetary"
    if frontmatter["task_kind"] == "closure_signal":
        frontmatter["planning_horizon"] = "maneuver_board"
    elif not frontmatter.get("planning_horizon"):
        frontmatter["planning_horizon"] = "maneuver" if frontmatter["task_kind"] == "external_ticket" else "day"
    frontmatter["domain"] = str(frontmatter.get("domain") or "work")
    frontmatter["timeframe"] = str(frontmatter.get("timeframe") or "anytime")

    frontmatter["done"] = frontmatter.get("task_status") == "completed"

    if frontmatter["task_kind"] == "external_ticket":
        frontmatter["jira_sync"] = True
        frontmatter["source_note"] = str(frontmatter.get("source_note") or DEFAULT_TASKS_SUMMARY)
        frontmatter["source_path"] = str(frontmatter.get("source_path") or "00 Inbox/Tasks.md")
        anchor = str(frontmatter.get("last_synced") or frontmatter.get("date") or frontmatter.get("due_date") or frontmatter.get("target_date") or date.today().isoformat())
        temporal = temporal_fields_for_date(anchor)
        frontmatter.setdefault("date", temporal["date"])
        frontmatter.setdefault("week", temporal["week"])
        frontmatter.setdefault("month", temporal["month"])
        frontmatter.setdefault("quarter", temporal["quarter"])
        frontmatter.setdefault("cycle_12w", temporal["cycle_12w"])
        frontmatter["horizon_note"] = str(frontmatter.get("horizon_note") or temporal["horizon_note"])
        frontmatter["thread"] = str(
            frontmatter.get("thread")
            or infer_thread_from_related_tasks(root, note.body)
            or infer_thread_from_periodic_notes(root, str(frontmatter.get("jira_key") or ""))
            or "unassigned"
        )
        if frontmatter["thread"] == "unassigned":
            warnings.append("thread defaulted to unassigned")
        if not frontmatter.get("project"):
            inferred_project = infer_project_from_related_tasks(root, note.body)
            if inferred_project:
                frontmatter["project"] = inferred_project
        if not frontmatter.get("companies"):
            frontmatter["companies"] = [DEFAULT_AUTOGRAB]
        if frontmatter.get("due_date") and not frontmatter.get("target_date"):
            frontmatter["target_date"] = str(frontmatter["due_date"])
    else:
        frontmatter["thread"] = str(frontmatter.get("thread") or "unassigned")
        if frontmatter.get("target_date") and not frontmatter.get("date"):
            frontmatter["date"] = str(frontmatter["target_date"])

    infer_relation_fields(frontmatter, note.body)

    context = list(frontmatter.get("context") or [])
    context.extend([frontmatter["source_note"], frontmatter["horizon_note"], DEFAULT_TASK_HUB])
    frontmatter["context"] = dedupe_preserve([str(item) for item in context if item])

    potential = list(frontmatter.get("potential_links") or [])
    for key in ("project", "goal"):
        if frontmatter.get(key):
            potential.append(str(frontmatter[key]))
    for item in frontmatter.get("people") or []:
        potential.append(str(item))
    for item in frontmatter.get("companies") or []:
        potential.append(str(item))
    potential.extend([DEFAULT_PLANNING_BASE, DEFAULT_TASKS_BASE, DEFAULT_TASK_HUB])
    frontmatter["potential_links"] = dedupe_preserve([str(item) for item in potential if item])
    frontmatter["tags"] = managed_tags(frontmatter)
    ensure_lists(frontmatter)
    new_body = append_planning_context(note.body, frontmatter)

    normalized = order_frontmatter(frontmatter, original_key_order)
    body_audit = classify_body_links(new_body)
    errors: list[str] = []
    ok_frontmatter, frontmatter_errors = validate_frontmatter(dict(normalized))
    errors.extend(frontmatter_errors)
    if not body_audit["concept_links"]:
        errors.append("Task body must contain at least one concept link.")
    if not body_audit["context_links"]:
        errors.append("Task body must contain at least one context link.")

    return {
        "frontmatter": dict(normalized),
        "body": new_body,
        "warnings": warnings,
        "errors": errors if not ok_frontmatter or errors else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize planetary task notes to the canonical task schema.")
    parser.add_argument("--path", action="append", default=[], help="Specific markdown path to migrate.")
    parser.add_argument("--glob", action="append", default=[], help="Glob pattern relative to vault root.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    default_globs = args.glob or ([] if args.path else ["Periodic/*/Planetary Tasks/*.md"])
    paths = expand_paths(root, args.path, default_globs)
    if not paths:
        print(json.dumps({"ok": False, "error": "no_paths"}, indent=2))
        return 1

    results: list[dict[str, Any]] = []
    overall_ok = True

    for path in paths:
        note = load_markdown_note(path)
        normalized = normalize_task(note, root)
        rendered = render_markdown(normalized["frontmatter"], normalized["body"])
        current = path.read_text(encoding="utf-8", errors="replace")
        changed = rendered != current
        result = {
            "path": str(path.relative_to(root)),
            "changed": changed,
            "warnings": normalized["warnings"],
            "errors": normalized["errors"],
        }
        if normalized["errors"]:
            overall_ok = False
        if args.mode == "check" and changed:
            overall_ok = False
            result["errors"] = result["errors"] + ["Note does not match canonical planetary task schema."]
        if args.mode == "fix" and not normalized["errors"] and changed:
            path.write_text(rendered, encoding="utf-8")
        results.append(result)

    print(json.dumps({"ok": overall_ok, "count": len(results), "results": results}, indent=2))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
