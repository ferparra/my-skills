---
name: obsidian-recipe-kind-manager
version: 1.0.0
dependencies: []
pipeline:
  inputs:
    - name: recipe_kind
      type: string
      required: false
      description: Filter by recipe kind (main_course, side_dish, snack, smoothie, soup, dessert)
    - name: glob
      type: string
      required: false
      default: "20 Resources/Nutrition/*.md"
      description: Glob pattern for recipe notes
    - name: mode
      type: string
      required: false
      default: check
      description: Mode (check or fix)
  outputs:
    - name: validated_recipes
      type: file
      path: "20 Resources/Nutrition/{slug}.md"
      description: Validated recipe notes
    - name: recipe_base
      type: file
      path: "20 Resources/Nutrition/Recipe Library.base"
      description: Recipe library Base
    - name: recipe_report
      type: json
      path: ".skills/recipe-report.json"
      description: Validation/migration report
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
description: Validate, migrate, and maintain typed recipe notes in Obsidian. Use for recipe_kind enforcement, recipe schema compliance, ingredient and equipment cross-reference integrity, per-serving macro tracking, and Recipe Library.base alignment.
category: note-taking
---

# Obsidian Recipe Kind Manager

## Overview

Run this skill when recipe notes need a real typed contract instead of loose
frontmatter. `recipe_kind` is the supertag: it selects the Pydantic v2 schema
behind each note and keeps the Recipe Library Base aligned with the same
contract.

Recipes in the vault live under `20 Resources/Nutrition/` and reference two
linked-note collections:

- **Ingredients** in `20 Resources/Ingredients/` — each ingredient note is a
  typed product entry tracked in the Ingredient Inventory Hub
- **Kitchen Equipment** in `20 Resources/Kitchen Equipment/` — each equipment
  note describes a tool or appliance used in preparation

Cross-referencing these as wikilinks enables nutrition roll-ups from
ingredient-level data, equipment availability checks, and meal-planning queries
that span recipe, ingredient, and equipment graphs.

## Strategic Role

Typed recipe notes are the structural backbone of Fernando's nutrition system.
Without a schema, the 11 existing free-form recipe notes in
`20 Resources/Nutrition/` cannot:

- Be reliably queried for macro totals across a meal plan
- Guarantee that ingredient links resolve to real ingredient notes
- Confirm that referenced kitchen equipment is owned and available
- Feed into the Nutrition Programme or Weight Loss Goal without manual
  transcription errors

By enforcing `recipe_kind` and a Pydantic v2 contract, this skill turns each
recipe note into a machine-verifiable unit that integrates with the ingredient
and equipment knowledge graphs already in the vault. This is the same pattern
that `obsidian-exercise-kind-manager` uses for exercise notes and
`obsidian-people-kind-manager` uses for person notes.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate recipe notes when the
tooling is unavailable.

### 2. Read Only the Required Surface

```bash
obsidian read path="20 Resources/Nutrition/Recipe Library.base"
obsidian read path="20 Resources/Nutrition/Nutrition Programme 2026.md"
qmd query "recipe ingredients nutrition meal prep cooking" -c resources -l 8
qmd query "recipe nutrition plan macro target" -c inbox -l 5
```

Default read scope stays inside:

- `20 Resources/Nutrition/*.md`
- `20 Resources/Nutrition/Recipe Library.base`
- `20 Resources/Nutrition/Nutrition Programme 2026.md`
- `20 Resources/Ingredients/*.md` (for cross-reference validation)
- `20 Resources/Kitchen Equipment/*.md` (for cross-reference validation)

### 3. Validate Before Editing

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-recipe-kind-manager/scripts/validate_recipes.py \
  --glob "20 Resources/Nutrition/*.md" --mode check
```

Review `recipe_kind`, inferred kind, and validation errors before fixing.

### 4. Dry-Run Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-recipe-kind-manager/scripts/migrate_recipes.py \
  --glob "20 Resources/Nutrition/*.md" --mode check
```

The migrator only changes frontmatter. It preserves note bodies, images,
nutrition tables, and preparation instructions.

### 5. Apply Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-recipe-kind-manager/scripts/migrate_recipes.py \
  --glob "20 Resources/Nutrition/*.md" --mode fix
