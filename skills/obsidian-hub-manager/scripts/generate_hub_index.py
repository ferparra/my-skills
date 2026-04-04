#!/usr/bin/env python3
"""Generate hub index from all _hub.md files in the vault.

Writes 10 Notes/_hub_index.md — a QMD-indexed compact tree of all hubs with
zettel_ids, taglines, and the agent context-loading protocol.

Usage:
    uvx --from python --with pyyaml python \\
        .skills/obsidian-hub-manager/scripts/generate_hub_index.py \\
        [--vault ~/My\\ Vault] [--output "10 Notes/_hub_index.md"]

Output JSON:
    {"ok": true, "output": "<path>", "hub_count": int, "domain_count": int}
"""

import argparse
import glob
import json
import os
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print(json.dumps({"ok": False, "error": "pyyaml not installed"}))
    sys.exit(1)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    try:
        fm = yaml.safe_load(content[3:end].strip()) or {}
    except yaml.YAMLError:
        return {}, content[end + 3:].strip()
    return fm, content[end + 3:].strip()


def extract_title(body: str) -> str:
    for line in body.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def extract_tagline(body: str) -> str:
    past_title = False
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("# ") and not past_title:
            past_title = True
            continue
        if past_title and s and not s.startswith("#") and not s.startswith("**") and not s.startswith("---"):
            return s
    return ""


def get_depth(path: Path, vault: Path) -> int:
    try:
        rel = path.relative_to(vault / "10 Notes")
    except ValueError:
        return -1
    return len(rel.parts) - 2


def hub_vault_path(path: Path, vault: Path) -> str:
    """Return vault-relative path without .md extension."""
    return str(path.relative_to(vault)).replace("/_hub.md", "/_hub")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate hub index markdown")
    parser.add_argument("--vault", default=os.path.expanduser("~/My Vault"))
    parser.add_argument("--output", default="10 Notes/_hub_index.md")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    pattern = str(vault / "10 Notes" / "**" / "_hub.md")
    hub_files = sorted(glob.glob(pattern, recursive=True))

    if not hub_files:
        print(json.dumps({"ok": False, "error": "No _hub.md files found"}))
        sys.exit(1)

    hubs = []
    for f in hub_files:
        path = Path(f)
        content = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(content)
        depth = get_depth(path, vault)
        domain_dir = str(path.parent.parent.relative_to(vault / "10 Notes")) if depth > 0 else str(path.parent.relative_to(vault / "10 Notes"))

        hubs.append({
            "path": hub_vault_path(path, vault),
            "abs_path": str(path),
            "depth": depth,
            "domain_dir": domain_dir,           # e.g. "Knowledge Management"
            "subdir": str(path.parent.relative_to(vault / "10 Notes")),  # full relative dir
            "zettel_id": fm.get("zettel_id", ""),
            "title": extract_title(body),
            "tagline": extract_tagline(body),
            "tags": fm.get("tags") or [],
        })

    hubs.sort(key=lambda h: (h["depth"], h["subdir"]))
    domain_hubs = [h for h in hubs if h["depth"] == 0]
    subdomain_hubs = [h for h in hubs if h["depth"] > 0]
    today = date.today().isoformat()

    lines = [
        "---",
        f"generated: {today}",
        f"hub_count: {len(hubs)}",
        "zettel_kind: index",
        "tags:",
        "  - type/index",
        "  - domain/knowledge-management",
        "---",
        "",
        "# Hub Index",
        "",
        f"Vault memory surface — {len(hubs)} hubs across {len(domain_hubs)} domains.",
        "Load this file for fast vault orientation. Navigate to domain hubs for compressed context.",
        "",
    ]

    for dh in domain_hubs:
        title = dh["title"] or dh["domain_dir"]
        tagline = dh["tagline"] or ""
        zettel_id = dh["zettel_id"]
        path_str = dh["path"]

        id_part = f" `{zettel_id}`" if zettel_id else ""
        lines.append(f"## {title}{id_part}")
        if tagline:
            lines.append(tagline)
        lines.append(f"→ `{path_str}`")
        lines.append("")

        # Children (depth 1 only for readability)
        children = [
            h for h in subdomain_hubs
            if h["domain_dir"] == dh["domain_dir"] and h["depth"] == 1
        ]
        if children:
            for ch in children:
                ch_title = ch["title"] or ch["subdir"].split("/")[-1]
                ch_tagline = f" — {ch['tagline']}" if ch["tagline"] else ""
                ch_id = f" `{ch['zettel_id']}`" if ch["zettel_id"] else ""
                lines.append(f"- **{ch_title}**{ch_id}{ch_tagline}")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## Agent Context Loading Protocol",
        "",
        "1. `qmd query \"<topic>\" -c notes -l 3` — find relevant hub",
        "2. Read domain hub (`depth=0`) for compressed context",
        "3. Read subdomain hub only if topic is specific to that subdomain",
        "4. Load individual notes only when the hub lists them as key and they are directly needed",
        "",
        "**Token budget**: 1 domain hub ≈ 500 tokens. Max 3 hubs per task.",
        "**Subagent handoff**: inject hub content directly into subagent prompt to skip rediscovery.",
        "",
        "Full protocol: `.skills/obsidian-hub-manager/references/agent-context-protocol.md`",
    ])

    output_path = vault / args.output
    output_path.write_text("\n".join(lines), encoding="utf-8")

    result = {
        "ok": True,
        "output": str(output_path),
        "hub_count": len(hubs),
        "domain_count": len(domain_hubs),
        "subdomain_count": len(subdomain_hubs),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
