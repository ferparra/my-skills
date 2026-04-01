#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

FRONTMATTER_DELIM = "\n---\n"
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
TRAINING_ROW_RE = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|", re.MULTILINE)
SESSIONS_RE = re.compile(r"^- Sessions:\s*([0-9]+)", re.MULTILINE)
LOAD_REPS_RE = re.compile(
    r"(?P<load>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)\s*x\s*(?P<reps>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
BODYWEIGHT_REPS_RE = re.compile(r"\bBW\s*x\s*(?P<reps>\d+(?:\.\d+)?)", re.IGNORECASE)
TOP_SET_RE = re.compile(r"^- Top set:\s*(.+)$", re.MULTILINE)
WORKING_AVG_RE = re.compile(r"^- Working avg:\s*(.+)$", re.MULTILINE)

EXERCISE_FILE_GLOB = "20 Resources/Exercises/*.md"
EXERCISE_BASE_PATH = "20 Resources/Exercises/Exercise Library.base"
TRAINING_GUIDING_PRINCIPLES_PATH = "00 Inbox/Training guiding principles.md"

EXERCISE_FRONTMATTER_ORDER = [
    "exercise_kind",
    "tags",
    "category",
    "region",
    "pattern",
    "primary_muscle",
    "muscle_group",
    "secondary_muscles",
    "force_profile",
    "stability_profile",
    "fatigue_cost",
    "progression_mode",
    "volume_tracking",
    "volume_primary_credit",
    "volume_secondary_credit",
    "equipment",
    "programme",
    "strong_name",
    "strong_exercise_names",
    "strong_weight_unit",
    "training_log_source",
    "strong_last_synced_at",
    "strong_session_count",
    "strong_work_set_count",
    "last_performed",
    "logged_sessions",
    "avg_weekly_primary_sets_6w",
    "avg_weekly_secondary_sets_6w",
    "progression_trend",
    "progression_delta_pct",
    "recommendation_signal",
    "top_set_load",
    "top_set_reps",
    "top_set_unit",
    "top_set_volume",
    "working_avg_load",
    "working_avg_reps",
    "working_avg_unit",
    "duration",
    "component_exercises",
    "aliases",
]


class ExerciseKind(StrEnum):
    HYPERTROPHY = "hypertrophy"
    MOBILITY_DRILL = "mobility_drill"
    WARMUP_FLOW = "warmup_flow"
    EXERCISE_BRIEF = "exercise_brief"


class Region(StrEnum):
    UPPER = "upper"
    LOWER = "lower"
    FULL_BODY = "full-body"
    CORE = "core"


class Pattern(StrEnum):
    ISOLATION = "isolation"
    PUSH = "push"
    PULL = "pull"
    SQUAT = "squat"
    HINGE = "hinge"
    LUNGE = "lunge"
    ROTATION = "rotation"


class ForceProfile(StrEnum):
    LENGTHENED = "lengthened"
    MID_RANGE = "mid-range"
    SHORTENED = "shortened"


class StabilityProfile(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FatigueCost(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ProgressionMode(StrEnum):
    LOAD_REPS = "load_reps"
    QUALITY = "quality"
    DURATION = "duration"


class VolumeTracking(StrEnum):
    PRIMARY_ONLY = "primary_only"
    SECONDARY_HALF = "secondary_half"
    NOT_COUNTED = "not_counted"


class LoadUnit(StrEnum):
    KG = "kg"
    LBS = "lbs"
    BODYWEIGHT = "bodyweight"


class TrainingLogSource(StrEnum):
    MANUAL = "manual"
    STRONG_CSV = "strong_csv"


class ProgressionTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    REGRESSING = "regressing"
    INSUFFICIENT_DATA = "insufficient_data"


class RecommendationSignal(StrEnum):
    MAINTAIN = "maintain"
    ADD_VOLUME = "add_volume"
    REVIEW_EXERCISE_CHOICE = "review_exercise_choice"
    CONSIDER_BETTER_VARIANT = "consider_better_variant"
    INSUFFICIENT_DATA = "insufficient_data"


MODEL_TO_REQUIRED_TAGS: dict[ExerciseKind, tuple[str, ...]] = {
    ExerciseKind.HYPERTROPHY: ("type/exercise", "fitness/exercise"),
    ExerciseKind.MOBILITY_DRILL: ("type/exercise", "fitness/exercise", "fitness/mobility"),
    ExerciseKind.WARMUP_FLOW: ("type/exercise", "fitness/warmup"),
    ExerciseKind.EXERCISE_BRIEF: ("type/exercise",),
}

EQUIPMENT_ALIASES = {
    "ab wheel": "[[Ab Wheel]]",
    "barbell": "[[Barbell]]",
    "bench": "[[Bench]]",
    "cable machine": "[[Cable Machine]]",
    "calf raise machine": "[[Calf Raise Machine]]",
    "chest fly machine": "[[Chest Fly Machine]]",
    "db": "[[Dumbbells]]",
    "dumbbell": "[[Dumbbells]]",
    "dumbbells": "[[Dumbbells]]",
    "incline bench": "[[Incline Bench]]",
    "k-bell": "[[Kettlebell]]",
    "kbell": "[[Kettlebell]]",
    "kettlebell": "[[Kettlebell]]",
    "kettlebells": "[[Kettlebell]]",
    "lateral raise machine": "[[Lateral Raise Machine]]",
    "leg extension machine": "[[Leg Extension Machine]]",
    "leg press machine": "[[Leg Press Machine]]",
    "machine": "[[Machine]]",
    "pull-up bar": "[[Pull-Up Bar]]",
    "preacher curl machine": "[[Preacher Curl Machine]]",
    "seated calf raise machine": "[[Seated Calf Raise Machine]]",
    "seated leg curl machine": "[[Seated Leg Curl Machine]]",
    "smith machine": "[[Smith Machine]]",
    "step platform": "[[Step Platform]]",
}


class CommonExerciseFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    exercise_kind: ExerciseKind
    tags: list[str] = Field(default_factory=list)
    programme: str | None = None
    equipment: list[str] = Field(default_factory=list)
    progression_mode: ProgressionMode
    volume_tracking: VolumeTracking
    volume_primary_credit: float = Field(ge=0.0, le=1.0)
    volume_secondary_credit: float = Field(ge=0.0, le=1.0)
    aliases: list[str] = Field(default_factory=list)
    strong_exercise_names: list[str] = Field(default_factory=list)
    strong_weight_unit: LoadUnit | None = None
    training_log_source: TrainingLogSource | None = None
    strong_last_synced_at: str | None = None
    strong_session_count: int | None = Field(default=None, ge=0)
    strong_work_set_count: int | None = Field(default=None, ge=0)
    logged_sessions: int | None = Field(default=None, ge=0)
    avg_weekly_primary_sets_6w: float | None = Field(default=None, ge=0.0)
    avg_weekly_secondary_sets_6w: float | None = Field(default=None, ge=0.0)
    progression_trend: ProgressionTrend | None = None
    progression_delta_pct: float | None = None
    recommendation_signal: RecommendationSignal | None = None
    top_set_load: float | None = Field(default=None, ge=0.0)
    top_set_reps: float | None = Field(default=None, ge=0.0)
    top_set_unit: LoadUnit | None = None
    top_set_volume: float | None = Field(default=None, ge=0.0)
    working_avg_load: float | None = Field(default=None, ge=0.0)
    working_avg_reps: float | None = Field(default=None, ge=0.0)
    working_avg_unit: LoadUnit | None = None

    @field_validator("programme")
    @classmethod
    def validate_programme(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not is_wikilink(value):
            raise ValueError(f"`programme` must be an Obsidian wikilink. Got: {value!r}")
        return value

    @field_validator("equipment", "aliases", "tags", "strong_exercise_names")
    @classmethod
    def validate_string_lists(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Expected a YAML list.")
        return [str(item) for item in value]

    @field_validator("equipment")
    @classmethod
    def validate_equipment_links(cls, value: list[str]) -> list[str]:
        for item in value:
            if not is_wikilink(item):
                raise ValueError(f"`equipment` entries must be wikilinks. Got: {item!r}")
        return value

    @model_validator(mode="after")
    def validate_tags(self) -> "CommonExerciseFrontmatter":
        required = set(MODEL_TO_REQUIRED_TAGS[self.exercise_kind]) | {f"exercise-kind/{self.exercise_kind.value}"}
        missing = required - set(self.tags)
        if missing:
            raise ValueError(f"`tags` must include: {sorted(missing)}. Got: {self.tags}")
        return self

    @model_validator(mode="after")
    def validate_volume_consistency(self) -> "CommonExerciseFrontmatter":
        expected = volume_credits_for(self.volume_tracking)
        actual = (round(self.volume_primary_credit, 3), round(self.volume_secondary_credit, 3))
        if actual != expected:
            raise ValueError(
                f"`volume_primary_credit`/`volume_secondary_credit` must match {self.volume_tracking.value}: "
                f"expected {expected}, got {actual}"
            )
        if self.top_set_load is not None and self.top_set_reps is not None and self.top_set_volume is not None:
            if abs((self.top_set_load * self.top_set_reps) - self.top_set_volume) > 0.5:
                raise ValueError("`top_set_volume` must equal `top_set_load * top_set_reps` when both are present.")
        if self.training_log_source == TrainingLogSource.STRONG_CSV and not self.strong_exercise_names:
            raise ValueError("`training_log_source: strong_csv` requires a non-empty `strong_exercise_names` list.")
        return self


class HypertrophyExerciseFrontmatter(CommonExerciseFrontmatter):
    exercise_kind: ExerciseKind = ExerciseKind.HYPERTROPHY
    category: str
    region: Region
    pattern: Pattern
    primary_muscle: str
    muscle_group: list[str]
    secondary_muscles: list[str] = Field(default_factory=list)
    force_profile: ForceProfile
    stability_profile: StabilityProfile
    fatigue_cost: FatigueCost
    progression_mode: ProgressionMode = ProgressionMode.LOAD_REPS
    volume_tracking: VolumeTracking = VolumeTracking.PRIMARY_ONLY

    @field_validator("primary_muscle")
    @classmethod
    def validate_primary_muscle(cls, value: str) -> str:
        if not is_wikilink(value):
            raise ValueError("`primary_muscle` must be a wikilink.")
        return value

    @field_validator("muscle_group")
    @classmethod
    def validate_muscle_group(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("`muscle_group` must be a non-empty list for hypertrophy exercises.")
        for item in value:
            if not is_wikilink(item):
                raise ValueError(f"Muscle entries must be wikilinks. Got: {item!r}")
        return value

    @field_validator("secondary_muscles")
    @classmethod
    def validate_secondary_muscles(cls, value: list[str]) -> list[str]:
        for item in value:
            if not is_wikilink(item):
                raise ValueError(f"Muscle entries must be wikilinks. Got: {item!r}")
        return value

    @model_validator(mode="after")
    def validate_category(self) -> "HypertrophyExerciseFrontmatter":
        if self.category != "hypertrophy":
            raise ValueError("`hypertrophy` exercises require `category: hypertrophy`.")
        if self.volume_tracking not in {VolumeTracking.PRIMARY_ONLY, VolumeTracking.SECONDARY_HALF}:
            raise ValueError("Hypertrophy exercises must use `primary_only` or `secondary_half` volume tracking.")
        return self


class MobilityDrillFrontmatter(CommonExerciseFrontmatter):
    exercise_kind: ExerciseKind = ExerciseKind.MOBILITY_DRILL
    category: str
    region: Region
    pattern: Pattern
    primary_muscle: str
    muscle_group: list[str]
    secondary_muscles: list[str] = Field(default_factory=list)
    force_profile: ForceProfile
    stability_profile: StabilityProfile
    fatigue_cost: FatigueCost = FatigueCost.LOW
    progression_mode: ProgressionMode = ProgressionMode.QUALITY
    volume_tracking: VolumeTracking = VolumeTracking.NOT_COUNTED

    @field_validator("primary_muscle")
    @classmethod
    def validate_primary_muscle(cls, value: str) -> str:
        if not is_wikilink(value):
            raise ValueError("`primary_muscle` must be a wikilink.")
        return value

    @field_validator("muscle_group")
    @classmethod
    def validate_muscle_group(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Mobility drills require a non-empty `muscle_group` list.")
        for item in value:
            if not is_wikilink(item):
                raise ValueError(f"Muscle entries must be wikilinks. Got: {item!r}")
        return value

    @field_validator("secondary_muscles")
    @classmethod
    def validate_secondary_muscles(cls, value: list[str]) -> list[str]:
        for item in value:
            if not is_wikilink(item):
                raise ValueError(f"Muscle entries must be wikilinks. Got: {item!r}")
        return value

    @model_validator(mode="after")
    def validate_category(self) -> "MobilityDrillFrontmatter":
        if self.category != "mobility":
            raise ValueError("`mobility_drill` notes require `category: mobility`.")
        if self.fatigue_cost == FatigueCost.HIGH:
            raise ValueError("Mobility drills must not have `fatigue_cost: high`.")
        return self


class WarmupFlowFrontmatter(CommonExerciseFrontmatter):
    exercise_kind: ExerciseKind = ExerciseKind.WARMUP_FLOW
    duration: str
    component_exercises: list[str]
    progression_mode: ProgressionMode = ProgressionMode.DURATION
    volume_tracking: VolumeTracking = VolumeTracking.NOT_COUNTED

    @field_validator("component_exercises")
    @classmethod
    def validate_components(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Warm-up flows require `component_exercises`.")
        for item in value:
            if not is_wikilink(item):
                raise ValueError(f"`component_exercises` entries must be wikilinks. Got: {item!r}")
        return value


class ExerciseBriefFrontmatter(CommonExerciseFrontmatter):
    exercise_kind: ExerciseKind = ExerciseKind.EXERCISE_BRIEF
    progression_mode: ProgressionMode = ProgressionMode.QUALITY
    volume_tracking: VolumeTracking = VolumeTracking.NOT_COUNTED


MODEL_BY_KIND: dict[ExerciseKind, type[CommonExerciseFrontmatter]] = {
    ExerciseKind.HYPERTROPHY: HypertrophyExerciseFrontmatter,
    ExerciseKind.MOBILITY_DRILL: MobilityDrillFrontmatter,
    ExerciseKind.WARMUP_FLOW: WarmupFlowFrontmatter,
    ExerciseKind.EXERCISE_BRIEF: ExerciseBriefFrontmatter,
}


@dataclass
class NoteParts:
    path: Path
    frontmatter: dict[str, Any]
    body: str


@dataclass
class ParsedSetMetric:
    load: float | None = None
    reps: float | None = None
    unit: LoadUnit | None = None

    @property
    def volume(self) -> float | None:
        if self.load is None or self.reps is None:
            return None
        return round(self.load * self.reps, 2)


@dataclass
class TrainingMetrics:
    logged_sessions: int | None = None
    top_set_load: float | None = None
    top_set_reps: float | None = None
    top_set_unit: str | None = None
    top_set_volume: float | None = None
    working_avg_load: float | None = None
    working_avg_reps: float | None = None
    working_avg_unit: str | None = None
    last_performed: str | None = None

    def as_updates(self) -> dict[str, Any]:
        payload = {
            "logged_sessions": self.logged_sessions,
            "top_set_load": self.top_set_load,
            "top_set_reps": self.top_set_reps,
            "top_set_unit": self.top_set_unit,
            "top_set_volume": self.top_set_volume,
            "working_avg_load": self.working_avg_load,
            "working_avg_reps": self.working_avg_reps,
            "working_avg_unit": self.working_avg_unit,
            "last_performed": self.last_performed,
        }
        return {key: value for key, value in payload.items() if value is not None}


def is_wikilink(value: str) -> bool:
    return bool(WIKILINK_RE.fullmatch(str(value).strip()))


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(normalize_jsonable(payload), indent=2)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find(FRONTMATTER_DELIM, 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len(FRONTMATTER_DELIM) :]
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise ValueError("Frontmatter must deserialize to a mapping.")
    return normalize_jsonable(dict(payload)), body


def load_markdown_note(path: Path) -> NoteParts:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    return NoteParts(path=path, frontmatter=frontmatter, body=body)


def dedupe_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def order_frontmatter(frontmatter: dict[str, Any], original_key_order: list[str] | None = None) -> OrderedDict[str, Any]:
    ordered: OrderedDict[str, Any] = OrderedDict()
    original_key_order = original_key_order or list(frontmatter.keys())
    for key in EXERCISE_FRONTMATTER_ORDER:
        if key in frontmatter:
            ordered[key] = frontmatter[key]
    for key in original_key_order:
        if key in frontmatter and key not in ordered:
            ordered[key] = frontmatter[key]
    for key, value in frontmatter.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    class _NoAliasSafeDumper(yaml.SafeDumper):
        def ignore_aliases(self, data: Any) -> bool:  # pragma: no cover - dumper hook
            return True

    payload = yaml.dump(
        normalize_jsonable(frontmatter),
        Dumper=_NoAliasSafeDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    ).strip()
    return f"---\n{payload}\n---\n"


def render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    normalized_body = body.lstrip("\n").rstrip() + "\n"
    return dump_frontmatter(frontmatter) + "\n" + normalized_body


def parse_frontmatter(frontmatter: dict[str, Any]) -> CommonExerciseFrontmatter:
    kind = ExerciseKind(str(frontmatter.get("exercise_kind")))
    model_cls = MODEL_BY_KIND[kind]
    return model_cls.model_validate(frontmatter)


def validate_frontmatter(frontmatter: dict[str, Any]) -> tuple[bool, list[str]]:
    try:
        parse_frontmatter(frontmatter)
    except ValidationError as exc:
        return False, [error["msg"] for error in exc.errors()]
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return False, [str(exc)]
    return True, []


def clean_link_text(value: str) -> str:
    match = WIKILINK_RE.search(str(value))
    return match.group(1).strip() if match else str(value).strip()


def normalize_link(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        return raw
    if is_wikilink(raw):
        return raw
    return f"[[{raw}]]"


def normalize_equipment_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    items: list[str] = []
    if isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item).strip()]
    else:
        compact = str(raw).replace(" and/or ", ",").replace(" / ", ",")
        items = [part.strip() for part in compact.split(",") if part.strip()]
    normalized: list[str] = []
    for item in items:
        if is_wikilink(item):
            normalized.append(item)
            continue
        token = item.lower()
        normalized.append(EQUIPMENT_ALIASES.get(token, normalize_link(item.title())))
    return dedupe_preserve(normalized)


def ensure_string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def volume_credits_for(volume_tracking: VolumeTracking | str) -> tuple[float, float]:
    mode = VolumeTracking(str(volume_tracking))
    if mode == VolumeTracking.PRIMARY_ONLY:
        return (1.0, 0.0)
    if mode == VolumeTracking.SECONDARY_HALF:
        return (1.0, 0.5)
    return (0.0, 0.0)


def normalize_text_key(value: str) -> str:
    raw = str(value).strip().lower()
    raw = raw.replace("&", "and")
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    return " ".join(raw.split())


def normalize_exercise_tags(frontmatter: dict[str, Any], *, kind: ExerciseKind) -> list[str]:
    raw = ensure_string_list(frontmatter.get("tags"))
    tags = [tag for tag in raw if tag != "type/exercise" and not tag.startswith("exercise-kind/")]
    managed = ["type/exercise", f"exercise-kind/{kind.value}"]
    for tag in MODEL_TO_REQUIRED_TAGS[kind]:
        if tag != "type/exercise":
            managed.append(tag)
    return dedupe_preserve(managed + tags)


def infer_exercise_kind(frontmatter: dict[str, Any], body: str, path: Path) -> tuple[ExerciseKind, bool]:
    raw_kind = str(frontmatter.get("exercise_kind") or "").strip()
    if raw_kind:
        return ExerciseKind(raw_kind), False

    tags = set(ensure_string_list(frontmatter.get("tags")))
    category = str(frontmatter.get("category") or "").strip().lower()
    has_primary = bool(frontmatter.get("primary_muscle"))
    body_links = extract_body_links(body)

    if category == "hypertrophy":
        return ExerciseKind.HYPERTROPHY, False
    if category == "mobility":
        return ExerciseKind.MOBILITY_DRILL, False
    if "fitness/warmup" in tags and frontmatter.get("duration") and len(body_links) >= 3:
        return ExerciseKind.WARMUP_FLOW, False
    if "fitness/mobility" in tags and not has_primary:
        return ExerciseKind.EXERCISE_BRIEF, False
    if "fitness/warmup" in tags and not has_primary:
        return ExerciseKind.EXERCISE_BRIEF, False
    return ExerciseKind.EXERCISE_BRIEF, True


def extract_body_links(body: str) -> list[str]:
    return dedupe_preserve(match.group(0) for match in WIKILINK_RE.finditer(body))


def infer_component_exercises(body: str) -> list[str]:
    return dedupe_preserve(normalize_link(match.group(1).strip()) for match in WIKILINK_RE.finditer(body))


def infer_progression_mode(kind: ExerciseKind, frontmatter: dict[str, Any]) -> ProgressionMode:
    if kind == ExerciseKind.HYPERTROPHY:
        return ProgressionMode.LOAD_REPS
    if kind == ExerciseKind.WARMUP_FLOW and frontmatter.get("duration"):
        return ProgressionMode.DURATION
    return ProgressionMode.QUALITY


def infer_volume_tracking(kind: ExerciseKind, frontmatter: dict[str, Any]) -> VolumeTracking:
    raw = str(frontmatter.get("volume_tracking") or "").strip()
    if raw:
        return VolumeTracking(raw)
    if kind == ExerciseKind.HYPERTROPHY:
        return VolumeTracking.PRIMARY_ONLY
    return VolumeTracking.NOT_COUNTED


def derive_secondary_muscles(frontmatter: dict[str, Any]) -> list[str]:
    primary = str(frontmatter.get("primary_muscle") or "").strip()
    muscles = ensure_string_list(frontmatter.get("muscle_group"))
    return [item for item in dedupe_preserve(muscles) if item != primary]


def infer_strong_exercise_names(frontmatter: dict[str, Any], path: Path) -> list[str]:
    names = ensure_string_list(frontmatter.get("strong_exercise_names"))
    if names:
        return dedupe_preserve(names)

    candidates = [frontmatter.get("strong_name"), *ensure_string_list(frontmatter.get("aliases")), path.stem]
    return dedupe_preserve(candidate for candidate in candidates if candidate)


def infer_strong_weight_unit(frontmatter: dict[str, Any], kind: ExerciseKind) -> LoadUnit | None:
    raw = str(frontmatter.get("strong_weight_unit") or "").strip()
    if raw:
        return LoadUnit(raw)

    top_unit = str(frontmatter.get("top_set_unit") or "").strip()
    if top_unit:
        return LoadUnit(top_unit)

    if kind != ExerciseKind.HYPERTROPHY:
        return None
    return LoadUnit.KG


def selection_score_for_frontmatter(frontmatter: dict[str, Any]) -> float:
    if str(frontmatter.get("exercise_kind") or "") != ExerciseKind.HYPERTROPHY.value:
        return 0.0

    force = str(frontmatter.get("force_profile") or "")
    stability = str(frontmatter.get("stability_profile") or "")
    fatigue = str(frontmatter.get("fatigue_cost") or "")
    volume_tracking = str(frontmatter.get("volume_tracking") or VolumeTracking.PRIMARY_ONLY.value)

    force_score = 2.0 if force == ForceProfile.LENGTHENED.value else 1.0 if force == ForceProfile.MID_RANGE.value else 0.0
    stability_score = 2.0 if stability == StabilityProfile.HIGH.value else 1.0 if stability == StabilityProfile.MEDIUM.value else 0.0
    fatigue_score = 2.0 if fatigue == FatigueCost.LOW.value else 1.0 if fatigue == FatigueCost.MODERATE.value else 0.0
    volume_score = 1.0 if volume_tracking == VolumeTracking.PRIMARY_ONLY.value else 0.5 if volume_tracking == VolumeTracking.SECONDARY_HALF.value else 0.0
    return round(force_score + stability_score + fatigue_score + volume_score, 2)


def infer_stability_profile(frontmatter: dict[str, Any], kind: ExerciseKind, path: Path) -> StabilityProfile:
    raw = str(frontmatter.get("stability_profile") or "").strip()
    if raw:
        return StabilityProfile(raw)

    title = path.stem.lower()
    equipment = {clean_link_text(item).lower() for item in normalize_equipment_list(frontmatter.get("equipment"))}
    pattern = str(frontmatter.get("pattern") or "").strip().lower()

    high_markers = {
        "smith machine",
        "cable machine",
        "leg extension machine",
        "leg press machine",
        "lateral raise machine",
        "preacher curl machine",
        "cable row machine",
        "seated calf raise machine",
        "seated leg curl machine",
        "chest fly machine",
        "incline bench",
        "bench",
    }
    low_markers = {"barbell"}

    if kind == ExerciseKind.WARMUP_FLOW:
        return StabilityProfile.MEDIUM
    if "machine" in title or "smith" in title or "seated" in title or "supported" in title or "preacher" in title:
        return StabilityProfile.HIGH
    if equipment & high_markers:
        return StabilityProfile.HIGH
    if equipment == low_markers and pattern in {"hinge", "squat"}:
        return StabilityProfile.LOW
    return StabilityProfile.MEDIUM


def infer_fatigue_cost(frontmatter: dict[str, Any], kind: ExerciseKind, path: Path) -> FatigueCost:
    raw = str(frontmatter.get("fatigue_cost") or "").strip()
    if raw:
        return FatigueCost(raw)

    if kind in {ExerciseKind.MOBILITY_DRILL, ExerciseKind.WARMUP_FLOW, ExerciseKind.EXERCISE_BRIEF}:
        return FatigueCost.LOW

    title = path.stem.lower()
    pattern = str(frontmatter.get("pattern") or "").strip().lower()
    equipment = {clean_link_text(item).lower() for item in normalize_equipment_list(frontmatter.get("equipment"))}

    if pattern == "isolation":
        return FatigueCost.LOW
    if "machine" in title or "smith" in title or "cable" in title or "supported" in title:
        return FatigueCost.LOW
    if "pull-up" in title or "ab-wheel" in title or "hip thrust" in title:
        return FatigueCost.MODERATE
    if equipment == {"barbell"} and pattern in {"hinge", "squat", "lunge"}:
        return FatigueCost.MODERATE
    if pattern in {"hinge", "squat", "lunge"}:
        return FatigueCost.MODERATE
    return FatigueCost.LOW


def parse_set_metric(raw: str) -> ParsedSetMetric:
    text = str(raw).strip()
    if not text:
        return ParsedSetMetric()
    match = LOAD_REPS_RE.search(text)
    if match:
        unit = match.group("unit").lower()
        normalized_unit = LoadUnit.KG if unit in {"kg", "kgs"} else LoadUnit.LBS
        return ParsedSetMetric(
            load=float(match.group("load")),
            reps=float(match.group("reps")),
            unit=normalized_unit,
        )
    match = BODYWEIGHT_REPS_RE.search(text)
    if match:
        return ParsedSetMetric(load=None, reps=float(match.group("reps")), unit=LoadUnit.BODYWEIGHT)
    return ParsedSetMetric()


def infer_last_performed_from_body(body: str) -> str | None:
    matches = TRAINING_ROW_RE.findall(body)
    return matches[-1] if matches else None


def extract_training_metrics(body: str) -> TrainingMetrics:
    metrics = TrainingMetrics(last_performed=infer_last_performed_from_body(body))

    sessions_match = SESSIONS_RE.search(body)
    if sessions_match:
        metrics.logged_sessions = int(sessions_match.group(1))

    top_match = TOP_SET_RE.search(body)
    if top_match:
        parsed = parse_set_metric(top_match.group(1))
        metrics.top_set_load = parsed.load
        metrics.top_set_reps = parsed.reps
        metrics.top_set_unit = parsed.unit.value if parsed.unit else None
        metrics.top_set_volume = parsed.volume

    avg_match = WORKING_AVG_RE.search(body)
    if avg_match:
        parsed = parse_set_metric(avg_match.group(1))
        metrics.working_avg_load = parsed.load
        metrics.working_avg_reps = parsed.reps
        metrics.working_avg_unit = parsed.unit.value if parsed.unit else None

    return metrics
