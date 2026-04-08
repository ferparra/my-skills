# Recipe Kind Taxonomy

Canonical kind values, inference rules, and migration policy for
`20 Resources/Nutrition/*.md` recipe notes.

---

## Kind Values

| Kind | Value | Typical Use |
|---|---|---|
| `MAIN_COURSE` | `main_course` | Full meals; protein-forward macro profile |
| `SIDE_DISH` | `side_dish` | Accompaniments; smaller portions |
| `SNACK` | `snack` | Minimal prep, no cooking |
| `SMOOTHIE` | `smoothie` | Blended drinks; blender required |
| `SOUP` | `soup` | Liquid-based; extended cooking |
| `DESSERT` | `dessert` | Sweet preparations |

---

## Inference Rules

The migrator infers `recipe_kind` from existing signals in priority order:

1. **Explicit `recipe_kind` field** — if present and valid, use it directly.
2. **Tag signals** — match known tag patterns:
   - `type/recipe/main-course` → `main_course`
   - `type/recipe/smoothie` → `smoothie`
   - `type/recipe/soup` → `soup`
   - `type/recipe/dessert` → `dessert`
   - `type/recipe/side-dish` → `side_dish`
   - `type/recipe/snack` → `snack`
3. **Title keywords** — match common words:
   - Title contains "smoothie" → `smoothie`
   - Title contains "soup" → `soup`
   - Title contains "dessert" → `dessert`
   - Title contains "side" → `side_dish`
   - Title contains "snack" → `snack`
4. **Fallback** — `main_course` (most existing recipes are main courses).

If multiple signals conflict, the note is flagged as ambiguous and requires
manual confirmation before migration.

---

## Kind-to-Required Tags

| Kind | Required Tags |
|---|---|
| `main_course` | `type/recipe`, `health/recipe`, `health/nutrition` |
| `side_dish` | `type/recipe`, `health/recipe` |
| `snack` | `type/recipe`, `health/recipe` |
| `smoothie` | `type/recipe`, `health/recipe`, `health/nutrition` |
| `soup` | `type/recipe`, `health/recipe` |
| `dessert` | `type/recipe`, `health/recipe` |

All kinds also require:
- `recipe-kind/{kind}` (e.g. `recipe-kind/main_course`)
- `status/{status}` (e.g. `status/processed`)

---

## Migration Policy

### What the Migrator Owns

- `recipe_kind` — classification and enforcement
- `title` — derived from filename
- `description` — derived from first body paragraph
- `status` — inferred from existing tags or `status` field
- `para_type` — always `resource`
- `macros` — migrated from existing scalar fields
- `tags` — managed prefixes injected, user tags preserved
- Canonical frontmatter key ordering

### What the Migrator Preserves

- Body content (instructions, nutrition tables, guardrails, rationale)
- User tags not matching managed prefixes
- Extra frontmatter keys not in the canonical list
- Existing `programme` wikilink
- Existing `source` and `cuisine` values

### What the Migrator Reports

- Ambiguous kind inferences (requires manual confirmation)
- Missing `description` (will inject `FIXME`)
- Unresolved ingredient wikilinks (ingredient note not found)
- Unresolved equipment wikilinks (equipment note not found)
- Macro values that look unreasonable (e.g. `calories: 0` for a main course)

---

## Status Lifecycle

```
draft → active → processed → archived
                ↑           |
                +-----------+  (re-activation)
```

- `draft`: New recipe, not yet tested or verified
- `active`: Tested and in rotation
- `processed`: Fully validated with complete macros and ingredients
- `archived`: No longer in rotation but kept for reference

The migrator never downgrades status. A `processed` note stays `processed`
unless explicitly changed by the user.
