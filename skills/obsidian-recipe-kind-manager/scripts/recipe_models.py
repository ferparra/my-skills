#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
FRONTMATTER_DELIM = "\n---\n"

RECIPE_FILE_GLOB = "20 Resources/Nutrition/*.md"
INGREDIENTS_PATH = "20 Resources/Ingredients"
KITCHEN_EQUIPMENT_PATH = "20 Resources/Kitchen Equipment"
RECIPE_BASE_PATH = "20 Resources/Nutrition/Recipe Library.base"
NUTRITION_PROGRAMME_PATH = "20 Resources/Nutrition/Nutrition Programme 2026.md"

RECIPE_FRONTMATTER_ORDER = [
    "recipe_kind",
    "title",
    "description",
    "tags",
    "status",
    "para_type",
    "servings",
    "prep_time_min",
    "cook_time_min",
    "macros",
    "ingredients",
    "equipment",
    "steps",
    "source",
    "cuisine",
    "programme",
    "aliases",
]


class RecipeKind(StrEnum):
    MAIN_COURSE = "main_course"
    SIDE_DISH = "side_dish"
    SNACK = "snack"
    SMOOTHIE = "smoothie"
    SOUP = "soup"
    DESSERT = "dessert"


class RecipeStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PROCESSED = "processed"
    ARCHIVED = "archived"


class ParaType(StrEnum):
    RESOURCE = "resource"


