# Zettel Kind Taxonomy

## Overview

`zettel_kind` is the supertag for zettel notes. It selects the note's schema contract, enforced by Pydantic v2 via `ZettelFrontmatter`. Choose the smallest stable kind — prefer `atomic` over `hub_synthesis` unless the note genuinely synthesises multiple inputs.

---

## Kind Table

| Kind | Description | Required Extra Fields | Title Pattern | Example |
|---|---|---|---|---|
| `atomic` | Single non-decomposable idea or mechanism | none | Plain noun phrase or short assertion | "Context Window Pressure" |
| `moc` | Map of Content — curates a cluster of related zettels | `hub_for: list[str]` | Topic + " Hub" suffix | "Agent Engineering Hub" |
| `litnote` | Literature note from an external source | `source: str` | "LastName - Title" or "Domain - Article Title" | "Newport - Deep Work" |
| `fleeting_capture` | Raw inbox capture, unprocessed | `captured_from` (optional) | "Idea - …" / "Friction - …" / "Capture - …" | "Friction - Thread Inference Fails Without Periodic Note" |
| `hub_synthesis` | New insight produced by connecting existing zettels | `synthesises: list[str]` | Causal or relational assertion with Why/How/When | "Why Token Pressure Forces Skill Decomposition" |
| `definition` | Canonical definitional reference for a term | `defines: str` | The bare canonical term | "Zettelkasten" |

---

## Kind-Specific Rules

### `atomic`
- One core idea per note. If you find yourself writing two arguments, split into two atomics.
- Title: title-cased noun phrase. No kind prefix in title.
- No extra required fields beyond the base schema.
- Connects to concept notes (`10 Notes/`) and at least one context note (`Periodic/` or `00 Inbox/`).

### `moc`
- Does not carry its own propositional argument; it indexes and curates.
- `hub_for`: list of topic domains this MOC organises (e.g., `["agent-engineering", "agentic-ai"]`).
- Title: Topic + " Hub" for standalone MOCs. Domain/subdomain hubs use `_hub.md` filename convention.
- Create a MOC when a topic has ≥5 linked atomics and navigation without a hub is cumbersome.
- Aligns with existing `type/moc` tag convention.

#### Domain Hub Convention

The vault uses a two-level domain hierarchy with `_hub.md` files:

| Hub Level | Location | `connection_strength` | Tags |
|---|---|---|---|
| Domain hub | `10 Notes/{Domain}/_hub.md` | `10.0` | `domain/{slug}` |
| Subdomain hub | `10 Notes/{Domain}/{Subdomain}/_hub.md` | `8.0` | `domain/{slug}`, `subdomain/{slug}` |

**Domain hub template** (15 domains):
- `## Subdomains` — links to subdomain `_hub.md` files
- `## Key Notes` — top atomic notes in this domain
- `## Cross-Domain Links` — links to related domain hubs

**Subdomain hub template** (49 subdomains):
- `**Parent domain**:` — backlink to parent domain hub
- `## Notes` — lists all atomic notes in the subdomain
- `## Related` — links to sibling subdomain hubs

Master index: `10 Notes/Domain Hubs for Vault Retrieval.md`

### `litnote`
- One litnote per source. Captures the source's key claims and the reader's reaction or synthesis.
- `source`: author/title string or URL. Format: "LastName, FirstName - Title (Year)" or URL.
- `source_date`: ISO date of publication or access (optional but recommended).
- Aligns with existing `type/resource-litnote` tag convention.
- Title: "LastName - Short Title" or "Domain - Article Title" for web sources.

### `fleeting_capture`
- Should not remain `fleeting_capture` long-term. Migrate to `atomic`, `litnote`, or `hub_synthesis` after processing.
- Lives in `00 Inbox/` before promotion to `10 Notes/{Domain}/{Subdomain}/`.
- When promoting, identify the target domain and subdomain from the note's topic. Use the domain hub's subdomain list to find the right destination.
- `captured_from`: wikilink to the daily note or session where the capture happened (optional).
- The migrate script warns if a `fleeting_capture` note is older than 30 days.
- Title: prefix with "Idea - ", "Friction - ", or "Capture - " to distinguish from durable notes.

### `hub_synthesis`
- Produces new knowledge by connecting two or more existing zettels.
- `synthesises`: list of wikilinks to the contributing atomics, litnotes, or hub_syntheses.
- Distinct from `moc` (which indexes) and `atomic` (which states one idea alone).
- `connection_strength` is expected to be higher for `hub_synthesis` notes since they depend on multiple strong inlinks to justify synthesis.
- Title: causal or relational assertion — "Why…", "How…", "When…".

### `definition`
- The stable reference for a term used across many notes.
- Use instead of `atomic` when primary value is definitional precision, not propositional argument.
- `defines`: the canonical term being defined (e.g., "Zettelkasten", "Context Window").
- If `defines` is missing during migration, the script infers it from the filename.
- Aligns with existing `type/definition` tag convention.
- Title: the bare canonical term, title-cased.

---

## Status Lifecycle

```
fleeting → processing → processed → evergreen
```

| Status | Meaning | Typical Location |
|---|---|---|
| `fleeting` | Raw capture, unreviewed | `00 Inbox/` |
| `processing` | Under active processing or in-flight enrichment | `00 Inbox/` or `10 Notes/{Domain}/{Subdomain}/` |
| `processed` | Reviewed, linked, frontmatter complete | `10 Notes/{Domain}/{Subdomain}/` |
| `evergreen` | Stable, well-connected, regularly revisited | `10 Notes/{Domain}/{Subdomain}/` |

Managed tag convention: `status/{status}` is injected by `normalize_zettel_tags` and must not be manually duplicated.

---

## Kind Selection Guidance

1. Start with `atomic` — it is the default for new ideas.
2. Upgrade to `hub_synthesis` only when the note's primary value is the _connection_ between inputs, not any single input alone.
3. Create `moc` when a topic has ≥5 linked atomics and direct note navigation becomes cumbersome.
4. Use `litnote` for every processed external source; do not mix source synthesis into atomics.
5. Use `fleeting_capture` for unprocessed inbox captures; promote promptly.
6. Use `definition` sparingly — only for terms that appear frequently enough across notes to warrant a canonical definitional anchor.

---

## Title Casing Convention

All zettel titles use **title case**. This distinguishes note titles from tag values (lowercase) and signal intentional naming.

| Kind | Example |
|---|---|
| `atomic` | "Context Window Pressure" |
| `moc` | "Agent Engineering Hub" |
| `litnote` | "Newport - Deep Work" |
| `fleeting_capture` | "Friction - Thread Inference Fails Without Periodic Note" |
| `hub_synthesis` | "Why Token Pressure Forces Skill Decomposition" |
| `definition` | "Zettelkasten" |
