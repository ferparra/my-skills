# CV Entry Kind Taxonomy

`cv_entry_kind` is the supertag for career entry notes. It selects the schema
contract enforced by Pydantic v2.

---

## Kind Values

| `cv_entry_kind` | Description | Required fields |
|---|---|---|
| `role` | Employment position at a company | `company_name`, `role_title`, `start_date` |
| `education` | Formal education or qualification | `institution`, `qualification` |
| `certification` | Professional certification | `certification_name` |
| `award` | Award or recognition | `award_name` |
| `community` | Community contribution, meetup, event | `activity_name` |

---

## Pillar Definitions

The three narrative pillars run transversally across career entries:

| Pillar | Name | Description |
|---|---|---|
| `P1` | Data with a Product Lens | Data infrastructure in service of product outcomes and monetisation |
| `P2` | Enabling Teams | Building data literacy, self-serve capability, governance, coaching |
| `P3` | Lean Experimentation & Change Management | Small bets, validated learning, incremental adoption |

Pillars are tagged at both the entry level (`pillars: [P1, P2]`) and the
bullet level (`bullets[].pillars: [P1]`). Entry-level pillars summarise;
bullet-level pillars enable filtering.

---

## Recency Weights

| Weight | Badge | Meaning |
|---|---|---|
| `high` | ★★★ | Most recent or highest-impact role (carries ~90% of CV weight) |
| `medium` | ★★ | Recent role with significant proof points |
| `low` | ★ | Older role or supporting backstory |

---

## Bullet Schema

Each role entry may include a `bullets` list:

```yaml
bullets:
  - text: "Built X that achieved Y"   # required — the achievement statement
    pillars: [P1, P3]                  # optional — which pillars this proves
    quantified: false                  # optional — true if the bullet includes a number
```

### Quantification Tracking

The `quantified` flag enables the "Needs Quantification" Base view — the
highest-leverage CV improvement is adding one number to each unquantified
bullet in recent roles.

---

## Kind Inference Heuristics

Applied by `migrate_cv.py` when `cv_entry_kind` is absent:

1. `company_name` + `role_title` present → `role`
2. `institution` + `qualification` present → `education`
3. `certification_name` present → `certification`
4. `award_name` present → `award`
5. `activity_name` present → `community`
6. Path contains `Roles/` → `role`
7. Path contains `Education/` → `education`
8. Path contains `Community/` → `community`
9. No signals → default `role` with warning

---

## Status Lifecycle

| Status | Meaning |
|---|---|
| `fleeting` | Note created; minimal enrichment |
| `processing` | Active refinement; bullets being quantified or updated |
| `processed` | Stable; ready for CV export |

---

## Migration Rules

- Never rewrite note bodies — body enrichment belongs to `obsidian-interweave-engine`.
- Preserve all existing metadata the skill does not own.
- FIXME placeholders are safe to search: `grep -r "FIXME" "20 Resources/Career/"`.
- `extract_cv_master.py` is idempotent via `cv_entry_id`.
