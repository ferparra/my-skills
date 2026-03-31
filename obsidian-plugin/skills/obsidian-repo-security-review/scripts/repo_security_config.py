"""Configuration and constants for repository security review."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from repo_security_models import PIIPatternConfig, MaliciousPackage, LockfileConfig

# Repository configuration
OWNER: Final[str] = "ferparra"
GITHUB_USER: Final[str] = "ferparra83"
REPOS_DIR: Final[Path] = Path.home() / ".hermes" / "repo_security_reviews"

# Known repositories
KNOWN_REPOS: Final[frozenset[str]] = frozenset([
    "My-Readwise",
    "Presentaci-n-Lean-Startup-Barcamp-2010",
    "data-engineering-zoomcamp",
    "gatsby-starter-netlify-cms",
    "graph-rag-mcp-server",
    "maybe",
    "my-chess-tutor",
    "my-skills",
    "next-blog-firestore",
    "nexus",
    "nexus-prisma-nextjs",
    "pds_docs",
    "pollenizer-startup-links",
    "study-hall-vite",
])

# Allowed contributors
ALLOWED_CONTRIBUTORS: Final[frozenset[str]] = frozenset([
    "ferparra",
    "github-actions[bot]",
])

# Agent/bot email patterns
AGENT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r".*@users\.noreply\.github\.com$"),
    re.compile(r".*\[bot\]@.*$"),
    re.compile(r"ci@.*$"),
    re.compile(r"runner@.*$"),
    re.compile(r"build@.*$"),
    re.compile(r"bot@.*$"),
)

# PII detection patterns (structured models)
PII_PATTERNS: Final[dict[str, PIIPatternConfig]] = {
    "github_token_gho": PIIPatternConfig(
        pattern=r"gho_[A-Za-z0-9]{36}",
        severity="HIGH",
        description="GitHub OAuth token",
    ),
    "github_token_ghp": PIIPatternConfig(
        pattern=r"ghp_[A-Za-z0-9]{36}",
        severity="HIGH",
        description="GitHub personal access token",
    ),
    "github_pat": PIIPatternConfig(
        pattern=r"github_pat_[A-Za-z0-9_]{22,}",
        severity="HIGH",
        description="GitHub personal access token (classic)",
    ),
    "aws_access_key": PIIPatternConfig(
        pattern=r"AKIA[A-Z0-9]{16}",
        severity="HIGH",
        description="AWS Access Key ID",
    ),
    "aws_secret_key": PIIPatternConfig(
        pattern=r"(?i)aws.{0,20}secret.{0,20}[\"'][A-Za-z0-9/+=]{40}[\"']",
        severity="HIGH",
        description="AWS Secret Access Key",
    ),
    "private_key": PIIPatternConfig(
        pattern=r"-----BEGIN\s+(RSA\s+|DSA\s+|EC\s+|PGP\s+)?PRIVATE\s+KEY-----",
        severity="HIGH",
        description="Private key file",
    ),
    "api_key_generic": PIIPatternConfig(
        pattern=r"(?i)(api[_-]?key|apikey|api[_-]?secret|secret[_-]?key)[\s:=]+['\"]?[A-Za-z0-9]{32,64}['\"]?",
        severity="MEDIUM",
        description="Generic API key",
    ),
    "stripe_key": PIIPatternConfig(
        pattern=r"sk_live_[A-Za-z0-9]{24,}",
        severity="HIGH",
        description="Stripe live API key",
    ),
    "stripe_key_test": PIIPatternConfig(
        pattern=r"sk_test_[A-Za-z0-9]{24,}",
        severity="MEDIUM",
        description="Stripe test API key",
    ),
    "phone_au_mobile": PIIPatternConfig(
        pattern=r"\b04[0-9]{7}\b",
        severity="HIGH",
        description="Australian mobile phone number",
    ),
    "phone_us": PIIPatternConfig(
        pattern=r"\+?1?\s*[-.]?\s*\(?[0-9]{3}\)?\s*[-.]?\s*[0-9]{3}\s*[-.]?\s*[0-9]{4}",
        severity="MEDIUM",
        description="US phone number",
    ),
    "email_personal": PIIPatternConfig(
        pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        severity="MEDIUM",
        description="Email address",
        exclude_domains=["github.com", "users.noreply.github.com"],
    ),
    "password_literal": PIIPatternConfig(
        pattern=r"(?i)(password|passwd|pwd|secret)\s*[:=]\s*['\"][^'\"]{8,128}['\"]",
        severity="HIGH",
        description="Hardcoded password",
    ),
    "slack_token": PIIPatternConfig(
        pattern=r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}",
        severity="HIGH",
        description="Slack token",
    ),
    "telegram_token": PIIPatternConfig(
        pattern=r"[0-9]{8,10}:[A-Za-z0-9_-]{35}",
        severity="HIGH",
        description="Telegram bot token",
    ),
    "jwt_token": PIIPatternConfig(
        pattern=r"eyJ[A-Za-z0-9_-]\.eyJ[A-Za-z0-9_-]\.[A-Za-z0-9_-]+",
        severity="HIGH",
        description="JWT token",
    ),
}

# File scanning configuration
SCANNABLE_EXTENSIONS: Final[frozenset[str]] = frozenset([
    '.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml',
    '.txt', '.md', '.rst', '.toml', '.env', '.ini', '.cfg',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.rb', '.go', '.rs', '.java', '.kt', '.swift', '.c', '.cpp',
    '.h', '.hpp', '.cs', '.php', '.pl', '.r', '.scala', '.vb',
    '.html', '.htm', '.xml', '.sql', '.graphql', '.vue', '.svelte',
])

SKIP_DIRECTORIES: Final[frozenset[str]] = frozenset([
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    '.pytest_cache', '.mypy_cache', '.tox', 'build', 'dist',
    '.eggs', '*.egg-info', 'vendor', 'third_party', 'third-party',
    '.next', '.nuxt', '.cache', '.tmp', 'tmp', 'temp', '.temp',
])

SCANNABLE_FILENAMES: Final[frozenset[str]] = frozenset([
    'Makefile', 'Dockerfile', 'docker-compose', 'Gemfile',
    'Podfile', 'Package.swift', 'Cargo.toml', 'go.mod',
    'requirements.txt', 'Pipfile', 'setup.py', 'build.gradle',
])

# Known malicious packages (structured models)
MALICIOUS_PACKAGES: Final[dict[str, MaliciousPackage]] = {
    "event-stream": MaliciousPackage(
        severity="CRITICAL",
        description="2018 compromise - cryptocurrency wallet theft via flatmap-stream dependency",
        attack_type="Cryptocurrency theft",
    ),
    "flatmap-stream": MaliciousPackage(
        severity="CRITICAL",
        description="2018 compromise - backdoor installed by event-stream maintainer",
        attack_type="Backdoor",
    ),
    "ua-parser-js": MaliciousPackage(
        severity="CRITICAL",
        description="Multiple supply chain attacks (2021-2022) - credential stealing backdoors",
        attack_type="Credential stealing",
    ),
    "coa": MaliciousPackage(
        severity="CRITICAL",
        description="2022 supply chain attack - command injection payload",
        attack_type="Command injection",
    ),
    "rc": MaliciousPackage(
        severity="CRITICAL",
        description="2022 supply chain attack - command injection payload (coa dependency)",
        attack_type="Command injection",
    ),
    "j舅": MaliciousPackage(
        severity="CRITICAL",
        description="2022 malicious package mimicking popular Chinese package",
        attack_type="Typosquatting",
    ),
}

# Lockfile configurations (structured models)
LOCKFILE_CONFIGS: Final[tuple[LockfileConfig, ...]] = (
    LockfileConfig(ecosystem="npm", lockfiles=["package-lock.json", "npm-shrinkwrap.json"]),
    LockfileConfig(ecosystem="yarn", lockfiles=["yarn.lock"]),
    LockfileConfig(ecosystem="pnpm", lockfiles=["pnpm-lock.yaml"]),
    LockfileConfig(ecosystem="pip", lockfiles=["requirements.txt", "Pipfile.lock", "poetry.lock", "pip-tools.lock"]),
    LockfileConfig(ecosystem="go", lockfiles=["go.sum"]),
    LockfileConfig(ecosystem="gem", lockfiles=["Gemfile.lock"]),
    LockfileConfig(ecosystem="cargo", lockfiles=["Cargo.lock"]),
    LockfileConfig(ecosystem="nuget", lockfiles=["packages.lock.json"]),
)

# Scanning limits
MAX_FILE_SIZE_MB: Final[int] = 5
MAX_FILE_SIZE_BYTES: Final[int] = MAX_FILE_SIZE_MB * 1024 * 1024
REDACT_MAX_LENGTH: Final[int] = 20
CONTEXT_LINES: Final[int] = 2