class Macros(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calories: int = Field(
        ...,
        ge=0,
        description="Total calories per serving (kcal)",
    )
    protein_g: float = Field(
        ...,
        ge=0.0,
        description="Protein per serving in grams",
    )
    carbs_g: float = Field(
        ...,
        ge=0.0,
        description="Carbohydrates per serving in grams",
    )
    fat_g: float = Field(
        ...,
        ge=0.0,
        description="Fat per serving in grams",
    )


class IngredientRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(
        ...,
        description="Wikilink to the ingredient note, e.g. '[[20 Resources/Ingredients/Yumi\\'s Chipotle Hommus Dip 200g]]'",
    )
    quantity: str = Field(
        ...,
        description="Human-readable quantity, e.g. '250 g', '1 tbsp', '2 slices'",
    )

    @field_validator("ref")
    @classmethod
    def validate_ref_is_wikilink(cls, value: str) -> str:
        if not is_wikilink(value):
            raise ValueError(f"`ref` must be a wikilink. Got: {value!r}")
        return value


class RecipeFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    # ── Required ──────────────────────────────────────────────
    recipe_kind: RecipeKind = Field(
        ...,
        description="Kind selector: determines the schema contract for the recipe note",
    )
    title: str = Field(
        ...,
        min_length=1,
        description="Display title of the recipe, matches the note filename",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="One-sentence summary of the recipe",
    )
    servings: int = Field(
        ...,
        gt=0,
        description="Number of servings the recipe yields",
    )
    prep_time_min: int = Field(
        ...,
        ge=0,
        description="Preparation time in minutes (active work, excluding cooking)",
    )
    cook_time_min: int = Field(
        default=0,
        ge=0,
        description="Cooking time in minutes (passive, e.g. baking, simmering, pressure cooking)",
    )
    macros: Macros = Field(
        ...,
        description="Per-serving macronutrient breakdown",
    )
    ingredients: list[IngredientRef] = Field(
        ...,
        min_length=1,
        description="Ordered list of ingredient references with quantities",
    )
    steps: list[str] = Field(
        ...,
        min_length=1,
        description="Ordered list of preparation/cooking steps",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Managed and user tags; managed prefixes are enforced",
    )

    # ── Optional ──────────────────────────────────────────────
    status: RecipeStatus = Field(
        default=RecipeStatus.DRAFT,
        description="Lifecycle status of the recipe note",
    )
    para_type: ParaType = Field(
        default=ParaType.RESOURCE,
        description="PARA category; always 'resource' for recipes",
    )
    equipment: list[str] = Field(
        default_factory=list,
        description="Wikilinks to kitchen equipment notes in 20 Resources/Kitchen Equipment/",
    )
    source: str | None = Field(
        default=None,
        description="Attribution or origin of the recipe, e.g. 'Traditional Sichuan (宫保鸡丁)'",
    )
    cuisine: str | None = Field(
        default=None,
        description="Cuisine tag, e.g. 'sichuan', 'argentine', 'australian'",
    )
    programme: str | None = Field(
        default=None,
        description="Wikilink to the nutrition programme note",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names for Obsidian search",
    )

    # ── Validators ────────────────────────────────────────────

    @field_validator("tags")
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
                raise ValueError(
                    f"`equipment` entries must be wikilinks. Got: {item!r}"
                )
        return value

    @field_validator("programme")
    @classmethod
    def validate_programme(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not is_wikilink(value):
            raise ValueError(f"`programme` must be an Obsidian wikilink. Got: {value!r}")
        return value

    @field_validator("steps")
    @classmethod
    def validate_steps_non_empty(cls, value: list[str]) -> list[str]:
        for i, step in enumerate(value):
            if not str(step).strip():
                raise ValueError(f"`steps[{i}]` must be a non-empty string.")
        return value

    @model_validator(mode="after")
    def validate_tag_requirements(self) -> "RecipeFrontmatter":
        required = {
            "type/recipe",
            f"recipe-kind/{self.recipe_kind.value}",
            f"status/{self.status.value}",
        }
        missing = required - set(self.tags)
        if missing:
            raise ValueError(
                f"`tags` must include: {sorted(missing)}. Got: {self.tags}"
            )
        return self

    @model_validator(mode="after")
    def validate_para_type(self) -> "RecipeFrontmatter":
        if self.para_type != ParaType.RESOURCE:
            raise ValueError(
                f"`para_type` must be 'resource' for recipe notes. Got: {self.para_type.value!r}"
            )
        return self


# ── Kind-to-required-tags mapping ────────────────────────────
MODEL_TO_REQUIRED_TAGS: dict[RecipeKind, tuple[str, ...]] = {
    RecipeKind.MAIN_COURSE: ("type/recipe", "health/recipe", "health/nutrition"),
    RecipeKind.SIDE_DISH: ("type/recipe", "health/recipe"),
    RecipeKind.SNACK: ("type/recipe", "health/recipe"),
    RecipeKind.SMOOTHIE: ("type/recipe", "health/recipe", "health/nutrition"),
    RecipeKind.SOUP: ("type/recipe", "health/recipe"),
    RecipeKind.DESSERT: ("type/recipe", "health/recipe"),
}


# ── Helper dataclasses / models ──────────────────────────────

class NoteParts(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    frontmatter: dict[str, Any]
    body: str


class ValidationResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)


class AuditResult(BaseModel):
    path: str
    ok: bool
    recipe_kind: str | None = None
    inferred_recipe_kind: str | None = None
    status: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    frontmatter_keys: list[str] = Field(default_factory=list)


class MigrateResult(BaseModel):
    path: str
    changed: bool
    changed_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


# ── Utility functions ────────────────────────────────────────

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
    body = text[end + len(FRONTMATTER_DELIM):]
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


def ensure_string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def order_frontmatter(
    frontmatter: dict[str, Any],
    original_key_order: list[str] | None = None,
) -> OrderedDict[str, Any]:
    ordered: OrderedDict[str, Any] = OrderedDict()
    original_key_order = original_key_order or list(frontmatter.keys())
    for key in RECIPE_FRONTMATTER_ORDER:
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
        def ignore_aliases(self, data: Any) -> bool:
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


def validate_frontmatter(frontmatter: dict[str, Any]) -> ValidationResult:
    try:
        RecipeFrontmatter.model_validate(frontmatter)
    except ValidationError as exc:
        return ValidationResult(ok=False, errors=[error["msg"] for error in exc.errors()])
    except Exception as exc:
        return ValidationResult(ok=False, errors=[str(exc)])
    return ValidationResult(ok=True)


def normalize_recipe_tags(
    frontmatter: dict[str, Any],
    *,
    kind: str,
    status: str,
) -> list[str]:
    raw = ensure_string_list(frontmatter.get("tags"))
    managed_prefixes = ("type/recipe", "recipe-kind/", "status/")
    user_tags = [t for t in raw if not any(t == p or t.startswith(p) for p in managed_prefixes)]
    managed = [
        "type/recipe",
        f"recipe-kind/{kind}",
        f"status/{status}",
    ]
    return dedupe_preserve(managed + user_tags)


def infer_recipe_kind(frontmatter: dict[str, Any]) -> RecipeKind | None:
    """Infer kind from existing signals. Never overwrites an explicit kind."""
    raw_kind = str(frontmatter.get("recipe_kind") or "").strip()
    if raw_kind:
        try:
            return RecipeKind(raw_kind)
        except ValueError:
            pass

    tags = set(ensure_string_list(frontmatter.get("tags")))
    title = str(frontmatter.get("title") or frontmatter.get("name") or "").lower()
    type_tag = str(frontmatter.get("type") or "").lower()

    # Check tags first for recipe sub-type hints
    if "type/recipe/smoothie" in tags or "smoothie" in title:
        return RecipeKind.SMOOTHIE
    if "type/recipe/soup" in tags or "soup" in title:
        return RecipeKind.SOUP
    if "type/recipe/dessert" in tags or "dessert" in title:
        return RecipeKind.DESSERT
    if "type/recipe/side-dish" in tags or "side" in title:
        return RecipeKind.SIDE_DISH
    if "type/recipe/snack" in tags or "snack" in title:
        return RecipeKind.SNACK
    if "type/recipe/main-course" in tags or type_tag == "recipe":
        return RecipeKind.MAIN_COURSE

    # Default for nutrition-directory recipes
    return RecipeKind.MAIN_COURSE


def infer_status_from_tags(frontmatter: dict[str, Any]) -> RecipeStatus:
    tags = [str(t) for t in ensure_string_list(frontmatter.get("tags"))]
    raw_status = str(frontmatter.get("status") or "").strip().lower()
    if raw_status == "processed" or "status/processed" in tags:
        return RecipeStatus.PROCESSED
    if raw_status == "active" or "status/active" in tags:
        return RecipeStatus.ACTIVE
    if raw_status == "archived":
        return RecipeStatus.ARCHIVED
    return RecipeStatus.DRAFT
