---
name: obsidian-token-budget-guard
version: 1.1.0
dependencies: []
description: >
  Enforce strict context and token budget gates for this personal Obsidian vault
  before substantial note reads or edits. Use when candidate files are known and
  you must validate max files, max chars, and max snippet counts with fail-fast
  obsidian/qmd dependency checks. Includes pre-flight estimation to predict token
  costs before executing broad queries.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Token Budget Guard

Use this skill before loading broad context. It provides two modes:

1. **Post-flight check** — validates token usage after files are selected
2. **Pre-flight estimation** — predicts token costs before executing a broad query

## Workflow

### Pre-Flight: Estimate Before Querying

Use pre-flight estimation when planning a broad search or read operation:

```bash
# Estimate cost of a query that might touch many files
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-token-budget-guard/scripts/token_guard.py \
  --mode preflight \
  --query "status:open AND priority:high" \
  --vault-root "." \
  --output token_estimate.json
```

Pre-flight scan results:
```json
{
  "ok": true,
  "mode": "preflight",
  "estimate": {
    "matching_notes": 47,
    "total_chars": 89400,
    "token_estimate": 22350,
    "warning_level": "yellow",
    "breakdown": [...]
  },
  "warning_thresholds": {
    "green": "<5000 tokens",
    "yellow": "5000-15000 tokens",
    "red": ">15000 tokens"
  }
}
```

### Post-Flight: Validate Before Reading

After building a candidate file list:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-token-budget-guard/scripts/token_guard.py \
  --mode guard \
  --candidate-files "People/Alice.md,People/Bob.md,20 Resources/Exercises/ bench.md" \
  --max-files 5 --max-chars 22000 --max-snippets 12
```

### Decision Flow

```
Query planned
    │
    ▼
┌─────────────────┐
│  Pre-flight     │  ◄─── Before running obsidian search or qmd query
│  estimation      │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Estimate │
    │ OK?      │
    └────┬────┘
         │
    ┌────┴─────────────────┐
    │                      │
    ▼                      ▼
  GREEN/YELLOW        RED (too expensive)
    │                      │
    ▼                      ▼
Execute query         Reduce scope
    │                 (narrow search,
    │                  add filters)
    ▼                      │
┌─────────────────┐         │
│  Post-flight    │  ◄──────┘
│  guard check    │     Re-run pre-flight
└────────┬────────┘
         │
    ┌────┴────┐
    │ Guard   │
    │ Passes? │
    └────┬────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  YES        NO
    │         │
    ▼         ▼
  Read    Reduce scope
  notes   and retry
```

## Modes

### Pre-Flight Mode (`--mode preflight`)

Estimates token cost before executing a query:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-token-budget-guard/scripts/token_guard.py \
  --mode preflight \
  --query "person_kind:collaborator" \
  --vault-root "." \
  --output token_estimate.json
```

Arguments:
- `--query` — the search query to estimate (used with `obsidian search`)
- `--vault-root` — vault root directory
- `--output` — output path for `token_estimate.json`

Output:
```json
{
  "ok": true,
  "mode": "preflight",
  "estimate": {
    "matching_notes": 23,
    "total_chars": 41200,
    "token_estimate": 10300,
    "warning_level": "yellow",
    "breakdown": [
      {"path": "People/Alice.md", "chars": 1800, "tokens_estimate": 450},
      ...
    ]
  },
  "thresholds": {
    "green_max": 5000,
    "yellow_max": 15000,
    "red_above": 15000
  }
}
```

### Guard Mode (`--mode guard`)

Validates token budget against hard limits (original behavior):

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-token-budget-guard/scripts/token_guard.py \
  --mode guard \
  --candidate-files "file1.md,file2.md" \
  --max-files 5 --max-chars 22000 --max-snippets 12
```

## Output Contract

### Pre-Flight Output

Returns JSON with:
- `ok`: true if estimate is within yellow threshold
- `mode`: "preflight"
- `estimate`: breakdown including matching_notes, total_chars, token_estimate, warning_level, breakdown
- `thresholds`: warning thresholds
- `recommendation`: action to take

### Guard Mode Output

Returns JSON with:
- `ok`: true only when all gates pass
- `summary`: candidate_count, existing_count, total_chars
- `limits`: max_files, max_chars, max_snippets
- `violations`: list of violated gates
- `remediation`: suggested actions

Exit code is non-zero on any gate violation.

## Warning Thresholds

| Level | Token Range | Action |
|---|---|---|
| GREEN | < 5,000 tokens | Safe to proceed |
| YELLOW | 5,000 – 15,000 tokens | Proceed with caution; narrow scope if possible |
| RED | > 15,000 tokens | Do not proceed; reduce scope |

## Token Estimation Formula

```
tokens ≈ chars / 4 (approximate ratio for typical English text)
per-note overhead: 50 tokens
total = sum((note_chars / 4) + 50) for each note
```

## Dependency Policy

Fail fast when `obsidian`, `qmd`, or `uvx` is missing.
Do not continue with broad reads after dependency failures.

## Query Patterns and Cost

| Query Type | Typical Scope | Cost |
|---|---|---|
| `tag:foo` | Narrow | Low |
| `person_kind:collaborator` | Medium | Medium |
| `status:open` | Broad | High |
| `folder:"20 Resources"` | Broad | High |
| Unfiltered search | Very broad | Red zone |

## Scope Reduction Patterns

See `references/compaction-playbook.md` for detailed strategies to reduce query scope.

## References

- `references/token-budget-rules.md` — enforced thresholds
- `references/compaction-playbook.md` — scope reduction patterns
- `scripts/token_guard.py` — the main script
