#!/usr/bin/env python3
"""Audit _hub.md files for schema compliance and predicate graph integrity.

Usage:
    uvx --from python --with pyyaml python \\
        .skills/obsidian-hub-manager/scripts/audit_hubs.py \\
        [--vault ~/My\\ Vault] [--path "10 Notes/Knowledge Management/_hub.md"]

Output JSON:
    {
      "ok": bool,
      "total": int,
      "compliant": int,
      "errors": [...],
      "warnings": [...],
      "hubs": [{"path", "zettel_id", "depth", "tagline", "ok", "errors", "warnings"}]
    }
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(json.dumps({"ok": False, "error": "pyyaml not installed — run: uvx --from python --with pyyaml python ..."}))
    sys.exit(1)

REQUIRED_FIELDS = ["zettel_id", "zettel_kind", "status", "connection_strength", "tags", "type"]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    try:
        fm = yaml.safe_load(content[3:end].strip()) or {}
    except yaml.YAMLError as e:
        return {"_yaml_error": str(e)}, content[end + 3:].strip()
    return fm, content[end + 3:].strip()


def infer_depth(path: Path, vault: Path) -> int:
    """Depth 0 = domain hub (10 Notes/Domain/_hub.md), 1 = subdomain, etc."""
    try:
        rel = path.relative_to(vault / "10 Notes")
    except ValueError:
        return -1
    # parts: ('Domain', '_hub.md') → depth 0; ('Domain', 'Sub', '_hub.md') → depth 1
    return len(rel.parts) - 2


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


def check_hub_graph_integrity(hub_graph: dict, path: Path, vault: Path) -> tuple[list, list]:
    errors, warnings = [], []
    if not isinstance(hub_graph, dict):
        errors.append("hub_graph must be a mapping/dict")
        return errors, warnings

    parent = hub_graph.get("parent", "")
    if parent:
        parent_path = vault / (parent + ".md")
        if not parent_path.exists():
            errors.append(f"hub_graph.parent path does not exist: {parent}")

    for child in hub_graph.get("children", []) or []:
        child_path = vault / (child + ".md")
        if not child_path.exists():
            warnings.append(f"hub_graph.children path does not exist: {child}")

    for cd in hub_graph.get("cross_domain", []) or []:
        cd_path = vault / (cd + ".md")
        if not cd_path.exists():
            warnings.append(f"hub_graph.cross_domain path does not exist: {cd}")

    depth_val = hub_graph.get("depth")
    if depth_val is not None and not isinstance(depth_val, int):
        errors.append(f"hub_graph.depth must be an integer, got: {depth_val!r}")

    return errors, warnings


def check_hub(path: Path, vault: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    errors: list[str] = []
    warnings: list[str] = []

    if "_yaml_error" in fm:
        errors.append(f"YAML parse error: {fm['_yaml_error']}")
        return {
            "path": str(path.relative_to(vault)),
            "zettel_id": "",
            "depth": infer_depth(path, vault),
            "tagline": "",
            "ok": False,
            "errors": errors,
            "warnings": warnings,
        }

    # Required field presence
    for field in REQUIRED_FIELDS:
        if field not in fm:
            errors.append(f"Missing required field: {field}")

    # zettel_id convention
    zettel_id = fm.get("zettel_id", "")
    if zettel_id and not str(zettel_id).startswith("zt-hub-"):
        errors.append(f"zettel_id must start with 'zt-hub-', got: {zettel_id!r}")

    # zettel_kind and type
    if fm.get("zettel_kind") != "moc":
        errors.append(f"zettel_kind must be 'moc', got: {fm.get('zettel_kind')!r}")
    if fm.get("type") != "moc":
        errors.append(f"type must be 'moc', got: {fm.get('type')!r}")

    # Tags
    tags = fm.get("tags") or []
    if not isinstance(tags, list):
        errors.append("tags must be a list")
        tags = []
    if "type/moc" not in tags:
        errors.append("tags must include 'type/moc'")
    domain_tags = [t for t in tags if str(t).startswith("domain/")]
    if not domain_tags:
        warnings.append("No 'domain/*' tag found in tags")

    # connection_strength
    conn = fm.get("connection_strength")
    if conn is not None and not isinstance(conn, (int, float)):
        errors.append(f"connection_strength must be a number, got: {conn!r}")
    elif conn is not None and conn < 0:
        errors.append(f"connection_strength must be >= 0, got: {conn}")

    # Body: H1 title
    lines = body.split("\n")
    has_h1 = any(ln.startswith("# ") for ln in lines)
    if not has_h1:
        errors.append("Missing H1 title in body")

    # Body: tagline
    tagline = extract_tagline(body)
    if not tagline:
        warnings.append("Missing tagline (first non-heading paragraph after H1)")

    # Body: sections
    sections = [ln.strip() for ln in lines if ln.strip().startswith("## ")]
    if not sections:
        warnings.append("No ## sections found in body")

    # Depth and parent reference
    depth = infer_depth(path, vault)
    if depth > 0:
        has_parent_ref = "**Parent domain**" in body or "**Parent**" in body
        if not has_parent_ref:
            warnings.append("Subdomain hub (depth > 0) missing '**Parent domain**:' reference")
        parent_in_graph = (fm.get("hub_graph") or {}).get("parent", "")
        if not parent_in_graph:
            warnings.append("Subdomain hub missing hub_graph.parent path")

    # hub_graph field
    hub_graph = fm.get("hub_graph")
    if hub_graph is None:
        warnings.append("Missing hub_graph frontmatter — add for predicate graph support")
    else:
        g_errors, g_warnings = check_hub_graph_integrity(hub_graph, path, vault)
        errors.extend(g_errors)
        warnings.extend(g_warnings)

        # Depth consistency check
        graph_depth = hub_graph.get("depth") if isinstance(hub_graph, dict) else None
        if graph_depth is not None and graph_depth != depth:
            warnings.append(f"hub_graph.depth={graph_depth} but inferred depth={depth} from path")

    return {
        "path": str(path.relative_to(vault)),
        "zettel_id": str(zettel_id),
        "depth": depth,
        "tagline": tagline,
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit _hub.md schema compliance")
    parser.add_argument("--vault", default=os.path.expanduser("~/My Vault"), help="Vault root directory")
    parser.add_argument("--path", help="Single hub file path (vault-relative or absolute)")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()

    if args.path:
        raw = args.path
        hub_path = Path(raw) if os.path.isabs(raw) else vault / raw
        if not hub_path.exists():
            print(json.dumps({"ok": False, "error": f"File not found: {hub_path}"}))
            sys.exit(1)
        results = [check_hub(hub_path, vault)]
    else:
        pattern = str(vault / "10 Notes" / "**" / "_hub.md")
        hub_files = sorted(glob.glob(pattern, recursive=True))
        if not hub_files:
            print(json.dumps({"ok": True, "total": 0, "compliant": 0, "errors": [], "warnings": ["No _hub.md files found"], "hubs": []}))
            return
        results = [check_hub(Path(f), vault) for f in hub_files]

    total = len(results)
    compliant = sum(1 for r in results if r["ok"])
    all_errors = [f"{r['path']}: {e}" for r in results for e in r["errors"]]
    all_warnings = [f"{r['path']}: {w}" for r in results for w in r["warnings"]]

    output = {
        "ok": all(r["ok"] for r in results),
        "total": total,
        "compliant": compliant,
        "errors": all_errors,
        "warnings": all_warnings,
        "hubs": results,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