```

The script fills stable defaults:

- `recipe_kind` (inferred from tags, title, and existing signals)
- `title` (from note filename)
- `description` (from first paragraph of body, or `[UNTITLED RECIPE]` if not inferable)
- `status` (inferred from existing tags)
- `para_type: resource`
- `macros` (from existing `calories`, `protein`, `fat`, `carbs` fields)
- `ingredients` (parsed from body `## Ingredients` section where wikilinks exist)
- `equipment` (parsed from body `## Equipment` section wikilinks)
- `steps` (parsed from body `## Preparation` numbered list)
- Managed tag prefixes: `type/recipe`, `recipe-kind/{kind}`, `status/{status}`

### 6. Render the Recipe Base

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-recipe-kind-manager/scripts/render_recipe_base.py \
  --output "20 Resources/Nutrition/Recipe Library.base"
```

The rendered Base exposes:

- `recipe_kind` and `status`
- Per-serving macros: `calories`, `protein_g`, `carbs_g`, `fat_g`
- `servings`, `prep_time_min`, `cook_time_min`
- Ingredient and equipment link counts
- `cuisine` and `source`

### 7. Re-Validate and Verify

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-recipe-kind-manager/scripts/validate_recipes.py \
  --glob "20 Resources/Nutrition/*.md" --mode check

obsidian read path="20 Resources/Nutrition/Recipe Library.base"
obsidian search query="recipe_kind" limit=20 total
obsidian unresolved total
```

Confirm `"ok": true` overall before closing.

## Schema Fields

### Required Fields

| Field | Type | Description |
|---|---|---|
| `recipe_kind` | `RecipeKind` enum | Kind selector: `main_course`, `side_dish`, `snack`, `smoothie`, `soup`, `dessert` |
| `title` | `str` | Display title; matches the note filename |
| `description` | `str` | One-sentence summary of the recipe |
| `servings` | `int` (> 0) | Number of servings the recipe yields |
| `prep_time_min` | `int` (>= 0) | Active preparation time in minutes |
| `macros` | `Macros` object | Per-serving macronutrient breakdown (see below) |
| `ingredients` | `list[IngredientRef]` (>= 1) | Ordered list of ingredient references with quantities |
| `steps` | `list[str]` (>= 1) | Ordered list of preparation/cooking steps |
| `tags` | `list[str]` | Managed and user tags |

### Macros Sub-object

| Field | Type | Description |
|---|---|---|
| `calories` | `int` (>= 0) | Total calories per serving (kcal) |
| `protein_g` | `float` (>= 0) | Protein per serving in grams |
| `carbs_g` | `float` (>= 0) | Carbohydrates per serving in grams |
| `fat_g` | `float` (>= 0) | Fat per serving in grams |

### IngredientRef Sub-object

| Field | Type | Description |
|---|---|---|
| `ref` | `str` (wikilink) | Wikilink to the ingredient note, e.g. `[[20 Resources/Ingredients/Yumi's Chipotle Hommus Dip 200g]]` |
| `quantity` | `str` | Human-readable quantity, e.g. `250 g`, `1 tbsp` |

### Optional Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `cook_time_min` | `int` (>= 0) | `0` | Passive cooking time in minutes |
| `status` | `RecipeStatus` enum | `draft` | Lifecycle status: `draft`, `active`, `processed`, `archived` |
| `para_type` | `ParaType` enum | `resource` | PARA category; always `resource` for recipes |
| `equipment` | `list[str]` (wikilinks) | `[]` | Links to kitchen equipment notes, e.g. `[[20 Resources/Kitchen Equipment/Electric Pressure Cooker.md]]` |
| `source` | `str` or `null` | `null` | Attribution or origin, e.g. `Traditional Sichuan (宫保鸡丁)` |
| `cuisine` | `str` or `null` | `null` | Cuisine tag, e.g. `sichuan`, `argentine` |
| `programme` | `str` or `null` (wikilink) | `null` | Wikilink to the nutrition programme note |
| `aliases` | `list[str]` | `[]` | Alternative names for Obsidian search |

### Tag Management Policy

Three managed tag prefixes are owned by this skill:

| Prefix | Example | Behaviour |
|---|---|---|
| `type/recipe` | `type/recipe` | Always injected; never removed |
| `recipe-kind/{kind}` | `recipe-kind/main_course` | One per note; stale kind tags removed on kind change |
| `status/{status}` | `status/processed` | Reflects current status; stale status tags removed |

All other tags (e.g. `health/nutrition`, `health/recipe`, `cuisine/sichuan`, `area/health/nutrition`) are user-owned and preserved unchanged.

## Kind Rules

- `main_course`
  - Default for notes with `type/recipe/main-course` tag or `type: recipe`.
  - Full macro and ingredient requirements apply.

