# Hub Schema Reference

`_hub.md` files are Map of Content (MOC) notes — one per directory under
`10 Notes/`. They provide compressed, predicate-linked representations of
their domain for both human navigation and AI agent context loading.

## Frontmatter Spec

### Required Fields

| Field | Type | Convention |
|---|---|---|
| `zettel_id` | string | `zt-hub-<slug>` where slug is kebab-case path (e.g. `zt-hub-knowledge-management`) |
| `zettel_kind` | string | Always `moc` |
| `status` | string | `processing` (active domain) or `stable` (dormant) |
| `connection_strength` | float | 0.0–10.0; root domains ≥ 8.0, subdomains ≥ 5.0 |
| `tags` | list | Must include `type/moc` and at least one `domain/<slug>` tag |
| `type` | string | Always `moc` |

### Optional Fields

| Field | Type | Purpose |
|---|---|---|
| `hub_for` | list | Legacy field; leave `[]` — use `hub_graph.children` instead |
| `hub_graph` | object | Machine-readable predicate graph (see predicate-graph.md) |

### Tag Conventions

```yaml
tags:
  - type/moc
  - domain/knowledge-management          # always: domain/<root-domain-slug>
  - subdomain/agent-memory               # if depth > 0: subdomain/<subdomain-slug>
```

## Body Spec

### Required Sections (in order)

1. **H1 Title** — matches the directory name (e.g. `# Knowledge Management`)
2. **Tagline paragraph** — one sentence describing the domain scope
3. At least one of the content sections below

### Content Sections

| Section header | When required | Content |
|---|---|---|
| `## Subdomains` | If hub has child hubs | Wikilinks to child `_hub.md` files with descriptions |
| `## Key Notes` or `## Notes` | Always | 3–10 wikilinks to the most important notes in this domain |
| `## Cross-Domain Links` or `## Related` | When cross-domain connections exist | Wikilinks to related domain/subdomain hubs |

### Parent Reference (subdomain hubs only)

Subdomain hubs (depth > 0) must include a bold parent reference immediately
after the tagline:

```markdown
**Parent domain**: [[10 Notes/Knowledge Management/_hub|Knowledge Management]]
```

### Wikilink Format

Always use full vault-relative paths with display text:

```markdown
[[10 Notes/Domain/Subdomain/_hub|Subdomain Name]] — brief description
```

## Hub Template

```markdown
---
zettel_id: zt-hub-<slug>
zettel_kind: moc
status: processing
connection_strength: 8.0
hub_for: []
hub_graph:
  depth: 0
  parent: ""
  children: []
  cross_domain: []
  feeds_into: []
  depends_on: []
tags:
  - type/moc
  - domain/<slug>
type: moc
---

# <Domain Name>

<One-sentence tagline describing the domain scope.>

## Key Notes

- [[<note title>]]

## Cross-Domain Links

- [[10 Notes/<Other Domain>/_hub|<Other Domain>]] (<relationship reason>)
```

For subdomain hubs (depth 1), change `hub_graph.depth` to `1`, set
`hub_graph.parent`, add `subdomain/<slug>` tag, and add the parent reference
line after the tagline.

## Validation Rules

Run `audit_hubs.py` to enforce all rules. Key checks:

- `zettel_id` starts with `zt-hub-`
- `zettel_kind` and `type` are both `moc`
- `tags` includes `type/moc`
- At least one `domain/*` tag present
- H1 title exists in body
- Tagline paragraph follows H1
- Subdomain hubs have parent reference
- `hub_graph` present (advisory; warns if missing)

## zettel_id Slug Conventions

| Path | zettel_id |
|---|---|
| `10 Notes/Knowledge Management/_hub.md` | `zt-hub-knowledge-management` |
| `10 Notes/Knowledge Management/Agent Memory/_hub.md` | `zt-hub-km-agent-memory` |
| `10 Notes/Work and Career/AutoGrab/_hub.md` | `zt-hub-work-career-autograb` |

Subdomain slugs use the format `zt-hub-<domain-abbrev>-<subdomain>` when the
full domain slug would be too long. Prefer clarity over brevity.
