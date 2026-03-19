#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import TypeAlias, TypedDict

from pydantic import BaseModel, Field


class ClosureSignalArtifacts(BaseModel):
    available: bool = False
    schema_present: bool = False
    total_in_year: int = 0
    linked_to_week: int = 0
    examples: list[str] = Field(default_factory=list)


FrontmatterValue: TypeAlias = str | list[str]


class ClosureSignals(TypedDict):
    completion_count: bool
    blocker_observed: bool
    first_maneuver_tomorrow: bool


class HorizonPresence(TypedDict):
    week: bool
    month: bool
    quarter: bool
    twelve_week: bool


class ClosureArtifactSummary(TypedDict):
    available: bool
    schema_present: bool
    total_in_year: int
    linked_to_week: int
    examples: list[str]


class WeeklyAnalysis(TypedDict):
    passed: bool
    closure_signals: ClosureSignals
    closure_signal_artifacts: ClosureArtifactSummary
    horizon_presence: HorizonPresence
    priority_thread_mentions: int
    maneuver_mentions: int
    missing_signals: list[str]


def dependency_error(missing: list[str]) -> int:
    payload = {
        "ok": False,
        "error": "missing_dependencies",
        "missing": missing,
        "fallback_checklist": [
            "Install/repair Obsidian CLI and qmd, and ensure uvx is available.",
            "Verify tools: obsidian --help && qmd status && uvx --version",
            "Retry weekly checks after dependencies are available.",
        ],
    }
    print(json.dumps(payload, indent=2))
    return 2


def locate_week_file(vault_root: Path, week: str) -> Path:
    year = week.split("-", 1)[0]
    direct = vault_root / "Periodic" / year / f"{week}.md"
    if direct.exists():
        return direct
    periodic = vault_root / "Periodic"
    if periodic.exists():
        candidates = sorted(periodic.rglob(f"{week}.md"))
        if candidates:
            return candidates[0]
    return direct


def split_frontmatter(text: str) -> dict[str, FrontmatterValue]:
    if not text.startswith("---\n"):
        return {}

    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}

    frontmatter: dict[str, FrontmatterValue] = {}
    current_key: str | None = None
    for line in parts[0].splitlines()[1:]:
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                frontmatter[key] = value.strip('"')
                current_key = None
            else:
                frontmatter[key] = []
                current_key = key
            continue

        if current_key and line.startswith("  - "):
            current_value = frontmatter.get(current_key)
            if isinstance(current_value, list):
                current_value.append(line.strip()[2:].strip().strip('"'))

    return frontmatter


def collect_closure_signal_tasks(vault_root: Path, week: str, week_content: str) -> ClosureSignalArtifacts:
    year = week.split("-", 1)[0]
    task_dir = vault_root / "Periodic" / year / "Planetary Tasks"
    if not task_dir.exists():
        return ClosureSignalArtifacts()

    matches = []
    linked_to_week = 0
    schema_present = False
    for note_path in sorted(task_dir.glob("*.md")):
        text = note_path.read_text(encoding="utf-8", errors="replace")
        frontmatter = split_frontmatter(text)
        if "task_kind" in frontmatter:
            schema_present = True
        if frontmatter.get("task_kind") != "closure_signal":
            continue
        matches.append(note_path.name)
        if week in text or note_path.stem in week_content:
            linked_to_week += 1

    return ClosureSignalArtifacts(
        available=bool(matches),
        schema_present=schema_present,
        total_in_year=len(matches),
        linked_to_week=linked_to_week,
        examples=matches[:5],
    )


