#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import yaml


def base_document() -> Dict[str, Any]:
    return {
        "$schema": "vault://schemas/obsidian/bases-2025-09.schema.json",
        "filters": {
            "and": [
                'file.ext == "md"',
                {
                    "or": [
                        'notebooklm_note_kind == "map"',
                        'notebooklm_note_kind == "index"',
                        'notebooklm_note_kind == "notebook"',
                    ]
                },
            ]
        },
        "formulas": {
            "record_title": 'if(notebooklm_title, notebooklm_title, file.basename)',
            "updated_relative": "file.mtime.relative()",
            "potential_link_count": "if(potential_links, potential_links.length, 0)",
            "review_in_days": 'if(notebooklm_review_due, (date(notebooklm_review_due) - today()).days.round(0), "")',
            "weaving_state": 'if(connection_strength >= 0.85, "woven", if(connection_strength >= 0.65, "growing", "needs-work"))',
        },
        "properties": {
            "formula.record_title": {"displayName": "Record"},
            "notebooklm_note_kind": {"displayName": "Kind"},
            "notebooklm_title": {"displayName": "Notebook"},
            "notebooklm_lane": {"displayName": "Lane"},
            "connection_strength": {"displayName": "Connection"},
            "notebooklm_professional_track": {"displayName": "Professional"},
            "notebooklm_life_track": {"displayName": "Life Wisdom"},
            "notebooklm_review_due": {"displayName": "Review Due"},
            "notebooklm_source_note": {"displayName": "Source"},
            "notebooklm_url": {"displayName": "NotebookLM URL"},
            "formula.updated_relative": {"displayName": "Updated"},
            "formula.potential_link_count": {"displayName": "Potential Links"},
            "formula.review_in_days": {"displayName": "Days to Review"},
            "formula.weaving_state": {"displayName": "Weaving"},
        },
        "views": [
            {
                "type": "table",
                "name": "NotebookLM Control",
                "filters": {"and": ['notebooklm_note_kind != "notebook"']},
                "order": [
                    "formula.record_title",
                    "notebooklm_note_kind",
                    "notebooklm_lane",
                    "connection_strength",
                    "formula.weaving_state",
                    "formula.potential_link_count",
                    "formula.updated_relative",
                    "file.path",
                ],
            },
            {
                "type": "table",
                "name": "Notebook Library",
                "filters": {"and": ['notebooklm_note_kind == "notebook"']},
                "groupBy": {"property": "notebooklm_lane", "direction": "ASC"},
                "order": [
                    "formula.record_title",
                    "notebooklm_lane",
                    "connection_strength",
                    "formula.weaving_state",
                    "formula.potential_link_count",
                    "notebooklm_professional_track",
                    "notebooklm_life_track",
                    "notebooklm_review_due",
                    "formula.updated_relative",
                    "notebooklm_source_note",
                    "notebooklm_url",
                    "file.path",
                ],
            },
            {
                "type": "table",
                "name": "Professional Transformation",
                "filters": {
                    "and": [
                        'notebooklm_note_kind == "notebook"',
                        'notebooklm_professional_track == true',
                    ]
                },
                "order": [
                    "formula.record_title",
                    "notebooklm_lane",
                    "connection_strength",
                    "formula.weaving_state",
                    "notebooklm_review_due",
                    "formula.review_in_days",
                    "notebooklm_url",
                ],
            },
            {
                "type": "table",
                "name": "Life Wisdom",
                "filters": {
                    "and": [
                        'notebooklm_note_kind == "notebook"',
                        'notebooklm_life_track == true',
                    ]
                },
                "order": [
                    "formula.record_title",
                    "notebooklm_lane",
                    "connection_strength",
                    "formula.weaving_state",
                    "notebooklm_review_due",
                    "formula.review_in_days",
                    "notebooklm_url",
                ],
            },
            {
                "type": "table",
                "name": "Review Queue",
                "filters": {
                    "and": [
                        'notebooklm_note_kind == "notebook"',
                        'notebooklm_review_due != ""',
                    ]
                },
                "order": [
                    "formula.record_title",
                    "notebooklm_lane",
                    "notebooklm_review_due",
                    "formula.review_in_days",
                    "connection_strength",
                    "formula.potential_link_count",
                    "formula.updated_relative",
                ],
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a canonical Obsidian Base scaffold for NotebookLM notebook notes.",
    )
    parser.add_argument(
        "--output",
        default="10 Notes/NotebookLM Notebooks.base",
        help="Output path for the .base file.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(
        base_document(),
        sort_keys=False,
        allow_unicode=False,
    )
    output_path.write_text(rendered, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
