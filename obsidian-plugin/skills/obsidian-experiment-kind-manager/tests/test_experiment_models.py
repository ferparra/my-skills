"""Unit tests for experiment_models.py (Pydantic v2).

Run:
    uvx --from python --with pydantic --with pyyaml python -m pytest tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running from any cwd
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from experiment_models import (
    COUNCIL_DOMAIN_MAP,
    ExperimentFrontmatter,
    ExperimentKind,
    ExperimentOutcome,
    ExperimentStatus,
    normalize_experiment_tags,
    validate_frontmatter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_HEALTH = {
    "experiment_kind": "health",
    "experiment_id": "exp-2026-001",
    "created": "2026-01-01",
    "modified": "2026-04-09T00:00:00Z",
    "status": "running",
    "council_owner": "sentinel",
    "domain_tag": "health-and-performance",
    "question": "What effect does 300mg Magnesium Glycinate have on sleep latency?",
    "hypothesis": "I believe it will reduce sleep latency by 10+ minutes due to its role in GABA modulation.",
    "method": "Take 300mg Magnesium Glycinate 30 minutes before bed for 30 days. Track sleep latency via Oura.",
    "metrics": ["sleep latency (minutes)", "HRV score", "subjective morning energy (1–10)"],
    "interventions": ["300mg Magnesium Glycinate 30 min pre-sleep"],
    "controls": ["consistent sleep time 22:30", "no alcohol during experiment"],
    "confounders": ["work stress levels", "travel"],
    "outcome": "ongoing",
    "connection_strength": 0.6,
    "potential_links": ["[[10 Notes/Health and Performance/_hub]]"],
    "tags": ["type/experiment", "experiment-kind/health", "status/running"],
}

VALID_TECHNICAL = {
    "experiment_kind": "technical",
    "experiment_id": "exp-2026-002",
    "created": "2026-02-01",
    "modified": "2026-04-09T00:00:00Z",
    "status": "design",
    "council_owner": "architect",
    "domain_tag": "agentic-systems",
    "question": "Does using Claude Opus for weekly planning reduce my planning session time?",
    "hypothesis": "Delegating planning synthesis will halve the cognitive load and save 30 minutes.",
    "method": "Use Claude Opus for weekly review synthesis for 4 weeks; log planning time in minutes.",
    "metrics": ["planning session duration (minutes)", "subjective clarity score (1–10)"],
    "outcome": "ongoing",
    "connection_strength": 0.5,
    "tags": ["type/experiment", "experiment-kind/technical", "status/design"],
}

VALID_CONCLUDED_COGNITIVE = {
    "experiment_kind": "cognitive",
    "experiment_id": "exp-2026-003",
    "created": "2026-01-10",
    "modified": "2026-04-09T00:00:00Z",
    "status": "concluded",
    "council_owner": "philosopher",
    "domain_tag": "philosophy-and-psychology",
    "question": "Does the Pomodoro technique improve my deep focus duration?",
    "hypothesis": "Structured 25-min blocks will increase sustained focus from 40 to 60 minutes.",
    "method": "Use Pomodoro for 3 weeks; track focus duration in daily log.",
    "metrics": ["max sustained focus (minutes)", "interruptions per session"],
    "start_date": "2026-01-10",
    "end_date": "2026-01-31",
    "outcome": "confirmed",
    "findings": "Average sustained focus increased from 38 to 62 minutes. Interruptions halved.",
    "confidence": "medium",
    "connection_strength": 0.7,
    "tags": ["type/experiment", "experiment-kind/cognitive", "status/concluded"],
}


# ---------------------------------------------------------------------------
# Valid schema tests
# ---------------------------------------------------------------------------

class TestValidFrontmatter:
    def test_health_experiment_validates(self):
        result = validate_frontmatter(VALID_HEALTH)
        assert result.ok, result.errors

    def test_technical_experiment_validates(self):
        result = validate_frontmatter(VALID_TECHNICAL)
        assert result.ok, result.errors

    def test_concluded_cognitive_validates(self):
        result = validate_frontmatter(VALID_CONCLUDED_COGNITIVE)
        assert result.ok, result.errors

    def test_all_kinds_have_council_mapping(self):
        for kind in ExperimentKind:
            assert kind.value in COUNCIL_DOMAIN_MAP, f"Missing council mapping for: {kind.value}"

    def test_council_mapping_correct_for_health(self):
        fm = ExperimentFrontmatter.model_validate(VALID_HEALTH)
        assert fm.council_owner == "sentinel"
        assert fm.domain_tag == "health-and-performance"

    def test_council_mapping_correct_for_technical(self):
        fm = ExperimentFrontmatter.model_validate(VALID_TECHNICAL)
        assert fm.council_owner == "architect"
        assert fm.domain_tag == "agentic-systems"


# ---------------------------------------------------------------------------
# Invalid schema tests
# ---------------------------------------------------------------------------

class TestInvalidFrontmatter:
    def test_wrong_council_owner_rejected(self):
        bad = {**VALID_HEALTH, "council_owner": "architect"}
        result = validate_frontmatter(bad)
        assert not result.ok
        assert any("council_owner" in e for e in result.errors)

    def test_wrong_domain_tag_rejected(self):
        bad = {**VALID_HEALTH, "domain_tag": "agentic-systems"}
        result = validate_frontmatter(bad)
        assert not result.ok

    def test_concluded_without_findings_rejected(self):
        bad = {
            **VALID_HEALTH,
            "status": "concluded",
            "outcome": "confirmed",
            "findings": None,
            "tags": ["type/experiment", "experiment-kind/health", "status/concluded"],
        }
        result = validate_frontmatter(bad)
        assert not result.ok
        assert any("findings" in e for e in result.errors)

    def test_concluded_with_ongoing_outcome_rejected(self):
        bad = {
            **VALID_HEALTH,
            "status": "concluded",
            "outcome": "ongoing",
            "findings": "Some findings here.",
            "tags": ["type/experiment", "experiment-kind/health", "status/concluded"],
        }
        result = validate_frontmatter(bad)
        assert not result.ok
        assert any("ongoing" in e for e in result.errors)

    def test_running_without_metrics_rejected(self):
        bad = {**VALID_HEALTH, "metrics": []}
        result = validate_frontmatter(bad)
        assert not result.ok
        assert any("metric" in e.lower() for e in result.errors)

    def test_invalid_experiment_id_rejected(self):
        bad = {**VALID_HEALTH, "experiment_id": "my-experiment"}
        result = validate_frontmatter(bad)
        assert not result.ok
        assert any("experiment_id" in e for e in result.errors)

    def test_missing_required_tag_rejected(self):
        bad = {**VALID_HEALTH, "tags": ["type/experiment"]}
        result = validate_frontmatter(bad)
        assert not result.ok

    def test_invalid_date_window_rejected(self):
        bad = {**VALID_HEALTH, "start_date": "2026-04-01", "end_date": "2026-01-01"}
        result = validate_frontmatter(bad)
        assert not result.ok
        assert any("start_date" in e for e in result.errors)

    def test_non_wikilink_potential_link_rejected(self):
        bad = {**VALID_HEALTH, "potential_links": ["not a wikilink"]}
        result = validate_frontmatter(bad)
        assert not result.ok

    def test_negative_duration_rejected(self):
        bad = {**VALID_HEALTH, "duration_days": -5}
        result = validate_frontmatter(bad)
        assert not result.ok


# ---------------------------------------------------------------------------
# Tag normalisation tests
# ---------------------------------------------------------------------------

class TestTagNormalisation:
    def test_managed_tags_injected(self):
        tags = normalize_experiment_tags({}, kind="health", status="running")
        assert "type/experiment" in tags
        assert "experiment-kind/health" in tags
        assert "status/running" in tags

    def test_user_tags_preserved(self):
        fm = {"tags": ["personal/sleep", "priority/high"]}
        tags = normalize_experiment_tags(fm, kind="health", status="hypothesis")
        assert "personal/sleep" in tags
        assert "priority/high" in tags

    def test_old_managed_tags_replaced(self):
        fm = {"tags": ["experiment-kind/technical", "status/running"]}
        tags = normalize_experiment_tags(fm, kind="health", status="concluded")
        assert "experiment-kind/health" in tags
        assert "status/concluded" in tags
        assert "experiment-kind/technical" not in tags

    def test_no_duplicates(self):
        fm = {"tags": ["type/experiment", "type/experiment"]}
        tags = normalize_experiment_tags(fm, kind="cognitive", status="design")
        assert tags.count("type/experiment") == 1
