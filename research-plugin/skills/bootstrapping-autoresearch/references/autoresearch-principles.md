# Autoresearch Principles

Seven non-negotiable design principles for autonomous optimization loops.

## 1. Single editable file

The agent modifies exactly one file (`train.py`). This prevents scope creep, keeps diffs reviewable, and simplifies rollback with `git reset --hard HEAD~1`. Everything — model architecture, optimizer, hyperparameters, training loop — lives in this single file.

## 2. Fixed time budget

Every experiment runs for the same wall-clock duration (default: 300 seconds). This makes results comparable regardless of what the agent changes. The budget is hardware-adaptive: the agent naturally finds the best model/algorithm that fits YOUR hardware within the time limit. Define `TIME_BUDGET` in `prepare.py` as a constant.

Guidance for choosing the budget:
- **Too short** (<30s): Not enough signal for meaningful optimization
- **Sweet spot** (60-300s): Enough to train/evaluate, fast enough for ~12-100 experiments overnight
- **Too long** (>600s): Too few experiments per night, slow feedback loop

## 3. Single numeric metric

One float, lower is better. Must be:
- **Scale-independent**: Bits-per-byte over raw cross-entropy (vocabulary-size independent). Relative error over absolute error.
- **Physically meaningful**: The number should mean something to a human reviewing results.
- **Architecture-agnostic**: The metric should not favor one approach over another by construction.

Print it to stdout in a greppable format:
```
metric_name: 1.234567
```

The agent parses this with `grep "^metric_name:" run.log`. No JSON, no structured output — just a line.

## 4. Read-only eval harness

The agent CANNOT modify the evaluation function. `prepare.py` contains data loading, preprocessing, the evaluation function, and the metric output format. By keeping this read-only, the agent cannot game the metric — it can only genuinely improve the solution.

The eval function in `prepare.py` is the arbiter. `train.py` imports from `prepare.py`, never the reverse.

## 5. Git-based experiment tracking

Zero infrastructure. No MLflow, no Weights & Biases, no experiment databases.

- **Commit on success**: `git add -A && git commit -m "experiment: <description>"`
- **Reset on failure**: `git reset --hard HEAD~1`
- **Branches = experiment series**: Use branches to explore different directions
- **results.tsv (untracked)**: Human-readable log of all experiments, kept or discarded

The `.gitignore` should include:
```
run.log
results.tsv
__pycache__/
*.pyc
data/
```

## 6. Simplicity criterion

Not all improvements are worth keeping. The agent should apply this heuristic:

> "A 0.001 improvement from deleting code? Definitely keep. A 0.001 improvement from adding 20 lines of hacky code? Probably not worth it."

Improvements must justify their complexity. A simpler solution at the same metric value is strictly preferred. This prevents the codebase from growing into an unmaintainable mess over hundreds of experiments.

## 7. Never stop

The agent runs indefinitely until manually interrupted. The human may be asleep. At ~12 experiments per hour with a 300s budget, an overnight run produces ~100 experiments. The agent should:

- Never ask for confirmation
- Never pause to summarize
- Never stop after N experiments
- Handle crashes gracefully (read the traceback, fix or skip, continue)

## Output pattern

All output goes to a file, not the terminal:
```bash
python3 train.py > run.log 2>&1
```

The agent reads `run.log` only to extract the metric via grep. This keeps the context window clean — the agent never loads the full training output into its conversation.

## Commit message convention

```
experiment: <one-line description of what changed>
```

Examples:
- `experiment: increase hidden dim from 256 to 512`
- `experiment: switch from Adam to Muon optimizer`
- `experiment: add RoPE positional encoding`
- `experiment: reduce batch size, increase gradient accumulation`

## Results log format

`results.tsv` (untracked by git):
```
experiment	metric	kept	notes
baseline	1.4523	yes	initial baseline
increase hidden dim 256→512	1.4201	yes	-0.032 improvement
add dropout 0.1	1.4198	yes	marginal but simpler is not worse
switch to cosine schedule	1.4350	no	regression, reverted
```
