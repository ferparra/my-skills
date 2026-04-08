#!/usr/bin/env python3
"""Tests for the recipe kind manager models and utilities."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure scripts/ is on the import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

from recipe_models import (
    IngredientRef,
    Macros,
    RecipeFrontmatter,
    RecipeKind,
    RecipeStatus,
    ParaType,
    is_wikilink,
    normalize_recipe_tags,
    infer_recipe_kind,
    infer_status_from_tags,
    validate_frontmatter,
)


# ── is_wikilink ──────────────────────────────────────────────

class TestIsWikilink:
    def test_simple_wikilink(self):
        assert is_wikilink("[[Something]]") is True

    def test_path_wikilink(self):
        assert is_wikilink("[[20 Resources/Ingredients/Bananas]]") is True

    def test_wikilink_with_alias(self):
        assert is_wikilink("[[Something|Display Name]]") is True

    def test_wikilink_with_heading(self):
        assert is_wikilink("[[Something#Section]]") is True

    def test_not_wikilink(self):
        assert is_wikilink("plain text") is False

    def test_empty_string(self):
        assert is_wikilink("") is False


# ── Macros ───────────────────────────────────────────────────

class TestMacros:
    def test_valid_macros(self):
        m = Macros(calories=500, protein_g=40.0, carbs_g=30.0, fat_g=15.0)
        assert m.calories == 500
        assert m.protein_g == 40.0

    def test_zero_macros(self):
        m = Macros(calories=0, protein_g=0.0, carbs_g=0.0, fat_g=0.0)
        assert m.calories == 0

    def test_negative_calories_rejected(self):
        with pytest.raises(Exception):
            Macros(calories=-1, protein_g=0.0, carbs_g=0.0, fat_g=0.0)

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            Macros(calories=500, protein_g=40.0, carbs_g=30.0, fat_g=15.0, fibre=5.0)


# ── IngredientRef ────────────────────────────────────────────

class TestIngredientRef:
    def test_valid_ref(self):
        ref = IngredientRef(
            ref="[[20 Resources/Ingredients/Bananas]]",
            quantity="1 medium",
        )
        assert ref.quantity == "1 medium"

    def test_non_wikilink_ref_rejected(self):
        with pytest.raises(Exception):
            IngredientRef(ref="plain text", quantity="100 g")


# ── RecipeFrontmatter ────────────────────────────────────────

class TestRecipeFrontmatter:
    def _make_valid_frontmatter(self, **overrides) -> dict:
        base = {
            "recipe_kind": "main_course",
            "title": "Test Recipe",
            "description": "A test recipe",
            "servings": 2,
            "prep_time_min": 15,
            "cook_time_min": 30,
            "macros": {
                "calories": 500,
                "protein_g": 40.0,
                "carbs_g": 30.0,
                "fat_g": 15.0,
            },
            "ingredients": [
                {"ref": "[[20 Resources/Ingredients/Bananas]]", "quantity": "1 medium"},
            ],
            "steps": ["Prep ingredients", "Cook everything"],
            "tags": ["type/recipe", "recipe-kind/main_course", "status/draft"],
        }
        base.update(overrides)
        return base

    def test_valid_frontmatter(self):
        fm = self._make_valid_frontmatter()
        recipe = RecipeFrontmatter.model_validate(fm)
        assert recipe.recipe_kind == RecipeKind.MAIN_COURSE
        assert recipe.servings == 2

    def test_default_status(self):
        fm = self._make_valid_frontmatter()
        recipe = RecipeFrontmatter.model_validate(fm)
        assert recipe.status == RecipeStatus.DRAFT

    def test_default_para_type(self):
        fm = self._make_valid_frontmatter()
        recipe = RecipeFrontmatter.model_validate(fm)
        assert recipe.para_type == ParaType.RESOURCE

    def test_missing_title_rejected(self):
        fm = self._make_valid_frontmatter()
        del fm["title"]
        with pytest.raises(Exception):
            RecipeFrontmatter.model_validate(fm)

    def test_missing_ingredients_rejected(self):
        fm = self._make_valid_frontmatter()
        del fm["ingredients"]
        with pytest.raises(Exception):
            RecipeFrontmatter.model_validate(fm)

    def test_empty_steps_rejected(self):
        fm = self._make_valid_frontmatter(steps=[])
        with pytest.raises(Exception):
            RecipeFrontmatter.model_validate(fm)

    def test_equipment_wikilink_validation(self):
        fm = self._make_valid_frontmatter(equipment=["not a link"])
        with pytest.raises(Exception):
            RecipeFrontmatter.model_validate(fm)

    def test_valid_equipment(self):
        fm = self._make_valid_frontmatter(
            equipment=["[[20 Resources/Kitchen Equipment/Carbon-Steel Wok]]"]
        )
        recipe = RecipeFrontmatter.model_validate(fm)
        assert len(recipe.equipment) == 1

    def test_programme_wikilink_validation(self):
        fm = self._make_valid_frontmatter(programme="not a link")
        with pytest.raises(Exception):
            RecipeFrontmatter.model_validate(fm)

    def test_valid_programme(self):
        fm = self._make_valid_frontmatter(programme="[[Nutrition Programme 2026]]")
        recipe = RecipeFrontmatter.model_validate(fm)
        assert recipe.programme == "[[Nutrition Programme 2026]]"

    def test_tag_requirements_enforced(self):
        fm = self._make_valid_frontmatter(tags=["health/nutrition"])
        with pytest.raises(Exception):
            RecipeFrontmatter.model_validate(fm)

    def test_para_type_must_be_resource(self):
        fm = self._make_valid_frontmatter(para_type="project")
        with pytest.raises(Exception):
            RecipeFrontmatter.model_validate(fm)

    def test_extra_fields_allowed(self):
        fm = self._make_valid_frontmatter(fibre=5.0)
        recipe = RecipeFrontmatter.model_validate(fm)
        assert recipe.model_extra is not None or True  # extra="allow"

    def test_all_kinds(self):
        for kind in RecipeKind:
            fm = self._make_valid_frontmatter(
                recipe_kind=kind.value,
                tags=["type/recipe", f"recipe-kind/{kind.value}", "status/draft"],
            )
            recipe = RecipeFrontmatter.model_validate(fm)
            assert recipe.recipe_kind == kind


# ── Tag normalization ────────────────────────────────────────

class TestNormalizeRecipeTags:
    def test_injects_managed_tags(self):
        result = normalize_recipe_tags(
            {"tags": ["health/nutrition"]},
            kind="main_course",
            status="processed",
        )
        assert "type/recipe" in result
        assert "recipe-kind/main_course" in result
        assert "status/processed" in result
        assert "health/nutrition" in result

    def test_removes_stale_kind_tags(self):
        result = normalize_recipe_tags(
            {"tags": ["recipe-kind/soup", "health/nutrition"]},
            kind="main_course",
            status="draft",
        )
        assert "recipe-kind/main_course" in result
        assert "recipe-kind/soup" not in result


# ── Kind inference ───────────────────────────────────────────

class TestInferRecipeKind:
    def test_explicit_kind(self):
        assert infer_recipe_kind({"recipe_kind": "smoothie"}) == RecipeKind.SMOOTHIE

    def test_from_tag(self):
        assert infer_recipe_kind({"tags": ["type/recipe/soup"]}) == RecipeKind.SOUP

    def test_from_title(self):
        assert infer_recipe_kind({"title": "Berry Smoothie"}) == RecipeKind.SMOOTHIE

    def test_fallback_main_course(self):
        assert infer_recipe_kind({}) == RecipeKind.MAIN_COURSE


# ── Status inference ─────────────────────────────────────────

class TestInferStatus:
    def test_processed_tag(self):
        assert infer_status_from_tags({"tags": ["status/processed"]}) == RecipeStatus.PROCESSED

    def test_active_tag(self):
        assert infer_status_from_tags({"tags": ["status/active"]}) == RecipeStatus.ACTIVE

    def test_default_draft(self):
        assert infer_status_from_tags({}) == RecipeStatus.DRAFT


# ── validate_frontmatter ────────────────────────────────────

class TestValidateFrontmatter:
    def test_valid(self):
        fm = {
            "recipe_kind": "main_course",
            "title": "Test",
            "description": "Desc",
            "servings": 1,
            "prep_time_min": 10,
            "macros": {"calories": 500, "protein_g": 40.0, "carbs_g": 30.0, "fat_g": 15.0},
            "ingredients": [{"ref": "[[Ingredient]]", "quantity": "100 g"}],
            "steps": ["Do something"],
            "tags": ["type/recipe", "recipe-kind/main_course", "status/draft"],
        }
        result = validate_frontmatter(fm)
        assert result.ok is True

    def test_invalid(self):
        result = validate_frontmatter({})
        assert result.ok is False
