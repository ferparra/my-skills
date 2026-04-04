---
name: obsidian-hub-manager
version: 1.0.0
description: Manage _hub.md notes as a compressed memory layer in this Obsidian vault. Use for hub schema validation, predicate graph maintenance (hub_graph), QMD-aligned hub index generation, hub creation, and tree auditing. Trigger on hub files, hub index, hub graph, context compression, or roll-up requests.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Hub Manager

Hub notes (`_hub.md`) are the vault's compressed memory layer. Each hub is a
predicate-linked Map of Content (MOC) for a domain or subdomain. Agents load
hubs first; individual notes only when hubs are insufficient.

64 hubs across 15 domains live at `~/My Vault/10 Notes/`.

## Workflows

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing.

### 2. Audit Hub Schema Compliance

```bash
uvx --from python --with pyyaml python \
  .skills/obsidian-hub-manager/scripts/audit_hubs.py
```

For a single hub:

```bash
uvx --from python --with pyyaml python \
  .skills/obsidian-hub-manager/scripts/audit_hubs.py \
  --path "10 Notes/Knowledge Management/_hub.md"
```

Output JSON: `ok`, `total`, `compliant`, `errors`, `warnings`, `hubs[]`.
Fix all `errors` before proceeding. `warnings` are advisory.

### 3. Generate / Refresh Hub Index

```bash
uvx --from python --with pyyaml python \
  .skills/obsidian-hub-manager/scripts/generate_hub_index.py
```

Writes `10 Notes/_hub_index.md` — a QMD-indexed tree of all 64 hubs with
zettel_ids, taglines, and the agent loading protocol. Re-run after any hub
creation or predicate graph change.

### 4. Create a New Hub

1. Copy the template from `references/hub-schema.md` (Template section).
2. Set `zettel_id: zt-hub-<slug>` where slug matches the directory path.
3. Set `hub_graph.depth`: 0 for domain hubs, 1 for subdomain hubs.
4. Add `hub_graph.parent` if depth > 0.
5. Save as `10 Notes/<Domain>[/<Subdomain>]/_hub.md`.
6. Add the new hub to its parent's `## Subdomains` section and `hub_graph.children`.
7. Re-run audit and regenerate index.

### 5. Enrich Predicate Graph

Add `hub_graph` frontmatter to any hub missing it (audit will warn).

See `references/predicate-graph.md` for the full predicate taxonomy and
`hub_graph` field spec. Key fields: `depth`, `parent`, `children`,
`cross_domain`, `feeds_into`, `depends_on`.

### 6. Agent Context Loading

See `references/agent-context-protocol.md` for the full protocol.
Short form:

1. `qmd query "<topic>" -c notes -l 3` — find the relevant hub
2. Read the domain hub for compressed context (~500 tokens)
3. Read subdomain hub only if the topic is specific
4. Load individual notes only when hub context is insufficient

## What This Skill Owns

- Hub schema: frontmatter fields, section conventions, `hub_graph` predicate graph
- Hub index: `10 Notes/_hub_index.md` (generated, not hand-edited)
- Hub creation and migration workflows
- Agent context-loading protocol anchored to hubs

## Guardrails

- **Never rewrite note body content.** Body enrichment belongs to `obsidian-interweave-engine`.
- **Never mutate non-hub notes.** This skill targets `_hub.md` files only.
- **Preserve existing wikilinks.** Only add `hub_graph` frontmatter; do not alter `## Subdomains` link text.
- **Fail fast on missing dependencies.** Do not write hub files when `qmd` or `obsidian` is unavailable.
- **Keep YAML valid.** Validate frontmatter before writing.

## QMD Collection Routing

```bash
qmd query "hub index memory context" -c notes -l 5
qmd query "<domain topic>" -c notes -l 3
```

Hub files are in the `notes` collection. The hub index `_hub_index.md` is also
in `notes` and surfaces as a fast memory map.

## References

- `references/hub-schema.md` — full frontmatter spec, required sections, template
- `references/predicate-graph.md` — hub_graph field spec, predicate taxonomy
- `references/agent-context-protocol.md` — how agents load hubs for minimal context
