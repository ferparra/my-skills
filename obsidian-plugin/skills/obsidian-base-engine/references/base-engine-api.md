# Base Engine API Reference

## BaseRenderer

### Constructor

```python
BaseRenderer(
    base_name: str,
    kind_field: str,
    folder_glob: str,
    formulas: dict[str, str] | None = None,
    properties: dict[str, dict[str, str]] | None = None,
    views: list[dict[str, Any]] | None = None,
    custom_formulas: dict[str, str] | None = None,
    custom_properties: dict[str, dict[str, str]] | None = None,
    custom_views: list[dict[str, Any]] | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `base_name` | str | Unique name for this base (e.g., "people", "exercise") |
| `kind_field` | str | Frontmatter field that holds the kind (e.g., "person_kind") |
| `folder_glob` | str | Glob pattern for notes belonging to this base |
| `formulas` | dict | Dataview-style formula expressions |
| `properties` | dict | Property display names and metadata |
| `views` | list | View definitions (tables, lists, etc.) |
| `custom_formulas` | dict | Additional formulas merged on top |
| `custom_properties` | dict | Additional properties merged on top |
| `custom_views` | list | Additional views appended to base |

### Methods

#### `build_config() -> dict[str, Any]`

Build the full .base configuration dictionary including filters, formulas, properties, and views.

#### `render(output_path: Path | str) -> dict[str, Any]`

Render the base to a YAML file. Returns `{"ok": True, "path": str, "views": int}`.

#### `validate() -> list[str]`

Validate the base configuration. Returns a list of issue strings (empty if valid).

### Class Methods

#### `from_registry(base_name: str) -> BaseRenderer`

Load a pre-configured BaseRenderer from the built-in registry.

**Available base types:**
- `brokerage_activity`
- `exercise`
- `people`
- `cv_entry`

## View Composition

### `compose_views()`

```python
compose_views(
    collections: list[tuple[str, list[dict[str, Any]]]],
    shared_properties: list[str] | None = None,
) -> list[dict[str, Any]]
```

Combine views from multiple note collections with prefixed names.

**Example:**
```python
views = compose_views([
    ("Exercise", exercise_views),
    ("Brokerage", brokerage_views),
])
# Result: "[Exercise] Selection Board", "[Brokerage] Activity Ledger", ...
```

### `merge_properties()`

```python
merge_properties(
    *property_dicts: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]
```

Merge multiple property dictionaries.

## Formula Parser

### `FormulaParser`

```python
parser = FormulaParser(strict=True)
```

**Parameters:**
- `strict`: If True, unknown functions raise errors. Default True.

#### `parse(formula: str) -> dict[str, Any]`

Parse a formula and return metadata:
```python
{
    "valid": bool,
    "issues": list[str],
    "tokens": list[str],
    "token_count": int,
}
```

#### `validate_formula(formula: str) -> tuple[bool, list[str]]`

Returns `(is_valid, issues)`.

#### `validate_formula_dict(formulas: dict[str, str]) -> dict[str, dict[str, Any]]`

Validate all formulas in a dictionary.

### Supported Dataview Expressions

**String literals:** `"text"` or `'text'`

**Field references:** `field_name`, `nested.field`

**Function calls:** `func(arg1, arg2)`

**Conditionals:** `if(condition, then, else)`

**Binary operators:** `+`, `-`, `*`, `/`, `%`, `==`, `!=`, `<`, `>`, `<=`, `>=`

**Logical operators:** `and`, `or`, `!`

**Array methods:** `.length`, `.join(sep)`, `.map(fn)`, `.filter(fn)`, `.includes(x)`

**String methods:** `.toString()`, `.replace(a, b)`, `.toLowerCase()`, `.toUpperCase()`

**Number methods:** `.toFixed(n)`

### Known Functions

```
if, default, join, map, filter, sort, reverse,
contains, includes, excludes, startswith, endswith,
replace, split, trim, lower, upper, length,
toString, toNumber, toFixed, floor, ceil, round,
min, max, sum, average, count, extract, any, all
```

## Base Registry

The registry contains pre-configured base types:

### brokerage_activity

- **kind_field:** `brokerage_activity_kind`
- **folder_glob:** `20 Resources/Investments/Brokerage Activity/**/*.md`
- **Formulas:** symbol_display, activity_label, provider_label, cash_badge, signed_units, merge_badge, review_badge, source_files_label
- **Views:** Activity Ledger, Trade Flow, Distributions, Cash Movements, Review Queue

### exercise

- **kind_field:** `exercise_kind`
- **folder_glob:** `20 Resources/Exercises/**/*.md`
- **Formulas:** primary_label, secondary_label, gear, bias, volume_mode, selection_score, top_set_display, working_avg_display, strong_names, sync_state, weekly_set_status, trend_badge, analysis_status
- **Views:** Selection Board, Strong Sync, Progression Trends, Weekly Volume, Recommendation Queue, Mobility and Warm-up, Full Library

### people

- **kind_field:** `person_kind`
- **folder_glob:** `People/**/*.md`
- **Formulas:** kind_label, status_badge, strength_label, recency_label
- **Views:** (minimal set — extend via custom_views)

### cv_entry

- **kind_field:** `cv_entry_kind`
- **folder_glob:** `20 Resources/Career/**/*.md`
- **Formulas:** kind_label, date_range, pillar_list, bullet_count, unquantified_count, recency_badge, title_display
- **Views:** Career Timeline, By Pillar (P1/P2/P3), Education and Credentials, Community, Needs Quantification, All Entries

## Migration Guide

Skills that previously had inline `render_*_base.py` scripts should migrate to use this engine:

**Before:**
```python
# In render_brokerage_activity_base.py
BASE_CONFIG = {
    "filters": {...},
    "formulas": {...},
    ...
}
```

**After:**
```python
from base_renderer import BaseRenderer

renderer = BaseRenderer.from_registry("brokerage_activity")
# Add any custom overrides
renderer.custom_formulas = {"my_formula": '...'}
renderer.render("/path/to/Brokerage Activity.base")
```

Or use the CLI:
```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-base-engine/scripts/base_renderer.py \
  --base brokerage_activity --output "Brokerage Activity.base"
```
