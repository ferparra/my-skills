---
zettel_id: zt-beef012300
zettel_kind: hub_synthesis
aliases:
  - Why Token Pressure Forces Skill Decomposition
status: processed
connection_strength: 7.5
potential_links:
  - "[[10 Notes/Context Window Pressure|Context Window Pressure]]"
  - "[[10 Notes/Token Management|Token Management]]"
  - "[[10 Notes/Agent Engineering Hub|Agent Engineering Hub]]"
synthesises:
  - "[[10 Notes/Context Window Pressure|Context Window Pressure]]"
  - "[[10 Notes/Token Management|Token Management]]"
tags:
  - type/zettel
  - zettel-kind/hub_synthesis
  - status/processed
  - tech/ai/context-engineering
  - concept/synthesis
---

# Why Token Pressure Forces Skill Decomposition

Synthesises [[10 Notes/Context Window Pressure|Context Window Pressure]] and [[10 Notes/Token Management|Token Management]].

When context window pressure exceeds 80%, the model cannot hold both the task graph and tool results simultaneously. The only escape is skill decomposition: routing subtasks to isolated subagents that each have a clean context, returning only the distilled result.

This is not a preference — it is an architectural necessity imposed by the token budget constraint.

Emerged from [[Periodic/2026/2026-W10|2026-W10]] production observations.
