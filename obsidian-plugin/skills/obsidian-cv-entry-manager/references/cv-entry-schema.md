# CV Entry Schema

Canonical frontmatter contract for `20 Resources/Career/**/*.md` notes.

Source of truth: `scripts/cv_models.py` — `CvEntryFrontmatter`.

---

## Scope

All notes matching `20 Resources/Career/**/*.md`.

---

## Common Fields (all kinds)

```yaml
cv_entry_id: ce-a1b2c3d4e5f6  # stable hash — required
cv_entry_kind: role             # CvEntryKind enum — required
status: processed               # CvEntryStatus enum — required
pillars:                        # list[CvPillar] — optional
  - P1
  - P2
recency_weight: high            # RecencyWeight enum — optional (default: low)
connection_strength: 0.5        # float 0.0–1.0 — optional (default: 0.0)
potential_links:                # list[str] — optional
  - '[[10 Notes/Fernando|Fernando]]'
tags:                           # list[str] — required; managed prefixes enforced
  - type/cv-entry
  - cv-entry-kind/role
  - status/processed
```

---

## Kind-Specific Fields

### `role`

```yaml
company: '[[Companies/Autograb|AutoGrab]]'  # wikilink — optional
company_name: AutoGrab                       # string — REQUIRED
role_title: Senior Analytics Engineer        # string — REQUIRED
start_date: '2024-03'                        # YYYY-MM — REQUIRED
end_date: '2023-11'                          # YYYY-MM or null (current) — optional
location: Melbourne                          # string — optional
reporting_to: Head of Data                   # string — optional
industry: B2B SaaS                           # string — optional
bullets:                                     # list[CvBullet] — optional
  - text: Built X                            # string — required per bullet
    pillars: [P1, P3]                        # list[CvPillar] — optional
    quantified: false                        # bool — optional (default: false)
```

### `education`

```yaml
institution: ITBA                  # string — REQUIRED
qualification: BBA, Info Systems   # string — REQUIRED
start_year: 2004                   # int — optional
end_year: 2009                     # int — optional
```

### `certification`

```yaml
certification_name: CSPO   # string — REQUIRED
issuing_body: Scrum Alliance  # string — optional
year_obtained: 2018           # int — optional
```

### `award`

```yaml
award_name: 2nd prize Startup Weekend  # string — REQUIRED
event: Startup Weekend Melbourne 2019   # string — optional
year: 2019                              # int — optional
```

### `community`

```yaml
activity_name: Lean Startup Meetup BA  # string — REQUIRED
duration: 4 years (2010-2014)          # string — optional
description: Founded and organised...  # string — optional
```

---

## Tag Management Policy

Three managed tag prefixes are owned by this skill:

| Prefix | Example | Behaviour |
|---|---|---|
| `type/cv-entry` | `type/cv-entry` | Always injected; never removed |
| `cv-entry-kind/{kind}` | `cv-entry-kind/role` | One per note; stale kind tags removed on kind change |
| `status/{status}` | `status/processed` | Reflects current status; stale status tags removed |

All other tags (e.g. `area/career`, `project/job-search-2026`) are user-owned and preserved unchanged.

---

## ID Generation

`cv_entry_id` is generated via `make_cv_entry_id(kind, key)`:
- For roles: `key = "{company_name}-{role_title}"`
- For education: `key = "{institution}-{qualification}"`
- For certifications: `key = "{certification_name}"`
- For awards: `key = "{award_name}"`
- For community: `key = "{activity_name}"`

Format: `ce-<12 lowercase hex chars>` (SHA-1 prefix).

---

## Path Convention

| Kind | Path |
|---|---|
| `role` | `20 Resources/Career/Roles/{start_date} {company} {title}.md` |
| `education` | `20 Resources/Career/Education/{institution} {qualification}.md` |
| `certification` | `20 Resources/Career/Credentials/{name}.md` |
| `award` | `20 Resources/Career/Credentials/{name}.md` |
| `community` | `20 Resources/Career/Community/{name}.md` |

---

## Frontmatter Key Order

Canonical order enforced by `order_frontmatter()`:

```
cv_entry_id, cv_entry_kind, status, company, company_name, role_title,
start_date, end_date, location, reporting_to, industry, pillars,
recency_weight, bullets, institution, qualification, start_year, end_year,
certification_name, issuing_body, year_obtained, award_name, event, year,
activity_name, duration, description, connection_strength, potential_links, tags
```

Extra keys (not in the canonical list) are appended after, in original insertion order.
