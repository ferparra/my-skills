# Recipe Schema

Canonical frontmatter contract for `20 Resources/Nutrition/*.md` recipe notes.

Source of truth: `scripts/recipe_models.py` — `RecipeFrontmatter`.

---

## Scope

All notes matching `20 Resources/Nutrition/*.md` that represent typed recipes.

---

## Common Fields (all kinds)

```yaml
recipe_kind: main_course           # RecipeKind enum — required
title: Kung Pao Chicken            # str — required; matches note filename
description: A Sichuan classic...  # str — required; one-sentence summary
tags:                              # list[str] — required; managed prefixes enforced
  - type/recipe
  - recipe-kind/main_course
  - status/processed
  - health/nutrition
  - health/recipe
status: processed                  # RecipeStatus enum — default: draft
para_type: resource                 # ParaType enum — always "resource"
servings: 1                         # int (> 0) — required
prep_time_min: 25                   # int (>= 0) — required
cook_time_min: 0                    # int (>= 0) — default: 0
macros:                             # Macros object — required
  calories: 740                     # int (>= 0)
  protein_g: 62.0                   # float (>= 0)
  carbs_g: 72.0                     # float (>= 0)
  fat_g: 18.0                       # float (>= 0)
ingredients:                        # list[IngredientRef] — required, non-empty
  - ref: "[[20 Resources/Ingredients/Coles Spring Onions]]"
    quantity: "2 stalks"
  - ref: "[[20 Resources/Ingredients/Coles Bananas]]"
    quantity: "1 medium"
equipment:                          # list[str] (wikilinks) — optional
  - "[[20 Resources/Kitchen Equipment/Carbon-Steel Wok]]"
  - "[[20 Resources/Kitchen Equipment/Cuckoo Rice Cooker]]"
steps:                              # list[str] — required, non-empty
  - "Rinse rice and cook in the rice cooker."
  - "Toss diced chicken with marinade ingredients."
source: Traditional Sichuan        # str | null — optional
cuisine: sichuan                    # str | null — optional
programme: "[[Nutrition Programme 2026]]"  # str (wikilink) | null — optional
aliases: []                         # list[str] — optional
```

---

## Kind-Specific Guidance

### `main_course`

Default for full meals. Macro and ingredient requirements strictly enforced.
Typically references 3+ ingredients and 1+ equipment items.

### `smoothie`

Blended drinks; `cook_time_min` should be `0`. Equipment typically includes
a blender or food processor wikilink.

### `side_dish`

Accompanies a main course. May have smaller macro values and fewer ingredients.

### `snack`

Minimal preparation, no cooking step. Often `prep_time_min <= 10`.

### `soup`

Liquid-based; may use pressure cooker or stovetop. Longer `cook_time_min`
expected.

### `dessert`

Sweet preparations; higher `carbs_g` relative to `protein_g` is common.

---

## Cross-Reference Integrity

- `ingredients[].ref` must be a valid wikilink pointing to a note in
  `20 Resources/Ingredients/`.
- `equipment[]` entries must be valid wikilinks pointing to notes in
  `20 Resources/Kitchen Equipment/`.
- `programme` must be a valid wikilink.
- Unresolved links are reported as warnings, not errors. The skill does not
  auto-create missing notes.

---

## Migration Policy

Scalar frontmatter fields in existing notes map to the new schema:

| Old Field | New Location | Notes |
|---|---|---|
| `calories` | `macros.calories` | int coercion |
| `protein` | `macros.protein_g` | float coercion |
| `carbs` | `macros.carbs_g` | float coercion |
| `fat` | `macros.fat_g` | float coercion |
| `prep_time` | `prep_time_min` | direct rename |
| `servings` | `servings` | unchanged |
| `type: recipe` | `recipe_kind` + managed tags | removed |
| `source` | `source` | unchanged |
| `programme` | `programme` | unchanged |

Fields NOT in the new schema (`fibre`, `potassium_mg`, `low_fodmap`,
`anti_inflammatory_profile`, `connection_strength`, `potential_links`) are
preserved as extra frontmatter keys or body content.

---

## Frontmatter Key Order

```
recipe_kind, title, description, tags, status, para_type, servings,
prep_time_min, cook_time_min, macros, ingredients, equipment, steps,
source, cuisine, programme, aliases
```

---

## Base Support

`20 Resources/Nutrition/Recipe Library.base` should expose:

- `recipe_kind` and `status`
- Per-serving macros: `calories`, `protein_g`, `carbs_g`, `fat_g`
- `servings`, `prep_time_min`, `cook_time_min`
- Ingredient count and equipment count
- `cuisine` and `source`

These fields support:

- Meal planning and macro budgeting queries
- Ingredient availability cross-checks
- Equipment-dependent recipe filtering
- Programme alignment audits
