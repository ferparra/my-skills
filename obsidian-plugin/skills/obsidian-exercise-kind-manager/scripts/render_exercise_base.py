#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

import yaml

from exercise_models import EXERCISE_BASE_PATH, dump_json


BASE_CONFIG = {
    "filters": {
        "and": [
            'file.ext == "md"',
            'file.inFolder("20 Resources/Exercises")',
            'exercise_kind != ""',
        ]
    },
    "formulas": {
        "primary_label": 'if(primary_muscle, primary_muscle.toString().replace("[[", "").replace("]]", ""), "")',
        "secondary_label": 'if(secondary_muscles, secondary_muscles.map(value.toString().replace("[[", "").replace("]]", "")).join(", "), "")',
        "gear": 'if(equipment, equipment.map(value.toString().replace("[[", "").replace("]]", "")).join(", "), "")',
        "bias": 'if(force_profile == "lengthened", "Lengthened", if(force_profile == "shortened", "Shortened", if(force_profile == "mid-range", "Mid", "")))',
        "volume_mode": 'if(volume_tracking == "primary_only", "Primary 1.0 / Secondary 0.0", if(volume_tracking == "secondary_half", "Primary 1.0 / Secondary 0.5", "Not counted"))',
        "selection_score": 'if(exercise_kind == "hypertrophy", if(force_profile == "lengthened", 2, if(force_profile == "mid-range", 1, 0)) + if(stability_profile == "high", 2, if(stability_profile == "medium", 1, 0)) + if(fatigue_cost == "low", 2, if(fatigue_cost == "moderate", 1, 0)) + if(volume_tracking == "primary_only", 1, if(volume_tracking == "secondary_half", 0.5, 0)), "")',
        "top_set_display": 'if(top_set_load && top_set_reps, top_set_load.toFixed(1) + " " + top_set_unit + " x " + top_set_reps.toFixed(1), if(top_set_reps, if(top_set_unit == "bodyweight", "BW x " + top_set_reps.toFixed(1), top_set_reps.toFixed(1) + " reps"), ""))',
        "working_avg_display": 'if(working_avg_load && working_avg_reps, working_avg_load.toFixed(1) + " " + working_avg_unit + " x " + working_avg_reps.toFixed(1), if(working_avg_reps, if(working_avg_unit == "bodyweight", "BW x " + working_avg_reps.toFixed(1), working_avg_reps.toFixed(1) + " reps"), ""))',
        "strong_names": 'if(strong_exercise_names, strong_exercise_names.join(", "), "")',
        "sync_state": 'if(training_log_source == "strong_csv", if(strong_last_synced_at, "synced", "pending"), "manual")',
        "weekly_set_status": 'if(exercise_kind == "hypertrophy", if(avg_weekly_primary_sets_6w < 12, "Below target", if(avg_weekly_primary_sets_6w <= 16, "In range", "Above target")), "n/a")',
        "trend_badge": 'if(progression_trend == "improving", "Up", if(progression_trend == "regressing", "Down", if(progression_trend == "stable", "Flat", "Insufficient")))',
        "analysis_status": 'if(training_log_source == "strong_csv", if(progression_trend && recommendation_signal, "ready", "partial"), if(logged_sessions && top_set_reps, "manual", "partial"))',
    },
    "properties": {
        "file.name": {"displayName": "Exercise"},
        "exercise_kind": {"displayName": "Kind"},
        "category": {"displayName": "Category"},
        "region": {"displayName": "Region"},
        "pattern": {"displayName": "Pattern"},
        "primary_muscle": {"displayName": "Primary"},
        "secondary_muscles": {"displayName": "Secondary"},
        "force_profile": {"displayName": "Force"},
        "stability_profile": {"displayName": "Stability"},
        "fatigue_cost": {"displayName": "Fatigue"},
        "volume_tracking": {"displayName": "Volume Mode"},
        "volume_primary_credit": {"displayName": "Primary Credit"},
        "volume_secondary_credit": {"displayName": "Secondary Credit"},
        "training_log_source": {"displayName": "Log Source"},
        "strong_weight_unit": {"displayName": "Strong Unit"},
        "strong_last_synced_at": {"displayName": "Last Synced"},
        "strong_session_count": {"displayName": "Strong Sessions"},
        "strong_work_set_count": {"displayName": "Strong Sets"},
        "logged_sessions": {"displayName": "Sessions"},
        "avg_weekly_primary_sets_6w": {"displayName": "Primary Sets 6w"},
        "avg_weekly_secondary_sets_6w": {"displayName": "Secondary Sets 6w"},
        "progression_trend": {"displayName": "Trend"},
        "progression_delta_pct": {"displayName": "Trend Delta %"},
        "recommendation_signal": {"displayName": "Recommendation"},
        "top_set_load": {"displayName": "Top Load"},
        "top_set_reps": {"displayName": "Top Reps"},
        "top_set_volume": {"displayName": "Top Volume"},
        "working_avg_load": {"displayName": "Avg Load"},
        "working_avg_reps": {"displayName": "Avg Reps"},
        "last_performed": {"displayName": "Last Performed"},
        "formula.primary_label": {"displayName": "Primary"},
        "formula.secondary_label": {"displayName": "Secondary"},
        "formula.gear": {"displayName": "Equipment"},
        "formula.bias": {"displayName": "Bias"},
        "formula.volume_mode": {"displayName": "Volume Model"},
        "formula.selection_score": {"displayName": "Selection Score"},
        "formula.top_set_display": {"displayName": "Top Set"},
        "formula.working_avg_display": {"displayName": "Working Avg"},
        "formula.strong_names": {"displayName": "Strong Names"},
        "formula.sync_state": {"displayName": "Sync State"},
        "formula.weekly_set_status": {"displayName": "Volume Status"},
        "formula.trend_badge": {"displayName": "Trend Badge"},
        "formula.analysis_status": {"displayName": "Analysis"},
    },
    "views": [
        {
            "type": "table",
            "name": "Selection Board",
            "filters": {"and": ['exercise_kind == "hypertrophy"']},
            "groupBy": {"property": "primary_muscle", "direction": "ASC"},
            "order": [
                "file.name",
                "primary_muscle",
                "force_profile",
                "stability_profile",
                "fatigue_cost",
                "formula.selection_score",
                "formula.volume_mode",
                "formula.gear",
                "recommendation_signal",
                "last_performed",
            ],
            "summaries": {"formula.selection_score": "Average"},
        },
        {
            "type": "table",
            "name": "Strong Sync",
            "filters": {"and": ['training_log_source == "strong_csv"']},
            "groupBy": {"property": "exercise_kind", "direction": "ASC"},
            "order": [
                "file.name",
                "training_log_source",
                "formula.strong_names",
                "strong_last_synced_at",
                "strong_session_count",
                "strong_work_set_count",
                "progression_trend",
                "recommendation_signal",
            ],
            "summaries": {
                "strong_session_count": "Sum",
                "strong_work_set_count": "Sum",
            },
        },
        {
            "type": "table",
            "name": "Progression Trends",
            "filters": {
                "and": [
                    'exercise_kind == "hypertrophy"',
                    'training_log_source == "strong_csv"',
                ]
            },
            "groupBy": {"property": "primary_muscle", "direction": "ASC"},
            "order": [
                "file.name",
                "formula.top_set_display",
                "formula.working_avg_display",
                "progression_trend",
                "progression_delta_pct",
                "formula.trend_badge",
                "avg_weekly_primary_sets_6w",
                "recommendation_signal",
                "last_performed",
            ],
            "summaries": {
                "progression_delta_pct": "Average",
                "avg_weekly_primary_sets_6w": "Average",
            },
        },
        {
            "type": "table",
            "name": "Weekly Volume",
            "filters": {
                "and": [
                    'exercise_kind == "hypertrophy"',
                    'training_log_source == "strong_csv"',
                ]
            },
            "groupBy": {"property": "primary_muscle", "direction": "ASC"},
            "order": [
                "file.name",
                "avg_weekly_primary_sets_6w",
                "avg_weekly_secondary_sets_6w",
                "formula.weekly_set_status",
                "strong_work_set_count",
                "last_performed",
            ],
            "summaries": {
                "avg_weekly_primary_sets_6w": "Average",
                "avg_weekly_secondary_sets_6w": "Average",
                "strong_work_set_count": "Sum",
            },
        },
        {
            "type": "table",
            "name": "Recommendation Queue",
            "filters": {
                "and": [
                    'exercise_kind == "hypertrophy"',
                    'training_log_source == "strong_csv"',
                    {
                        "or": [
                            'recommendation_signal == "add_volume"',
                            'recommendation_signal == "review_exercise_choice"',
                            'recommendation_signal == "consider_better_variant"',
                        ]
                    },
                ],
            },
            "order": [
                "file.name",
                "recommendation_signal",
                "progression_trend",
                "progression_delta_pct",
                "avg_weekly_primary_sets_6w",
                "formula.selection_score",
                "fatigue_cost",
                "stability_profile",
                "force_profile",
            ],
            "summaries": {
                "avg_weekly_primary_sets_6w": "Average",
                "formula.selection_score": "Average",
            },
        },
        {
            "type": "table",
            "name": "Mobility and Warm-up",
            "filters": {
                "or": [
                    'exercise_kind == "mobility_drill"',
                    'exercise_kind == "warmup_flow"',
                    'exercise_kind == "exercise_brief"',
                ]
            },
            "order": [
                "file.name",
                "exercise_kind",
                "region",
                "pattern",
                "duration",
                "formula.gear",
                "programme",
                "training_log_source",
            ],
        },
        {
            "type": "table",
            "name": "Full Library",
            "groupBy": {"property": "exercise_kind", "direction": "ASC"},
            "order": [
                "file.name",
                "exercise_kind",
                "category",
                "region",
                "pattern",
                "primary_muscle",
                "formula.secondary_label",
                "formula.gear",
                "training_log_source",
                "last_performed",
            ],
        },
    ],
}


def dump_yaml(payload: dict[str, object]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=4096)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the canonical Obsidian Base for exercise notes.")
    parser.add_argument("--output", default=EXERCISE_BASE_PATH, help="Path to the Exercise Library.base file.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    output_path = (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dump_yaml(BASE_CONFIG), encoding="utf-8")
    views = cast(list[dict[str, object]], BASE_CONFIG["views"])
    formulas = cast(list[object], BASE_CONFIG["formulas"])

    print(
        dump_json(
            {
                "ok": True,
                "output_path": str(output_path.relative_to(root) if output_path.is_relative_to(root) else output_path),
                "views": [str(view["name"]) for view in views],
                "formula_count": len(formulas),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
