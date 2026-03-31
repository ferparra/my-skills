#!/usr/bin/env python3
"""
CLI wrapper for the Skill Pipeline Composer.

Usage:
    python pipeline/pipeline_composer_cli.py run --skills skill1,skill2,skill3 --input key=value
    python pipeline/pipeline_composer_cli.py dry-run --skills skill1,skill2,skill3
    python pipeline/pipeline_composer_cli.py list
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.pipeline_composer import PipelineComposer


def parse_input_overrides(inputs_str: str | None) -> dict[str, any]:
    """Parse input overrides from CLI string."""
    if not inputs_str:
        return {}
    result = {}
    for pair in inputs_str.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            key, value = key.strip(), value.strip()
            # Try to parse as int, float, or bool
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.isdigit():
                value = int(value)
            else:
                try:
                    value = float(value)
                except ValueError:
                    pass  # Keep as string
            result[key] = value
    return result


def run_command(args: argparse.Namespace) -> int:
    """Execute a pipeline."""
    composer = PipelineComposer(repo_root=args.repo_root)

    skills = [s.strip() for s in args.skills.split(",")]
    pipeline_def = [{"skill": s} for s in skills]

    # Add inputs to steps
    inputs = parse_input_overrides(args.input)
    if inputs:
        for i, (key, value) in enumerate(inputs.items()):
            if i == 0 and pipeline_def:
                pipeline_def[0]["inputs"] = pipeline_def[0].get("inputs", {})
                pipeline_def[0]["inputs"][key] = value
            else:
                # Add to appropriate step based on dependency
                pipeline_def.append({
                    "skill": "passthrough",
                    "inputs": {key: value},
                })

    print(f"Running pipeline with {len(pipeline_def)} steps...")
    result = composer.compose(pipeline_def)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to {args.output}")

    return 0 if result["pipeline_run"]["failed_steps"] == 0 else 1


def dry_run_command(args: argparse.Namespace) -> int:
    """Show what would run without executing."""
    composer = PipelineComposer(repo_root=args.repo_root)

    skills = [s.strip() for s in args.skills.split(",")]
    pipeline_def = [{"skill": s} for s in skills]

    # Add inputs to first step
    inputs = parse_input_overrides(args.input)
    if inputs and pipeline_def:
        pipeline_def[0]["inputs"] = pipeline_def[0].get("inputs", {})
        pipeline_def[0]["inputs"].update(inputs)

    print(f"Dry run for pipeline with {len(pipeline_def)} steps...\n")
    result = composer.dry_run(pipeline_def)

    # Pretty print the dry run result
    for step in result["steps"]:
        print(f"\nStep: {step['skill']} ({step['mode']})")
        print(f"  Depends on: {step['depends_on'] or 'none'}")
        print(f"  Command: {step['command']}")
        if step["missing_inputs"]:
            print(f"  Missing inputs: {step['missing_inputs']}")
        if step["pipeline_outputs"]:
            print(f"  Produces: {', '.join(o['name'] for o in step['pipeline_outputs'])}")

    print(f"\n{'='*60}")
    print(f"Dry run complete: {result['total_steps']} steps planned")
    print(f"{'='*60}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Output written to {args.output}")

    return 0


def list_command(args: argparse.Namespace) -> int:
    """List all available skills."""
    composer = PipelineComposer(repo_root=args.repo_root)

    print(f"\n{'='*60}")
    print("Available Skills")
    print(f"{'='*60}\n")

    skills = composer.list_skills()

    # Group by category
    obsidian_skills = [s for s in skills if s["name"].startswith("obsidian-")]
    productivity_skills = [s for s in skills if s["name"].startswith("jira-") or s["name"] == "qmd"]
    research_skills = [s for s in skills if "research" in s["name"]]
    other_skills = [s for s in skills if s not in obsidian_skills + productivity_skills + research_skills]

    def print_skill_group(title: str, group: list):
        if not group:
            return
        print(f"\n{title}")
        print("-" * 40)
        for skill in sorted(group, key=lambda s: s["name"]):
            status = "✓" if "error" not in skill else "✗"
            print(f"  [{status}] {skill['name']} (v{skill['version']})")
            if "error" in skill:
                print(f"      Error: {skill['error']}")
            else:
                if skill["pipeline_inputs"]:
                    ins = ", ".join(f"{i['name']}:{i['type']}" for i in skill["pipeline_inputs"])
                    print(f"      Inputs: {ins}")
                if skill["pipeline_outputs"]:
                    outs = ", ".join(f"{o['name']}" for o in skill["pipeline_outputs"])
                    print(f"      Outputs: {outs}")

    print_skill_group("Obsidian Skills", obsidian_skills)
    print_skill_group("Productivity Skills", productivity_skills)
    print_skill_group("Research Skills", research_skills)
    print_skill_group("Other Skills", other_skills)

    print(f"\n{'='*60}")
    print(f"Total: {len(skills)} skills")
    print(f"{'='*60}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Skill Pipeline Composer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list
  %(prog)s dry-run --skills obsidian-planetary-tasks-manager,obsidian-people-kind-manager
  %(prog)s run --skills obsidian-planetary-tasks-manager --input task_kind=action
        """,
    )

    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory (default: current directory)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    list_parser = subparsers.add_parser("list", help="List all available skills")

    # dry-run command
    dry_parser = subparsers.add_parser("dry-run", help="Show what would run without executing")
    dry_parser.add_argument("--skills", required=True, help="Comma-separated skill names")
    dry_parser.add_argument("--input", help="Input overrides as key=value pairs")
    dry_parser.add_argument("--output", help="Write output to file")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a pipeline")
    run_parser.add_argument("--skills", required=True, help="Comma-separated skill names")
    run_parser.add_argument("--input", help="Input overrides as key=value pairs")
    run_parser.add_argument("--output", help="Write results to file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "list":
        return list_command(args)
    elif args.command == "dry-run":
        return dry_run_command(args)
    elif args.command == "run":
        return run_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
