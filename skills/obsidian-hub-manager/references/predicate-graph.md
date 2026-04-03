# Hub Predicate Graph Reference

Hubs form a typed predicate graph that makes the vault's knowledge structure
machine-readable. Predicates live in the `hub_graph` frontmatter field.

## hub_graph Frontmatter Spec

```yaml
hub_graph:
  depth: 0              # int: 0=domain root, 1=subdomain, 2=deep subdomain
  parent: ""            # vault-relative path without .md (empty for depth-0 hubs)
  children:             # list of child hub paths (vault-relative, no .md)
    - "10 Notes/Knowledge Management/Agent Memory/_hub"
    - "10 Notes/Knowledge Management/Processing/_hub"
  cross_domain:         # semantically linked hubs outside parent/child hierarchy
    - "10 Notes/Agentic Systems/_hub"
  feeds_into: []        # output/conclusions of this domain flow into these domains
  depends_on: []        # this domain draws heavily from these domains for context
```

All paths are vault-relative without the `.md` extension.

## Predicate Taxonomy

### Hierarchical Predicates

| Predicate | Direction | Field | Example |
|---|---|---|---|
| `parent_of` | hub → child hubs | `hub_graph.children` | KM → Agent Memory |
| `child_of` | hub → parent hub | `hub_graph.parent` | Agent Memory → KM |

These mirror the `## Subdomains` and `**Parent domain**:` body sections.
Both must be kept in sync.

### Cross-Domain Predicates

| Predicate | Direction | Field | Semantics |
|---|---|---|---|
| `related_to` | bidirectional | `hub_graph.cross_domain` | Shares concepts or audience |
| `feeds_into` | hub → target | `hub_graph.feeds_into` | Output/insights flow toward target |
| `depends_on` | hub → source | `hub_graph.depends_on` | Draws context or primitives from source |

### Choosing the Right Predicate

Use `cross_domain` (related_to) as the default for loose semantic connection.

Use `feeds_into` when: conclusions from one domain improve work in another.
  - Reading feeds_into Personal Development (insights → growth)
  - Data Engineering feeds_into Agentic Systems (pipelines → agent tools)

Use `depends_on` when: one domain cannot be understood without another.
  - Agentic Systems depends_on Software Engineering (foundations)
  - Financial Stewardship/Portfolio depends_on Data Engineering (analytics)

## Graph Integrity Rules

Run `audit_hubs.py` to check these automatically:

1. **Bidirectional parent/child**: if hub A lists B in `children`, B must set `parent` to A.
2. **Cross-domain symmetry**: preferred but not required — note asymmetric edges in comments.
3. **Path existence**: all paths in `hub_graph` must resolve to real `_hub.md` files.
4. **Depth consistency**: `depth` must equal the number of directory levels below `10 Notes/` minus 1.

## Mapping Body Sections to Predicates

The body sections are the human-readable view; `hub_graph` is the machine-readable view.
Keep both in sync after any hub edit.

| Body section | Predicate field |
|---|---|
| `## Subdomains` | `hub_graph.children` |
| `**Parent domain**:` | `hub_graph.parent` |
| `## Cross-Domain Links` | `hub_graph.cross_domain` |
| `## Related` | `hub_graph.cross_domain` |

## Example: Knowledge Management Hub

```yaml
hub_graph:
  depth: 0
  parent: ""
  children:
    - "10 Notes/Knowledge Management/Vault Infrastructure/_hub"
    - "10 Notes/Knowledge Management/Agent Memory/_hub"
    - "10 Notes/Knowledge Management/Processing/_hub"
  cross_domain:
    - "10 Notes/Agentic Systems/_hub"
    - "10 Notes/Productivity/_hub"
  feeds_into:
    - "10 Notes/Agentic Systems/_hub"
  depends_on: []
```

## Graph Traversal for Agents

When an agent needs context on a topic:

1. Start at the domain hub (depth 0) — covers ~80% of cases.
2. Follow `children` only if subdomain precision is needed.
3. Follow `cross_domain` links when the topic spans multiple domains.
4. Follow `feeds_into` / `depends_on` when tracing knowledge flow.
5. Stop before loading individual notes unless the hub references one directly.

Maximum recommended traversal: 3 hubs per task (1 domain + 1 subdomain + 1 cross-domain).
