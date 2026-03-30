#!/usr/bin/env python3
"""Export a tailored CV in markdown from structured CV entry notes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cv_models import (
    CV_NOTE_GLOB,
    CvEntryKind,
    CvPillar,
    RecencyWeight,
    load_markdown_note,
    split_frontmatter,
)

CONTACT = {
    "name": "Fernando Parra",
    "email": "ferparra83@gmail.com",
    "phone": "+61427894294",
    "linkedin": "https://www.linkedin.com/in/fparra",
    "portfolio": "https://ferparra.carrd.co",
    "location": "Melbourne, VIC, Australia",
    "languages": "Spanish (native), English (native/bilingual)",
}

HEADLINES: dict[str, str] = {
    "analytics-forward": (
        "Senior Analytics Engineer with a product instinct — builds data "
        "infrastructure that directly enables teams and revenue"
    ),
    "pm-forward": (
        "Product Manager and analytics practitioner who makes product "
        "decisions defensible with data"
    ),
    "growth-forward": (
        "Growth specialist who operationalises analytics into measurable "
        "revenue through lean experimentation"
    ),
    "player-coach": (
        "Analytics leader who builds the team, the stack, and the data "
        "culture simultaneously"
    ),
}

SUMMARIES: dict[str, str] = {
    "analytics-forward": (
        "Analytics & Product Growth specialist who builds the foundations for "
        "data-driven cultures. At B2B SaaS companies across Australia, I've "
        "designed production data infrastructure, self-serve governance "
        "frameworks, and customer-facing data products — always oriented "
        "around what the product team needs to decide and what the business "
        "needs to monetise. I default to small validated bets over big-bang "
        "rollouts."
    ),
    "pm-forward": (
        "Product Manager and analytics practitioner with deep data-engineering "
        "fluency. I've launched SaaS platforms from zero, re-architected "
        "conversion flows through funnel analysis, and built the instrumentation "
        "stacks that make growth measurable. I bring a coaching style to "
        "cross-functional teams — enabling self-serve analytics, running "
        "prioritisation workshops, and building data literacy alongside the "
        "product."
    ),
}

RECENCY_ORDER = {
    RecencyWeight.HIGH.value: 0,
    RecencyWeight.MEDIUM.value: 1,
    RecencyWeight.LOW.value: 2,
}


def load_cv_entries(root: Path, globs: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for pattern in globs:
        for path in sorted(root.glob(pattern)):
            if path.suffix != ".md":
                continue
            note = load_markdown_note(path)
            if note.frontmatter.get("cv_entry_kind"):
                entries.append(note.frontmatter)
    return entries


def filter_bullets_by_pillars(
    bullets: list[dict[str, Any]],
    pillar_filter: set[str],
) -> list[dict[str, Any]]:
    if not pillar_filter:
        return bullets
    return [
        b for b in bullets
        if not b.get("pillars") or set(b["pillars"]) & pillar_filter
    ]


def render_role(entry: dict[str, Any], pillar_filter: set[str]) -> str:
    lines: list[str] = []
    company = entry.get("company_name", "Unknown")
    title = entry.get("role_title", "Unknown")
    start = entry.get("start_date", "?")
    end = entry.get("end_date", "present")
    location = entry.get("location", "")
    industry = entry.get("industry", "")

    header = f"### {company} — {title}"
    lines.append(header)
    meta = f"**{start} – {end}**"
    if location:
        meta += f" · {location}"
    if industry:
        meta += f" · {industry}"
    lines.append(meta)
    lines.append("")

    bullets = entry.get("bullets") or []
    if isinstance(bullets, list):
        filtered = filter_bullets_by_pillars(bullets, pillar_filter)
        for bullet in filtered:
            text = bullet.get("text", "") if isinstance(bullet, dict) else str(bullet)
            lines.append(f"- {text}")
        if filtered:
            lines.append("")

    return "\n".join(lines)


def render_education(entry: dict[str, Any]) -> str:
    institution = entry.get("institution", "Unknown")
    qualification = entry.get("qualification", "Unknown")
    start = entry.get("start_year", "")
    end = entry.get("end_year", "")
    years = f" ({start}–{end})" if start and end else ""
    return f"| {institution} | {qualification} | {years.strip()} |"


def render_credential(entry: dict[str, Any]) -> str:
    kind = entry.get("cv_entry_kind", "")
    if kind == "certification":
        name = entry.get("certification_name", "Unknown")
        body = entry.get("issuing_body", "")
        return f"- **{name}**" + (f" ({body})" if body else "")
    if kind == "award":
        name = entry.get("award_name", "Unknown")
        event = entry.get("event", "")
        return f"- **{name}**" + (f" — {event}" if event else "")
    return ""


def export_cv(
    entries: list[dict[str, Any]],
    *,
    headline_key: str = "analytics-forward",
    pillar_filter: set[str] | None = None,
) -> str:
    pillar_set = pillar_filter or set()
    lines: list[str] = []

    # Header
    lines.append(f"# {CONTACT['name']}")
    lines.append("")
    lines.append(
        f"{CONTACT['email']} · {CONTACT['phone']} · "
        f"[LinkedIn]({CONTACT['linkedin']}) · "
        f"[Portfolio]({CONTACT['portfolio']})"
    )
    lines.append(f"{CONTACT['location']} · {CONTACT['languages']}")
    lines.append("")

    # Headline
    headline = HEADLINES.get(headline_key, HEADLINES["analytics-forward"])
    lines.append(f"> {headline}")
    lines.append("")

    # Summary
    summary = SUMMARIES.get(headline_key, SUMMARIES.get("analytics-forward", ""))
    if summary:
        lines.append(summary)
        lines.append("")

    # Roles
    roles = [e for e in entries if e.get("cv_entry_kind") == CvEntryKind.ROLE.value]
    roles.sort(key=lambda e: RECENCY_ORDER.get(e.get("recency_weight", "low"), 2))

    lines.append("## Experience")
    lines.append("")
    for role in roles:
        lines.append(render_role(role, pillar_set))

    # Education
    education = [e for e in entries if e.get("cv_entry_kind") == CvEntryKind.EDUCATION.value]
    if education:
        lines.append("## Education")
        lines.append("")
        lines.append("| Institution | Qualification | Years |")
        lines.append("|-------------|--------------|-------|")
        for edu in education:
            lines.append(render_education(edu))
        lines.append("")

    # Credentials
    creds = [
        e for e in entries
        if e.get("cv_entry_kind") in (CvEntryKind.CERTIFICATION.value, CvEntryKind.AWARD.value)
    ]
    if creds:
        lines.append("## Certifications & Awards")
        lines.append("")
        for cred in creds:
            line = render_credential(cred)
            if line:
                lines.append(line)
        lines.append("")

    # Community
    community = [e for e in entries if e.get("cv_entry_kind") == CvEntryKind.COMMUNITY.value]
    if community:
        lines.append("## Community")
        lines.append("")
        for comm in community:
            name = comm.get("activity_name", "Unknown")
            duration = comm.get("duration", "")
            desc = comm.get("description", "")
            line = f"- **{name}**"
            if duration:
                line += f" ({duration})"
            if desc:
                line += f" — {desc}"
            lines.append(line)
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a tailored CV from structured notes.")
    parser.add_argument("--glob", action="append", default=[], help="Glob patterns for CV notes.")
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument(
        "--pillars",
        default="",
        help="Comma-separated pillar filter (e.g. P1,P2). Empty = all.",
    )
    parser.add_argument(
        "--headline",
        default="analytics-forward",
        choices=list(HEADLINES.keys()),
        help="Headline style.",
    )
    parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "json"],
        help="Output format.",
    )
    parser.add_argument("--output", default=None, help="Output file path (default: stdout).")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    globs = args.glob or [CV_NOTE_GLOB]
    entries = load_cv_entries(root, globs)

    pillar_filter: set[str] = set()
    if args.pillars:
        pillar_filter = {p.strip() for p in args.pillars.split(",") if p.strip()}

    if args.format == "json":
        output = json.dumps(
            {"entries": entries, "pillar_filter": sorted(pillar_filter)},
            indent=2,
            default=str,
        )
    else:
        output = export_cv(
            entries,
            headline_key=args.headline,
            pillar_filter=pillar_filter,
        )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(json.dumps({"ok": True, "path": str(out_path)}, indent=2))
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
