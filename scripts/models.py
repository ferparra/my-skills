"""Pydantic models for skill validation."""
from __future__ import annotations

from pydantic import BaseModel


class ParsedFrontmatter(BaseModel):
    """Parsed SKILL.md frontmatter with body and line offset."""
    frontmatter: dict[str, object]
    body: str
    body_start_line: int


class ValidationResult(BaseModel):
    """Validation result with separate error and warning lists."""
    errors: list[str] = []
    warnings: list[str] = []
