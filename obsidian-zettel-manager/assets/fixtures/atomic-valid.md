---
zettel_id: zt-a1b2c3d4e5
zettel_kind: atomic
aliases:
  - Context Window Pressure
  - Token Pressure
status: processed
connection_strength: 6.5
potential_links:
  - "[[10 Notes/Token Management|Token Management]]"
  - "[[10 Notes/Agent Loop|Agent Loop]]"
tags:
  - type/zettel
  - zettel-kind/atomic
  - status/processed
  - tech/ai/context-engineering
  - concept/mechanism
---

# Context Window Pressure

When an agent's context window fills beyond 80% capacity, retrieval quality degrades and the model begins truncating earlier reasoning. This pressure forces tradeoffs between history depth and working memory.

Related concepts: [[10 Notes/Token Management|Token Management]], [[10 Notes/Agent Loop|Agent Loop]], [[10 Notes/Multi-Agent Systems|Multi-Agent Systems]].

Created during [[Periodic/2026/2026-W10|2026-W10]] after observing repeated compaction events in production agent runs.
