"""Configuration and constants for skill validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).parent.parent

# All skill directories to scan
SKILL_DIRS: Final[list[Path]] = [
    REPO_ROOT / "obsidian-plugin" / "skills",
    REPO_ROOT / "productivity-plugin" / "skills",
    REPO_ROOT / "research-plugin" / "skills",
    REPO_ROOT / "skills",
]

# Maximum file size in bytes (128KB)
MAX_SKILL_SIZE: Final[int] = 128 * 1024

# Known Hermes tool references (for warning only)
KNOWN_TOOLS: Final[set[str]] = {
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
PLACEHOLDER_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"\bfill\s+in\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bXXX\b", re.IGNORECASE),
]

# Regex for wiki-links and markdown links (to check description field)
WIKI_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[\[[^\]]+\]\]")
MD_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

# Semver regex
SEMVER_RE: Final[re.Pattern[str]] = re.compile(r"^\d+\.\d+\.\d+$")
