#!/usr/bin/env python3
"""Obsidian Base Renderer — shared engine for all kind-manager skills.

This module provides the BaseRenderer class that renders Obsidian .base YAML
files from typed note collections. It is the canonical rendering engine
used by all obsidian-* kind-manager skills.

Usage:
    uvx --from python --with pydantic --with pyyaml python \
      .skills/obsidian-base-engine/scripts/base_renderer.py \
      --base people --output People.base --vault-root .
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

# ── Constants ─────────────────────────────────────────────────────────────────

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")

BASE_REGISTRY: dict[str, dict[str, Any]] = {
    "brokerage_activity": {
        "kind_field": "brokerage_activity_kind",
        "folder_glob": "20 Resources/Investments/Brokerage Activity/**/*.md",
        "formulas": {
            "symbol_display": 'if(instrument_symbol, instrument_symbol, "CASH")',
            "activity_label": 'brokerage_activity_kind.replace("_", " ").title()',
            "provider_label": 'if(brokerage_provider == "stake_au", "Stake AU", if(brokerage_provider == "stake_us", "Stake US", if(brokerage_provider == "betashares", "Betashares", brokerage_provider.replace("_", " ").title())))',
            "cash_badge": 'if(cash_direction == "inflow", "In", if(cash_direction == "outflow", "Out", "Flat"))',
            "signed_units": 'if(quantity, if(brokerage_activity_kind == "trade_sell", quantity * -1, quantity), "")',
            "merge_badge": 'if(merge_count > 1, "merged", "single")',
            "review_badge": 'if(review_status == "needs_review", "review", "ok")',
            "source_files_label": 'if(source_files, source_files.join(", "), "")',
        },
        "properties": {
            "activity_date": {"displayName": "Date"},
            "activity_month": {"displayName": "Month"},
            "brokerage_activity_kind": {"displayName": "Kind"},
            "brokerage_provider": {"displayName": "Provider"},
            "instrument_symbol": {"displayName": "Symbol"},
            "asset_note": {"displayName": "Asset"},
            "instrument_market": {"displayName": "Market"},
            "instrument_kind": {"displayName": "Instrument"},
            "activity_status": {"displayName": "Status"},
            "net_amount": {"displayName": "Net Amount"},
            "gross_amount": {"displayName": "Gross Amount"},
            "quantity": {"displayName": "Units"},
            "unit_price": {"displayName": "Unit Price"},
            "fee_amount": {"displayName": "Fee"},
            "tax_amount": {"displayName": "Tax"},
            "cash_direction": {"displayName": "Cash Flow"},
            "merge_count": {"displayName": "Merge Count"},
            "review_status": {"displayName": "Review"},
            "source_files": {"displayName": "Source Files"},
            "formula.symbol_display": {"displayName": "Symbol"},
            "formula.activity_label": {"displayName": "Activity"},
            "formula.provider_label": {"displayName": "Provider"},
            "formula.cash_badge": {"displayName": "Flow"},
            "formula.signed_units": {"displayName": "Signed Units"},
            "formula.merge_badge": {"displayName": "Merge"},
            "formula.review_badge": {"displayName": "Review"},
            "formula.source_files_label": {"displayName": "Sources"},
        },
    },
    "exercise": {
        "kind_field": "exercise_kind",
        "folder_glob": "20 Resources/Exercises/**/*.md",
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
    },
    "people": {
        "kind_field": "person_kind",
        "folder_glob": "People/**/*.md",
        "formulas": {
            "kind_label": 'person_kind.replace("_", " ").title()',
            "status_badge": 'if(status == "processed", "✓", if(status == "processing", "⏳", if(status == "dormant", "💤", "○")))',
            "strength_label": 'if(connection_strength >= 0.7, "High", if(connection_strength >= 0.4, "Medium", "Low"))',
            "recency_label": 'if(last_interaction_date, last_interaction_date, "never")',
        },
        "properties": {
            "file.name": {"displayName": "Person"},
            "person_kind": {"displayName": "Kind"},
            "status": {"displayName": "Status"},
            "relationship_to_fernando": {"displayName": "Relationship"},
            "primary_context": {"displayName": "Context"},
            "connection_strength": {"displayName": "Strength"},
            "potential_links": {"displayName": "Potential Links"},
            "last_interaction_date": {"displayName": "Last Contact"},
            "interaction_frequency": {"displayName": "Frequency"},
            "formula.kind_label": {"displayName": "Type"},
            "formula.status_badge": {"displayName": "Status"},
            "formula.strength_label": {"displayName": "Strength"},
            "formula.recency_label": {"displayName": "Recency"},
        },
    },
    "cv_entry": {
        "kind_field": "cv_entry_kind",
        "folder_glob": "20 Resources/Career/**/*.md",
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
    },
}


# ── BaseRenderer class ─────────────────────────────────────────────────────────

class BaseRenderer:
    """Renders Obsidian .base YAML files from typed note collections."""

    def __init__(
        self,
        base_name: str,
        kind_field: str,
        folder_glob: str,
        formulas: dict[str, str] | None = None,
        properties: dict[str, dict[str, str]] | None = None,
        views: list[dict[str, Any]] | None = None,
        custom_formulas: dict[str, str] | None = None,
        custom_properties: dict[str, dict[str, str]] | None = None,
        custom_views: list[dict[str, Any]] | None = None,
    ):
        self.base_name = base_name
        self.kind_field = kind_field
        self.folder_glob = folder_glob
        self.formulas: dict[str, str] = dict(formulas or {})
        self.properties: dict[str, dict[str, str]] = dict(properties or {})
        self.views: list[dict[str, Any]] = list(views or [])

        # Merge custom overrides
        if custom_formulas:
            self.formulas.update(custom_formulas)
        if custom_properties:
            self.properties.update(custom_properties)
        if custom_views:
            self.views.extend(custom_views)

    def build_config(self) -> dict[str, Any]:
        """Build the full .base configuration dictionary."""
        return {
            "filters": {
                "and": [
                    f'file.ext == "md"',
                    f'file.inFolder("{self.folder_glob}")',
                    f'{self.kind_field} != ""',
                ]
            },
            "formulas": self.formulas,
            "properties": self.properties,
            "views": self.views,
        }

    def render(self, output_path: Path | str) -> dict[str, Any]:
        """Render the base to a YAML file."""
        config = self.build_config()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        class NoAliasDumper(yaml.SafeDumper):
            def ignore_aliases(self, data: Any) -> bool:
                return True

        output = yaml.dump(
            config,
            Dumper=NoAliasDumper,
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        )
        path.write_text(output, encoding="utf-8")
        return {"ok": True, "path": str(path), "views": len(self.views)}

    def validate(self) -> list[str]:
        """Validate the base configuration. Returns list of issues."""
        issues = []
        if not self.formulas:
            issues.append("No formulas defined")
        if not self.properties:
            issues.append("No properties defined")
        if not self.views:
            issues.append("No views defined")
        for view in self.views:
            if "name" not in view:
                issues.append(f"View missing 'name': {view}")
            if "type" not in view:
                issues.append(f"View '{view.get('name', '?')}' missing 'type'")
        return issues

    @classmethod
    def from_registry(cls, base_name: str) -> "BaseRenderer":
        """Load a base type from the registry."""
        if base_name not in BASE_REGISTRY:
            raise ValueError(f"Unknown base type: {base_name}. Available: {list(BASE_REGISTRY.keys())}")
        spec = BASE_REGISTRY[base_name]
        return cls(base_name=base_name, **spec)


# ── View composition ───────────────────────────────────────────────────────────

def compose_views(
    collections: list[tuple[str, list[dict[str, Any]]]],
    shared_properties: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compose views from multiple note collections.

    Args:
        collections: List of (name, views) tuples
        shared_properties: Properties available across all collections

    Returns:
        Combined list of views with prefixed names
    """
    combined: list[dict[str, Any]] = []
    for prefix, views in collections:
        for view in views:
            composed = dict(view)
            composed["name"] = f"[{prefix}] {view.get('name', 'Unnamed')}"
            combined.append(composed)
    return combined


def merge_properties(
    *property_dicts: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    """Merge multiple property dictionaries, later ones override."""
    result: dict[str, dict[str, str]] = {}
    for pd in property_dicts:
        result.update(pd)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render an Obsidian .base file using the base engine.",
    )
    parser.add_argument(
        "--base",
        required=True,
        choices=list(BASE_REGISTRY.keys()),
        help="Base type to render.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for the .base file.",
    )
    parser.add_argument(
        "--vault-root",
        default=".",
        help="Vault root directory.",
    )
    parser.add_argument(
        "--format",
        default="yaml",
        choices=["yaml", "json"],
        help="Output format.",
    )
    args = parser.parse_args()

    try:
        renderer = BaseRenderer.from_registry(args.base)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    issues = renderer.validate()
    if issues:
        print(json.dumps({"ok": False, "issues": issues}))
        return 1

    root = Path(args.vault_root).resolve()
    output_path = root / args.output

    result = renderer.render(output_path)
    result["relative_path"] = str(output_path.relative_to(root))

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
