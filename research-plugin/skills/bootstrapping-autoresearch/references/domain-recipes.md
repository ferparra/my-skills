# Domain Recipes

How to map different optimization problems to the three-file autoresearch pattern. Each recipe includes the metric choice, prepare.py sketch, train.py sketch, time budget, and domain-specific gotchas.

## LLM Training

**Metric:** `val_bpb` (validation bits per byte) — lower is better, vocabulary-size independent.

**Time budget:** 300s (5 minutes per experiment).

**prepare.py sketch:**
```python
import os, struct, numpy as np

TIME_BUDGET = 300
METRIC_NAME = "val_bpb"
MAX_SEQ_LEN = 2048
VOCAB_SIZE = 8192  # BPE tokenizer size

def download_data():
    """Download and tokenize dataset if not present."""
    ...

def get_dataloader(split, batch_size, seq_len):
    """Return batches of token IDs."""
    ...

def evaluate_bpb(model, dataloader):
    """Compute bits per byte on validation set."""
    total_loss, total_bytes = 0.0, 0
    for batch in dataloader:
        loss = model.forward_loss(batch)
        total_loss += loss.item() * batch.numel()
        total_bytes += count_bytes(batch)
    return total_loss / (total_bytes * math.log(2))
```

**train.py contains:** Model architecture (transformer), optimizer, LR schedule, training loop. All hyperparameters as top-level constants.

**Gotchas:**
- Use bits-per-byte, not cross-entropy — makes results comparable across tokenizers
- Fix the validation set — never let the agent change what's being evaluated
- Pin the random seed in prepare.py for reproducible evaluation

## Routing / Classification Accuracy

**Metric:** `error_rate` (1 - accuracy) — lower is better.

**Time budget:** 60-120s.

**prepare.py sketch:**
```python
import json

TIME_BUDGET = 120
METRIC_NAME = "error_rate"

def load_test_cases():
    """Load held-out test cases with ground truth labels."""
    with open("data/test_cases.json") as f:
        return json.load(f)

def evaluate(predict_fn, test_cases):
    """Compute error rate on held-out test set."""
    errors = sum(1 for tc in test_cases if predict_fn(tc["input"]) != tc["expected"])
    return errors / len(test_cases)
```

**train.py contains:** The routing/classification logic, feature extraction, decision rules, or model weights. The `predict_fn` is defined here.

**Gotchas:**
- Hold out at least 20% of cases — the agent should never see the test set
- Include edge cases in the test set — the metric should penalize failures on tricky inputs
- For LLM-based routers: the train.py contains the prompt and parsing logic, prepare.py contains the test harness

## Website Performance

**Metric:** `load_time_p95` (95th percentile page load time in seconds) — lower is better.

**Time budget:** 30-60s per evaluation run.

**prepare.py sketch:**
```python
import subprocess, json, statistics

TIME_BUDGET = 60
METRIC_NAME = "load_time_p95"
N_RUNS = 5  # repeat measurement for stability

def evaluate(config_path="config.json"):
    """Run Lighthouse N times, return p95 load time."""
    times = []
    for _ in range(N_RUNS):
        result = subprocess.run(
            ["npx", "lighthouse", URL, "--output=json", "--quiet"],
            capture_output=True, text=True
        )
        data = json.loads(result.stdout)
        times.append(data["audits"]["speed-index"]["numericValue"] / 1000)
    return sorted(times)[int(len(times) * 0.95)]
```

**train.py contains:** The web configuration, build settings, asset pipeline, caching rules, code splitting strategy — whatever the agent can modify to improve load times.

**Gotchas:**
- Run evaluations on a consistent network/machine — variance kills signal
- Use `--quiet` and `--no-sandbox` flags for headless evaluation
- Consider `largest-contentful-paint` as an alternative metric

## Financial Model Accuracy

**Metric:** `mape` (mean absolute percentage error) or `rmse` — lower is better.

**Time budget:** 120s.

