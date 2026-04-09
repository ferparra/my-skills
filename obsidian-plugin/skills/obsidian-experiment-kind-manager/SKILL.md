---
name: obsidian-experiment-kind-manager
version: 1.0.0
dependencies:
  - obsidian-interweave-engine
pipeline:
  inputs:
    - name: experiment_kind
      type: string
      required: false
      description: Filter by kind (health, cognitive, technical, social, financial, creative, philosophical)
    - name: glob
      type: string
      required: false
      default: "10 Notes/Productivity/Experiments/**/*.md"
      description: Glob pattern for experiment notes
    - name: mode
      type: string
      required: false
      default: check
      description: Mode (check, fix)
  outputs:
    - name: validated_experiments
      type: file
      path: "10 Notes/Productivity/Experiments/{slug}.md"
      description: Validated experiment notes
    - name: experiments_base
      type: file
      path: "10 Notes/Productivity/Experiments/Experiments.base"
      description: Experiments Base (Obsidian YAML DSL)
    - name: experiment_report
      type: json
      path: ".skills/experiment-report.json"
      description: Validation / migration report
description: Validate, migrate, scaffold, and render typed experiment notes in Obsidian. Use for experiment_kind enforcement, hypothesis lifecycle management, Experiments.base rendering, connection_strength scoring, and cross-council experiment graph traversal.
metadata:
  openclaw:
    os:
      - darwin
    requires:
      bins:
        - obsidian
        - qmd
        - uvx
---

# Obsidian Experiment Kind Manager

Run this skill for experiment lifecycle work: kind classification, frontmatter
normalisation, lifecycle transitions, and Base rendering.

`experiment_kind` is the supertag — inspired by Tana's supertag concept. It
selects each experiment note's strict Pydantic v2 schema contract and routes
accountability to the correct council member. The seven kinds are: `health`,
`cognitive`, `technical`, `social`, `financial`, `creative`, `philosophical`.

Experiments live at `10 Notes/Productivity/Experiments/` under the Strategist's
Productivity domain. Each experiment carries a `council_owner` field that
identifies which council member is accountable for the experiment's domain
(e.g. `sentinel` for health, `architect` for technical).

## Lifecycle

```
hypothesis → design → running → paused → concluded → archived
```

`outcome` tracks epistemic result: `confirmed`, `refuted`, `inconclusive`,
`abandoned`, `ongoing`.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Never mutate notes when tooling is
unavailable.

### 2. Read the Experiment Surface

```bash
obsidian read path="10 Notes/Productivity/Experiments/Experiments.base"
qmd query "experiment hypothesis running concluded health cognitive" -c notes -l 8
qmd query "experiment design protocol intervention metric" -c inbox -l 5
```

Default scope: `10 Notes/Productivity/Experiments/**/*.md`.

### 3. Validate in Check Mode

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/validate_experiments.py \
  --glob "10 Notes/Productivity/Experiments/**/*.md" --mode check
```

Review per-note: `experiment_kind`, `status`, `errors`, `warnings`. No files
are written.

### 4. Dry-Run Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/migrate_experiments.py \
  --glob "10 Notes/Productivity/Experiments/**/*.md" --mode check
```

Inspect `changed_fields` and `warnings`. Notes with ambiguous kind require
manual confirmation before applying.

### 5. Apply Migration

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/migrate_experiments.py \
  --glob "10 Notes/Productivity/Experiments/**/*.md" --mode fix
```

Injects `experiment_kind`, `experiment_id`, `status`, `council_owner`,
`domain_tag`, normalised tags. Never rewrites note bodies.

### 6. Scaffold a New Experiment

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/new_experiment.py \
  --kind health \
  --question "What effect does 300mg Magnesium Glycinate have on sleep latency?" \
  --output "10 Notes/Productivity/Experiments/Magnesium Sleep Experiment.md"
```

Creates a well-formed experiment note with all required fields pre-filled and
a structured body template. Status starts at `hypothesis`.

### 7. Render the Experiments Base

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/render_experiments_base.py \
  --output "10 Notes/Productivity/Experiments/Experiments.base"
```

Writes the Obsidian YAML DSL Base file. Reads all validated experiment notes,
aggregates lifecycle and outcome signals, and produces a filterable table view
grouped by `status` and `experiment_kind`.

### 8. Re-Validate and Verify

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/validate_experiments.py \
  --glob "10 Notes/Productivity/Experiments/**/*.md" --mode check

obsidian read path="10 Notes/Productivity/Experiments/Experiments.base"
obsidian search query="experiment_kind" limit=20 total
obsidian unresolved total
```

Confirm `"ok": true` overall before closing.

### Single-Note Workflow

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/validate_experiments.py \
  --path "10 Notes/Productivity/Experiments/Magnesium Sleep Experiment.md"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-experiment-kind-manager/scripts/migrate_experiments.py \
  --path "10 Notes/Productivity/Experiments/Magnesium Sleep Experiment.md" --mode fix
```

## Council Ownership Routing

| experiment_kind   | council_owner | domain_tag                  |
|-------------------|---------------|-----------------------------|
| health            | sentinel      | health-and-performance      |
| cognitive         | philosopher   | philosophy-and-psychology   |
| technical         | architect     | agentic-systems             |
| social            | steward       | relationships               |
| financial         | sentinel      | financial-stewardship       |
| creative          | philosopher   | philosophy-and-psychology   |
| philosophical     | philosopher   | philosophy-and-psychology   |

## What This Skill Owns

- Canonical experiment frontmatter: `experiment_kind`, `experiment_id`,
  `status`, `outcome`, `council_owner`, `domain_tag`, `question`,
  `hypothesis`, `method`, `metrics`, `interventions`, `controls`,
  `confounders`, `findings`, `confidence`, `connection_strength`,
  `potential_links`, `related`, `next_experiments`, `tags`.
- Lifecycle transitions and Pydantic v2 schema enforcement.
- Experiment notes under `10 Notes/Productivity/Experiments/**/*.md`.
- `Experiments.base` rendering and column definitions.
- Managed tag prefixes: `type/experiment`, `experiment-kind/*`, `status/*`.

## Guardrails

- **Never rewrite body content.** Body enrichment belongs to
  `obsidian-interweave-engine`.
- **Never auto-conclude an experiment.** Status transitions to `concluded` or
  `archived` require explicit human intent.
- **Never overwrite explicit user values.** Only inject missing canonical fields.
- **`outcome` defaults to `ongoing`.** Never infer a terminal outcome.
- **`experiment_id` is stable once set.** Never regenerate an existing ID.
- **Keep YAML valid** — validate output before writing.
- **Ambiguous kind blocks fix mode.** Emit warning, skip write, require
  human confirmation.

## QMD Collection Routing

| Query intent                     | Collection   |
|----------------------------------|--------------|
| Active / concluded experiments   | `-c notes`   |
| Experiment ideas in inbox        | `-c inbox`   |

```bash
qmd query "experiment hypothesis running concluded health cognitive" -c notes -l 8
qmd query "experiment design protocol intervention metric" -c inbox -l 5
```

## References

- `references/experiment-schema.md` — canonical field contract and scoring formula
- `references/experiment-kind-taxonomy.md` — kind values, council routing, lifecycle policy
- `scripts/experiment_models.py` — shared Pydantic v2 models (source of truth)
- Cross-skill: run `obsidian-interweave-engine` after migration if body link density is low
