from __future__ import annotations

import re
import sys
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# All skill directories to scan
SKILL_dirs: list[Path] = [
    REPO_ROOT / "obsidian-plugin" / "skills",
    REPO_ROOT / "productivity-plugin" / "skills",
    REPO_ROOT / "research-plugin" / "skills",
    REPO_ROOT / "skills",
]

# Maximum file size in bytes (128KB)
MAX_SKILL_SIZE = 128 * 1024

# Known Hermes tool references (for warning only)
KNOWN_TOOLS: set[str] = {
    "browser_navigate", "browser_click", "browser_type", "browser_screenshot",
    "bash", "shell", "terminal", "run", "exec",
    "write_file", "read_file", "edit_file", "delete_file",
    "search", "grep", "find",
    "http_request", "curl", "wget",
    "uvx", "pip", "pip install",
    "git", "clone", "commit", "push", "pull",
    "docker", "docker run", "docker build",
    "obsidian", "qmd",
    "Claude", "claude",
}

# Placeholder patterns
PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"\bfill\s+in\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bXXX\b", re.IGNORECASE),
]

# Regex for wiki-links and markdown links (to check description field)
WIKI_LINK_RE = re.compile(r"\[\[[^\]]+\]\]")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

# Semver regex
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def find_all_skill_dirs() -> list[Path]:
    """Find all skill directories across all SKILL_dirs.

    Skips symlinks in the top-level `skills/` directory to avoid
    double-checking skills that live under plugin directories.
    """
    skill_dirs = []
    for base_dir in SKILL_dirs:
        if not base_dir.is_dir():
            continue
        for p in base_dir.iterdir():
            # Skip symlinks — they point to plugin directories already scanned
            if p.is_symlink():
                continue
            if p.is_dir() and (p / "SKILL.md").exists():
                skill_dirs.append(p)
    return sorted(skill_dirs)


def parse_frontmatter(content: str) -> tuple[dict, str, int]:
    """
    Parse YAML frontmatter from SKILL.md content.
    Returns (frontmatter_dict, body_content, line_where_body_starts).
    Raises ValueError if YAML is invalid.
    """
    if not content.startswith("---"):
        raise ValueError("No frontmatter found (missing leading ---)")

    end_marker = content.find("\n---\n", 4)
    if end_marker == -1:
        # Could be a single-line frontmatter or no closing ---
        # Try to find --- on its own line
        end_marker = content.find("\n---", 4)
        if end_marker == -1:
            raise ValueError("Frontmatter not properly closed")

    frontmatter_text = content[4:end_marker]
    body = content[end_marker + 4:]

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")

    if frontmatter is None:
        frontmatter = {}

    return frontmatter, body, content.count("\n", 0, end_marker + 4)


def check_frontmatter_fields(fm: dict, skill_path: Path) -> list[str]:
    """Check required frontmatter fields. Returns list of error strings."""
    errors = []

    # name (required, string)
    if "name" not in fm:
        errors.append("missing required field: name")
    elif not isinstance(fm["name"], str):
        errors.append("field 'name' must be a string")
    elif not fm["name"].strip():
        errors.append("field 'name' must not be empty or whitespace")

    # description (required, string, max 300 chars)
    if "description" not in fm:
        errors.append("missing required field: description")
    elif not isinstance(fm["description"], str):
        errors.append("field 'description' must be a string")
    elif not fm["description"].strip():
        errors.append("field 'description' must not be empty or whitespace")
    else:
        desc = fm["description"]
        # Handle YAML folded scalar (> or >-)
        if isinstance(desc, str):
            # Count actual characters (folded scalars may have newlines)
            clean_desc = " ".join(desc.split())
            if len(clean_desc) > 300:
                errors.append(f"description exceeds 300 chars ({len(clean_desc)})")

        # Check for broken links in description
        if isinstance(desc, str):
            # Wiki links
            wiki_matches = WIKI_LINK_RE.findall(desc)
            for wl in wiki_matches:
                inner = wl[2:-2]  # strip [[ ]]
                # Check if it looks like a broken link (empty or just spaces)
                if not inner.strip():
                    errors.append(f"broken wiki-link in description: {wl}")
                    break

            # Markdown links
            md_matches = MD_LINK_RE.findall(desc)
            for link_text, link_url in md_matches:
                if not link_text.strip() or not link_url.strip():
                    errors.append(f"broken markdown link in description: [{link_text}]({link_url})")
                    break

    # version (required, semver format like "1.0.0")
    if "version" not in fm:
        errors.append("missing required field: version")
    elif not isinstance(fm["version"], str):
        errors.append("field 'version' must be a string")
    elif not SEMVER_RE.match(str(fm["version"])):
        errors.append(f"field 'version' must be semver format (e.g. 1.0.0), got: {fm['version']}")

    # tags (optional, list of strings) — just validate it's a list if present
    if "tags" in fm and fm["tags"] is not None:
        if not isinstance(fm["tags"], list):
            errors.append("field 'tags' must be a list")
        else:
            for tag in fm["tags"]:
                if not isinstance(tag, str):
                    errors.append(f"field 'tags' must contain strings, got: {type(tag).__name__}")
                    break

    return errors


