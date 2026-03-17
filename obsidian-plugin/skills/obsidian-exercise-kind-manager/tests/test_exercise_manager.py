from pathlib import Path

from exercise_models import (
    ExerciseKind,
    extract_training_metrics,
    infer_exercise_kind,
    normalize_equipment_list,
    normalize_exercise_tags,
    validate_frontmatter,
)


def test_infer_hypertrophy_kind_from_category():
    kind, ambiguous = infer_exercise_kind(
        {
            "category": "hypertrophy",
            "tags": ["fitness/exercise"],
        },
        "",
        Path("20 Resources/Exercises/Leg Press.md"),
    )
    assert kind == ExerciseKind.HYPERTROPHY
    assert ambiguous is False


def test_normalize_equipment_list_from_string():
    assert normalize_equipment_list("kettlebell, bench") == ["[[Kettlebell]]", "[[Bench]]"]


def test_extract_training_metrics_for_weighted_set():
    body = """
## Training Log

| Date | Best Set | Notes |
|------|----------|-------|
| 2026-02-05 | 140kg x 6 | |

**Key Metrics**
- Sessions: 11
- Top set: 140kg x 6
- Working avg: 132.3kg x 5.5
"""
    metrics = extract_training_metrics(body)
    assert metrics.logged_sessions == 11
    assert metrics.top_set_load == 140.0
    assert metrics.top_set_reps == 6.0
    assert metrics.top_set_unit == "kg"
    assert metrics.top_set_volume == 840.0
    assert metrics.last_performed == "2026-02-05"


def test_validate_warmup_flow_frontmatter():
    frontmatter = {
        "exercise_kind": "warmup_flow",
        "tags": normalize_exercise_tags({"tags": ["fitness/warmup"]}, kind=ExerciseKind.WARMUP_FLOW),
        "programme": "[[Kettlebell Mobility Warm-up]]",
        "duration": "~7 min",
        "component_exercises": ["[[Tall-Kneeling Halo]]", "[[Prying Goblet Squat]]"],
        "progression_mode": "duration",
        "volume_tracking": "not_counted",
        "volume_primary_credit": 0.0,
        "volume_secondary_credit": 0.0,
        "aliases": ["Kettlebell Warm-up"],
        "equipment": [],
    }
    ok, errors = validate_frontmatter(frontmatter)
    assert ok is True, errors
