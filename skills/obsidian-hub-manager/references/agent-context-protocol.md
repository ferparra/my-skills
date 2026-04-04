# Agent Context Protocol

Hubs are the vault's compressed memory layer. This protocol defines how AI
agents and subagents load hub context efficiently — maximising relevance while
minimising token cost.

## Core Principle

**Load hubs top-down, stop as early as sufficient.**

A domain hub (~300–600 tokens) covers ~80% of context needs for that domain.
Individual notes average ~1500 tokens. Always prefer hub context over note content.

## Loading Sequence

### Step 1: Query QMD for Relevant Domain

```bash
qmd query "<user topic>" -c notes -l 3
```

Look for `_hub.md` results. The hub index (`10 Notes/_hub_index.md`) is also
queryable and provides a compact tree of all 64 hubs.

For broad vault overview:
```bash
qmd get "10 Notes/_hub_index.md"
```

### Step 2: Load Domain Hub

Read the matching domain hub (`depth=0`). This gives:
- Domain scope and tagline
- Subdomain map
- Key notes list
- Cross-domain connections

**Stop here** if the task needs general domain context.

### Step 3: Load Subdomain Hub (if needed)

If the topic maps to a specific subdomain, read its `_hub.md`.
Do not read both domain and all subdomain hubs — pick the most specific one.

**Stop here** for most tasks.

### Step 4: Load Individual Notes (last resort)

Only load individual notes when:
- The hub explicitly names a note as key/critical for this topic
- The task requires exact frontmatter, dates, or verbatim content
- The hub's tagline clearly excludes the needed information

## Token Budget Guidance

| Load level | Approx tokens | When to use |
|---|---|---|
| Hub index only | ~800 | "What domains exist?" / broad orientation |
| 1 domain hub | ~500 | Domain-level context for a task |
| 1 domain + 1 subdomain hub | ~900 | Specific subdomain work |
| 1 hub + 1–2 notes | ~2500 | Precise note-level task |

Stay within the `obsidian-token-budget-guard` limits: max 5 files, max 22 000 chars.

## Subagent Handoff Pattern

When spawning a subagent for vault work, inject the relevant hub(s) directly
into the subagent prompt rather than having it rediscover them:

```
Context for this task:
<hub content from 10 Notes/Knowledge Management/_hub.md>

Task: [specific instruction]
```

This saves the subagent one full QMD + read round trip and keeps its context clean.

## Hub Index as Memory Surface

`10 Notes/_hub_index.md` is the vault's master memory surface. It contains:
- All 64 hubs with zettel_ids and taglines
- Domain tree (depth 0 → depth 1 children)
- Agent loading protocol footer

Regenerate with:
```bash
uvx --from python --with pyyaml python \
  .skills/obsidian-hub-manager/scripts/generate_hub_index.py
```

QMD indexes this file under the `notes` collection. Query it with:
```bash
qmd query "hub index domains memory" -c notes -l 1
```

## QMD Collection for Hubs

| Goal | Command |
|---|---|
| Find relevant domain | `qmd query "<topic>" -c notes -l 3` |
| Load full hub index | `qmd get "10 Notes/_hub_index.md"` |
| Find notes within a domain | `qmd query "<topic>" -c notes -l 8` then read hub |

Never use `-c obsidian` (removed). Use `-c notes` for hub discovery.

## Cross-Domain Context

When a task spans multiple domains (e.g. "AI agent memory in the vault"):

1. Load the primary domain hub (Agentic Systems or Knowledge Management)
2. Check `hub_graph.cross_domain` for linked hubs
3. Load at most 1 additional hub from the cross-domain list
4. Do not load both sides of every cross-domain link — pick the most relevant

## What Hubs Do NOT Replace

- Exact note content (dates, values, verbatim quotes)
- Notes not yet linked from any hub
- Inbox captures not yet promoted to `10 Notes/`

For these, fall through to direct QMD search or `obsidian read`.
