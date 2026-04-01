"""
Skill Pipeline Composer

Allows chaining skills together where output of one feeds into the next.
Reads SKILL.md frontmatter to understand skill inputs/outputs and resolves
dependencies automatically.
"""

from pipeline.pipeline_composer import (
    PipelineComposer,
    PipelineInput,
    PipelineOutput,
    PipelineStep,
    SkillSpec,
    StepResult,
)

__all__ = [
    "PipelineComposer",
    "PipelineInput",
    "PipelineOutput",
    "PipelineStep",
    "SkillSpec",
    "StepResult",
]

__version__ = "1.0.0"
