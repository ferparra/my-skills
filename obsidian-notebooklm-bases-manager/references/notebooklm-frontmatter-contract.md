# NotebookLM Frontmatter Contract

Use this contract for notes that should appear in a NotebookLM-oriented Obsidian Base.

## Required common fields

| Field | Type | Notes |
|---|---|---|
| `type` | string | Use `note`, `resource`, or `moc` depending on the note role. |
| `tags` | list or string | Must include at least one `status/...` tag. |
| `connection_strength` | number | Range `0.0` to `1.0`. |
| `potential_links` | list | Candidate `[[wikilinks]]` for future weaving. |
| `notebooklm_note_kind` | string | One of `index`, `map`, `notebook`. |

## Notebook record fields

These fields are required when `notebooklm_note_kind: notebook`.

| Field | Type | Notes |
|---|---|---|
| `notebooklm_title` | string | Human-readable notebook title. |
| `notebooklm_url` | string | Must begin with `https://notebooklm.google.com/notebook/`. |
| `notebooklm_lane` | string | One of `ai-systems`, `strategic-judgment`, `philosophy-meaning`, `health-resilience`, `pkm-operations`, `unassigned`. |

## Recommended notebook record fields

| Field | Type | Notes |
|---|---|---|
| `para_type` | string | Usually `resource`, `project`, or `area`. |
| `notebooklm_professional_track` | boolean | Mark notes that serve professional transformation. |
| `notebooklm_life_track` | boolean | Mark notes that serve wisdom, character, or life design. |
| `notebooklm_review_due` | date string | Use `YYYY-MM-DD`. |
| `notebooklm_source_note` | wikilink string | Usually a link back to the index or map note. |

## Shape rules

- `notebooklm_note_kind: map` should usually pair with `type: moc`.
- `potential_links` items should be literal wikilinks like `[[10 Notes/Fernando|Fernando's Hub]]`.
- `connection_strength` should express note maturity, not topic importance.

## Example notebook record

```yaml
---
type: resource
para_type: resource
tags:
  - status/processing
  - area/development/learning
  - resource/topic/ai
connection_strength: 0.68
potential_links:
  - "[[10 Notes/Fernando|Fernando's Hub]]"
  - "[[10 Projects/AI Research/AI and LLM Application Development Map|AI and LLM Application Development Map]]"
notebooklm_note_kind: notebook
notebooklm_title: Foundations of Large Language Models
notebooklm_url: https://notebooklm.google.com/notebook/e1f23d34-8d11-4a0b-acfb-c4e73f524e34
notebooklm_lane: ai-systems
notebooklm_professional_track: true
notebooklm_life_track: false
notebooklm_review_due: 2026-03-20
notebooklm_source_note: "[[00 Inbox/Notebook LM notebooks|Notebook LM notebooks]]"
---
```
