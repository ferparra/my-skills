#!/usr/bin/env python3
"""Generate CV Entries.base for Obsidian Bases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cv_models import CV_BASE_PATH


def build_base_config() -> dict[str, object]:
    return {
        "filters": {
            "and": [
                'file.ext == "md"',
                'file.inFolder("20 Resources/Career")',
                'cv_entry_kind != ""',
            ]
        },
        "formulas": {
            "kind_label": 'cv_entry_kind.replace("_", " ").title()',
            "date_range": 'if(start_date, start_date + " – " + if(end_date, end_date, "present"), if(start_year, start_year + "–" + if(end_year, end_year, ""), ""))',
            "pillar_list": 'if(pillars, pillars.join(", "), "")',
            "bullet_count": 'if(bullets, bullets.length, 0)',
            "unquantified_count": 'if(bullets, bullets.filter(b => !b.quantified).length, 0)',
            "recency_badge": 'if(recency_weight == "high", "★★★", if(recency_weight == "medium", "★★", "★"))',
            "title_display": 'if(cv_entry_kind == "role", company_name + " — " + role_title, if(cv_entry_kind == "education", institution + " — " + qualification, if(cv_entry_kind == "certification", certification_name, if(cv_entry_kind == "award", award_name, if(cv_entry_kind == "community", activity_name, file.name)))))',
        },
        "properties": {
            "cv_entry_kind": {"displayName": "Kind"},
            "status": {"displayName": "Status"},
            "company_name": {"displayName": "Company"},
            "role_title": {"displayName": "Title"},
            "start_date": {"displayName": "Start"},
            "end_date": {"displayName": "End"},
            "location": {"displayName": "Location"},
            "industry": {"displayName": "Industry"},
            "recency_weight": {"displayName": "Recency"},
            "pillars": {"displayName": "Pillars"},
            "institution": {"displayName": "Institution"},
            "qualification": {"displayName": "Qualification"},
            "certification_name": {"displayName": "Certification"},
            "award_name": {"displayName": "Award"},
            "activity_name": {"displayName": "Activity"},
            "connection_strength": {"displayName": "Strength"},
            "formula.kind_label": {"displayName": "Type"},
            "formula.date_range": {"displayName": "Period"},
            "formula.pillar_list": {"displayName": "Pillars"},
            "formula.bullet_count": {"displayName": "Bullets"},
            "formula.unquantified_count": {"displayName": "Unquantified"},
            "formula.recency_badge": {"displayName": "Recency"},
            "formula.title_display": {"displayName": "Entry"},
        },
        "views": [
            {
                "type": "table",
                "name": "Career Timeline",
                "filter": {"and": ['cv_entry_kind == "role"']},
                "order": [
                    "formula.recency_badge",
                    "company_name",
                    "role_title",
                    "formula.date_range",
                    "location",
                    "formula.pillar_list",
                    "formula.bullet_count",
                    "formula.unquantified_count",
                ],
                "sort": [{"property": "start_date", "direction": "DESC"}],
            },
            {
                "type": "table",
                "name": "By Pillar — P1 Data Product Lens",
                "filter": {"and": ['cv_entry_kind == "role"', 'pillars.includes("P1")']},
                "order": [
                    "company_name",
                    "role_title",
                    "formula.date_range",
                    "formula.bullet_count",
                    "formula.recency_badge",
                ],
                "sort": [{"property": "start_date", "direction": "DESC"}],
            },
            {
                "type": "table",
                "name": "By Pillar — P2 Enabling Teams",
                "filter": {"and": ['cv_entry_kind == "role"', 'pillars.includes("P2")']},
                "order": [
                    "company_name",
                    "role_title",
                    "formula.date_range",
                    "formula.bullet_count",
                    "formula.recency_badge",
                ],
                "sort": [{"property": "start_date", "direction": "DESC"}],
            },
            {
                "type": "table",
                "name": "By Pillar — P3 Lean Experimentation",
                "filter": {"and": ['cv_entry_kind == "role"', 'pillars.includes("P3")']},
                "order": [
                    "company_name",
                    "role_title",
                    "formula.date_range",
                    "formula.bullet_count",
                    "formula.recency_badge",
                ],
                "sort": [{"property": "start_date", "direction": "DESC"}],
            },
            {
                "type": "table",
                "name": "Education and Credentials",
                "filter": {"or": [
                    'cv_entry_kind == "education"',
                    'cv_entry_kind == "certification"',
                    'cv_entry_kind == "award"',
                ]},
                "order": [
                    "formula.kind_label",
                    "formula.title_display",
                    "formula.date_range",
                ],
            },
            {
                "type": "table",
                "name": "Community",
                "filter": {"and": ['cv_entry_kind == "community"']},
                "order": [
                    "activity_name",
                    "duration",
                ],
            },
            {
                "type": "table",
                "name": "Needs Quantification",
                "filter": {"and": [
                    'cv_entry_kind == "role"',
                    "formula.unquantified_count > 0",
                ]},
                "order": [
                    "formula.recency_badge",
                    "company_name",
                    "role_title",
                    "formula.unquantified_count",
                    "formula.bullet_count",
                ],
                "sort": [{"property": "recency_weight", "direction": "DESC"}],
            },
            {
                "type": "table",
                "name": "All Entries",
                "order": [
                    "formula.kind_label",
                    "formula.title_display",
                    "formula.date_range",
                    "formula.pillar_list",
                    "formula.recency_badge",
                    "status",
                ],
                "sort": [{"property": "cv_entry_kind", "direction": "ASC"}],
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CV Entries.base for Obsidian.")
    parser.add_argument(
        "--output",
        default=str(CV_BASE_PATH),
        help="Output path for the .base file.",
    )
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    config = build_base_config()
    content = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    output.write_text(content, encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(output.relative_to(root))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
