#!/usr/bin/env python3
"""Token budget guard for Obsidian vault.

Provides two modes:
1. preflight - Estimate token cost before executing a query
2. guard    - Validate token budget against hard limits (original behavior)

Usage:
    # Pre-flight estimation
    uvx --from python --with pydantic --with pyyaml python \
      .skills/obsidian-token-budget-guard/scripts/token_guard.py \
      --mode preflight --query "person_kind:collaborator" --vault-root . \
      --output token_estimate.json

    # Guard check
    uvx --from python --with pydantic --with pyyaml python \
      .skills/obsidian-token-budget-guard/scripts/token_guard.py \
      --mode guard --candidate-files "file1.md,file2.md" \
      --max-files 5 --max-chars 22000 --max-snippets 12
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, List

# Token estimation constants
CHARS_PER_TOKEN = 4.0
PER_NOTE_OVERHEAD = 50  # tokens for frontmatter, path, metadata

# Warning thresholds (tokens)
THRESHOLD_GREEN = 5000
THRESHOLD_YELLOW = 15000


def dependency_error(missing: List[str]) -> int:
    payload = {
        "ok": False,
        "error": "missing_dependencies",
        "missing": missing,
        "fallback_checklist": [
            "Install/repair Obsidian CLI and ensure uvx is available.",
            "Install qmd: npm install -g @tobilu/qmd",
            "Re-index if needed: qmd update && qmd embed",
            "Re-run this guard command before any broad reads.",
        ],
    }
    print(json.dumps(payload, indent=2))
    return 2


def parse_files(csv_value: str) -> List[str]:
    return [part.strip() for part in csv_value.split(",") if part.strip()]


def get_warning_level(token_estimate: int) -> str:
    """Determine warning level based on token estimate."""
    if token_estimate < THRESHOLD_GREEN:
        return "green"
    elif token_estimate < THRESHOLD_YELLOW:
        return "yellow"
    else:
        return "red"


def estimate_tokens(chars: int) -> int:
    """Estimate tokens from character count."""
    return int(chars / CHARS_PER_TOKEN) + PER_NOTE_OVERHEAD


def scan_vault_for_query(
    vault_root: Path,
    query: str,
) -> dict[str, Any]:
    """Run obsidian search and estimate token cost for matching notes.

    Args:
        vault_root: Root of the vault
        query: The search query

    Returns:
        Dict with matching_notes, total_chars, token_estimate, warning_level, breakdown
    """
    # Try obsidian search first
    obsidian_available = shutil.which("obsidian") is not None

    matching_notes: List[str] = []
    if obsidian_available:
        try:
            result = subprocess.run(
                ["obsidian", "search", f"query={query}", "limit=1000", "total"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(vault_root),
            )
            if result.returncode == 0:
                # Parse output - each line is a note path
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and not line.startswith("("):
                        matching_notes.append(line)
        except (subprocess.TimeoutExpired, Exception):
            pass

    # Fallback: scan vault using glob and basic filtering
    if not matching_notes:
        query_lower = query.lower()
        for md_file in vault_root.rglob("*.md"):
            if any(part.startswith(".") for part in md_file.parts):
                continue
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace").lower()
                # Simple keyword matching for common query patterns
                if ":" in query:
                    field = query.split(":")[0].strip().lower()
                    value = query.split(":")[1].strip().lower()
                    if field in content and value in content:
                        matching_notes.append(str(md_file.relative_to(vault_root)))
                elif query_lower in content:
                    matching_notes.append(str(md_file.relative_to(vault_root)))
            except Exception:
                continue

    # Build breakdown
    breakdown: List[dict[str, Any]] = []
    total_chars = 0

    for note_path in matching_notes:
        full_path = vault_root / note_path
        chars = 0
        if full_path.exists():
            try:
                text = full_path.read_text(encoding="utf-8", errors="replace")
                chars = len(text)
            except Exception:
                chars = 0

        tokens = estimate_tokens(chars)
        total_chars += chars
        breakdown.append({
            "path": note_path,
            "chars": chars,
            "tokens_estimate": tokens,
        })

    token_estimate = sum(n["tokens_estimate"] for n in breakdown)
    warning_level = get_warning_level(token_estimate)

    return {
        "matching_notes": len(matching_notes),
        "total_chars": total_chars,
        "token_estimate": token_estimate,
        "warning_level": warning_level,
        "breakdown": breakdown,
    }


def run_preflight(
    vault_root: Path,
    query: str,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run pre-flight estimation."""
    estimate = scan_vault_for_query(vault_root, query)

    warning_level = estimate["warning_level"]
    token_estimate = estimate["token_estimate"]

    # Determine overall ok status
    ok = warning_level != "red"

    # Build recommendation
    if warning_level == "green":
        recommendation = "Safe to proceed with query."
    elif warning_level == "yellow":
        recommendation = "Proceed with caution. Consider narrowing scope if possible."
    else:
        recommendation = "Do not proceed. Reduce query scope before executing."

    payload = {
        "ok": ok,
        "mode": "preflight",
        "query": query,
        "estimate": estimate,
        "thresholds": {
            "green_max": THRESHOLD_GREEN,
            "yellow_max": THRESHOLD_YELLOW,
            "red_above": THRESHOLD_YELLOW,
        },
        "recommendation": recommendation,
    }

    if output_path:
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def run_guard(
    candidate_files: List[str],
    max_files: int,
    max_chars: int,
    max_snippets: int,
) -> dict[str, Any]:
    """Run guard mode check against hard limits."""
    missing = [cmd for cmd in ["obsidian", "qmd", "uvx"] if shutil.which(cmd) is None]
    if missing:
        return {"ok": False, "error": "missing_dependencies", "missing": missing}

    files = parse_files(",".join(candidate_files)) if isinstance(candidate_files[0], list) else parse_files(",".join(candidate_files))
    existing = []
    missing_files = []
    total_chars = 0

    for item in files:
        path = Path(item)
        if path.exists() and path.is_file():
            existing.append(str(path))
            try:
                total_chars += len(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                total_chars += 0
        else:
            missing_files.append(item)

    violations = []
    remediation = []

    if len(files) > max_files:
        violations.append(f"file_count_exceeded:{len(files)}>{max_files}")
        remediation.append("Reduce candidate files to highest-signal 3-5 notes.")

    if total_chars > max_chars:
        violations.append(f"char_budget_exceeded:{total_chars}>{max_chars}")
        remediation.append("Switch to search snippets and read only targeted sections.")

    if len(files) > max_snippets:
        violations.append(f"snippet_budget_exceeded:{len(files)}>{max_snippets}")
        remediation.append("Limit retrieval snippets before loading full note bodies.")

    if missing_files:
        violations.append(f"missing_files:{len(missing_files)}")
        remediation.append("Fix candidate paths or regenerate candidates from search results.")

    payload = {
        "ok": len(violations) == 0,
        "mode": "guard",
        "summary": {
            "candidate_count": len(files),
            "existing_count": len(existing),
            "missing_files": missing_files,
            "total_chars": total_chars,
        },
        "limits": {
            "max_files": max_files,
            "max_chars": max_chars,
            "max_snippets": max_snippets,
        },
        "violations": violations,
        "remediation": remediation,
    }

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Token budget guard for Obsidian vault. "
                    "Run pre-flight estimation or post-flight guard checks.",
    )
    parser.add_argument(
        "--mode",
        default="guard",
        choices=["preflight", "guard"],
        help="preflight: estimate cost before query. guard: validate hard limits.",
    )
    parser.add_argument(
        "--candidate-files",
        help="Comma-separated file paths (guard mode only)",
    )
    parser.add_argument(
        "--query",
        help="Search query to estimate (preflight mode only)",
    )
    parser.add_argument(
        "--vault-root",
        default=".",
        help="Vault root directory",
    )
    parser.add_argument(
        "--output",
        help="Output path for the estimate JSON (preflight mode)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=5,
        help="Max files (guard mode)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=22000,
        help="Max characters (guard mode)",
    )
    parser.add_argument(
        "--max-snippets",
        type=int,
        default=12,
        help="Max snippets (guard mode)",
    )
    args = parser.parse_args()

    vault_root = Path(args.vault_root).resolve()
    if not vault_root.exists():
        print(json.dumps({"ok": False, "error": f"Vault root not found: {vault_root}"}))
        return 1

    if args.mode == "preflight":
        if not args.query:
            print(json.dumps({"ok": False, "error": "--query is required for preflight mode"}))
            return 1

        # Check dependencies
        missing = [cmd for cmd in ["obsidian", "qmd", "uvx"] if shutil.which(cmd) is None]
        if missing:
            return dependency_error(missing)

        output_path = Path(args.output) if args.output else None
        result = run_preflight(vault_root, args.query, output_path)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    else:  # guard mode
        if not args.candidate_files:
            print(json.dumps({"ok": False, "error": "--candidate-files is required for guard mode"}))
            return 1

        result = run_guard(
            parse_files(args.candidate_files),
            args.max_files,
            args.max_chars,
            args.max_snippets,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
