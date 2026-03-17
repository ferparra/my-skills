from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = ROOT / ".skills" / "obsidian-planetary-tasks-manager"
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(SCRIPTS))

from migrate_tasks import normalize_task  # noqa: E402
from task_models import ensure_planning_context_section, load_markdown_note  # noqa: E402


def test_action_fixture_normalizes_to_action() -> None:
    note = load_markdown_note(FIXTURES / "pt-action.md")
    normalized = normalize_task(note, ROOT)
    assert normalized["frontmatter"]["task_kind"] == "action"
    assert normalized["frontmatter"]["project"] == "[[Project – Trademe KPI tree]]"
    assert "task-kind/action" in normalized["frontmatter"]["tags"]


def test_external_ticket_fixture_infers_thread_and_context() -> None:
    note = load_markdown_note(FIXTURES / "ag-external-ticket.md")
    normalized = normalize_task(note, FIXTURES)
    assert normalized["frontmatter"]["task_kind"] == "external_ticket"
    assert normalized["frontmatter"]["thread"] == "T3"
    assert normalized["frontmatter"]["source_note"] == "[[00 Inbox/Tasks|Tasks]]"


def test_closure_fixture_classifies_closure_signal() -> None:
    note = load_markdown_note(FIXTURES / "pt-closure-signal.md")
    normalized = normalize_task(note, ROOT)
    assert normalized["frontmatter"]["task_kind"] == "closure_signal"
    assert "task-kind/closure_signal" in normalized["frontmatter"]["tags"]


def test_invalid_fixture_fails_validator() -> None:
    command = [
        "uvx",
        "--from",
        "python",
        "--with",
        "pydantic",
        "--with",
        "pyyaml",
        "python",
        str(SCRIPTS / "validate_tasks.py"),
        "--path",
        str(FIXTURES / "invalid-task.md"),
        "--vault-root",
        str(ROOT),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["results"][0]["ok"] is False


def test_weekly_fixture_supports_thread_inference() -> None:
    note = load_markdown_note(FIXTURES / "ag-external-ticket.md")
    normalized = normalize_task(note, FIXTURES)
    assert normalized["frontmatter"]["horizon_note"] == "[[Periodic/2026/2026-W10|2026-W10]]"


def test_planning_context_section_is_rewritten_canonically() -> None:
    body = """# Task

- [ ] Define migration checklist. [[Project – Trademe KPI tree]] [[2026-W08]]

## Planning Context

- Status: `next`
- Horizon: `day`
- Domain: `work`
- Planning base: [[10 Notes/Planetary Planning.base|Planetary Planning Base]]
- Planning base: [[10 Notes/Planetary Tasks.base|Planetary Tasks Base]]
"""
    lines = [
        "- Task kind: `action`",
        "- Status: `next`",
        "- Horizon: `day`",
        "- Timeframe: `anytime`",
        "- Thread: `T3`",
        "- Domain: `work`",
        "- Project: [[Project – Trademe KPI tree]]",
        "- Source: [[00 Inbox/2026-02-17 tasks in mind|2026-02-17 tasks in mind]]",
        "- Horizon note: [[Periodic/2026/2026-W08|2026-W08]]",
        "- Task hub: [[Periodic/Periodic Planning and Tasks Hub|Periodic Planning and Tasks Hub]]",
        "- Planning base: [[10 Notes/Planetary Planning.base|Planetary Planning Base]]",
        "- Task base: [[10 Notes/Planetary Tasks.base|Planetary Tasks Base]]",
    ]

    rendered = ensure_planning_context_section(body, lines)

    assert rendered.count("Planning base") == 1
    assert rendered.count("Task base") == 1
    assert "- Task kind: `action`" in rendered
    assert rendered.rstrip().endswith("- Task base: [[10 Notes/Planetary Tasks.base|Planetary Tasks Base]]")
