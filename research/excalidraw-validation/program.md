# Excalidraw Validation Optimization — Agent Instructions

## Objective

Minimize `validation_error_rate` for Excalidraw drawing validation.

- **Metric**: `validation_error_rate` — fraction of 31 drawing test cases where actual errors/warnings do not match expected (lower is better, 0.0 = perfect).
- **Baseline**: ~0.258 (23/31 correct on first run).
- **Target**: 0.000000 (perfect).
- **Why it matters**: These validation skills guard diagram quality across an Obsidian vault. False positives waste human time investigating non-issues. Missed detections let broken diagrams through. Perfect validation means reliable auto-layout and diagram generation.

## Files you may edit

| File | Status |
|------|--------|
| `train.py` | **YES** — your only target |
| `prepare.py` | **NEVER** — read-only ground truth |
| `results.tsv` | Append only (logging) |
| `program.md` | **NEVER** — human-editable only |

## What can be improved in train.py

The baseline uses ported validation logic from two existing skills but has 8 known gaps causing test failures:

### Missing schema checks (6 test cases failing)

1. **Missing enum field validation** (`fillStyle`, `strokeStyle`)
   - Baseline accepts any string value
   - Failures: `invalid_fill_style`, `invalid_stroke_style`
   - Fix: Add `check_enum_fields()` function that validates fillStyle in {"solid", "hachure", "cross-hatch"} and strokeStyle in {"solid", "dashed", "dotted"}

2. **Missing numeric range checks** (`opacity`, `roughness`, `fontFamily`)
   - Baseline does not validate numeric constraints
   - Failures: `opacity_out_of_range`, `roughness_out_of_range`, `invalid_font_family`
   - Fix: Add `check_numeric_ranges()` function that validates opacity 0-100, roughness 0-2, fontFamily 1-5

3. **Missing arrow points structure validation**
   - Baseline does not check that arrow points sub-lists have exactly 2 elements [x, y]
   - Failures: `arrow_points_bad`
   - Fix: Add `check_arrow_points_structure()` function

### isDeleted filtering bug (1 test case failing)

4. **No isDeleted filtering in validate_all()**
   - Baseline validates deleted elements, causing false positive errors
   - Failures: `deleted_broken_binding`
   - Fix: Filter `isDeleted=True` elements before passing to check functions in `validate_all()`

### Visual check gaps (3 test cases failing)

5. **Container-child overlap false positive**
   - Baseline checks all element pairs including text-inside-container
   - Failures: `text_in_container_no_overlap`
   - Fix: In `check_overlaps()`, skip pairs where one element's containerId points to the other

6. **Missing dangling arrow detection**
   - Baseline does not check for arrows with no bindings
   - Failures: `dangling_arrow`
   - Fix: Add `check_dangling_arrows()` function that warns when arrow has neither startBinding nor endBinding

7. **Missing arrow-crossing detection**
   - Baseline does not detect when an arrow path passes through an unrelated element
   - Failures: `arrow_crosses_element`
   - Fix: Add `check_arrow_crossings()` function that checks if arrow line segment intersects unrelated element bboxes (not start/end binding targets)

## Experiment loop

```
LOOP until 30 minutes of wall-clock time have elapsed:

1. Read train.py and results.tsv to understand current state
2. Formulate ONE hypothesis (e.g., "add check_enum_fields to validate fillStyle/strokeStyle")
3. Edit train.py with your experimental change
4. Run:  git add train.py && git commit -m "experiment: <short description>"
5. Run:  python3 train.py > run.log 2>&1
6. Run:  grep "^validation_error_rate:" run.log
7. If improved (lower score):
       → KEEP: record in results.tsv, move to next hypothesis
8. If worse or crashed:
       → DISCARD: git reset --hard HEAD~1
9. Append one TSV row to results.tsv:
       <experiment_description>\t<metric_value>\t<kept|discarded>\t<notes>
10. NEVER STOP — loop until the 30-minute wall clock expires
```

## Simplicity criterion

- Small improvement (+2% accuracy) from adding a 3-line enum check → **definitely keep**
- Large improvement from fixing isDeleted filtering → **keep**
- Small improvement from adding 50 lines of complex line-segment intersection logic → **worth it for arrow-crossing check** (it's a real gap)
- Same score with simpler code → **keep the simpler version**

Prefer targeted check functions over sprawling if-else logic. Each check should be a self-contained function added to `ALL_CHECKS`.

## Reading the test output

Every `python3 train.py` run prints:
```
[PASS] valid_drawing
[FAIL] invalid_fill_style
  Expected errors: ['fillStyle']
  Actual errors:   []
...
=== Validation evaluation (23/31 correct) ===

validation_error_rate: 0.258065
```

Use this to identify which test cases are failing and why. Fix the smallest change that addresses the most errors.

## Expected iteration trajectory

Based on the 8 known gaps:

1. **Add `check_enum_fields`** — validates fillStyle, strokeStyle → fixes 2 cases → score drops to ~0.194
2. **Add `check_numeric_ranges`** — validates opacity, roughness, fontFamily → fixes 3 cases → score drops to ~0.097
3. **Add `check_arrow_points_structure`** — validates arrow points are [[x,y], ...] → fixes 1 case → score drops to ~0.065
4. **Filter isDeleted in validate_all()** — skip deleted elements → fixes 1 case → score drops to ~0.032
5. **Fix container-child overlap in check_overlaps()** — exclude containerId pairs → fixes 1 case → may already be fixed by isDeleted filter depending on test case structure
6. **Add `check_dangling_arrows`** — warn on arrows with no bindings → score drops further
7. **Add `check_arrow_crossings`** — detect arrow-through-element → score drops to 0.000000

Each fix is independent. You can tackle them in any order, but the order above is roughly increasing in complexity.

## Results logging

Append to `results.tsv` after each experiment:

```
experiment	metric	kept	notes
baseline	0.258065	kept	initial validation logic ported from both skills
add check_enum_fields	0.193548	kept	validates fillStyle and strokeStyle enums
add check_numeric_ranges	0.096774	kept	validates opacity, roughness, fontFamily ranges
...
```

## Constraints

- No external API calls during training
- No network access
- Do not modify `prepare.py`
- Do not create additional `.py` files (keep everything in `train.py`)
- Each `python3 train.py` run must complete in under 30 seconds (TIME_BUDGET)
- All imports must be from stdlib or `prepare`

## Tools to use

- `Bash` — run commands, commit, check logs
- `Read` — read `train.py`, `run.log`, `results.tsv`
- `Edit` — modify `train.py`
- Parse metrics: `grep "^validation_error_rate:" run.log`
- Monitor progress: `tail -20 results.tsv`

## Starting command

```bash
python3 train.py > run.log 2>&1 && grep "^validation_error_rate:" run.log
```

Confirm you see `validation_error_rate: 0.XXXXXX` (around 0.258), then begin the loop.
