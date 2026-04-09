#!/usr/bin/env python3
"""Scaffold a new experiment note with a well-formed ExperimentFrontmatter.

Usage:
    uvx --from python --with pydantic --with pyyaml python new_experiment.py \
        --kind health \
        --question "What effect does 300mg Magnesium Glycinate have on sleep latency?" \
        --output "10 Notes/Productivity/Experiments/Magnesium Sleep Experiment.md"

    # Optional: add hypothesis and method at creation time
    uvx --from python --with pydantic --with pyyaml python new_experiment.py \
        --kind technical \
        --question "Does using Claude Opus for planning reduce my weekly planning time?" \
        --hypothesis "Delegating planning synthesis to an AI will halve the cognitive load." \
        --method "Use Claude Opus for weekly review for 4 weeks; track planning time in minutes." \
        --duration 28 \
        --output "10 Notes/Productivity/Experiments/AI Planning Experiment.md"

Exit code: 0 on success, 1 on failure.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from experiment_models import (
    COUNCIL_DOMAIN_MAP,
    ExperimentKind,
    ExperimentOutcome,
    ExperimentStatus,
    ScaffoldResult,
    dump_json,
    dump_frontmatter,
    next_experiment_id,
    normalize_experiment_tags,
    order_frontmatter,
)


NOTE_BODY_TEMPLATE = """\
## Question

{question}

## Hypothesis

{hypothesis}

## Method

{method}

## Metrics

- <!-- Define what you will measure -->

## Interventions

- <!-- What are you changing or introducing? -->

## Controls

- <!-- What stays constant to isolate the variable? -->

## Confounders

- <!-- What external factors could contaminate results? -->

## Log

<!-- Add dated entries as you run the experiment -->

### {today}

Initial setup.

## Findings

<!-- Complete when experiment concludes -->

## Next Experiments

<!-- Wikilink follow-on experiments here -->
"""


def build_frontmatter(
    kind: ExperimentKind,
    question: str,
    hypothesis: str,
    method: str,
    duration_days: int | None,
    experiment_id: str,
) -> dict:
    today = date.today().isoformat()
    council_owner, domain_tag = COUNCIL_DOMAIN_MAP[kind.value]
    tags = normalize_experiment_tags(
        {},
        kind=kind.value,
        status=ExperimentStatus.HYPOTHESIS.value,
    )
    fm: dict = {
        "experiment_kind": kind.value,
        "experiment_id": experiment_id,
        "created": today,
        "modified": today,
        "status": ExperimentStatus.HYPOTHESIS.value,
        "council_owner": council_owner,
        "domain_tag": domain_tag,
        "question": question,
        "hypothesis": hypothesis,
        "method": method,
        "metrics": [],
        "duration_days": duration_days,
        "start_date": None,
        "end_date": None,
        "interventions": [],
        "controls": [],
        "confounders": [],
        "outcome": ExperimentOutcome.ONGOING.value,
        "findings": None,
        "confidence": None,
        "next_experiments": [],
        "connection_strength": 0.5,
        "related": [],
        "potential_links": [],
        "tags": tags,
    }
    # Strip None values for cleaner YAML
    return {k: v for k, v in fm.items() if v is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new experiment note.")
    parser.add_argument(
        "--kind", required=True,
        choices=[k.value for k in ExperimentKind],
        help="Experiment kind (supertag).",
    )
    parser.add_argument("--question", required=True, help="The research question.")
    parser.add_argument(
        "--hypothesis", default="<!-- TODO: state your hypothesis -->",
        help="What you believe will happen and why.",
    )
    parser.add_argument(
        "--method", default="<!-- TODO: describe your protocol -->",
        help="Protocol / intervention description.",
    )
    parser.add_argument("--duration", type=int, default=None, help="Duration in days.")
    parser.add_argument("--output", required=True, help="Output path for the new note.")
    parser.add_argument(
        "--vault", default=str(Path.home() / "my-vault"),
        help="Vault root path.",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing note (default: abort if exists).",
    )
    args = parser.parse_args()

    vault_root = Path(args.vault)
    output_path = Path(args.output) if Path(args.output).is_absolute() else vault_root / args.output

    if output_path.exists() and not args.overwrite:
        print(dump_json({
            "ok": False,
            "error": f"Note already exists: {output_path}. Use --overwrite to replace.",
        }))
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect existing notes to generate the next ID
    existing = list(vault_root.rglob("10 Notes/Productivity/Experiments/**/*.md"))
    experiment_id = next_experiment_id(existing)

    kind = ExperimentKind(args.kind)
    fm = build_frontmatter(
        kind=kind,
        question=args.question,
        hypothesis=args.hypothesis,
        method=args.method,
        duration_days=args.duration,
        experiment_id=experiment_id,
    )

    ordered = dict(order_frontmatter(fm))
    body = NOTE_BODY_TEMPLATE.format(
        question=args.question,
        hypothesis=args.hypothesis,
        method=args.method,
        today=date.today().isoformat(),
    )

    content = dump_frontmatter(ordered) + "\n" + body
    output_path.write_text(content, encoding="utf-8")

    result = ScaffoldResult(
        path=str(output_path),
        ok=True,
        experiment_id=experiment_id,
        experiment_kind=kind.value,
    )
    print(dump_json(result.model_dump()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
