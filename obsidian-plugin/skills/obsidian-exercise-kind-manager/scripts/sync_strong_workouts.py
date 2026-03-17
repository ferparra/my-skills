#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import re
from statistics import fmean, median
from typing import Any

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from exercise_models import (
    EXERCISE_FILE_GLOB,
    ExerciseKind,
    LoadUnit,
    ProgressionTrend,
    RecommendationSignal,
    TRAINING_GUIDING_PRINCIPLES_PATH,
    TrainingLogSource,
    clean_link_text,
    dedupe_preserve,
    dump_json,
    infer_strong_exercise_names,
    load_markdown_note,
    normalize_text_key,
    order_frontmatter,
    render_markdown,
    selection_score_for_frontmatter,
    validate_frontmatter,
)

REQUIRED_COLUMNS = [
    "Date",
    "Workout Name",
    "Duration",
    "Exercise Name",
    "Set Order",
    "Weight",
    "Reps",
    "Distance",
    "Seconds",
    "Notes",
    "Workout Notes",
    "RPE",
]

BODYWEIGHT_KEYWORDS = ("pull up", "chin up", "dip", "dead hang")
TRAINING_SECTION_RE = re.compile(r"(?ms)^## Training Log \(Strong CSV\).*?(?=^## |\Z)")


class StrongWorkoutRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: datetime
    workout_name: str
    duration: str | None = None
    exercise_name: str
    set_order: str
    weight: float = 0.0
    reps: float = 0.0
    distance: float = 0.0
    seconds: float = 0.0
    notes: str | None = None
    workout_notes: str | None = None
    rpe: str | None = None

    @field_validator("workout_name", "exercise_name", "set_order", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("required string value is empty")
        return text

    @field_validator("duration", "notes", "workout_notes", "rpe", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


@dataclass
class NoteRegistryEntry:
    path: Path
    frontmatter: dict[str, Any]
    body: str


@dataclass
class SessionSummary:
    note_path: str
    exercise_names: list[str]
    timestamp: datetime
    workout_name: str
    best_weight: float | None
    best_reps: float | None
    best_distance: float | None
    best_seconds: float | None
    work_set_count: int
    total_volume: float
    note_text: str
    score: float

    @property
    def date(self) -> str:
        return self.timestamp.date().isoformat()


def read_strong_csv(csv_path: Path) -> tuple[pl.DataFrame, list[str]]:
    df = pl.read_csv(csv_path, null_values=["", " "], try_parse_dates=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Strong CSV missing required columns: {missing}")

    working = (
        df.select(REQUIRED_COLUMNS)
        .with_columns(
            pl.col("Date").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=True).alias("date"),
            pl.col("Workout Name").cast(pl.String).str.strip_chars().alias("workout_name"),
            pl.col("Duration").cast(pl.String).str.strip_chars().alias("duration"),
            pl.col("Exercise Name").cast(pl.String).str.strip_chars().alias("exercise_name"),
            pl.col("Set Order").cast(pl.String).str.strip_chars().alias("set_order"),
            pl.col("Weight").cast(pl.Float64).fill_null(0.0).alias("weight"),
            pl.col("Reps").cast(pl.Float64).fill_null(0.0).alias("reps"),
            pl.col("Distance").cast(pl.Float64).fill_null(0.0).alias("distance"),
            pl.col("Seconds").cast(pl.Float64).fill_null(0.0).alias("seconds"),
            pl.col("Notes").cast(pl.String).str.strip_chars().alias("notes"),
            pl.col("Workout Notes").cast(pl.String).str.strip_chars().alias("workout_notes"),
            pl.col("RPE").cast(pl.String).str.strip_chars().alias("rpe"),
        )
        .select(
            "date",
            "workout_name",
            "duration",
            "exercise_name",
            "set_order",
            "weight",
            "reps",
            "distance",
            "seconds",
            "notes",
            "workout_notes",
            "rpe",
        )
        .unique(maintain_order=True)
    )

    working, normalization_warnings = normalize_obvious_weight_outliers(working)

    TypeAdapter(list[StrongWorkoutRow]).validate_python(working.to_dicts())
    duplicate_rows_removed = df.height - working.height
    warnings: list[str] = []
    if duplicate_rows_removed > 0:
        warnings.append(f"Removed {duplicate_rows_removed} exact duplicate Strong rows before sync.")
    warnings.extend(normalization_warnings)
    return working, warnings


def normalize_obvious_weight_outliers(df: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    rows = df.to_dicts()
    positive_weights_by_exercise: dict[str, list[float]] = defaultdict(list)
    peer_weights: dict[tuple[datetime, str, str], list[float]] = defaultdict(list)

    for row in rows:
        weight = float(row.get("weight") or 0.0)
        reps = float(row.get("reps") or 0.0)
        if weight <= 0 or reps <= 0 or str(row.get("set_order")) == "W":
            continue
        exercise_name = str(row["exercise_name"])
        positive_weights_by_exercise[exercise_name].append(weight)
        peer_weights[(row["date"], str(row["workout_name"]), exercise_name)].append(weight)

    exercise_medians = {name: median(values) for name, values in positive_weights_by_exercise.items() if values}
    correction_counts: dict[str, int] = defaultdict(int)

    for row in rows:
        weight = float(row.get("weight") or 0.0)
        reps = float(row.get("reps") or 0.0)
        if weight <= 0 or reps <= 0 or str(row.get("set_order")) == "W":
            continue

        exercise_name = str(row["exercise_name"])
        median_weight = exercise_medians.get(exercise_name)
        if not median_weight or weight < median_weight * 5:
            continue

        peer_key = (row["date"], str(row["workout_name"]), exercise_name)
        peers = [value for value in peer_weights.get(peer_key, []) if value < median_weight * 5]
        peer_median = median(peers) if peers else None

        corrected_weight = None
        for divisor in (10.0, 100.0):
            candidate = round(weight / divisor, 2)
            if not (median_weight * 0.5 <= candidate <= median_weight * 1.5):
                continue
            if peer_median is not None and abs(candidate - peer_median) <= max(1.0, peer_median * 0.1):
                corrected_weight = round(peer_median, 2)
            else:
                corrected_weight = candidate
            break

        if corrected_weight is None or corrected_weight == weight:
            continue

        row["weight"] = corrected_weight
        correction_counts[exercise_name] += 1

    warnings = [
        f"Normalized {count} obvious weight outlier row(s) for `{exercise_name}`."
        for exercise_name, count in sorted(correction_counts.items())
    ]
    normalized = pl.from_dicts(rows, schema=df.schema, strict=False)
    return normalized.select(df.columns), warnings


def build_note_registry(root: Path) -> tuple[dict[str, NoteRegistryEntry], dict[str, str], dict[str, list[str]]]:
    entries: dict[str, NoteRegistryEntry] = {}
    candidate_map: dict[str, set[str]] = defaultdict(set)

    for path in sorted(root.glob(EXERCISE_FILE_GLOB)):
        note = load_markdown_note(path)
        relative = str(path.relative_to(root))
        entries[relative] = NoteRegistryEntry(path=path, frontmatter=dict(note.frontmatter), body=note.body)

        for candidate in infer_strong_exercise_names(note.frontmatter, path):
            key = normalize_text_key(candidate)
            if key:
                candidate_map[key].add(relative)

    resolved: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    for key, paths in candidate_map.items():
        if len(paths) == 1:
            resolved[key] = next(iter(paths))
        else:
            collisions[key] = sorted(paths)
    return entries, resolved, collisions


def is_bodyweight_style(entry: NoteRegistryEntry) -> bool:
    text_pool = [entry.path.stem, entry.frontmatter.get("strong_name"), *entry.frontmatter.get("strong_exercise_names", [])]
    combined = " ".join(str(item or "") for item in text_pool).lower()
    return any(keyword in combined for keyword in BODYWEIGHT_KEYWORDS)


def format_number(value: float | None, *, digits: int = 1) -> str:
    if value is None:
        return ""
    rounded = round(float(value), digits)
    if abs(rounded - round(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.{digits}f}".rstrip("0").rstrip(".")


def escape_table_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br>")


def format_set_display(
    *,
    weight: float | None,
    reps: float | None,
    unit: str | None,
    distance: float | None = None,
    seconds: float | None = None,
    bodyweight_style: bool = False,
    average: bool = False,
) -> str:
    load_text = format_number(weight, digits=1 if average else 0)
    reps_text = format_number(reps, digits=1 if average else 0)

    if bodyweight_style:
        if weight and weight > 0:
            unit_text = unit or LoadUnit.KG.value
            return f"BW+{load_text}{unit_text} x {reps_text}"
        if reps and reps > 0:
            return f"BW x {reps_text}"

    if weight is not None and weight > 0 and reps is not None and reps > 0:
        unit_text = unit or LoadUnit.KG.value
        return f"{load_text}{unit_text} x {reps_text}"
    if reps is not None and reps > 0:
        return f"{reps_text} reps"
    if seconds is not None and seconds > 0:
        return f"{format_number(seconds, digits=0)}s"
    if distance is not None and distance > 0:
        return f"{format_number(distance, digits=0)}m"
    return ""


def choose_best_row(rows: list[dict[str, Any]], *, bodyweight_style: bool) -> dict[str, Any]:
    def key(row: dict[str, Any]) -> tuple[float, float, float, float]:
        weight = float(row.get("weight") or 0.0)
        reps = float(row.get("reps") or 0.0)
        seconds = float(row.get("seconds") or 0.0)
        distance = float(row.get("distance") or 0.0)
        if bodyweight_style and weight <= 0:
            return (reps, 0.0, seconds, distance)
        return (weight, reps, seconds, distance)

    return max(rows, key=key)


def compute_session_score(row: dict[str, Any], *, bodyweight_style: bool) -> float:
    weight = float(row.get("weight") or 0.0)
    reps = float(row.get("reps") or 0.0)
    seconds = float(row.get("seconds") or 0.0)
    distance = float(row.get("distance") or 0.0)
    if bodyweight_style and weight <= 0:
        return reps
    if weight > 0:
        return round(weight + (reps / 10.0), 4)
    if reps > 0:
        return round(reps / 10.0, 4)
    if seconds > 0:
        return seconds
    return distance


def summarize_sessions(df: pl.DataFrame, registry: dict[str, NoteRegistryEntry]) -> tuple[dict[str, list[SessionSummary]], pl.DataFrame]:
    matched = df.filter(pl.col("note_path").is_not_null())
    work_sets = matched.filter(pl.col("set_order") != "W")
    session_map: dict[str, list[SessionSummary]] = defaultdict(list)

    if work_sets.height == 0:
        return session_map, matched

    for group in work_sets.partition_by(["note_path", "date", "workout_name"], as_dict=False, maintain_order=True):
        rows = group.to_dicts()
        note_path = str(rows[0]["note_path"])
        entry = registry[note_path]
        bodyweight_style = is_bodyweight_style(entry)
        best = choose_best_row(rows, bodyweight_style=bodyweight_style)
        total_volume = round(sum(float(row.get("weight") or 0.0) * float(row.get("reps") or 0.0) for row in rows), 2)

        note_parts = []
        for raw in [*(row.get("notes") for row in rows), *(row.get("workout_notes") for row in rows)]:
            text = str(raw or "").strip()
            if text:
                note_parts.append(text)

        session_map[note_path].append(
            SessionSummary(
                note_path=note_path,
                exercise_names=sorted({str(row["exercise_name"]) for row in rows}),
                timestamp=rows[0]["date"],
                workout_name=str(rows[0]["workout_name"]),
                best_weight=float(best.get("weight") or 0.0) or None,
                best_reps=float(best.get("reps") or 0.0) or None,
                best_distance=float(best.get("distance") or 0.0) or None,
                best_seconds=float(best.get("seconds") or 0.0) or None,
                work_set_count=len(rows),
                total_volume=total_volume,
                note_text=" / ".join(dict.fromkeys(note_parts)),
                score=compute_session_score(best, bodyweight_style=bodyweight_style),
            )
        )

    for note_path in session_map:
        session_map[note_path].sort(key=lambda item: item.timestamp)

    return session_map, matched


def weekly_average_for_sessions(sessions: list[SessionSummary], *, credit: float, weeks: int = 6) -> float:
    if not sessions or credit <= 0:
        return 0.0

    latest_date = max(session.timestamp.date() for session in sessions)
    monday = latest_date - timedelta(days=latest_date.weekday())
    week_starts = [monday - timedelta(weeks=offset) for offset in range(weeks - 1, -1, -1)]
    weekly_counts: dict[date, float] = {week_start: 0.0 for week_start in week_starts}

    for session in sessions:
        session_monday = session.timestamp.date() - timedelta(days=session.timestamp.date().weekday())
        if session_monday in weekly_counts:
            weekly_counts[session_monday] += session.work_set_count * credit

    return round(sum(weekly_counts.values()) / weeks, 2)


def progression_for_sessions(sessions: list[SessionSummary]) -> tuple[ProgressionTrend, float | None]:
    scores = [session.score for session in sessions if session.score > 0]
    if len(scores) < 4:
        return ProgressionTrend.INSUFFICIENT_DATA, None

    if len(scores) >= 6:
        previous = fmean(scores[-6:-3])
        latest = fmean(scores[-3:])
    else:
        split = len(scores) // 2
        previous = fmean(scores[:split])
        latest = fmean(scores[split:])

    if previous <= 0:
        return ProgressionTrend.INSUFFICIENT_DATA, None

    delta_pct = round(((latest / previous) - 1.0) * 100.0, 2)
    if delta_pct >= 5.0:
        return ProgressionTrend.IMPROVING, delta_pct
    if delta_pct <= -5.0:
        return ProgressionTrend.REGRESSING, delta_pct
    return ProgressionTrend.STABLE, delta_pct


def recommendation_for_note(frontmatter: dict[str, Any], avg_weekly_primary_sets: float, trend: ProgressionTrend) -> RecommendationSignal:
    if str(frontmatter.get("exercise_kind") or "") != ExerciseKind.HYPERTROPHY.value:
        return RecommendationSignal.INSUFFICIENT_DATA
    if trend == ProgressionTrend.INSUFFICIENT_DATA:
        return RecommendationSignal.INSUFFICIENT_DATA
    fatigue = str(frontmatter.get("fatigue_cost") or "")
    selection = selection_score_for_frontmatter(frontmatter)
    if avg_weekly_primary_sets < 12.0:
        return RecommendationSignal.ADD_VOLUME
    if trend == ProgressionTrend.REGRESSING and fatigue in {"moderate", "high"}:
        return RecommendationSignal.REVIEW_EXERCISE_CHOICE
    if trend == ProgressionTrend.STABLE and selection < 5.0:
        return RecommendationSignal.CONSIDER_BETTER_VARIANT
    return RecommendationSignal.MAINTAIN


def note_link(relative_path: str) -> str:
    path = Path(relative_path)
    return f"[[{path.with_suffix('').as_posix()}|{path.stem}]]"


def muscle_label(value: str) -> str:
    return clean_link_text(value).split("/")[-1]


def build_training_log_section(
    entry: NoteRegistryEntry,
    sessions: list[SessionSummary],
    *,
    top_set_display: str,
    working_avg_display: str,
    avg_weekly_primary_sets: float,
    avg_weekly_secondary_sets: float,
    progression_trend: ProgressionTrend,
    progression_delta_pct: float | None,
    unit: str | None,
) -> str:
    bodyweight_style = is_bodyweight_style(entry)
    first_date = sessions[0].date
    last_date = sessions[-1].date
    rows = [
        "| Date | Workout | Best Set | Work Sets | Volume | Notes |",
        "|------|---------|----------|-----------|--------|-------|",
    ]
    for session in sessions:
        best_set = format_set_display(
            weight=session.best_weight,
            reps=session.best_reps,
            unit=unit,
            distance=session.best_distance,
            seconds=session.best_seconds,
            bodyweight_style=bodyweight_style,
        )
        volume_text = format_number(session.total_volume, digits=1) if session.total_volume > 0 else ""
        rows.append(
            f"| {escape_table_cell(session.date)} | {escape_table_cell(session.workout_name)} | {escape_table_cell(best_set)} | "
            f"{session.work_set_count} | {escape_table_cell(volume_text)} | {escape_table_cell(session.note_text)} |"
        )

    trend_suffix = ""
    if progression_delta_pct is not None:
        sign = "+" if progression_delta_pct > 0 else ""
        trend_suffix = f" ({sign}{format_number(progression_delta_pct, digits=1)}%)"

    return (
        "## Training Log (Strong CSV)\n\n"
        f"Range: `{first_date}` to `{last_date}`\n\n"
        + "\n".join(rows)
        + "\n\n"
        + "**Key Metrics**\n"
        + f"- Sessions: {len(sessions)}\n"
        + f"- Work sets: {sum(session.work_set_count for session in sessions)}\n"
        + f"- Top set: {top_set_display}\n"
        + f"- Working avg: {working_avg_display}\n"
        + f"- Avg weekly primary sets (6w): {format_number(avg_weekly_primary_sets, digits=1)}\n"
        + f"- Avg weekly secondary sets (6w): {format_number(avg_weekly_secondary_sets, digits=1)}\n"
        + f"- Progression trend: {progression_trend.value}{trend_suffix}\n"
    )


def replace_training_log_section(body: str, section: str) -> str:
    rendered = section.rstrip() + "\n"
    if TRAINING_SECTION_RE.search(body):
        return TRAINING_SECTION_RE.sub(rendered + "\n", body, count=1).rstrip() + "\n"
    stripped = body.rstrip()
    spacer = "\n\n" if stripped else ""
    return f"{stripped}{spacer}{rendered}"


def build_note_update(
    root: Path,
    entry: NoteRegistryEntry,
    sessions: list[SessionSummary],
    matched_export_names: list[str],
    *,
    synced_at: datetime,
) -> dict[str, Any]:
    updated = dict(entry.frontmatter)
    original_order = list(entry.frontmatter.keys())
    changed_fields: list[str] = []
    bodyweight_style = is_bodyweight_style(entry)
    unit = str(updated.get("strong_weight_unit") or updated.get("top_set_unit") or LoadUnit.KG.value)

    def set_if_changed(key: str, value: Any) -> None:
        if updated.get(key) != value:
            updated[key] = value
            changed_fields.append(key)

    strongest = max(sessions, key=lambda session: (session.score, session.best_weight or 0.0, session.best_reps or 0.0))
    avg_weight_values = [session.best_weight for session in sessions if session.best_weight is not None and session.best_weight > 0]
    avg_reps_values = [session.best_reps for session in sessions if session.best_reps is not None and session.best_reps > 0]
    avg_weight = round(fmean(avg_weight_values), 2) if avg_weight_values else None
    avg_reps = round(fmean(avg_reps_values), 2) if avg_reps_values else None

    primary_credit = float(updated.get("volume_primary_credit") or 0.0)
    secondary_credit = float(updated.get("volume_secondary_credit") or 0.0)
    avg_weekly_primary_sets = weekly_average_for_sessions(sessions, credit=primary_credit, weeks=6)
    avg_weekly_secondary_sets = weekly_average_for_sessions(sessions, credit=secondary_credit, weeks=6)
    progression_trend, progression_delta_pct = progression_for_sessions(sessions)
    recommendation = recommendation_for_note(updated, avg_weekly_primary_sets, progression_trend)

    merged_export_names = dedupe_preserve([*infer_strong_exercise_names(entry.frontmatter, entry.path), *matched_export_names])
    set_if_changed("strong_exercise_names", merged_export_names)
    set_if_changed("training_log_source", TrainingLogSource.STRONG_CSV.value)
    set_if_changed("strong_last_synced_at", synced_at.isoformat())
    set_if_changed("strong_session_count", len(sessions))
    set_if_changed("strong_work_set_count", sum(session.work_set_count for session in sessions))
    set_if_changed("logged_sessions", len(sessions))
    set_if_changed("last_performed", sessions[-1].date)
    set_if_changed("avg_weekly_primary_sets_6w", avg_weekly_primary_sets)
    set_if_changed("avg_weekly_secondary_sets_6w", avg_weekly_secondary_sets)
    set_if_changed("progression_trend", progression_trend.value)
    set_if_changed("progression_delta_pct", progression_delta_pct)
    set_if_changed("recommendation_signal", recommendation.value)

    top_set_display = format_set_display(
        weight=strongest.best_weight,
        reps=strongest.best_reps,
        unit=unit,
        distance=strongest.best_distance,
        seconds=strongest.best_seconds,
        bodyweight_style=bodyweight_style,
    )
    working_avg_display = format_set_display(
        weight=avg_weight,
        reps=avg_reps,
        unit=unit,
        bodyweight_style=bodyweight_style,
        average=True,
    )

    set_if_changed("top_set_load", strongest.best_weight)
    set_if_changed("top_set_reps", strongest.best_reps)
    set_if_changed("top_set_unit", LoadUnit.BODYWEIGHT.value if bodyweight_style and (strongest.best_weight or 0.0) <= 0 else unit)
    set_if_changed("top_set_volume", round((strongest.best_weight or 0.0) * (strongest.best_reps or 0.0), 2) or None)
    set_if_changed("working_avg_load", avg_weight)
    set_if_changed("working_avg_reps", avg_reps)
    set_if_changed("working_avg_unit", LoadUnit.BODYWEIGHT.value if bodyweight_style and (avg_weight or 0.0) <= 0 else unit)

    section = build_training_log_section(
        entry,
        sessions,
        top_set_display=top_set_display,
        working_avg_display=working_avg_display,
        avg_weekly_primary_sets=avg_weekly_primary_sets,
        avg_weekly_secondary_sets=avg_weekly_secondary_sets,
        progression_trend=progression_trend,
        progression_delta_pct=progression_delta_pct,
        unit=unit,
    )
    new_body = replace_training_log_section(entry.body, section)

    ordered = order_frontmatter(updated, original_order)
    ok, errors = validate_frontmatter(ordered)
    return {
        "path": str(entry.path),
        "relative_path": str(entry.path.relative_to(root)),
        "ok": ok,
        "errors": errors,
        "changed": ordered != order_frontmatter(entry.frontmatter, original_order) or new_body != entry.body,
        "changed_fields": changed_fields,
        "frontmatter": ordered,
        "body": new_body,
        "sessions_imported": len(sessions),
        "matched_export_names": matched_export_names,
        "recommendation_signal": recommendation.value,
        "progression_trend": progression_trend.value,
        "progression_delta_pct": progression_delta_pct,
        "avg_weekly_primary_sets_6w": avg_weekly_primary_sets,
        "selection_score": selection_score_for_frontmatter(ordered),
    }


def render_retrospective_report(
    *,
    csv_path: Path,
    synced_at: datetime,
    updated_results: list[dict[str, Any]],
    unresolved_df: pl.DataFrame,
    matched_df: pl.DataFrame,
    registry: dict[str, NoteRegistryEntry],
) -> str:
    imported = [result for result in updated_results if result["ok"]]
    if not imported:
        return "# Strong Training Retrospective\n\nNo matched exercise notes were available for analysis.\n"

    analyzable = [
        item
        for item in imported
        if str(registry[item["relative_path"]].frontmatter.get("exercise_kind") or "") == ExerciseKind.HYPERTROPHY.value
    ]

    matched_dates = matched_df.select(pl.col("date").min().alias("min_date"), pl.col("date").max().alias("max_date")).row(0)
    period_start = matched_dates[0].date().isoformat() if matched_dates[0] else ""
    period_end = matched_dates[1].date().isoformat() if matched_dates[1] else ""

    imported_sorted = sorted(
        analyzable,
        key=lambda item: ((item["progression_delta_pct"] or -10_000), item["selection_score"]),
        reverse=True,
    )
    review_items = [
        item
        for item in analyzable
        if item["recommendation_signal"]
        in {RecommendationSignal.REVIEW_EXERCISE_CHOICE.value, RecommendationSignal.CONSIDER_BETTER_VARIANT.value}
    ]
    low_volume_items = [item for item in analyzable if float(item["avg_weekly_primary_sets_6w"] or 0.0) < 12.0]

    muscle_volume: dict[str, float] = defaultdict(float)
    for item in analyzable:
        entry = registry[item["relative_path"]]
        muscle = str(entry.frontmatter.get("primary_muscle") or "")
        if muscle:
            muscle_volume[muscle] += float(item["avg_weekly_primary_sets_6w"] or 0.0)

    volume_rows = sorted(muscle_volume.items(), key=lambda pair: pair[1])

    recommendation_lines: list[str] = []
    for item in low_volume_items[:6]:
        entry = registry[item["relative_path"]]
        primary = str(entry.frontmatter.get("primary_muscle") or "")
        candidates = []
        for candidate in analyzable:
            candidate_entry = registry[candidate["relative_path"]]
            if candidate_entry.frontmatter.get("primary_muscle") == primary:
                candidates.append((candidate["selection_score"], note_link(candidate["relative_path"])))
        candidates = sorted(candidates, reverse=True)
        recommendation_lines.append(
            f"- {muscle_label(primary)} is averaging {item['avg_weekly_primary_sets_6w']:.1f} primary sets/week via {note_link(item['relative_path'])}. "
            f"High-fit library options: {', '.join(link for _, link in candidates[:3]) or note_link(item['relative_path'])}."
        )

    for item in review_items[:6]:
        entry = registry[item["relative_path"]]
        primary = str(entry.frontmatter.get("primary_muscle") or "")
        alternatives = []
        for candidate in analyzable:
            candidate_entry = registry[candidate["relative_path"]]
            if candidate["relative_path"] == item["relative_path"]:
                continue
            if candidate_entry.frontmatter.get("primary_muscle") == primary and candidate["selection_score"] >= item["selection_score"]:
                alternatives.append((candidate["selection_score"], note_link(candidate["relative_path"])))
        alternatives = sorted(alternatives, reverse=True)
        recommendation_lines.append(
            f"- {note_link(item['relative_path'])} is `{item['progression_trend']}` with recommendation `{item['recommendation_signal']}`. "
            f"Review against [[{TRAINING_GUIDING_PRINCIPLES_PATH.removesuffix('.md')}|Training guiding principles]] and consider {', '.join(link for _, link in alternatives[:2]) or 'a lower-fatigue, higher-stability variant'}."
        )

    unresolved_lines = []
    if unresolved_df.height > 0:
        for row in unresolved_df.sort("len", descending=True).head(15).iter_rows(named=True):
            unresolved_lines.append(f"- `{row['exercise_name']}`: {row['len']} rows not mapped to an exercise note")

    lines = [
        "---",
        "tags:",
        "- area/health/fitness",
        "- resource/topic/fitness/hypertrophy",
        "- status/processed",
        f"generated_at: {synced_at.isoformat()}",
        f"generated_from: {csv_path.name}",
        f"period_start: {period_start}",
        f"period_end: {period_end}",
        "potential_links:",
        f"- '[[{TRAINING_GUIDING_PRINCIPLES_PATH.removesuffix('.md')}|Training guiding principles]]'",
        "- '[[20 Resources/Exercises/Exercise Library.base|Exercise Library]]'",
        "---",
        "",
        "# Strong Training Retrospective",
        "",
        f"Source: `{csv_path.name}` synced on `{synced_at.date().isoformat()}` for [[{TRAINING_GUIDING_PRINCIPLES_PATH.removesuffix('.md')}|Training guiding principles]] and the [[20 Resources/Exercises/Exercise Library.base|Exercise Library]].",
        "",
        "## Coverage",
        "",
        f"- Matched exercise notes: {len(imported)}",
        f"- Matched Strong rows: {matched_df.height}",
        f"- Review window: `{period_start}` to `{period_end}`",
        "",
        "## Weekly Volume Snapshot",
        "",
        "| Primary Muscle | Avg Weekly Sets (6w) | Status |",
        "|---|---:|---|",
    ]
    for muscle, value in volume_rows:
        status = "Below target" if value < 12.0 else "In range" if value <= 16.0 else "Above target"
        lines.append(f"| {muscle_label(muscle)} | {value:.1f} | {status} |")

    lines.extend(
        [
            "",
            "## Progressive Overload Highlights",
            "",
        ]
    )
    for item in imported_sorted[:8]:
        delta = item["progression_delta_pct"]
        delta_text = "n/a" if delta is None else f"{delta:+.1f}%"
        lines.append(
            f"- {note_link(item['relative_path'])}: `{item['progression_trend']}` with {delta_text} trend delta and {item['avg_weekly_primary_sets_6w']:.1f} primary sets/week."
        )

    lines.extend(["", "## Recommendations", ""])
    lines.extend(recommendation_lines or ["- No recommendation deltas were generated from the current matched note set."])

    if unresolved_lines:
        lines.extend(["", "## Unresolved Strong Exercises", ""])
        lines.extend(unresolved_lines)

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Strong CSV exports into typed exercise notes with polars-backed retrospective analysis.")
    parser.add_argument("--csv", default="strong_workouts.csv", help="Path to the Strong CSV export.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    parser.add_argument("--report-path", help="Optional markdown report path to write after a successful sync.")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    csv_path = (root / args.csv).resolve() if not Path(args.csv).is_absolute() else Path(args.csv).resolve()
    if not csv_path.exists():
        print(dump_json({"ok": False, "error": "csv_missing", "csv_path": str(csv_path)}))
        return 1

    warnings: list[str] = []
    try:
        strong_df, csv_warnings = read_strong_csv(csv_path)
    except (ValidationError, ValueError) as exc:
        print(dump_json({"ok": False, "error": "invalid_csv", "details": str(exc), "csv_path": str(csv_path)}))
        return 1

    warnings.extend(csv_warnings)
    registry, resolved_map, collisions = build_note_registry(root)
    working = strong_df.with_columns(
        pl.col("exercise_name").map_elements(normalize_text_key, return_dtype=pl.String).alias("exercise_key"),
        pl.col("exercise_name").map_elements(lambda value: resolved_map.get(normalize_text_key(value)), return_dtype=pl.String).alias("note_path"),
    )
    unresolved = working.filter(pl.col("note_path").is_null()).group_by("exercise_name").len()
    session_map, matched_df = summarize_sessions(working, registry)

    synced_at = datetime.now(UTC).replace(microsecond=0)
    results = []
    for relative_path, sessions in session_map.items():
        entry = registry[relative_path]
        matched_names = dedupe_preserve(name for session in sessions for name in session.exercise_names)
        results.append(build_note_update(root, entry, sessions, matched_names, synced_at=synced_at))

    overall_ok = all(result["ok"] for result in results)
    report_content = None
    if overall_ok and args.report_path:
        report_content = render_retrospective_report(
            csv_path=csv_path,
            synced_at=synced_at,
            updated_results=results,
            unresolved_df=unresolved,
            matched_df=matched_df,
            registry=registry,
        )

    if args.mode == "fix" and overall_ok:
        for result in results:
            if not result["changed"]:
                continue
            Path(result["path"]).write_text(render_markdown(result["frontmatter"], result["body"]), encoding="utf-8")
        if report_content and args.report_path:
            report_path = (root / args.report_path).resolve() if not Path(args.report_path).is_absolute() else Path(args.report_path).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report_content, encoding="utf-8")

    payload = {
        "ok": overall_ok,
        "mode": args.mode,
        "csv_path": str(csv_path.relative_to(root) if csv_path.is_relative_to(root) else csv_path),
        "strong_rows": strong_df.height,
        "matched_rows": matched_df.height,
        "matched_notes": len(results),
        "unresolved_exercises": unresolved.sort("len", descending=True).to_dicts(),
        "mapping_collisions": collisions,
        "warnings": warnings,
        "results": [
            {
                "path": result["relative_path"],
                "ok": result["ok"],
                "changed": result["changed"],
                "changed_fields": result["changed_fields"],
                "sessions_imported": result["sessions_imported"],
                "matched_export_names": result["matched_export_names"],
                "progression_trend": result["progression_trend"],
                "progression_delta_pct": result["progression_delta_pct"],
                "avg_weekly_primary_sets_6w": result["avg_weekly_primary_sets_6w"],
                "recommendation_signal": result["recommendation_signal"],
                "errors": result["errors"],
            }
            for result in sorted(results, key=lambda item: item["relative_path"])
        ],
        "report_path": args.report_path,
    }
    print(dump_json(payload))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
