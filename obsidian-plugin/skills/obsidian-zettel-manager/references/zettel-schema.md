# Zettel Schema

Canonical contract for zettel notes in `10 Notes/` and fleeting captures in `00 Inbox/`.

Enforced by `scripts/zettel_models.py` (`ZettelFrontmatter`).

---

## Scope

- **Primary**: `10 Notes/**/*.md`
- **Secondary (fleeting)**: `00 Inbox/**/*.md` — use `--glob "00 Inbox/**/*.md"` for inbox sweeps

---

## Required Frontmatter

```yaml
---
zettel_id: zt-a1b2c3d4e5         # zt-[10 lowercase hex chars]; generated from path hash
zettel_kind: atomic               # see zettel-kind-taxonomy.md
aliases:
  - Alternative Name
status: processed                 # fleeting | processing | processed | evergreen
connection_strength: 6.5          # float 0.0-10.0; computed by score_zettels.py
potential_links:
  - "[[10 Notes/Related Note|Related Note]]"   # non-empty list required
tags:
  - type/zettel                   # required managed tag
  - zettel-kind/atomic            # required; matches zettel_kind
  - status/processed              # required; matches status
  - tech/ai/context-engineering   # user-defined domain/topic tags
---
```

---

## Kind-Specific Additional Fields

### `moc`
```yaml
hub_for:
  - agent-engineering
  - agentic-ai
```

### `litnote`
```yaml
source: "Newport, Cal - Deep Work (2016)"
source_date: "2016-01-05"   # optional ISO date
```

### `fleeting_capture`
```yaml
captured_from: "[[Periodic/2026/2026-03-06|2026-03-06]]"  # optional
```

### `hub_synthesis`
```yaml
synthesises:
  - "[[10 Notes/Context Window Pressure|Context Window Pressure]]"
  - "[[10 Notes/Token Management|Token Management]]"
```

### `definition`
```yaml
defines: Zettelkasten
```

---

## Managed Tags

Three tags are managed by `normalize_zettel_tags` and must not be manually duplicated:

| Tag | Value | Notes |
|---|---|---|
| `type/zettel` | always `type/zettel` | Marks the note as a zettel |
| `zettel-kind/{kind}` | matches `zettel_kind` value | e.g., `zettel-kind/atomic` |
| `status/{status}` | matches `status` value | e.g., `status/processed` |

All other tags are user-defined and preserved during migration.

---

## Interweaving Minimum

Every zettel body must contain:
- **≥1 concept link**: a wikilink to a note under `10 Notes/`, `20 Resources/`, `Projects/`, `10 Projects/`, `Companies/`, `People/`, or `Products/`.
- **≥1 context link**: a wikilink to a note under `Periodic/` or `00 Inbox/`, or a date-like target matching `YYYY-MM-DD` or `YYYY-Www`.

The migrate script validates these requirements and reports errors if unmet. Body enrichment (adding links) is the domain of `obsidian-interweave-engine`, not this skill.

---

## Frontmatter Key Order

The canonical order enforced by `order_frontmatter`:

```
zettel_id → zettel_kind → aliases → status → connection_strength →
potential_links → source → source_date → captured_from → hub_for →
synthesises → defines → tags → [extra fields preserved as-is]
```

---

## connection_strength Formula

Scored by `score_zettels.py` using `score_connection_strength(path, body, frontmatter, backlink_count)`:

```
out_score   = min(body_outlinks / 6,  1.0) × 4.0   # max 4 pts
pl_score    = min(potential_links / 4, 1.0) × 2.0   # max 2 pts
back_score  = min(backlinks / 5,      1.0) × 4.0   # max 4 pts
total       = round(out_score + pl_score + back_score, 2)   # 0.0–10.0
```

Backlink count is retrieved via `obsidian backlinks path="<note>" counts total`. Falls back to 0 if obsidian CLI is unavailable.

---

## Migration Policy

`migrate_zettels.py` normalises existing notes to this schema. Rules:

1. **Additive only**: never remove existing metadata that is not managed.
2. **Kind inference**: infer from existing tags (`type/moc`, `type/definition`, `type/resource-litnote`) or fields (`source`, `hub_for`, `synthesises`, `defines`, inbox path). Default to `atomic`.
3. **Ambiguity rule**: if heuristics produce multiple conflicting signals, emit a warning and skip the write — require manual confirmation.
4. **Status inference**: read from existing `status/` tags. Default to `fleeting`.
5. **zettel_id generation**: sha1 hash of the absolute file path, first 10 hex chars, prefixed with `zt-`. Stable and deterministic.
6. **`potential_links` initialisation**: if missing, initialise to `[["[[10 Notes/Notes Infrastructure Hub|Notes Infrastructure Hub]]"]]` as a placeholder.
7. **`connection_strength` initialisation**: if missing, set to `0.0`. Run `score_zettels.py` after migration to update.
8. **Body content**: never modified by migrate. Only frontmatter is updated.
9. **PIT notes**: preserve `pit_status` and period fields without rewriting.
10. **YAML validity**: always check that output YAML is valid before writing.

---

## Verification Commands

```bash
# Validate after migration
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/validate_zettels.py \
  --glob "10 Notes/**/*.md"

# Score connection_strength
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-zettel-manager/scripts/score_zettels.py \
  --glob "10 Notes/**/*.md" --mode fix

# Obsidian CLI checks
obsidian read path="10 Notes/<note>.md"
obsidian links path="10 Notes/<note>.md" total
obsidian backlinks path="10 Notes/<note>.md" counts total
obsidian unresolved counts total
```
