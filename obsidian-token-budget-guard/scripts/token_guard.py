#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate candidate file reads against strict token/context gates.")
    parser.add_argument("--candidate-files", required=True, help="Comma-separated file paths")
    parser.add_argument("--max-files", type=int, default=5)
    parser.add_argument("--max-chars", type=int, default=22000)
    parser.add_argument("--max-snippets", type=int, default=12)
    args = parser.parse_args()

    missing = [cmd for cmd in ["obsidian", "qmd", "uvx"] if shutil.which(cmd) is None]
    if missing:
        return dependency_error(missing)

    files = parse_files(args.candidate_files)
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

    if len(files) > args.max_files:
        violations.append(f"file_count_exceeded:{len(files)}>{args.max_files}")
        remediation.append("Reduce candidate files to highest-signal 3-5 notes.")

    if total_chars > args.max_chars:
        violations.append(f"char_budget_exceeded:{total_chars}>{args.max_chars}")
        remediation.append("Switch to search snippets and read only targeted sections.")

    if len(files) > args.max_snippets:
        violations.append(f"snippet_budget_exceeded:{len(files)}>{args.max_snippets}")
        remediation.append("Limit retrieval snippets before loading full note bodies.")

    if missing_files:
        violations.append(f"missing_files:{len(missing_files)}")
        remediation.append("Fix candidate paths or regenerate candidates from search results.")

    payload = {
        "ok": len(violations) == 0,
        "summary": {
            "candidate_count": len(files),
            "existing_count": len(existing),
            "missing_files": missing_files,
            "total_chars": total_chars,
        },
        "limits": {
            "max_files": args.max_files,
            "max_chars": args.max_chars,
            "max_snippets": args.max_snippets,
        },
        "violations": violations,
        "remediation": remediation,
    }

    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
