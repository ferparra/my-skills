# Excalidraw SVG Generation Quality — Agent Instructions

## Objective

Minimize `svg_structural_error_rate` for annotated SVG diagram generation.

- **Metric**: `svg_structural_error_rate` — fraction of test cases where the generated SVG fails structural validation against the reference annotation schema (lower is better, 0.0 = perfect).
- **Target**: push to `0.0` (all generated SVGs pass schema validation).
- **Why**: These SVGs are the intermediate representation in the Excalidraw pipeline. If the SVG annotation schema is followed correctly, the deterministic transform to `.excalidraw.md` will produce a valid diagram. Poor SVG generation is the primary failure mode.

## Files you may edit

| File | Status |
|------|--------|
| `train.py` | **YES** — your only target |
| `prepare.py` | **NEVER** — read-only ground truth |
| `results.tsv` | Append only (logging) |
| `program.md` | **NEVER** |

## What can be improved

The baseline generates SVG from a simple template string approach. Failure modes:

1. **Template structure** — the SVG generation template may produce malformed XML or miss required attributes
2. **Annotation completeness** — generated SVGs may be missing `data-semantic-role`, `data-upstream`/`data-downstream`, or `data-from`/`data-to`
3. **ID consistency** — IDs in `data-from`/`data-to` may not match actual `<g>` element IDs
4. **Topology accuracy** — TOPOLOGY comment may not match actual node/edge counts
5. **Vocabulary compliance** — `data-semantic-role` values may not be from the valid vocabulary

## Reference SVGs

The ground-truth structural blueprints live at:
`../excalidraw-svg-references/annotated/`

These are the 22 reference SVGs that define what "correct" looks like. The eval harness (`prepare.py`) loads them, extracts their structure, and compares against generated output.

## Experiment loop

```
LOOP until 30 minutes of wall-clock time have elapsed:

1. Read train.py and results.tsv
2. Formulate ONE hypothesis
3. Edit train.py
4. Run:  git add train.py && git commit -m "experiment: <description>"
5. Run:  python3 train.py > run.log 2>&1
6. Run:  grep "^svg_structural_error_rate:" run.log
7. Improved → KEEP; Worse or crashed → git reset --hard HEAD~1
8. Append to results.tsv: <experiment>\t<metric>\t<kept|discarded>\t<notes>
9. NEVER STOP until 30 minutes elapsed
```

## Starting command

```bash
python3 train.py > run.log 2>&1 && grep "^svg_structural_error_rate:" run.log
```
