---
name: qmd
version: 1.0.0
description: Search markdown knowledge bases, notes, and documentation using QMD. Use when users ask to search notes, find documents, or look up information.
license: MIT
compatibility: Requires qmd CLI or MCP server. Install via `npm install -g @tobilu/qmd`.
metadata:
  author: tobi
  version: "2.0.0"
  openclaw:
    requires:
      bins:
        - qmd
        - obsidian
        - curl
        - npm
allowed-tools: Bash(qmd:*), mcp__qmd__*
---

# QMD - Quick Markdown Search

Local search engine for markdown content.

## Status

!`qmd status 2>/dev/null || echo "Not installed: npm install -g @tobilu/qmd"`

## Vault Search Workflow

1. Route the search to the narrowest relevant collection first. Use the collection table below; fall back to `all` only when intent is broad or unclear.
2. When using the MCP `query` tool, pass `searches` as a real array of objects. Never wrap the array in a JSON-encoded string.
3. Treat search results as candidate selection, not the final answer. Open the best hit with `get`, `multi_get`, or `obsidian read`, then answer from the note content.
4. If the top hit is ambiguous, read the top 2-3 results before answering.
5. If `qmd query` fails to initialize local models, use `qmd search` for keyword recall and then open the hit directly.
6. If QMD ranking is weak, results look stale, or you need vault-native follow-up, fall back to `obsidian search` plus `obsidian read`.

## MCP: `query`

```json
{
  "searches": [
    { "type": "lex", "query": "CAP theorem consistency" },
    { "type": "vec", "query": "tradeoff between consistency and availability" }
  ],
  "collections": ["docs"],
  "limit": 10
}
```

Use this exact shape when calling the MCP tool. If you are unsure about the live schema, inspect the tool signature first and then issue the query.

### Query Types

| Type | Method | Input |
|------|--------|-------|
| `lex` | BM25 | Keywords — exact terms, names, code |
| `vec` | Vector | Question — natural language |
| `hyde` | Vector | Answer — hypothetical result (50-100 words) |

### Writing Good Queries

**lex (keyword)**
- 2-5 terms, no filler words
- Exact phrase: `"connection pool"` (quoted)
- Exclude terms: `performance -sports` (minus prefix)
- Code identifiers work: `handleError async`

**vec (semantic)**
- Full natural language question
- Be specific: `"how does the rate limiter handle burst traffic"`
- Include context: `"in the payment service, how are refunds processed"`

**hyde (hypothetical document)**
- Write 50-100 words of what the *answer* looks like
- Use the vocabulary you expect in the result

**expand (auto-expand)**
- Use a single-line query (implicit) or `expand: question` on its own line
- Lets the local LLM generate lex/vec/hyde variations
- Do not mix `expand:` with other typed lines — it's either a standalone expand query or a full query document

### Combining Types

| Goal | Approach |
|------|----------|
| Know exact terms | `lex` only |
| Don't know vocabulary | Use a single-line query (implicit `expand:`) or `vec` |
| Best recall | `lex` + `vec` |
| Complex topic | `lex` + `vec` + `hyde` |

First query gets 2x weight in fusion — put your best guess first.

### Lex Query Syntax

| Syntax | Meaning | Example |
|--------|---------|---------|
| `term` | Prefix match | `perf` matches "performance" |
| `"phrase"` | Exact phrase | `"rate limiter"` |
| `-term` | Exclude | `performance -sports` |

Note: `-term` only works in lex queries, not vec/hyde.

### Collection Filtering

```json
{ "collections": ["docs"] }              // Single
{ "collections": ["docs", "notes"] }     // Multiple (OR)
```

Omit to search all collections.

**Vault collection routing** — scope searches for token efficiency:

| Query intent          | Collection   |
|-----------------------|-------------|
| Unprocessed captures  | `inbox`     |
| Durable knowledge     | `notes`     |
| Planning / reviews    | `periodic`  |
| External references   | `resources` |
| Web clips             | `clippings` |
| Project context       | `projects`  |
| Person/company lookup | `entities`  |
| Historical recall     | `archive`   |
| Unknown / broad       | `all`       |

## Other MCP Tools

| Tool | Use |
|------|-----|
| `get` | Retrieve doc by path or `#docid` |
| `multi_get` | Retrieve multiple by glob/list |
| `status` | Collections and health |

For note lookup tasks, the expected sequence is usually `query` -> `get` (or `multi_get`) -> answer.

## CLI

```bash
qmd query "question"              # Auto-expand + rerank
qmd query "lex: X
vec: Y"                            # Structured
qmd query $'expand: question'     # Explicit expand
qmd search "keywords"             # BM25 only (no LLM)
qmd get "#abc123"                 # By docid
qmd get "qmd://inbox/00 Inbox/empanadas.md" -l 80
qmd multi-get "journals/2026-*.md" -l 40  # Batch pull snippets by glob
qmd multi-get notes/foo.md,notes/bar.md   # Comma-separated list, preserves order
```

For vault questions, prefer a two-step pattern:

```bash
qmd query "empanadas recipe" -c inbox -n 5
qmd get "qmd://inbox/00 Inbox/empanadas.md" -l 120
```

If you need a vault-native fallback or exact-path read after ranking:

```bash
obsidian search query="empanadas" limit=5
obsidian read path="00 Inbox/empanadas.md"
```

If the local QMD model backend is unavailable, use the zero-LLM fallback:

```bash
qmd search "empanadas" -c inbox -n 5
qmd get "qmd://inbox/00-inbox/empanadas.md" -l 120
```

## HTTP API

```bash
curl -X POST http://localhost:8181/query -H "Content-Type: application/json" -d '{"searches": [{"type": "lex", "query": "test"}]}'
```

## Setup

```bash
npm install -g @tobilu/qmd
qmd collection add ~/notes --name notes
qmd embed
```