- `smoothie`
  - For blended drinks; typically `prep_time_min` only, `cook_time_min: 0`.
  - Usually references `equipment: ["[[...High-Power Food Processor]]"]` or similar.

- `side_dish`
  - Accompanies a main course; smaller macro profile.

- `snack`
  - Minimal prep, no cooking step expected.

- `soup`
  - Liquid-based; may use pressure cooker or stovetop.

- `dessert`
  - Sweet preparations; may have higher `carbs_g` relative to `protein_g`.

## Cross-Reference Paths

Recipes link out to two other typed collections in the vault:

- **Ingredients**: `20 Resources/Ingredients/` — each `IngredientRef.ref` should
  resolve to an existing note in this directory. Example:
  `[[20 Resources/Ingredients/Yumi's Chipotle Hommus Dip 200g]]`

- **Kitchen Equipment**: `20 Resources/Kitchen Equipment/` — each entry in
  `equipment` should resolve to an existing note. Example:
  `[[20 Resources/Kitchen Equipment/Electric Pressure Cooker]]`

When validating, the skill should report unresolved ingredient or equipment
links rather than silently creating missing notes.

## Migration Guidance for Existing Free-Form Recipes

The 11 existing recipe notes in `20 Resources/Nutrition/` have heterogeneous
frontmatter. Migration proceeds in these phases:

1. **Infer `recipe_kind`** from existing tags (`type/recipe/main-course`,
   `type/recipe/smoothie`, etc.) and title keywords. Report ambiguous cases
   for manual confirmation.

2. **Map existing scalar fields** to the new schema:
   - `calories` → `macros.calories`
   - `protein` → `macros.protein_g`
   - `carbs` → `macros.carbs_g`
   - `fat` → `macros.fat_g`
   - `prep_time` → `prep_time_min`
   - `servings` → `servings` (already matching)
   - `type: recipe` → removed (replaced by `recipe_kind` + managed tags)

3. **Parse body sections** into structured fields:
   - `## Ingredients` → `ingredients` list (where wikilinks exist)
   - `## Equipment` → `equipment` list
   - `## Preparation` → `steps` list (from numbered items)

4. **Synthesize missing fields**:
   - `description`: first non-heading, non-tag paragraph from body
   - `cook_time_min`: `0` if not inferable
   - `para_type: resource`: always set

5. **Normalize tags**: inject managed prefixes, preserve user tags.

6. **Remove migrated scalar fields**: `calories`, `protein`, `fat`, `carbs`,
   `prep_time`, `type`, `fibre`, `potassium_mg`, `low_fodmap`,
   `anti_inflammatory_profile`, `connection_strength`, `potential_links` are
   NOT carried into the new schema. They remain in the body or as extra
   frontmatter keys (the model allows `extra="allow"`).

The migrator only rewrites frontmatter. Body content (nutrition tables,
low-FODMAP guardrails, rationale sections) is preserved verbatim.

## Guardrails

- Never rewrite note bodies during schema migration.
- Preserve existing metadata unless the skill owns the field.
- Prefer filling missing heuristics over overwriting explicit user values.
- Treat `description` as a required field; inject `[UNTITLED RECIPE]` if the description cannot be inferred
  rather than leaving it absent.
- Do not auto-create missing ingredient or equipment notes during migration;
  unresolved links should be reported as warnings.
- Keep `para_type: resource` as the default and only valid value.
- **Never silently guess ambiguous kind.** If heuristics conflict, emit warning,
  skip write, require human confirmation.
- Custom fields not in the canonical list are preserved during re-migration
  (`extra="allow"`).
- **Keep YAML valid** — validate output before writing.

## QMD Collection Routing

| Query intent | Collection |
|---|---|
| Existing recipes and nutrition | `-c resources` |
| New recipe captures and ideas | `-c inbox` |

```bash
qmd query "recipe ingredients nutrition meal prep cooking" -c resources -l 8
qmd query "recipe nutrition plan macro target" -c inbox -l 5
```

## Frontmatter Key Order

Canonical order enforced by `order_frontmatter()`:

```
recipe_kind, title, description, tags, status, para_type, servings,
prep_time_min, cook_time_min, macros, ingredients, equipment, steps,
source, cuisine, programme, aliases
```

Extra keys (not in the canonical list) are appended after, in original
insertion order.

## References

- `references/recipe-schema.md` — canonical field contract and Base support surface
- `references/recipe-kind-taxonomy.md` — kind values, inference rules, migration policy
- `scripts/recipe_models.py` — shared Pydantic v2 models and utilities (source of truth)
