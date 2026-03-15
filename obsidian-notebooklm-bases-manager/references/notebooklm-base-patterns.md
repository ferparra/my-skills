# NotebookLM Base Patterns

Use these patterns when creating or updating `10 Notes/NotebookLM Notebooks.base`.

## Default path

- Preferred canonical path: `10 Notes/NotebookLM Notebooks.base`

## Expected filters

```yaml
filters:
  and:
    - 'file.ext == "md"'
    - or:
        - 'notebooklm_note_kind == "map"'
        - 'notebooklm_note_kind == "index"'
        - 'notebooklm_note_kind == "notebook"'
```

## Safe formulas

```yaml
formulas:
  record_title: 'if(notebooklm_title, notebooklm_title, file.basename)'
  updated_relative: "file.mtime.relative()"
  potential_link_count: "if(potential_links, potential_links.length, 0)"
  review_in_days: 'if(notebooklm_review_due, (date(notebooklm_review_due) - today()).days.round(0), "")'
  weaving_state: 'if(connection_strength >= 0.85, "woven", if(connection_strength >= 0.65, "growing", "needs-work"))'
```

## Stable views

- `NotebookLM Control`: map/index control notes, operational notes, and lane anchors
- `Notebook Library`: all notebook notes, grouped by `notebooklm_lane`
- `Professional Transformation`: filter `notebooklm_professional_track == true`
- `Life Wisdom`: filter `notebooklm_life_track == true`
- `Review Queue`: filter `notebooklm_review_due != ""`

## Minimal property set

```yaml
properties:
  notebooklm_note_kind:
    displayName: Kind
  notebooklm_title:
    displayName: Notebook
  notebooklm_lane:
    displayName: Lane
  connection_strength:
    displayName: Connection
  notebooklm_professional_track:
    displayName: Professional
  notebooklm_life_track:
    displayName: Life Wisdom
  notebooklm_review_due:
    displayName: Review Due
  notebooklm_url:
    displayName: NotebookLM URL
```

## Notes

- Materialize raw inventory entries into notebook notes before expecting the `Notebook Library` view to show the full notebook count.
- Keep formulas tolerant of missing fields so the base remains stable during gradual metadata cleanup.
- Keep the base useful before notebook records exist by surfacing `map` and `index` control notes in a dedicated view.
- Prefer boolean track flags over tag parsing when the base needs clean filters.
- Use the validator before expanding a view over many notes.
