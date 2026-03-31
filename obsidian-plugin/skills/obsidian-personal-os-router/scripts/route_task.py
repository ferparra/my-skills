#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from typing import Iterable, List

from router_models import DependencyStatus, ReadBudget, RouteOutput, RouteSpec

DEFAULT_BUDGET = ReadBudget()

ROUTES = [
    # key_dates_base is evaluated first — prevents "review" in weekly_feedback
    # from stealing date-related intents like "annual performance review".
    RouteSpec(
        route_id="key_dates_base",
        keywords=[
            "key dates.base",
            "key dates base",
            "key date base",
            "key dates",
            "date-link base",
            "10 notes/key dates.base",
            "date link",
            "mortgage review date",
            "annual performance review",
            "performance review date",
        ],
        selected_skill="obsidian-key-dates-base-manager",
        required_commands=[
            'obsidian read path="10 Notes/Key Dates.base"',
            "qmd ls periodic | awk -F 'qmd://periodic/' 'NF > 1 { print $2 }' | rg '^[0-9]{4}/[0-9]{4}-w[0-9]{2}[.]md$|^[0-9]{4}/[0-9]{4}-[0-9]{2}-monthly-review[.]md$|^[0-9]{4}/[0-9]{4}[.]md$'",
            "qmd ls inbox | awk -F 'qmd://inbox/' 'NF > 1 { print $2 }' | rg '^[0-9]{4}-[0-9]{2}-[0-9]{2}[.]md$'",
            'obsidian unresolved total',
        ],
    ),
    RouteSpec(
        route_id="planetary_task_management",
        keywords=[
            "planetary tasks.base",
            "planetary tasks base",
            "planetary tasks",
            "planetary task",
            "task_kind",
            "task kind",
            "task schema",
            "periodic planning and tasks hub",
            "planning hub",
            "maneuver board",
            "jira sync",
            "current sprint",
            "sprint tasks",
            "sprint assigned",
            "project milestone",
            "milestone done",
            "deliverable",
            "company goals",
            "ongoing goals",
        ],
        selected_skill="obsidian-planetary-tasks-manager",
        required_commands=[
            'obsidian read path="10 Notes/Planetary Tasks.base"',
            'obsidian read path="Periodic/Periodic Planning and Tasks Hub.base"',
            'obsidian backlinks path="Periodic/Periodic Planning and Tasks Hub.md" counts total',
            'qmd query "planetary task task_kind closure signal" -c periodic -l 8',
            'qmd query "planetary task company person project goal" -c projects -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-planetary-tasks-manager/scripts/validate_tasks.py --mode check --glob "Periodic/*/Planetary Tasks/*.md"',
        ],
    ),
    RouteSpec(
        route_id="exercise_kind_management",
        keywords=[
            "exercise kind",
            "exercise_kind",
            "exercise schema",
            "exercise library.base",
            "exercise library base",
            "exercise library",
            "progressive overload",
            "exercise selection",
            "training guiding principles",
            "strong csv",
            "strong export",
            "strong workouts",
            "sync strong",
            "strong app",
            "ios strong",
            "mobility drill",
            "warm-up flow",
            "warmup flow",
            "volume tracking",
            "20 resources/exercises",
            "strength training",
            "gym session",
            "squat progression",
            "fitness goals",
            "training session",
            "training history",
            "workout",
        ],
        selected_skill="obsidian-exercise-kind-manager",
        required_commands=[
            'obsidian read path="20 Resources/Exercises/Exercise Library.base"',
            'obsidian read path="00 Inbox/Training guiding principles.md"',
            'qmd query "exercise selection hypertrophy volume progressive overload" -c resources -l 8',
            'qmd query "training guiding principles hypertrophy volume" -c inbox -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-exercise-kind-manager/scripts/validate_exercises.py --glob "20 Resources/Exercises/*.md" --mode check',
            'uvx --from python --with polars --with pydantic --with pyyaml python .skills/obsidian-exercise-kind-manager/scripts/sync_strong_workouts.py --csv strong_workouts.csv --mode check',
        ],
    ),
    RouteSpec(
        route_id="portfolio_holdings_management",
        keywords=[
            "portfolio holdings",
            "portfolio holdings base",
            "portfolio holdings.base",
            "portfolio holdings history",
            "portfolio holdings history base",
            "portfolio holdings history.base",
            "current holdings",
            "current portfolio positions",
            "actual holdings",
            "active holding",
            "holdings timeline",
            "holdings history",
            "position history",
            "how many units",
            "rebalancing",
            "investment portfolio",
            "target percentage band",
            "vdhg allocation",
            "dhhf",
            "allocation within",
        ],
        selected_skill="obsidian-portfolio-holdings-manager",
        required_commands=[
            'obsidian read path="20 Resources/Investments/Brokerage Activity/Brokerage Activity.base"',
            'obsidian read path="20 Resources/Investments/Portfolio Holdings/Portfolio Holdings.base"',
            'obsidian read path="20 Resources/Investments/Portfolio Holdings History/Portfolio Holdings History.base"',
            'qmd query "portfolio holdings actual holdings current position holding history" -c resources -l 8',
            'qmd query "investment holdings valuation portfolio" -c inbox -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-portfolio-holdings-manager/scripts/sync_portfolio_holdings.py --mode check',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-portfolio-holdings-manager/scripts/validate_portfolio_holdings.py',
        ],
    ),
    RouteSpec(
        route_id="brokerage_activity_management",
        keywords=[
            "betashares",
            "brokerage activity",
            "brokerage csv",
            "brokerage export",
            "transaction history",
            "trade history",
            "dividend log",
            "distribution reinvestment",
            "etf distribution",
            "received a distribution",
            "investment ledger",
            "portfolio ledger",
            "brokerage_activity_kind",
            "brokerage_asset_kind",
            "brokerage activity base",
            "brokerage activity.base",
            "brokerage assets base",
            "brokerage assets.base",
            "ticker asset",
            "asset registry",
        ],
        selected_skill="obsidian-brokerage-activity-manager",
        required_commands=[
            'obsidian read path="20 Resources/Investments/Brokerage Activity/Brokerage Activity.base"',
            'obsidian read path="20 Resources/Investments/Brokerage Assets/Brokerage Assets.base"',
            'qmd query "brokerage activity investment ledger dividends portfolio" -c resources -l 8',
            'qmd query "Betashares Stake brokerage dividends trading" -c inbox -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-brokerage-activity-manager/scripts/validate_brokerage_activity.py --glob "20 Resources/Investments/Brokerage Activity/**/*.md"',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-brokerage-activity-manager/scripts/validate_brokerage_assets.py --glob "20 Resources/Investments/Brokerage Assets/*.md"',
            'uvx --from python --with polars --with pydantic --with pyyaml python .skills/obsidian-brokerage-activity-manager/scripts/sync_brokerage_activity.py --input "<brokerage-export>.csv" --provider auto --mode check',
        ],
    ),
    RouteSpec(
        route_id="notebooklm_base",
        keywords=[
            "notebooklm base",
            "notebook lm base",
            "notebooklm frontmatter",
            "notebook lm frontmatter",
            "notebooklm metadata",
            "notebook lm metadata",
            "notebooklm notebooks base",
            "notebooklm notebooks",
            "notebooks.base",
            "notebook list",
            "ai notebook",
            "notebooklm",
        ],
        selected_skill="obsidian-notebooklm-bases-manager",
        required_commands=[
            'obsidian read path="00 Inbox/NotebookLM map.md"',
            'obsidian read path="10 Notes/NotebookLM Notebooks.base"',
            'qmd query "NotebookLM" -c inbox -l 8',
            'qmd query "NotebookLM skill lane MOC" -c notes -l 5',
            'uvx --from python --with pydantic --with pyyaml --with jsonschema python .skills/obsidian-notebooklm-bases-manager/scripts/validate_notebooklm_frontmatter.py --path "<note>.md"',
        ],
    ),
    RouteSpec(
        route_id="pit_snapshot",
        keywords=["pit", "point-in-time", "point in time", "pit_status", "snapshot"],
        selected_skill="obsidian-interweave-engine",
        required_commands=[
            'obsidian read path="<note>.md"',
            'obsidian links path="<note>.md" total',
            'qmd query "related concepts <topic>" -c notes -l 8',
            'qmd query "<topic>" -c clippings -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-interweave-engine/scripts/link_audit.py --path "<note>.md"',
        ],
    ),
    # zettel_management evaluated before weekly_feedback — prevents broad "synthesis"
    # and "hub synthesis" from being stolen by weekly_feedback's generic triggers.
    RouteSpec(
        route_id="zettel_management",
        keywords=[
            "zettel",
            "zettel_kind",
            "zettel_id",
            "zettel schema",
            "connection_strength",
            "connection strength",
            "score zettels",
            "migrate zettels",
            "fleeting capture",
            "promote note",
            "evergreen note",
            "litnote",
            "atomic note",
            "hub synthesis",
            "rough idea note",
            "permanent note",
            "how should i file",
            "file it in my note",
            "zettel frontmatter",
            "properly structured",
            # domain hub navigation
            "domain hub",
            "_hub",
            "hub note",
            "which domain",
            "browse domains",
            "vault structure",
            "domain hubs",
            "navigate domain",
        ],
        selected_skill="obsidian-zettel-manager",
        required_commands=[
            'obsidian read path="10 Notes/Domain Hubs for Vault Retrieval.md"',
            'obsidian backlinks path="<note>.md" counts total',
            'qmd query "zettel kind status connection_strength" -c notes -l 8',
            'qmd query "<topic>" -c inbox -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-zettel-manager/scripts/validate_zettels.py --path "<note>.md"',
        ],
    ),
    RouteSpec(
        route_id="cv_entry_management",
        keywords=[
            "cv entry",
            "cv_entry_kind",
            "cv entry kind",
            "cv entries base",
            "cv entries.base",
            "career entry",
            "role note",
            "cv schema",
            "curriculum vitae",
            "resume",
            "cv master",
            "extract cv",
            "export cv",
            "career timeline",
            "pillar alignment",
            "quantification gap",
            "achievement bullet",
            "role history",
            "work history",
            "employment history",
        ],
        selected_skill="obsidian-cv-entry-manager",
        required_commands=[
            'obsidian read path="20 Resources/Career/CV Entries.base"',
            'qmd query "cv entry career role pillar achievement" -c resources -l 8',
            'qmd query "cv master career pathway job search" -c projects -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-cv-entry-manager/scripts/validate_cv.py --glob "20 Resources/Career/**/*.md" --mode check',
        ],
    ),
    RouteSpec(
        route_id="weekly_feedback",
        keywords=[
            "weekly",
            "weekly review",
            "control plane",
            "w10",
            "periodic note",
            "periodic review",
            "weekly note",
            "what i accomplished",
            "accomplished last week",
            "still open",
            "thread alignment",
            "open closure signal",
            "closure signal",
        ],
        selected_skill="obsidian-weekly-feedback-loop",
        required_commands=[
            'obsidian read path="Periodic/<year>/<week>.md"',
            'obsidian search:context query="priority thread" limit=20 format=json',
            'qmd query "weekly closure signals blockers maneuvers" -c periodic -l 8',
            'qmd query "active thread maneuver" -c inbox -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-weekly-feedback-loop/scripts/weekly_ops.py --week YYYY-Www --mode check',
        ],
    ),
    RouteSpec(
        route_id="excalidraw_visual_validation",
        keywords=[
            "excalidraw render",
            "excalidraw png",
            "excalidraw visual",
            "excalidraw layout",
            "excalidraw overlap",
            "excalidraw spacing",
            "render excalidraw",
            "visual validation",
            "diagram render",
            "excalidraw screenshot",
            "excalidraw quality",
            "excalidraw composition",
            "excalidraw balance",
            "render diagram",
            "diagram quality",
        ],
        selected_skill="obsidian-excalidraw-visual-validator",
        required_commands=[
            'qmd query "excalidraw drawing diagram" -c notes -l 8',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py --glob "**/*.excalidraw.md" --mode report',
            'uvx --from python --with pydantic --with pyyaml --with playwright python .skills/obsidian-excalidraw-visual-validator/scripts/validate_visual.py --glob "**/*.excalidraw.md" --mode check --render',
        ],
    ),
    RouteSpec(
        route_id="excalidraw_drawing_management",
        keywords=[
            "excalidraw",
            "excalidraw.md",
            "excalidraw plugin",
            "excalidraw schema",
            "excalidraw data",
            "excalidraw element",
            "excalidraw drawing",
            "drawing validation",
            "drawing binding",
            "canvas drawing",
        ],
        selected_skill="obsidian-excalidraw-drawing-manager",
        required_commands=[
            'qmd query "excalidraw drawing diagram" -c notes -l 8',
            'qmd query "excalidraw" -c inbox -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-excalidraw-drawing-manager/scripts/validate_excalidraw.py --glob "**/*.excalidraw.md" --mode check',
        ],
    ),
    RouteSpec(
        route_id="interweave",
        keywords=[
            "interweave",
            "wikilink",
            "weave this",
            "weave into",
            "connect my",
            "connect my reading",
            "enrich",
            "clipping",
            "link this",
            "frontmatter",
        ],
        selected_skill="obsidian-interweave-engine",
        required_commands=[
            'obsidian read path="<note>.md"',
            'obsidian links path="<note>.md" total',
            'qmd query "related concepts <topic>" -c notes -l 8',
            'qmd query "<topic>" -c clippings -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-interweave-engine/scripts/link_audit.py --path "<note>.md"',
        ],
    ),
    RouteSpec(
        route_id="memory_capture",
        keywords=[
            "memory",
            "friction",
            "routing mistake",
            "same mistake",
            "document it as a lesson",
            "lesson learned",
            "capture as a lesson",
            "agent insight",
            "durable note",
            "key insight",
            "debugging session",
            "persist it",
            "capture this",
        ],
        selected_skill="obsidian-agent-memory-capture",
        required_commands=[
            'obsidian read path="<candidate>.md"',
            'obsidian backlinks path="<candidate>.md" counts total',
            'qmd query "zettel <topic> concept pattern" -c notes -l 8',
            'qmd query "<topic>" -c inbox -l 5',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-agent-memory-capture/scripts/memory_capture_audit.py --path "<candidate>.md"',
        ],
    ),
    RouteSpec(
        route_id="token_guard",
        keywords=["token", "budget", "context", "window", "compaction"],
        selected_skill="obsidian-token-budget-guard",
        required_commands=[
            'obsidian search:context query="<topic>" limit=20 format=json',
            'qmd query "<topic>" -c all -l 12',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-token-budget-guard/scripts/token_guard.py --candidate-files "<csv>" --max-files 5 --max-chars 22000 --max-snippets 12',
        ],
    ),
]


