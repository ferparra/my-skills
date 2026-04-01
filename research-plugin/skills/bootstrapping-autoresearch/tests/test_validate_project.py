"""Tests for the autoresearch project validator.

Run with:
    uv run pytest research-plugin/skills/bootstrapping-autoresearch/tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_project import validate_project


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal valid autoresearch project."""
    (tmp_path / "prepare.py").write_text(
        dedent("""\
        TIME_BUDGET = 60
        METRIC_NAME = "error_rate"

        def evaluate(predictions, actuals):
            return sum(1 for p, a in zip(predictions, actuals) if p != a) / len(actuals)
        """)
    )
    (tmp_path / "train.py").write_text(
        dedent("""\
        from prepare import evaluate, TIME_BUDGET, METRIC_NAME

        LEARNING_RATE = 0.01

        def predict(x):
            return 0

        if __name__ == "__main__":
            score = evaluate([predict(x) for x in range(10)], list(range(10)))
            print(f"{METRIC_NAME}: {score:.6f}")
        """)
    )
    (tmp_path / "program.md").write_text(
        dedent("""\
        # Autoresearch: Error Rate Optimization

        ## Objective
        Minimize `error_rate` (lower is better).

        ## Files you may edit
        Only `train.py`.

        ## Experiment loop
        LOOP FOREVER:
        1. Edit train.py
        2. git commit
        3. Run train.py
        4. grep "^error_rate:" run.log
        5. If improved → keep
        6. If worse → git reset --hard HEAD~1
        7. Do not stop — never stop, the human may be asleep.

        ## Simplicity criterion
        Prefer simplicity. A small improvement from deleting code? Keep it.

        ## Results logging
        Append to results.tsv: experiment, metric, kept, notes
        """)
    )
    return tmp_path


def test_valid_project(tmp_project: Path) -> None:
    result = validate_project(tmp_project)
    assert result["ok"] is True
    assert result["errors"] == []
    assert result["files_checked"]["prepare.py"] is True
    assert result["files_checked"]["train.py"] is True
    assert result["files_checked"]["program.md"] is True


def test_missing_prepare(tmp_project: Path) -> None:
    (tmp_project / "prepare.py").unlink()
    result = validate_project(tmp_project)
    assert result["ok"] is False
    assert any("prepare.py" in e for e in result["errors"])


def test_missing_train(tmp_project: Path) -> None:
    (tmp_project / "train.py").unlink()
    result = validate_project(tmp_project)
    assert result["ok"] is False
    assert any("train.py" in e for e in result["errors"])


def test_missing_program(tmp_project: Path) -> None:
    (tmp_project / "program.md").unlink()
    result = validate_project(tmp_project)
    assert result["ok"] is False
    assert any("program.md" in e for e in result["errors"])


def test_prepare_missing_time_budget(tmp_project: Path) -> None:
    (tmp_project / "prepare.py").write_text(
        dedent("""\
        METRIC_NAME = "val_loss"

        def evaluate(model):
            return 1.0
        """)
    )
    result = validate_project(tmp_project)
    assert result["ok"] is False
    assert any("TIME_BUDGET" in e for e in result["errors"])


def test_prepare_missing_evaluate(tmp_project: Path) -> None:
    (tmp_project / "prepare.py").write_text(
        dedent("""\
        TIME_BUDGET = 300
        METRIC_NAME = "val_loss"

        def compute_loss(model):
            return 1.0
        """)
    )
    result = validate_project(tmp_project)
    assert result["ok"] is False
    assert any("evaluate" in e for e in result["errors"])


def test_train_syntax_error(tmp_project: Path) -> None:
    (tmp_project / "train.py").write_text("def broken(:\n    pass\n")
    result = validate_project(tmp_project)
    assert result["ok"] is False
    assert any("syntax error" in e for e in result["errors"])


def test_program_missing_git(tmp_project: Path) -> None:
    (tmp_project / "program.md").write_text(
        dedent("""\
        # Experiment

        ## Objective
        Minimize the metric (lower is better).

        ## Loop
        Run the experiment. Never stop. Simplicity matters.
        """)
    )
    result = validate_project(tmp_project)
    assert result["ok"] is False
    assert any("git" in e for e in result["errors"])


def test_empty_directory(tmp_path: Path) -> None:
    result = validate_project(tmp_path)
    assert result["ok"] is False
    assert len(result["errors"]) == 3  # all three files missing
