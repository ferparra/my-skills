# People Schema

Canonical frontmatter contract for `People/**/*.md` notes.

Source of truth: `scripts/people_models.py` — `PersonFrontmatter`.

---

## Scope

All notes matching `People/**/*.md`.

---

## Common Fields (all kinds)

```yaml
person_kind: manager            # PersonKind enum — required
aliases: []                     # list[str] — optional
created: '2025-09-05T15:33:18' # ISO datetime string — required
modified: '2026-03-18T18:17:00' # ISO datetime string — required
relationship_to_fernando: colleague  # free string — required
status: processed               # PersonStatus enum — required
primary_context: professional/autograb  # free string — required
relationship_conditions:        # list[str] — optional
  - line manager in data and analytics
organizations:                  # list[wikilink] — optional; entries must be wikilinks
  - '[[Companies/Autograb|Autograb]]'
connection_strength: 0.82       # float 0.0–1.0 — required (managed by score_people.py)
potential_links:                # list[str] — required, non-empty
  - '[[10 Notes/Fernando|Fernando]]'
last_interaction_date: '2026-02-28'  # YYYY-MM-DD — optional (managed by enrich_people.py)
interaction_frequency: weekly   # InteractionFrequency enum — optional (managed by enrich_people.py)
unique_attributes:              # list[dict] — optional; free-form key-value pairs
  - LinkedIn: https://...
tags:                           # list[str] — required; managed prefixes enforced
  - type/person
  - person-kind/manager
  - status/processed
```

---

## Kind-Specific Fields

### `manager`

```yaml
management_cadence: weekly 1:1  # free string — injected as FIXME if absent
```

### `stakeholder`

```yaml
influence_domain: data-platform  # free string — injected as FIXME if absent
```

### `customer_contact`

```yaml
account_context: '[[Companies/Acme|Acme]]'  # wikilink or free string — injected as FIXME if absent
```

### `mentor`

```yaml
domain_of_mentorship: career    # free string — injected as FIXME if absent
```

### `author`

```yaml
primary_works:                  # list[str] — REQUIRED (hard validation error if absent)
  - '[[10 Notes/Replacing Guilt Series|Replacing Guilt Series]]'
```

### `acquaintance`

```yaml
personal_context: friend        # free string — injected as FIXME if absent
```

---

## Tag Management Policy

Three managed tag prefixes are owned by this skill:

| Prefix | Example | Behaviour |
|---|---|---|
| `type/person` | `type/person` | Always injected; never removed |
| `person-kind/{kind}` | `person-kind/manager` | One per note; stale kind tags removed on kind change |
| `status/{status}` | `status/processed` | Reflects current status; stale status tags removed |

All other tags (e.g. `person`, `person/autograb`, `role/team-lead`, `author`) are user-owned and preserved unchanged.

---

## connection_strength Scoring Formula (0.0–1.0)

```
outlink_score  = min(body_outlinks / 8,  1.0) × 0.35   # max 0.35
pl_score       = min(potential_links / 6, 1.0) × 0.25  # max 0.25
backlink_score = min(backlinks / 4, 1.0) × 0.25        # max 0.25
recency_score  = recency_bonus(last_interaction_date)   # max 0.15

total = round(sum, 2)
```

Only written if score changes by > 0.01. Falls back to 0 backlinks when `obsidian` CLI unavailable.

---

## Interaction Enrichment Policy

`enrich_people.py` scans note bodies for headings matching `## YYYY-MM-DD` pattern:

- Latest date → `last_interaction_date` (only_if_missing)
- Gap distribution from 3+ dates → `interaction_frequency` (only_if_missing)

Never overwrites fields that are explicitly set.

---

## Frontmatter Key Order

Canonical order enforced by `order_frontmatter()`:

```
person_kind, aliases, created, modified, relationship_to_fernando,
status, primary_context, relationship_conditions, organizations,
connection_strength, potential_links, last_interaction_date,
interaction_frequency, management_cadence, influence_domain,
account_context, domain_of_mentorship, primary_works,
personal_context, unique_attributes, tags
```

Extra keys (not in the canonical list) are appended after, in original insertion order.
