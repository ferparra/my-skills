"""
Skill Pipeline Composer

Chains skills together where output of one feeds into the next.
Reads SKILL.md frontmatter to understand skill inputs/outputs and resolves
dependencies automatically.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PipelineInput:
    """Represents a pipeline input parameter."""
    name: str
    type: str
    required: bool = False
    description: str = ""
    default: Any = None


@dataclass
class PipelineOutput:
    """Represents a pipeline output artifact."""
    name: str
    type: str
    path: str = ""
    description: str = ""


@dataclass
class SkillSpec:
    """Parsed skill specification from SKILL.md frontmatter."""
    name: str
    version: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    pipeline_inputs: list[PipelineInput] = field(default_factory=list)
    pipeline_outputs: list[PipelineOutput] = field(default_factory=list)
    skill_dir: Path = None

    @classmethod
    def from_skill_md(cls, skill_dir: Path) -> "SkillSpec":
        """Parse SKILL.md frontmatter from a skill directory."""
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        with open(skill_md_path, "r") as f:
            content = f.read()

        # Parse YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1]) or {}
            else:
                frontmatter = {}
        else:
            frontmatter = {}

        # Extract pipeline config
        pipeline_config = frontmatter.get("pipeline", {}) or {}
        inputs = []
        for inp in pipeline_config.get("inputs", []):
            inputs.append(PipelineInput(
                name=inp.get("name", ""),
                type=inp.get("type", "string"),
                required=inp.get("required", False),
                description=inp.get("description", ""),
                default=inp.get("default"),
            ))
        outputs = []
        for out in pipeline_config.get("outputs", []):
            outputs.append(PipelineOutput(
                name=out.get("name", ""),
                type=out.get("type", "file"),
                path=out.get("path", ""),
                description=out.get("description", ""),
            ))

        return cls(
            name=frontmatter.get("name", skill_dir.name),
            version=frontmatter.get("version", "1.0.0"),
            description=frontmatter.get("description", ""),
            dependencies=frontmatter.get("dependencies", []),
            pipeline_inputs=inputs,
            pipeline_outputs=outputs,
            skill_dir=skill_dir,
        )


@dataclass
class PipelineStep:
    """A single step in a pipeline definition."""
    skill: str
    mode: str = "run"
    depends_on: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """Result of executing a pipeline step."""
    step: PipelineStep
    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_seconds: float = 0.0


class PipelineComposer:
    """
    Orchestrates skill pipelines by reading SKILL.md frontmatter,
    resolving dependencies, and executing skills in order.

    Usage:
        composer = PipelineComposer(repo_root="~/my-skills")
        composer.compose([
            {"skill": "obsidian-planetary-tasks-manager", "mode": "validate"},
            {"skill": "obsidian-people-kind-manager", "mode": "migrate", "depends_on": ["obsidian-planetary-tasks-manager"]},
        ])
    """

    SKILL_GLOB = "**/SKILL.md"

    def __init__(self, repo_root: str | Path = "."):
        self.repo_root = Path(repo_root).expanduser().resolve()
        self._skill_cache: dict[str, SkillSpec] = {}

    def find_skill_dirs(self) -> list[Path]:
        """Find all skill directories containing SKILL.md (deduplicates symlinks)."""
        seen: set[Path] = set()
        skill_dirs = []
        for pattern in [
            "obsidian-plugin/skills/*/SKILL.md",
            "productivity-plugin/skills/*/SKILL.md",
            "research-plugin/skills/*/SKILL.md",
            "skills/*/SKILL.md",
        ]:
            for skill_md in self.repo_root.glob(pattern):
                # Resolve symlinks to avoid duplicates
                real_path = skill_md.resolve()
                if real_path not in seen:
                    seen.add(real_path)
                    skill_dirs.append(skill_md.parent)
        return skill_dirs

    def load_skill(self, skill_name: str) -> SkillSpec:
        """Load a skill by name, searching all skill directories."""
        if skill_name in self._skill_cache:
            return self._skill_cache[skill_name]

        # Try to find the skill directory
        skill_dirs = self.find_skill_dirs()
        for skill_dir in skill_dirs:
            spec = SkillSpec.from_skill_md(skill_dir)
            if spec.name == skill_name:
                self._skill_cache[skill_name] = spec
                return spec

        raise ValueError(f"Skill '{skill_name}' not found. Available skills: {[d.name for d in skill_dirs]}")

    def resolve_dependencies(self, steps: list[PipelineStep]) -> list[PipelineStep]:
        """
        Resolve explicit and implicit dependencies between steps.

        A step depends on another if:
        1. It explicitly lists the other in depends_on
        2. Its inputs reference outputs from the other step
        """
        # Build a map of skill name -> step
        skill_to_step = {step.skill: step for step in steps}

        # Resolve implicit dependencies from input/output contracts
        for step in steps:
            for inp in step.inputs.keys():
                # Check if any other step produces this input
                for other_step in steps:
                    if other_step == step:
                        continue
                    try:
                        other_skill = self.load_skill(other_step.skill)
                        for output in other_skill.pipeline_outputs:
                            if output.name == inp:
                                if other_step.skill not in step.depends_on:
                                    step.depends_on.append(other_step.skill)
                    except ValueError:
                        continue

        # Topological sort based on dependencies
        resolved = []
        remaining = list(steps)
        while remaining:
            # Find steps with no unresolved dependencies
            ready = []
            for step in remaining:
                deps_satisfied = all(
                    dep in [s.skill for s in resolved] or dep not in skill_to_step
                    for dep in step.depends_on
                )
                if deps_satisfied:
                    ready.append(step)

            if not ready:
                # Circular dependency or missing skill
                remaining_names = [s.skill for s in remaining]
                raise ValueError(
                    f"Circular dependency or missing skill in: {remaining_names}"
                )

            # Add all ready steps (maintain order for same-level dependencies)
            for step in ready:
                if step not in resolved:
                    resolved.append(step)
                remaining.remove(step)

        return resolved

    def validate_inputs(self, step: PipelineStep, available_outputs: dict[str, Any]) -> list[str]:
        """
        Validate that all required inputs for a step are satisfied.

        Returns list of missing required inputs (empty if all satisfied).
        """
        try:
            skill = self.load_skill(step.skill)
        except ValueError as e:
            return [str(e)]

        missing = []
        for inp in skill.pipeline_inputs:
            if inp.required:
                # Check if provided via inputs dict
                if inp.name not in step.inputs and inp.name not in available_outputs:
                    if inp.default is None:
                        missing.append(inp.name)
                    else:
                        # Use default if available
                        step.inputs.setdefault(inp.name, inp.default)

        return missing

    def build_command(self, step: PipelineStep) -> list[str]:
        """Build the command to execute a skill step."""
        skill = self.load_skill(step.skill)
        skill_path = skill.skill_dir.relative_to(self.repo_root)

        # Build uvx command based on skill type
        # Most skills use uvx with pydantic and pyyaml
        base_cmd = [
            "uvx", "--from", "python",
            "--with", "pydantic", "--with", "pyyaml", "python",
            f".{skill_path}/scripts/run_skill.py",
        ]

        # Add mode if specified
        if step.mode and step.mode != "run":
            base_cmd.extend(["--mode", step.mode])

        # Add inputs as key=value arguments
        for key, value in step.inputs.items():
            if isinstance(value, bool):
                if value:
                    base_cmd.append(f"--{key}")
            elif isinstance(value, list):
                for v in value:
                    base_cmd.extend([f"--{key}", str(v)])
            else:
                base_cmd.extend([f"--{key}", str(value)])

        return base_cmd

    def dry_run(self, pipeline_def: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Show what would run without executing.

        Args:
            pipeline_def: List of step definitions with skill, mode, depends_on, inputs

        Returns:
            Dictionary describing what would run
        """
        steps = self._parse_pipeline_def(pipeline_def)
        resolved_steps = self.resolve_dependencies(steps)

        available_outputs = {}
        planned_steps = []

        for step in resolved_steps:
            missing_inputs = self.validate_inputs(step, available_outputs)
            try:
                skill = self.load_skill(step.skill)
                cmd = self.build_command(step)
            except ValueError as e:
                cmd = ["# skill not found"]

            planned_steps.append({
                "skill": step.skill,
                "mode": step.mode,
                "depends_on": step.depends_on,
                "command": " ".join(cmd),
                "inputs": step.inputs,
                "available_outputs_from_previous": list(available_outputs.keys()),
                "missing_inputs": missing_inputs,
                "pipeline_outputs": [
                    {"name": o.name, "type": o.type, "path": o.path}
                    for o in skill.pipeline_outputs
                ] if step.skill in self._skill_cache else [],
            })

            # Update available outputs (assume all outputs are produced)
            if step.skill in self._skill_cache:
                for output in self._skill_cache[step.skill].pipeline_outputs:
                    available_outputs[output.name] = {
                        "type": output.type,
                        "path": output.path,
                    }

        return {
            "dry_run": True,
            "timestamp": datetime.now().isoformat(),
            "total_steps": len(resolved_steps),
            "steps": planned_steps,
        }

    def compose(self, pipeline_def: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Execute a pipeline, running skills in dependency order.

        Args:
            pipeline_def: List of step definitions with skill, mode, depends_on, inputs

        Returns:
            Pipeline run manifest with results
        """
        steps = self._parse_pipeline_def(pipeline_def)
        resolved_steps = self.resolve_dependencies(steps)

        available_outputs = {}
        results: list[dict[str, Any]] = []
        start_time = datetime.now()

        print(f"\n{'='*60}")
        print(f"Pipeline Composer")
        print(f"{'='*60}")
        print(f"Starting pipeline with {len(resolved_steps)} steps")
        print(f"{'='*60}\n")

        for i, step in enumerate(resolved_steps, 1):
            print(f"\n[{i}/{len(resolved_steps)}] {step.skill} ({step.mode})")
            print(f"  Depends on: {step.depends_on or 'none'}")

            # Validate inputs
            missing_inputs = self.validate_inputs(step, available_outputs)
            if missing_inputs:
                print(f"  ERROR: Missing required inputs: {missing_inputs}")
                results.append({
                    "step": step.skill,
                    "mode": step.mode,
                    "success": False,
                    "error": f"Missing required inputs: {missing_inputs}",
                })
                continue

            try:
                skill = self.load_skill(step.skill)
                cmd = self.build_command(step)

                print(f"  Command: {' '.join(cmd)}")

                # Simulate execution (print what would run)
                # In production, this would actually run the command:
                # result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)

                # For simulation, we'll just record the step
                step_result = StepResult(
                    step=step,
                    success=True,
                    outputs={},
                    duration_seconds=0.0,
                )

                # Record outputs from this step
                for output in skill.pipeline_outputs:
                    available_outputs[output.name] = {
                        "type": output.type,
                        "path": output.path,
                        "produced_by": step.skill,
                    }

                results.append({
                    "step": step.skill,
                    "mode": step.mode,
                    "success": True,
                    "command": " ".join(cmd),
                    "outputs": {
                        o.name: {"type": o.type, "path": o.path}
                        for o in skill.pipeline_outputs
                    },
                })

                print(f"  Status: SIMULATED (would succeed)")

            except ValueError as e:
                print(f"  ERROR: {e}")
                results.append({
                    "step": step.skill,
                    "mode": step.mode,
                    "success": False,
                    "error": str(e),
                })
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({
                    "step": step.skill,
                    "mode": step.mode,
                    "success": False,
                    "error": str(e),
                })

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Build manifest
        manifest = {
            "pipeline_run": {
                "timestamp": start_time.isoformat(),
                "duration_seconds": duration,
                "total_steps": len(resolved_steps),
                "successful_steps": sum(1 for r in results if r["success"]),
                "failed_steps": sum(1 for r in results if not r["success"]),
                "results": results,
                "available_outputs": available_outputs,
            }
        }

        # Write manifest
        manifest_path = self.repo_root / "pipeline_run.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\n{'='*60}")
        print(f"Pipeline complete")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Successful: {manifest['pipeline_run']['successful_steps']}")
        print(f"  Failed: {manifest['pipeline_run']['failed_steps']}")
        print(f"  Manifest: {manifest_path}")
        print(f"{'='*60}\n")

        return manifest

    def _parse_pipeline_def(self, pipeline_def: list[dict[str, Any]]) -> list[PipelineStep]:
        """Parse pipeline definition into PipelineStep objects."""
        steps = []
        for item in pipeline_def:
            steps.append(PipelineStep(
                skill=item.get("skill", ""),
                mode=item.get("mode", "run"),
                depends_on=item.get("depends_on", []),
                inputs=item.get("inputs", {}),
            ))
        return steps

    def list_skills(self) -> list[dict[str, Any]]:
        """List all available skills with their pipeline contracts."""
        skills = []
        for skill_dir in self.find_skill_dirs():
            try:
                spec = self.load_skill(skill_dir.name)
                skills.append({
                    "name": spec.name,
                    "version": spec.version,
                    "description": spec.description[:100] + "..." if len(spec.description) > 100 else spec.description,
                    "dependencies": spec.dependencies,
                    "pipeline_inputs": [
                        {"name": i.name, "type": i.type, "required": i.required}
                        for i in spec.pipeline_inputs
                    ],
                    "pipeline_outputs": [
                        {"name": o.name, "type": o.type, "path": o.path}
                        for o in spec.pipeline_outputs
                    ],
                })
            except Exception:
                # Skip skills that can't be parsed
                skills.append({
                    "name": skill_dir.name,
                    "version": "unknown",
                    "error": "Failed to parse SKILL.md",
                })
        return skills


def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Skill Pipeline Composer")
    parser.add_argument("--repo-root", default=".", help="Repository root directory")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List skills command
    list_parser = subparsers.add_parser("list", help="List all available skills")

    # Dry run command
    dry_parser = subparsers.add_parser("dry-run", help="Show what would run")
    dry_parser.add_argument("--skills", required=True, help="Comma-separated skill names")
    dry_parser.add_argument("--inputs", help="Input overrides as key=value pairs")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a pipeline")
    run_parser.add_argument("--skills", required=True, help="Comma-separated skill names")
    run_parser.add_argument("--inputs", help="Input overrides as key=value pairs")

    args = parser.parse_args()

    composer = PipelineComposer(repo_root=args.repo_root)

    if args.command == "list":
        for skill in composer.list_skills():
            print(f"\n{skill['name']} (v{skill['version']})")
            if "error" in skill:
                print(f"  ERROR: {skill['error']}")
            else:
                print(f"  {skill['description']}")
                if skill["pipeline_inputs"]:
                    print(f"  Inputs: {', '.join(i['name'] for i in skill['pipeline_inputs'])}")
                if skill["pipeline_outputs"]:
                    print(f"  Outputs: {', '.join(o['name'] for o in skill['pipeline_outputs'])}")
    elif args.command == "dry-run":
        skills = args.skills.split(",")
        pipeline_def = [{"skill": s.strip()} for s in skills]
        if args.inputs:
            # Add inputs to first step
            for pair in args.inputs.split(","):
                key, value = pair.split("=")
                pipeline_def[0]["inputs"] = pipeline_def[0].get("inputs", {})
                pipeline_def[0]["inputs"][key.strip()] = value.strip()
        result = composer.dry_run(pipeline_def)
        print(json.dumps(result, indent=2))
    elif args.command == "run":
        skills = args.skills.split(",")
        pipeline_def = [{"skill": s.strip()} for s in skills]
        if args.inputs:
            for pair in args.inputs.split(","):
                key, value = pair.split("=")
                pipeline_def[0]["inputs"] = pipeline_def[0].get("inputs", {})
                pipeline_def[0]["inputs"][key.strip()] = value.strip()
        result = composer.compose(pipeline_def)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
