# Skill Pipeline Composer

Chains skills together where output of one feeds into the next.

## Overview

The Pipeline Composer reads `SKILL.md` frontmatter from each skill to understand:
- What inputs each skill requires
- What outputs each skill produces
- What other skills it depends on

It then automatically resolves dependencies and executes skills in the correct order.

## Pipeline Contract Format

Skills declare their pipeline inputs and outputs in `SKILL.md` frontmatter:

```yaml
---
name: obsidian-planetary-tasks-manager
version: 1.0.0
pipeline:
  inputs:
    - name: task_kind
      type: string
      required: false
      description: Filter by task kind
  outputs:
    - name: validated_tasks
      type: file
      path: "Periodic/{year}/Planetary Tasks/{slug}.md"
      description: Validated task notes
---
```

### Input Types

| Type | Description |
|------|-------------|
| `string` | Text value |
| `integer` | Whole number |
| `boolean` | true/false |
| `file` | Path to a file |
| `json` | JSON data structure |
| `array` | List of values |

### Output Types

| Type | Description |
|------|-------------|
| `file` | A file path (may contain template variables like `{year}`) |
| `json` | JSON output file |
| `array` | List of values |

## Usage

### CLI

```bash
# List all available skills
python pipeline/pipeline_composer_cli.py list

# Dry run a pipeline
python pipeline/pipeline_composer_cli.py dry-run \
  --skills obsidian-planetary-tasks-manager,obsidian-people-kind-manager

# Run a pipeline
python pipeline/pipeline_composer_cli.py run \
  --skills obsidian-planetary-tasks-manager,obsidian-people-kind-manager \
  --input task_kind=action
```

### Python API

```python
from pipeline import PipelineComposer

composer = PipelineComposer(repo_root="~/my-skills")

# Define pipeline
pipeline_def = [
    {"skill": "obsidian-planetary-tasks-manager", "mode": "validate"},
    {
        "skill": "obsidian-people-kind-manager",
        "mode": "migrate",
        "depends_on": ["obsidian-planetary-tasks-manager"],
    },
]

# Dry run
result = composer.dry_run(pipeline_def)
print(json.dumps(result, indent=2))

# Execute
result = composer.compose(pipeline_def)
```

## Example Pipelines

### Validate → Migrate → Enrich → Render

```yaml
name: Multi-Kind Import Pipeline
description: Validate, migrate, and render multiple kind managers in sequence

steps:
  - skill: obsidian-planetary-tasks-manager
    mode: validate
  - skill: obsidian-people-kind-manager
    mode: migrate
    depends_on: [obsidian-planetary-tasks-manager]
  - skill: obsidian-interweave-engine
    mode: enrich
    depends_on: [obsidian-people-kind-manager]
```

### Brokerage Activity Pipeline

```yaml
name: Brokerage Activity Pipeline
description: Import, validate, and render brokerage activity

steps:
  - skill: obsidian-brokerage-activity-manager
    mode: validate
  - skill: obsidian-brokerage-activity-manager
    mode: sync
    depends_on: [obsidian-brokerage-activity-manager]
  - skill: obsidian-portfolio-holdings-manager
    mode: sync
    depends_on: [obsidian-brokerage-activity-manager]
  - skill: obsidian-brokerage-activity-manager
    mode: render
    depends_on: [obsidian-portfolio-holdings-manager]
```

## Dependency Resolution

The Pipeline Composer automatically resolves dependencies:

1. **Explicit dependencies**: Steps can declare `depends_on` to specify ordering
2. **Implicit dependencies**: If a step's inputs reference an output from another step, that dependency is inferred

Example of implicit dependency:
```python
pipeline_def = [
    {"skill": "obsidian-planetary-tasks-manager", "mode": "validate"},
    {
        "skill": "obsidian-people-kind-manager",
        "mode": "migrate",
        # implicitly depends on validated_tasks from previous step
    },
]
```

## Pipeline Run Manifest

After running a pipeline, a `pipeline_run.json` manifest is produced:

```json
{
  "pipeline_run": {
    "timestamp": "2026-03-31T11:20:00",
    "duration_seconds": 12.5,
    "total_steps": 3,
    "successful_steps": 3,
    "failed_steps": 0,
    "results": [
      {
        "step": "obsidian-planetary-tasks-manager",
        "mode": "validate",
        "success": true,
        "outputs": {...}
      }
    ],
    "available_outputs": {
      "validated_tasks": {
        "type": "file",
        "path": "Periodic/2026/Planetary Tasks/*.md",
        "produced_by": "obsidian-planetary-tasks-manager"
      }
    }
  }
}
```

## Skill Categories

### Pipeline Skills (validate→migrate→enrich→render)

These skills participate in the main pipeline:

- `obsidian-planetary-tasks-manager` - Task notes management
- `obsidian-people-kind-manager` - Person notes management
- `obsidian-brokerage-activity-manager` - Investment activity tracking
- `obsidian-exercise-kind-manager` - Exercise notes management
- `obsidian-portfolio-holdings-manager` - Portfolio derived from brokerage
- `obsidian-zettel-manager` - Zettel notes management
- `obsidian-cv-entry-manager` - Career entry notes management
- `jira-sprint-sync` - Jira integration

### Thin Skills (empty pipeline)

These skills don't participate in data pipelines:

- `obsidian-token-budget-guard` - Token budget enforcement
- `obsidian-interweave-engine` - Link enrichment
- `obsidian-agent-memory-capture` - Memory pattern capture
- `obsidian-vault-health-auditor` - Vault health checks
- `obsidian-weekly-feedback-loop` - Weekly review
- `obsidian-base-engine` - Shared rendering library
- `obsidian-cli` - Obsidian CLI wrapper
- `obsidian-personal-os-router` - Request routing
- `qmd` - Search engine
- `game-theory-engine` - Decision analysis
- `bootstrapping-autoresearch` - Research bootstrapping

## File Structure

```
pipeline/
├── __init__.py              # Package exports
├── pipeline_composer.py     # Core engine
├── pipeline_composer_cli.py # CLI wrapper
├── README.md                # This file
└── examples/
    └── multi_kind_import.yaml  # Example pipeline
```
