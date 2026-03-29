# Link Patterns

## Concept Links

Use idea-level notes, typically:
- `[[10 Notes/{Domain}/{Subdomain}/...]]` — atomic notes in their domain
- Canonical concept definitions or MOCs
- Domain/subdomain `_hub.md` files when linking to a broad topic area

### Hub Traversal for Link Discovery

When interweaving a note, use the domain hub hierarchy to discover link targets:

1. **Identify the note's domain** — which of the 15 domains does the note belong to?
2. **Read the domain `_hub.md`** — check its Key Notes and Subdomains for relevant targets
3. **Check Cross-Domain Links** — domain hubs list related domains; follow those for cross-cutting connections
4. **Read sibling subdomain `_hub.md` files** — use the Related section for adjacent topics

**Entry point**: `10 Notes/Domain Hubs for Vault Retrieval.md` links all 15 domain hubs.

### Hub Link Conventions

- Link to a **domain hub** when the connection is broad (e.g., "relates to agentic systems")
- Link to a **subdomain hub** when the connection is specific (e.g., "relates to agent architecture")
- Link to an **atomic note** for precise concept connections
- Prefer the most specific link level that accurately represents the relationship

## Context Links

Use execution anchors, typically:
- `[[Periodic/...]]`
- `[[Projects/...]]`
- `[[00 Inbox/...]]` when context is capture/process state

## Placement

- Add links where they improve retrieval, not as link dumps.
- Prefer one precise link over multiple weak links.
- Every interweaved note should have at least one concept link and one context link.
- When adding a concept link, prefer linking to notes within the same domain first, then cross-domain.

## Cross-Domain Interweaving

Domain hubs contain a `## Cross-Domain Links` section. Use these to discover connections across knowledge boundaries:

- Agentic Systems ↔ Knowledge Management (agent memory)
- Agentic Systems ↔ Security and Privacy (agent sandboxing)
- Health and Performance ↔ Personal Development (habit stacks)
- Philosophy and Psychology ↔ Personal Development (values, identity)
- Data Engineering ↔ Work and Career (employer data platform)
- Productivity ↔ Work and Career (professional execution)
