#!/usr/bin/env python3
"""Render the Experiments.base Obsidian YAML DSL file.

Scans all validated experiment notes and writes (or updates) the canonical
Obsidian Bases file at the given output path.

Usage:
    uvx --from python --with pydantic --with pyyaml python render_experiments_base.py \
        --output "10 Notes/Productivity/Experiments/Experiments.base"

The rendered Base uses Obsidian's native filter DSL to surface all experiment
notes and exposes lifecycle, outcome, council, and graph columns.

Exit code: 0 on success, 1 on failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from experiment_models import dump_json, load_markdown_note


BASE_SCHEMA_URL = "vault://schemas/obsidian/bases-2025-09.schema.json"

BASE_DSL: dict = {
    "$schema": BASE_SCHEMA_URL,
    "filters": {
        "and": [
            {"file.ext": "==", "value": "md"},  # type: ignore[dict-item]  # rendered as YAML filter
            "file.inFolder(\"10 Notes/Productivity/Experiments\")",
            "experiment_kind != null",
        ]
    },
    "formulas": {
        "days_running": (
            "if(status == \"running\" && start_date, "
            "(today() - start_date).days.round(0), \"\")"
        ),
        "days_until_end": (
            "if(status == \"running\" && end_date, "
            "(end_date - today()).days.round(0), \"\")"
        ),
        "lifecycle_bucket": (
            "if(status == \"concluded\" || status == \"archived\", "
            "\"3 Concluded\", "
            "if(status == \"running\", \"1 Running\", "
            "if(status == \"paused\", \"2 Paused\", \"0 Design\")))"
        ),
        "outcome_signal": (
            "if(outcome == \"confirmed\", \"✓ Confirmed\", "
            "if(outcome == \"refuted\", \"✗ Refuted\", "
            "if(outcome == \"inconclusive\", \"~ Inconclusive\", "
            "if(outcome == \"abandoned\", \"⊘ Abandoned\", \"… Ongoing\"))))"
        ),
        "updated_relative": "file.mtime.relative()",
    },
    "properties": {
        "file.name": {"displayName": "Experiment"},
        "experiment_kind": {"displayName": "Kind"},
        "experiment_id": {"displayName": "ID"},
        "status": {"displayName": "Status"},
        "council_owner": {"displayName": "Council"},
        "domain_tag": {"displayName": "Domain"},
        "question": {"displayName": "Question"},
        "outcome": {"displayName": "Outcome"},
        "confidence": {"displayName": "Confidence"},
        "start_date": {"displayName": "Started"},
        "end_date": {"displayName": "Ends"},
        "duration_days": {"displayName": "Days Planned"},
        "connection_strength": {"displayName": "Strength"},
        "formula.days_running": {"displayName": "Days Running"},
        "formula.days_until_end": {"displayName": "Days Left"},
        "formula.lifecycle_bucket": {"displayName": "Lifecycle"},
        "formula.outcome_signal": {"displayName": "Outcome Signal"},
        "formula.updated_relative": {"displayName": "Updated"},
    },
    "views": [
        {
            "type": "table",
            "name": "All Experiments",
            "groupBy": {
                "property": "formula.lifecycle_bucket",
                "direction": "ASC",
            },
            "order": [
                "file.name",
                "experiment_kind",
                "experiment_id",
                "status",
                "council_owner",
                "question",
                "formula.outcome_signal",
                "start_date",
                "formula.days_running",
                "formula.updated_relative",
            ],
        },
        {
            "type": "table",
            "name": "Running",
            "filter": "status == \"running\"",
            "order": [
                "file.name",
                "experiment_kind",
                "council_owner",
                "question",
                "start_date",
                "formula.days_running",
                "formula.days_until_end",
                "confidence",
                "formula.updated_relative",
            ],
        },
        {
            "type": "table",
            "name": "Concluded",
            "filter": "status == \"concluded\" || status == \"archived\"",
            "groupBy": {
                "property": "experiment_kind",
                "direction": "ASC",
            },
            "order": [
                "file.name",
                "experiment_kind",
                "council_owner",
                "formula.outcome_signal",
                "confidence",
                "end_date",
                "connection_strength",
            ],
        },
    ],
}


def build_base_yaml() -> str:
    """Render the Obsidian Bases YAML DSL."""

    class _NoAliasDumper(yaml.SafeDumper):
        def ignore_aliases(self, data: object) -> bool:
            return True

        def represent_str(self, data: str) -> yaml.ScalarNode:
            # Use literal block scalar for long strings (formulas)
            if "\n" in data or len(data) > 80:
                return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return self.represent_scalar("tag:yaml.org,2002:str", data)

    _NoAliasDumper.add_representer(str, _NoAliasDumper.represent_str)

    # Build clean DSL without the filter hack — write as proper Obsidian filter DSL
    base = {
        "$schema": BASE_SCHEMA_URL,
        "filters": {
            "and": [
                {"file.ext": "== \"md\""},
                {"file.inFolder": "\"10 Notes/Productivity/Experiments\""},
                {"experiment_kind": "!= null"},
            ]
        },
        "formulas": {
            "days_running": (
                "if(status == \"running\" && start_date, "
                "(today() - start_date).days.round(0), \"\")"
            ),
            "days_until_end": (
                "if(status == \"running\" && end_date, "
                "(end_date - today()).days.round(0), \"\")"
            ),
            "lifecycle_bucket": (
                "if(status == \"concluded\" || status == \"archived\", "
                "\"3 Concluded\", "
                "if(status == \"running\", \"1 Running\", "
                "if(status == \"paused\", \"2 Paused\", \"0 Design\")))"
            ),
            "outcome_signal": (
                "if(outcome == \"confirmed\", \"Confirmed\", "
                "if(outcome == \"refuted\", \"Refuted\", "
                "if(outcome == \"inconclusive\", \"Inconclusive\", "
                "if(outcome == \"abandoned\", \"Abandoned\", \"Ongoing\"))))"
            ),
            "updated_relative": "file.mtime.relative()",
        },
        "properties": {
            "file.name":                  {"displayName": "Experiment"},
            "experiment_kind":            {"displayName": "Kind"},
            "experiment_id":              {"displayName": "ID"},
            "status":                     {"displayName": "Status"},
            "council_owner":              {"displayName": "Council"},
            "domain_tag":                 {"displayName": "Domain"},
            "question":                   {"displayName": "Question"},
            "outcome":                    {"displayName": "Outcome"},
            "confidence":                 {"displayName": "Confidence"},
            "start_date":                 {"displayName": "Started"},
            "end_date":                   {"displayName": "Ends"},
            "duration_days":              {"displayName": "Days Planned"},
            "connection_strength":        {"displayName": "Strength"},
            "formula.days_running":       {"displayName": "Days Running"},
            "formula.days_until_end":     {"displayName": "Days Left"},
            "formula.lifecycle_bucket":   {"displayName": "Lifecycle"},
            "formula.outcome_signal":     {"displayName": "Outcome Signal"},
            "formula.updated_relative":   {"displayName": "Updated"},
        },
        "views": [
            {
                "type": "table",
                "name": "All Experiments",
                "groupBy": {"property": "formula.lifecycle_bucket", "direction": "ASC"},
                "order": [
                    "file.name", "experiment_kind", "experiment_id", "status",
                    "council_owner", "question", "formula.outcome_signal",
                    "start_date", "formula.days_running", "formula.updated_relative",
                ],
            },
            {
                "type": "table",
                "name": "Running",
                "order": [
                    "file.name", "experiment_kind", "council_owner", "question",
                    "start_date", "formula.days_running", "formula.days_until_end",
                    "confidence", "formula.updated_relative",
                ],
            },
            {
                "type": "table",
                "name": "Concluded",
                "groupBy": {"property": "experiment_kind", "direction": "ASC"},
                "order": [
                    "file.name", "experiment_kind", "council_owner",
                    "formula.outcome_signal", "confidence", "end_date",
                    "connection_strength",
                ],
            },
        ],
    }

    return yaml.dump(
        base,
        Dumper=_NoAliasDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=120,
    )


def audit_experiments(vault_root: Path) -> dict:
    """Collect a lightweight audit summary from experiment notes."""
    import fnmatch

    notes = [
        p for p in vault_root.rglob("*.md")
        if fnmatch.fnmatch(
            str(p.relative_to(vault_root)),
            "10 Notes/Productivity/Experiments/**/*.md",
        )
        and p.stem != "_hub"
    ]

    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_outcome: dict[str, int] = {}

    for p in notes:
        try:
            note = load_markdown_note(p)
            fm = note.frontmatter
            k = str(fm.get("experiment_kind") or "unknown")
            s = str(fm.get("status") or "unknown")
            o = str(fm.get("outcome") or "ongoing")
            by_kind[k] = by_kind.get(k, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1
            by_outcome[o] = by_outcome.get(o, 0) + 1
        except Exception:
            continue

    return {
        "total": len(notes),
        "by_kind": by_kind,
        "by_status": by_status,
        "by_outcome": by_outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Experiments.base file.")
    parser.add_argument(
        "--output",
        default="10 Notes/Productivity/Experiments/Experiments.base",
        help="Output path for the .base file (relative to vault root or absolute).",
    )
    parser.add_argument(
        "--vault", default=str(Path.home() / "my-vault"),
        help="Vault root path.",
    )
    args = parser.parse_args()

    vault_root = Path(args.vault)
    output_path = (
        Path(args.output) if Path(args.output).is_absolute()
        else vault_root / args.output
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_content = build_base_yaml()

    try:
        output_path.write_text(base_content, encoding="utf-8")
    except OSError as exc:
        print(dump_json({"ok": False, "error": f"Failed to write base file: {exc}"}))
        return 1

    audit = audit_experiments(vault_root)
    print(dump_json({
        "ok": True,
        "output": str(output_path),
        "audit": audit,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