def check_body_content(body: str, skill_path: Path) -> tuple[list[str], list[str]]:
    """
    Check body content requirements.
    Returns (errors, warnings) lists.
    """
    errors = []
    warnings = []

    # Must not exceed 128KB
    if len(body.encode("utf-8")) > MAX_SKILL_SIZE:
        size_kb = len(body.encode("utf-8")) // 1024
        errors.append(f"SKILL.md exceeds 128KB limit ({size_kb}KB)")

    # Must have at least one ## heading
    h2_headings = re.findall(r"^##\s+.+$", body, re.MULTILINE)
    if not h2_headings:
        errors.append("SKILL.md must have at least one ## heading (skill has documentation)")

    # Must not contain placeholder text
    for pattern in PLACEHOLDER_PATTERNS:
        match = pattern.search(body)
        if match:
            # Find line number
            lines_before = body[:match.start()].count("\n")
            errors.append(
                f"placeholder text '{match.group()}' found in body (line ~{lines_before + 1})"
            )
            break

    # Must have at least one Workflow section or equivalent
    workflow_indicators = [
        r"##\s+Workflow",
        r"##\s+Usage",
        r"##\s+How to use",
        r"##\s+Steps",
        r"##\s+Commands",
        r"##\s+Reference",
    ]
    workflow_pattern = re.compile("|".join(workflow_indicators), re.IGNORECASE)
    if not workflow_pattern.search(body):
        errors.append("SKILL.md must have a Workflow section or equivalent (## Workflow, ## Usage, ## Steps, etc.)")

    # Tool references — warn if tools don't match known Hermes toolsets
    # Find all quoted tool-like strings (e.g., `uvx`, `browser_navigate`, etc.)
    tool_mentions = re.findall(r"`([a-z_][a-z0-9_]*)`", body, re.IGNORECASE)
    unknown_tools = set(tool_mentions) - KNOWN_TOOLS
    for tool in sorted(unknown_tools):
        # Only warn once per skill
        warnings.append(f"unknown tool referenced: `{tool}` (may not be a Hermes tool)")

    return errors, warnings


def check_skill(skill_dir: Path) -> tuple[list[str], list[str]]:
    """
    Check a single skill's SKILL.md for compliance.
    Returns (errors, warnings) lists.
    """
    errors: list[str] = []
    warnings: list[str] = []
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    rel_path = skill_md.relative_to(REPO_ROOT)

    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(f"could not read SKILL.md: {e}")
        return errors, warnings

    # Parse frontmatter
    try:
        fm, body, _ = parse_frontmatter(content)
    except ValueError as e:
        errors.append(f"frontmatter parse error: {e}")
        return errors, warnings

    # Check frontmatter fields
    fm_errors = check_frontmatter_fields(fm, skill_dir)
    errors.extend(fm_errors)

    # Check body content
    body_errors, body_warnings = check_body_content(body, skill_dir)
    errors.extend(body_errors)
    warnings.extend(body_warnings)

    return errors, warnings


def main() -> None:
    all_errors: dict[str, list[str]] = {}
    all_warnings: dict[str, list[str]] = {}
    ok_count = 0

    skill_dirs = find_all_skill_dirs()

    for skill_dir in skill_dirs:
        rel_path = skill_dir.relative_to(REPO_ROOT)
        errors, warnings = check_skill(skill_dir)

        if errors:
            all_errors[str(rel_path)] = errors
        if warnings:
            all_warnings[str(rel_path)] = warnings
        if not errors:
            ok_count += 1

    # Print results
    if all_errors:
        for path_str, errs in sorted(all_errors.items()):
            print(f"✗ {path_str}/SKILL.md")
            for err in errs:
                print(f"  - {err}")

    if all_warnings:
        for path_str, warns in sorted(all_warnings.items()):
            for warn in warns:
                print(f"⚠ {path_str}/SKILL.md: {warn}")

    if all_errors:
        total_skills = ok_count + len(all_errors)
        print(f"\n✗ Anthropic compliance check failed — {ok_count}/{total_skills} skills OK")
        sys.exit(1)

    print(f"✓ Anthropic compliance check passed — {ok_count} skills OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