**prepare.py sketch:**
```python
import pandas as pd, numpy as np

TIME_BUDGET = 120
METRIC_NAME = "mape"

def load_validation_data():
    """Load held-out validation period with actuals."""
    df = pd.read_csv("data/validation.csv", parse_dates=["date"])
    return df

def evaluate(predictions, actuals):
    """MAPE on validation set."""
    return np.mean(np.abs((actuals - predictions) / actuals)) * 100
```

**train.py contains:** The valuation/pricing model, feature engineering, regression coefficients, ensemble strategy, or ML model definition.

**Gotchas:**
- Use a held-out time period, not random split — prevents lookahead bias
- MAPE is undefined when actuals contain zeros — use RMSE or sMAPE as fallback
- Normalize financial values to comparable scales

## Algorithm Optimization

**Metric:** `inv_throughput` (1 / operations per second) or `latency_p99` — lower is better.

**Time budget:** 60s.

**prepare.py sketch:**
```python
import time, random

TIME_BUDGET = 60
METRIC_NAME = "latency_p99"

def generate_benchmark_inputs(seed=42):
    """Fixed benchmark inputs for reproducibility."""
    rng = random.Random(seed)
    return [rng.randint(0, 10**6) for _ in range(10000)]

def evaluate(algorithm_fn, inputs):
    """Measure p99 latency over benchmark inputs."""
    times = []
    for inp in inputs:
        start = time.perf_counter_ns()
        algorithm_fn(inp)
        elapsed = (time.perf_counter_ns() - start) / 1e6  # ms
        times.append(elapsed)
    times.sort()
    return times[int(len(times) * 0.99)]
```

**train.py contains:** The algorithm implementation — sorting, searching, encoding, compression, etc.

**Gotchas:**
- Pin the random seed for benchmark inputs
- Warm up the CPU/cache before timing
- Use `time.perf_counter_ns()` for nanosecond precision

## Prompt Engineering

**Metric:** `1 - judge_score` — lower is better (judge scores 0-1).

**Time budget:** 120s (LLM inference can be slow).

**prepare.py sketch:**
```python
import os, json

TIME_BUDGET = 120
METRIC_NAME = "prompt_error"

def load_test_cases():
    """Load input/expected pairs for evaluation."""
    with open("data/eval_cases.json") as f:
        return json.load(f)

def judge(output, expected):
    """LLM-as-judge scoring. Returns 0-1."""
    # Call judge model (e.g., Claude, GPT-4) with rubric
    ...

def evaluate(generate_fn, test_cases):
    """Average error rate across test cases."""
    scores = [judge(generate_fn(tc["input"]), tc["expected"]) for tc in test_cases]
    return 1 - (sum(scores) / len(scores))
```

**train.py contains:** The prompt template, few-shot examples, chain-of-thought structure, output parsing logic.

**Gotchas:**
- Use a deterministic judge (temperature=0, fixed model version)
- Include diverse test cases — prompts that work on easy cases may fail on hard ones
- Budget for API costs — each experiment calls the LLM N times

## Configuration Tuning

**Metric:** Domain-specific error or cost metric — lower is better.

**Time budget:** 60-300s depending on what's being configured.

**prepare.py sketch:**
```python
import subprocess, json

TIME_BUDGET = 180
METRIC_NAME = "error_metric"

def evaluate(config_path="config.json"):
    """Run application with config, measure outcome."""
    result = subprocess.run(
        ["./run_benchmark.sh", config_path],
        capture_output=True, text=True, timeout=TIME_BUDGET
    )
    metrics = json.loads(result.stdout)
    return metrics["error_rate"]
```

**train.py contains:** Configuration values, parameter definitions, feature flags. May generate a config file rather than being a traditional training script.

**Gotchas:**
- Ensure the benchmark script is deterministic
- Set sensible bounds on config values to prevent the agent from exploring nonsensical settings
- Consider adding constraint validation in prepare.py