def analyze(content: str, closure_signal_artifacts: ClosureSignalArtifacts) -> WeeklyAnalysis:
    lower = content.lower()

    closure: ClosureSignals = {
        "completion_count": bool(re.search(r"completion count|completed\s+\d+", lower)),
        "blocker_observed": "blocker" in lower,
        "first_maneuver_tomorrow": bool(re.search(r"tomorrow.*maneuver|maneuver.*tomorrow", lower)),
    }

    horizon: HorizonPresence = {
        "twelve_week": "12-week" in lower or "12 week" in lower,
        "quarter": "quarter" in lower,
        "month": "month" in lower,
        "week": "week" in lower,
    }

    priority_threads = len(re.findall(r"(?im)^\s*[-*]\s.*(priority thread|thread)", content))
    maneuver_mentions = len(re.findall(r"(?i)maneuver", content))

    missing = [k for k, v in closure.items() if not v]
    if "task base" in lower and closure_signal_artifacts.schema_present and closure_signal_artifacts.total_in_year < 3:
        missing.append("closure_signal_task_artifacts")
    pass_check = len(missing) == 0 and priority_threads >= 2

    artifact_summary: ClosureArtifactSummary = {
        "available": closure_signal_artifacts.available,
        "schema_present": closure_signal_artifacts.schema_present,
        "total_in_year": closure_signal_artifacts.total_in_year,
        "linked_to_week": closure_signal_artifacts.linked_to_week,
        "examples": list(closure_signal_artifacts.examples),
    }

    return {
        "passed": pass_check,
        "closure_signals": closure,
        "closure_signal_artifacts": artifact_summary,
        "horizon_presence": horizon,
        "priority_thread_mentions": priority_threads,
        "maneuver_mentions": maneuver_mentions,
        "missing_signals": missing,
    }


def markdown_report(week: str, path: Path, analysis: WeeklyAnalysis) -> str:
    closure = analysis["closure_signals"]
    closure_artifacts = analysis["closure_signal_artifacts"]
    horizon = analysis["horizon_presence"]
    lines = [
        f"# Weekly Feedback Report: {week}",
        "",
        f"Source: `{path}`",
        "",
        "## Compliance",
        f"- Pass: **{analysis['passed']}**",
        f"- Priority thread mentions: **{analysis['priority_thread_mentions']}** (target >= 2)",
        f"- Maneuver mentions: **{analysis['maneuver_mentions']}**",
        "",
        "## Closure Signals",
        f"- Completion count present: **{closure['completion_count']}**",
        f"- Blocker observed present: **{closure['blocker_observed']}**",
        f"- First maneuver for tomorrow present: **{closure['first_maneuver_tomorrow']}**",
        "",
        "## Closure-Signal Task Artifacts",
        f"- Schema-backed closure tasks found: **{closure_artifacts['available']}**",
        f"- Task schema present in year folder: **{closure_artifacts['schema_present']}**",
        f"- Closure tasks in year folder: **{closure_artifacts['total_in_year']}**",
        f"- Closure tasks explicitly linked to week: **{closure_artifacts['linked_to_week']}**",
        "",
        "## Horizon Presence",
        f"- 12-week: **{horizon['twelve_week']}**",
        f"- Quarter: **{horizon['quarter']}**",
        f"- Month: **{horizon['month']}**",
        f"- Week: **{horizon['week']}**",
        "",
        "## Missing Signals",
    ]

    missing = analysis["missing_signals"]
    if missing:
        lines.extend([f"- `{m}`" for m in missing])
    else:
        lines.append("- None")

    examples = closure_artifacts["examples"]
    if examples:
        lines.extend(
            [
                "",
                "## Example Closure Tasks",
                *[f"- `{name}`" for name in examples],
            ]
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check/report weekly control-plane quality.")
    parser.add_argument("--week", required=True, help="Week id as YYYY-Www")
    parser.add_argument("--mode", required=True, choices=["report", "check"])
    parser.add_argument("--vault-root", default=".", help="Vault root directory")
    args = parser.parse_args()

    missing = [cmd for cmd in ["obsidian", "qmd", "uvx"] if shutil.which(cmd) is None]
    if missing:
        return dependency_error(missing)

    if not re.match(r"^\d{4}-W\d{2}$", args.week):
        payload = {"ok": False, "error": "invalid_week_format", "expected": "YYYY-Www"}
        print(json.dumps(payload, indent=2))
        return 1

    root = Path(args.vault_root).resolve()
    week_file = locate_week_file(root, args.week)

    if not week_file.exists():
        payload = {
            "ok": False,
            "error": "week_note_not_found",
            "week": args.week,
            "searched_path": str(week_file),
        }
        print(json.dumps(payload, indent=2))
        return 1

    content = week_file.read_text(encoding="utf-8", errors="replace")
    closure_signal_artifacts = collect_closure_signal_tasks(root, args.week, content)
    analysis = analyze(content, closure_signal_artifacts)

    if args.mode == "check":
        payload = {
            "ok": True,
            "week": args.week,
            "path": str(week_file),
            "compliance": analysis,
        }
        print(json.dumps(payload, indent=2))
        return 0 if analysis["passed"] else 1

    print(markdown_report(args.week, week_file, analysis))
    return 0


if __name__ == "__main__":
    sys.exit(main())
