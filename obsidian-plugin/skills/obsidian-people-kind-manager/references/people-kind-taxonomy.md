# People Kind Taxonomy

`person_kind` is the supertag for person notes. It selects the schema contract enforced by Pydantic v2.

---

## Kind Values

| `person_kind` | Description | Kind-specific field |
|---|---|---|
| `manager` | Has direct authority or accountability over Fernando's work, scope, or compensation. | `management_cadence` — cadence of accountability touchpoints (e.g. "weekly 1:1", "monthly review"). |
| `collaborator` | Peer-level working relationship; shares delivery ownership without a reporting structure. | none beyond common fields |
| `stakeholder` | Influences outcomes Fernando works on but is not a delivery partner; decision-maker or approver. | `influence_domain` — area of influence (e.g. "data-platform", "sales", "product"). |
| `customer_contact` | External or internal customer; relationship is oriented around Fernando delivering value to them. | `account_context` — wikilink or free string identifying the account (e.g. `[[Companies/Acme\|Acme]]`). |
| `mentor` | Advisorial relationship; expertise and guidance flow primarily from them toward Fernando. | `domain_of_mentorship` — domain of mentoring (e.g. "career", "technical", "leadership"). |
| `author` | Intellectual influence only; relationship is through their published works, not direct interaction. | `primary_works` — **required, non-empty list** of titles or wikilinks to their works. Hard validation error if absent. |
| `acquaintance` | Personal relationship (friend, family, partner, sibling, etc.); non-professional primary context. | `personal_context` — e.g. "friend", "family/sibling", "partner". |

---

## Kind-Specific Enforcement Policy

- **`author`**: `primary_works` is a hard validation error if absent. Without it the note has no meaningful CRM content.
- **All other kinds**: Kind-specific fields use FIXME placeholders injected by `migrate_people.py` on first migration, paired with a warning. They are never hard errors.
- The migrator uses `only_if_missing` logic — it never overwrites explicit user values.

---

## Kind Inference Heuristics

Applied by `migrate_people.py` when `person_kind` is absent. Rules evaluated top-to-bottom; first match wins. Ambiguous = multiple signals → skip write, emit warning, require human confirmation.

1. `relationship_conditions` contains "line manager", "reports to", "manager", "managing" → **`manager`**
2. `relationship_conditions` contains "stakeholder", "CTO", "head of", "director", "decision" → **`stakeholder`**
3. `relationship_conditions` contains "customer", "account", "client", "dealer" → **`customer_contact`**
4. `relationship_conditions` contains "mentor", "advisory", "coach" → **`mentor`**
5. `tags` contains `author` AND `relationship_conditions` is empty → **`author`**
6. `relationship_to_fernando` is "friend", "family", "partner", "sibling" OR `primary_context` starts with "personal" → **`acquaintance`**
7. `relationship_to_fernando` is "colleague" AND none of the above → **`collaborator`** (unambiguous)
8. No signals → **`collaborator`** flagged ambiguous

---

## Status Lifecycle

| Status | Meaning | Transition |
|---|---|---|
| `fleeting` | Note created; minimal enrichment | Automatic default on creation |
| `processing` | Active relationship; note being built up over time | Set by user or migrator from `status/processing` tag |
| `processed` | Stable profile; low-frequency updates expected | Set by user |
| `dormant` | Relationship inactive; note preserved for history | **Manual only** — migrator never sets or downgrades to dormant |

---

## Interaction Tracking Policy

- `last_interaction_date` (YYYY-MM-DD): derived by `enrich_people.py` from the latest `## YYYY-MM-DD` heading in the note body. Always `only_if_missing`.
- `interaction_frequency`: inferred from gap distribution between dated headings if 3+ entries. Always `only_if_missing`.
- Neither field is ever overwritten if explicitly set by the user.

Recency bonus in `connection_strength` scoring:

| Days since last interaction | Recency bonus |
|---|---|
| ≤ 30 days | +0.15 |
| ≤ 90 days | +0.10 |
| ≤ 180 days | +0.05 |
| > 180 days or absent | +0.00 |

---

## Migration Rules

- Never rewrite note bodies — body enrichment belongs to `obsidian-interweave-engine`.
- Preserve all existing metadata the skill does not own.
- Skip ambiguous kind inference; emit warning; require human confirmation.
- `status: dormant` is manual-only; migrator never downgrades an active status.
- FIXME placeholders are safe to search for: `grep -r "FIXME" People/`.
