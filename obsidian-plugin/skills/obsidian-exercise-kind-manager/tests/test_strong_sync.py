from datetime import UTC, datetime
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from exercise_models import render_markdown
from sync_strong_workouts import (
    NoteRegistryEntry,
    SessionSummary,
    build_note_update,
    progression_for_sessions,
    read_strong_csv,
)


def test_read_strong_csv_dedupes_exact_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "strong_workouts.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Date,Workout Name,Duration,Exercise Name,Set Order,Weight,Reps,Distance,Seconds,Notes,Workout Notes,RPE",
                "2026-03-01 09:00:00,Pull,45m,Pull-Ups,1,0,8,0,0,,,8",
                "2026-03-01 09:00:00,Pull,45m,Pull-Ups,1,0,8,0,0,,,8",
            ]
        ),
        encoding="utf-8",
    )

    df, warnings = read_strong_csv(csv_path)
    assert df.height == 1
    assert warnings == ["Removed 1 exact duplicate Strong rows before sync."]


def test_progression_for_sessions_marks_improving() -> None:
    sessions = [
        SessionSummary("x.md", ["Pull-Ups"], datetime(2026, 1, 1, tzinfo=UTC), "A", 20.0, 5.0, None, None, 3, 300.0, "", 20.5),
        SessionSummary("x.md", ["Pull-Ups"], datetime(2026, 1, 8, tzinfo=UTC), "A", 22.5, 5.0, None, None, 3, 337.5, "", 23.0),
        SessionSummary("x.md", ["Pull-Ups"], datetime(2026, 1, 15, tzinfo=UTC), "A", 25.0, 5.0, None, None, 3, 375.0, "", 25.5),
        SessionSummary("x.md", ["Pull-Ups"], datetime(2026, 1, 22, tzinfo=UTC), "A", 27.5, 5.0, None, None, 3, 412.5, "", 28.0),
    ]

    trend, delta = progression_for_sessions(sessions)
    assert trend.value == "improving"
    assert delta is not None and delta > 5.0


def test_read_strong_csv_normalizes_obvious_decimal_shift_outlier(tmp_path: Path) -> None:
    csv_path = tmp_path / "strong_workouts.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Date,Workout Name,Duration,Exercise Name,Set Order,Weight,Reps,Distance,Seconds,Notes,Workout Notes,RPE",
                "2026-03-01 09:00:00,Pull,45m,Lat Pulldown (Cable),1,91.0,6,0,0,,,8",
                "2026-03-01 09:00:00,Pull,45m,Lat Pulldown (Cable),2,91.0,6,0,0,,,8",
                "2026-03-01 09:00:00,Pull,45m,Lat Pulldown (Cable),3,916.0,7,0,0,,,8",
            ]
        ),
        encoding="utf-8",
    )

    df, warnings = read_strong_csv(csv_path)
    assert sorted(df["weight"].to_list()) == [91.0, 91.0, 91.0]
    assert warnings == ["Normalized 1 obvious weight outlier row(s) for `Lat Pulldown (Cable)`."]


def test_build_note_update_preserves_manual_training_log_and_replaces_managed_section(tmp_path: Path) -> None:
    note_path = tmp_path / "20 Resources/Exercises/Pull-Ups.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "exercise_kind": "hypertrophy",
        "tags": ["type/exercise", "exercise-kind/hypertrophy", "fitness/exercise"],
        "category": "hypertrophy",
        "region": "upper",
        "pattern": "pull",
        "primary_muscle": "[[Lats]]",
        "muscle_group": ["[[Lats]]", "[[Biceps]]"],
        "secondary_muscles": ["[[Biceps]]"],
        "force_profile": "lengthened",
        "stability_profile": "high",
        "fatigue_cost": "low",
        "progression_mode": "load_reps",
        "volume_tracking": "primary_only",
        "volume_primary_credit": 1.0,
        "volume_secondary_credit": 0.0,
        "strong_exercise_names": ["Pull-Ups"],
        "strong_weight_unit": "kg",
        "equipment": ["[[Pull-Up Bar]]"],
    }
    body = """## Notes

Keep chest up.

## Training Log

Legacy manual log stays here.

## Training Log (Strong CSV)

Old managed section.
"""
    note_path.write_text(render_markdown(frontmatter, body), encoding="utf-8")
    entry = NoteRegistryEntry(note_path, frontmatter, body)
    sessions = [
        SessionSummary(
            note_path="20 Resources/Exercises/Pull-Ups.md",
            exercise_names=["Pull-Ups", "Chin Up"],
            timestamp=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
            workout_name="Pull",
            best_weight=0.0,
            best_reps=8.0,
            best_distance=None,
            best_seconds=None,
            work_set_count=3,
            total_volume=0.0,
            note_text="",
            score=8.0,
        ),
        SessionSummary(
            note_path="20 Resources/Exercises/Pull-Ups.md",
            exercise_names=["Pull-Ups"],
            timestamp=datetime(2026, 2, 8, 9, 0, tzinfo=UTC),
            workout_name="Pull",
            best_weight=5.0,
            best_reps=8.0,
            best_distance=None,
            best_seconds=None,
            work_set_count=3,
            total_volume=120.0,
            note_text="Solid set",
            score=5.8,
        ),
        SessionSummary(
            note_path="20 Resources/Exercises/Pull-Ups.md",
            exercise_names=["Pull-Ups"],
            timestamp=datetime(2026, 2, 15, 9, 0, tzinfo=UTC),
            workout_name="Pull",
            best_weight=7.5,
            best_reps=8.0,
            best_distance=None,
            best_seconds=None,
            work_set_count=3,
            total_volume=180.0,
            note_text="",
            score=8.3,
        ),
        SessionSummary(
            note_path="20 Resources/Exercises/Pull-Ups.md",
            exercise_names=["Pull-Ups"],
            timestamp=datetime(2026, 2, 22, 9, 0, tzinfo=UTC),
            workout_name="Pull",
            best_weight=10.0,
            best_reps=8.0,
            best_distance=None,
            best_seconds=None,
            work_set_count=3,
            total_volume=240.0,
            note_text="",
            score=10.8,
        ),
    ]

    result = build_note_update(tmp_path, entry, sessions, ["Pull-Ups", "Chin Up"], synced_at=datetime(2026, 3, 14, tzinfo=UTC))

    assert result["ok"] is True
    assert result["frontmatter"]["training_log_source"] == "strong_csv"
    assert result["frontmatter"]["strong_exercise_names"] == ["Pull-Ups", "Chin Up"]
    assert "Legacy manual log stays here." in result["body"]
    assert result["body"].count("## Training Log (Strong CSV)") == 1
    assert "Range: `2026-02-01` to `2026-02-22`" in result["body"]
