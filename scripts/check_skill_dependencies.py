#!/usr/bin/env python3
"""
Check skill dependencies.

Scans all SKILL.md files, parses their `dependencies:` frontmatter field,
and verifies each listed dependency's SKILL.md exists.

Exit codes:
    0 - All dependencies are valid
    1 - One or more dependencies are missing or invalid
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL | re.MULTILINE)
DEPS_LIST_RE = re.compile(r"^\s*-\s+(\S+)\s*$", re.MULTILINE)
DEPS_FIELD_RE = re.compile(r"^dependencies:\s*$", re.MULTILINE)


def parse_frontmatter_deps(content: str) -> list[str]:
    """Parse dependencies list from SKILL.md frontmatter."""
    match = FRONTMATTER_RE.search(content)
    if not match:
        return []

    frontmatter = match.group(1)

    # Find the dependencies section
    deps_match = DEPS_FIELD_RE.search(frontmatter)
    if not deps_match:
        return []

    # Extract all list items after "dependencies:"
    start_pos = deps_match.end()
    deps_section = frontmatter[start_pos:]

    # Find where the next top-level key starts (no indentation)
    next_key_match = re.search(r"\n\S", deps_section)
    if next_key_match:
        deps_section = deps_section[:next_key_match.start()]

    # Parse list items
    deps = []
    for item_match in DEPS_LIST_RE.finditer(deps_section):
        deps.append(item_match.group(1))

    return deps


def find_all_skill_dirs(root: Path) -> list[Path]:
    """Find all directories containing a SKILL.md file."""
    skill_dirs = []
    for path in root.rglob("SKILL.md"):
        skill_dirs.append(path.parent)
    return sorted(skill_dirs)


def get_skill_name(skill_dir: Path) -> str:
    """Infer skill name from directory path."""
    # Pattern: .../skills/<skill-name>/
    parts = skill_dir.parts
    for i, part in enumerate(parts):
        if part == "skills" and i + 1 < len(parts):
            return parts[i + 1]
    # Fallback to directory name
    return skill_dir.name


def check_dependencies(skills_root: Path) -> tuple[bool, list[str]]:
    """
    Check all skill dependencies.

    Returns:
        (all_valid, error_messages)
    """
    errors: list[str] = []
    skill_dirs = find_all_skill_dirs(skills_root)

    # Build a set of all valid skill names
    valid_skills: set[str] = set()

    for skill_dir in skill_dirs:
        skill_name = get_skill_name(skill_dir)
        valid_skills.add(skill_name)

    # Now check each skill's dependencies
    for skill_dir in skill_dirs:
        skill_name = get_skill_name(skill_dir)
        skill_md = skill_dir / "SKILL.md"

        text = skill_md.read_text(encoding="utf-8", errors="replace")
        dependencies = parse_frontmatter_deps(text)

        for dep in dependencies:
            if dep not in valid_skills:
                errors.append(f"[{skill_name}] missing dependency: '{dep}' (no SKILL.md found)")

    return len(errors) == 0, errors


def main() -> int:
    # Find the repo root (parent of this script's directory)
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent

    all_valid, errors = check_dependencies(repo_root)

    if all_valid:
        print("All skill dependencies are valid.")
        return 0

    print("Skill dependency check FAILED:")
    for error in errors:
        print(f"  - {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
