"""Models for skill validation."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedFrontmatter:
    """Parsed SKILL.md frontmatter with body and line offset."""
    frontmatter: dict[str, object]
    body: str
    body_start_line: int


@dataclass
class ValidationResult:
    """Validation result with separate error and warning lists."""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