def dump_payload(payload: RouteOutput) -> None:
    print(json.dumps(payload.model_dump(mode="json", exclude_none=True), indent=2))


def dependency_error(missing: List[str]) -> int:
    payload = RouteOutput(
        ok=False,
        selected_skill=None,
        required_commands=[],
        read_budget=DEFAULT_BUDGET,
        dependency_status=DependencyStatus.MISSING,
        error="missing_dependencies",
        missing=missing,
        fallback_checklist=[
            "Install Obsidian CLI and ensure Obsidian desktop is up to date.",
            "Install qmd: npm install -g @tobilu/qmd",
            "Verify: obsidian --help && qmd status && uvx --version",
            "Retry the command after dependencies are available.",
        ],
    )
    dump_payload(payload)
    return 2


def first_matching_route(intent: str, routes: Iterable[RouteSpec]) -> RouteSpec | None:
    lower = intent.lower()
    for route in routes:
        if any(keyword in lower for keyword in route.keywords):
            return route
    return None


def classify_intent(intent: str) -> RouteOutput:
    route = first_matching_route(intent, ROUTES)
    if route is not None:
        return RouteOutput(
            ok=True,
            selected_route=route.route_id,
            selected_skill=route.selected_skill,
            required_commands=route.required_commands,
            read_budget=DEFAULT_BUDGET,
            dependency_status=DependencyStatus.OK,
        )

    return RouteOutput(
        ok=True,
        selected_route="token_guard",
        selected_skill="obsidian-token-budget-guard",
        required_commands=[
            'obsidian search query="<topic>" limit=20 total',
            'qmd query "<topic>" -c all -l 8',
            'uvx --from python --with pydantic --with pyyaml python .skills/obsidian-token-budget-guard/scripts/token_guard.py --candidate-files "<csv>" --max-files 5 --max-chars 22000 --max-snippets 12',
        ],
        read_budget=DEFAULT_BUDGET,
        dependency_status=DependencyStatus.OK,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Route vault tasks to a minimum-context downstream skill.")
    parser.add_argument("--intent", required=True, help="User intent to classify")
    parser.add_argument("--mode", choices=["plan", "execute"], default="plan")
    args = parser.parse_args()

    missing = [cmd for cmd in ["obsidian", "qmd", "uvx"] if shutil.which(cmd) is None]
    if missing:
        return dependency_error(missing)

    result = classify_intent(args.intent)
    result.mode = args.mode
    dump_payload(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
