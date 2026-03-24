---
name: bootstrapping-autoresearch
version: 0.1.0
description: >
  Bootstraps autoresearch projects — autonomous AI-driven optimization loops.
  Generates prepare.py (read-only eval harness), train.py (agent-editable solution),
  and program.md (Claude Code experiment instructions) for any measurable optimization
  problem. Use when the user wants to set up automated experiments, optimize a metric,
  run autonomous research, apply Karpathy's autoresearch pattern, or create a
  self-improving optimization loop.
metadata:
  openclaw:
    os: [darwin, linux]
    requires:
      bins: [git, python3]
---

# Bootstrapping Autoresearch

Generate a complete autoresearch project: three files that let a coding agent autonomously optimize any measurable objective. The agent modifies code, evaluates, keeps improvements, discards regressions, and repeats indefinitely.

## The Three-File Contract

| File | Role | Editable by agent? |
|------|------|--------------------|
| `prepare.py` | Data loading, evaluation function, metric output. Defines `TIME_BUDGET` and prints `metric_name: <float>` to stdout. | **NO** — read-only |
| `train.py` | The entire solution in one file: model/algorithm, optimizer/strategy, hyperparameters, training loop. Imports only from stdlib and pip packages. | **YES** — agent's only target |
| `program.md` | Agent instructions: metric definition, experiment loop, simplicity criterion, logging format. | **NO** — human-editable only |

## Workflow

Copy this checklist and track progress:

```
Autoresearch Bootstrap:
- [ ] Step 1: Classify the optimization problem
- [ ] Step 2: Design the metric
- [ ] Step 3: Generate prepare.py
- [ ] Step 4: Generate train.py (baseline)
- [ ] Step 5: Generate program.md
- [ ] Step 6: Validate the project
- [ ] Step 7: Brief the user
```

### Step 1: Classify the optimization problem

Ask the user:
- **What are you optimizing?** (model accuracy, latency, cost, routing, etc.)
- **What data or environment is available?** (dataset, API, benchmark suite)
- **What compute is available?** (GPU type, CPU-only, cloud budget)

See [domain-recipes.md](references/domain-recipes.md) for domain-specific guidance.

### Step 2: Design the metric

**Rules — all metrics must satisfy these:**

1. **Single number.** One float, not a dashboard.
2. **Lower is better.** For accuracy-like metrics, use `1 - accuracy`. For throughput, use `1 / throughput`.
3. **Scale-independent.** Bits-per-byte over cross-entropy. Relative error over absolute error.
4. **Ungameable.** The eval harness is read-only — the agent cannot modify how the metric is computed.
5. **Greppable.** Printed to stdout as `metric_name: <float>` so the agent can parse it with `grep "^metric_name:" run.log`.

### Step 3: Generate `prepare.py`

This file is the **immovable ground truth**. It must contain:

```python
# Required constants
TIME_BUDGET = 300          # seconds — all experiments get the same wall-clock budget
METRIC_NAME = "val_loss"   # must match the grep pattern in program.md

# Required function
def evaluate(model_or_artifact):
    """Return a single float — lower is better."""
    ...

# Required output (called at end of train.py)
# print(f"{METRIC_NAME}: {score:.6f}")
```

**Constraints on prepare.py:**
- Contains ALL data loading, preprocessing, and evaluation logic
- Defines `TIME_BUDGET` and `METRIC_NAME` as top-level constants
- The evaluate function accepts whatever train.py produces
- Must be self-contained: downloading data, building dataloaders, tokenizers — all here
- train.py imports from prepare.py, never the reverse

### Step 4: Generate `train.py` (baseline)

The initial baseline solution. Must:

- Import evaluation utilities from prepare.py: `from prepare import evaluate, TIME_BUDGET, METRIC_NAME`
- Contain the entire solution (model definition, optimization, training loop) in one file
- Import only from stdlib, pip packages, and prepare.py
- Print the metric at the end: `print(f"{METRIC_NAME}: {score:.6f}")`
- Respect `TIME_BUDGET` — stop training/optimization before the budget expires
- All hyperparameters as top-level constants for easy agent modification
- Be a reasonable but not over-optimized baseline — leave room for the agent to improve

### Step 5: Generate `program.md`

Agent instructions targeting Claude Code. Must include these sections:

**Required sections:**

1. **Objective** — What metric to minimize, the current best value, and why it matters.
2. **Files you may edit** — Only `train.py`. Never touch `prepare.py`.
3. **Experiment loop** — The exact steps:
   ```
   LOOP FOREVER:
   1. Read train.py and results.tsv to understand current state
   2. Formulate a hypothesis for improvement
   3. Edit train.py with your experimental change
   4. Run: git add -A && git commit -m "experiment: <description>"
   5. Run: python3 train.py > run.log 2>&1
   6. Run: grep "^<METRIC_NAME>:" run.log
   7. If improved → keep (record in results.tsv, continue)
   8. If worse or crashed → discard: git reset --hard HEAD~1
   9. Append result to results.tsv (experiment, metric, kept/discarded, notes)
   10. NEVER STOP — the human may be asleep
   ```
4. **Simplicity criterion** — "A small improvement from deleting code? Definitely keep. A small improvement from adding 20 lines of hacky code? Probably not worth it."
5. **Results logging** — TSV format: `experiment\tmetric\tkept\tnotes`
6. **Constraints** — No external API calls, no network access during training, no modifying prepare.py, no creating additional Python files.

**Claude Code specific instructions:**
- Use the Bash tool to run commands
- Use the Read tool to check run.log and results.tsv
- Use the Edit tool to modify train.py
- Redirect stdout+stderr to run.log: `python3 train.py > run.log 2>&1`
- Parse metrics with grep, not by reading the full log

### Step 6: Validate the project

```bash
python3 scripts/validate_project.py --dir /path/to/project
```

Fix any errors before proceeding. See the JSON output for specific issues.

### Step 7: Brief the user

Tell the user:
1. The three files have been generated at `<path>`
2. The baseline metric value (run train.py once to establish it)
3. How to start the loop: open Claude Code in the project directory and paste the contents of program.md as the prompt
4. How to monitor: `tail -f results.tsv` in another terminal
5. How to stop: interrupt Claude Code (Ctrl+C)
6. How to review: `git log --oneline` shows the experiment history

## References

- See [autoresearch-principles.md](references/autoresearch-principles.md) for the core design principles
- See [domain-recipes.md](references/domain-recipes.md) for domain-specific metric choices and prepare.py patterns
