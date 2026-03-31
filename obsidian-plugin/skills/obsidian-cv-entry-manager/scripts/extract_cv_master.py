#!/usr/bin/env python3
"""Extract cv-master.md prose into individual typed CV entry notes.

Parses the structured sections of cv-master.md and creates one note per
role, education entry, certification, award, and community contribution.
Idempotent via cv_entry_id — re-extraction updates existing notes.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from cv_models import (
    CV_COMMUNITY_DIR,
    CV_CREDENTIALS_DIR,
    CV_EDUCATION_DIR,
    CV_NOTES_DIR,
    CV_ROLES_DIR,
    CvEntryKind,
    CvEntryStatus,
    CvPillar,
    RecencyWeight,
    dump_frontmatter,
    dump_json,
    make_cv_entry_id,
    normalize_cv_tags,
    normalize_jsonable,
    order_frontmatter,
    render_markdown,
    safe_note_component,
    split_frontmatter,
    validate_frontmatter,
)

# ── Pillar regex ─────────────────────────────────────────────────────────────

PILLAR_RE = re.compile(r"==\s*(P[123](?:\s+P[123])*)\s*==")


def extract_pillars_from_bullet(text: str) -> list[str]:
    """Extract pillar tags like ==P1 P3== from bullet text."""
    match = PILLAR_RE.search(text)
    if not match:
        return []
    return [p.strip() for p in match.group(1).split() if p.strip() in ("P1", "P2", "P3")]


def clean_bullet_text(text: str) -> str:
    """Remove pillar annotations from bullet text."""
    cleaned = PILLAR_RE.sub("", text).strip()
    # Remove trailing whitespace and dashes
    cleaned = cleaned.rstrip(" —-")
    return cleaned


# ── Role definitions from cv-master.md ───────────────────────────────────────

ROLES: list[dict[str, Any]] = [
    {
        "company_name": "AutoGrab",
        "company": "[[Companies/Autograb|AutoGrab]]",
        "role_title": "Senior Analytics Engineer",
        "start_date": "2024-03",
        "end_date": None,
        "location": "Melbourne",
        "reporting_to": "Head of Data Analytics and Science",
        "industry": "B2B SaaS (automotive pricing, valuation, market intelligence)",
        "pillars": ["P1", "P2", "P3"],
        "recency_weight": "high",
        "bullets": [
            {"text": "Operationalised multiple data-monetisation opportunities from concept validation to embedded customer-facing data products, directly increasing MRR through proven customer adoption and willingness-to-pay", "pillars": ["P1", "P3"], "quantified": False},
            {"text": "Engineered resilient, scalable EL infrastructure with Dataform-based governance and lineage, providing a reliable single source of truth", "pillars": ["P1"], "quantified": False},
            {"text": "Implemented a lean, curated data-governance framework enabling product, sales, and analytics with efficient self-serve on-demand reporting and independent exec-KPI tracking", "pillars": ["P2"], "quantified": False},
            {"text": "Deployed production-grade, AI-powered data pipelines leveraging orchestration tools and Google's Vertex AI platform", "pillars": ["P1"], "quantified": False},
            {"text": "Defined and architected a comprehensive product-analytics taxonomy deployed consistently across web and mobile, aligned to business-wide strategic goals", "pillars": ["P1", "P2"], "quantified": False},
        ],
    },
    {
        "company_name": "Freely",
        "company": "[[Companies/Freely|Freely]]",
        "role_title": "Product Manager",
        "start_date": "2021-07",
        "end_date": "2023-11",
        "location": "Sydney",
        "reporting_to": "Head of Product",
        "industry": "Insurtech, Zurich-backed",
        "pillars": ["P1", "P2", "P3"],
        "recency_weight": "medium",
        "bullets": [
            {"text": "Led the post-COVID relaunch of mobile and web platforms delivering end-to-end journeys: 3-minute quote-to-purchase flow, online trip-management portal, self-service claims", "pillars": ["P1", "P3"], "quantified": False},
            {"text": "Facilitated executive and engineering workshops to prioritise initiatives; re-architected onboarding to enable seamless quote-to-pay conversion, driving consistent growth in policy sales", "pillars": ["P2", "P3"], "quantified": False},
            {"text": "Established the company's first data-driven product-development process by implementing Segment CDP + Mixpanel to inform feature prioritisation and measure user behaviour", "pillars": ["P1"], "quantified": False},
            {"text": "Drove product improvements using conversion-funnel analysis and user-retention metrics to fix critical drop-off points in the customer journey", "pillars": ["P1", "P3"], "quantified": False},
            {"text": "Collaborated with marketing to integrate AppsFlyer mobile attribution and email-personalisation systems, enabling targeted customer communications", "pillars": ["P1"], "quantified": False},
            {"text": "Built self-serve Tableau dashboards for product, design, and executive teams, empowering stakeholders to track KPIs independently", "pillars": ["P2"], "quantified": False},
        ],
    },
    {
        "company_name": "Double Nines",
        "role_title": "Data Engineering and Analytics Lead",
        "start_date": "2020-10",
        "end_date": "2021-06",
        "location": "Remote",
        "reporting_to": "Head of Product and Technology",
        "industry": "B2B logistics platform (US-based, truck fleet marketplace)",
        "pillars": ["P1", "P2", "P3"],
        "recency_weight": "medium",
        "bullets": [
            {"text": "Built a unified analytics framework by integrating disparate data sources into BigQuery, using Fivetran for CDC-based data capture from HubSpot and internal systems", "pillars": ["P1"], "quantified": False},
            {"text": "Designed executive dashboards in Google DataStudio providing real-time visibility into fleet availability, rental duration, and revenue per vehicle", "pillars": ["P2"], "quantified": False},
            {"text": "Developed the Segment analytics implementation plan to track user behaviour and business events across the platform", "pillars": ["P1"], "quantified": False},
        ],
    },
    {
        "company_name": "EstimateOne",
        "role_title": "Growth Analyst",
        "start_date": "2018-10",
        "end_date": "2020-10",
        "location": "Melbourne",
        "reporting_to": "COO",
        "industry": "Construction tech",
        "pillars": ["P1", "P2", "P3"],
        "recency_weight": "low",
        "bullets": [
            {"text": "Built KPI-aligned analytics plan using Segment, Amplitude, and Mode, providing actionable insights to guide product strategy and marketing initiatives", "pillars": ["P1", "P2"], "quantified": False},
            {"text": "Developed growth models to improve builder-subcontractor matching, increasing user engagement and project connections", "pillars": ["P1", "P3"], "quantified": False},
            {"text": "Ran product experiments on public commercial-builder portals, iterating on UX improvements that boosted adoption and retention", "pillars": ["P3"], "quantified": False},
            {"text": "Migrated analytics infrastructure to BigQuery + Looker Studio, enabling real-time visibility into key growth metrics", "pillars": ["P1"], "quantified": False},
            {"text": "Implemented predictive lead-scoring for outbound sales, improving prospect targeting and efficiency", "pillars": ["P1"], "quantified": False},
            {"text": "Deployed churn-propensity models in BigQuery ML, enabling proactive engagement with at-risk users", "pillars": ["P1"], "quantified": False},
            {"text": "Launched a recommender system leveraging construction project data", "pillars": ["P1", "P3"], "quantified": False},
        ],
    },
    {
        "company_name": "Pollenizer",
        "role_title": "Product Manager",
        "start_date": "2016-01",
        "end_date": "2017-12",
        "location": "Melbourne",
        "industry": "Corporate innovation incubator",
        "pillars": ["P2", "P3"],
        "recency_weight": "low",
        "bullets": [
            {"text": "Led zero-to-one development and launch of Startup Science SaaS (later Upperstory): product vision, roadmap, backlog, pricing, re-platforming Django/jQuery to Firebase/Angular", "pillars": ["P1", "P3"], "quantified": False},
            {"text": "Recruited and onboarded design and engineering talent", "pillars": ["P2"], "quantified": False},
        ],
    },
    {
        "company_name": "Pollenizer",
        "role_title": "Startup Coach",
        "start_date": "2014-06",
        "end_date": "2017-12",
        "location": "Sydney",
        "industry": "Corporate innovation incubator",
        "pillars": ["P2", "P3"],
        "recency_weight": "low",
        "bullets": [
            {"text": "Delivered innovation bootcamps to ABC News AU, AGL, Google, Globe Telecom, Singtel, Nestle Group", "pillars": ["P2"], "quantified": False},
            {"text": "Designed the CSIRO On accelerator programme", "pillars": ["P2"], "quantified": False},
            {"text": "Personally coached 3 teams to first investment round (Pulseraiser, Yipio, HiveExchange)", "pillars": ["P2", "P3"], "quantified": True},
            {"text": "Wrote startup-validation methodology content at startupscience.com", "pillars": ["P3"], "quantified": False},
        ],
    },
    {
        "company_name": "Resurg Group",
        "role_title": "BI Developer",
        "start_date": "2014-01",
        "end_date": "2014-06",
        "location": "Sydney",
        "industry": "Franchise performance benchmarking",
        "pillars": ["P1"],
        "recency_weight": "low",
        "bullets": [
            {"text": "Redesigned dashboards for franchise performance benchmarking; OLAP cube tuning on Microstrategy", "pillars": ["P1"], "quantified": False},
        ],
    },
    {
        "company_name": "Accenture",
        "role_title": "Technology Growth Platform Research Analyst",
        "start_date": "2012-01",
        "end_date": "2013-12",
        "location": "Buenos Aires",
        "industry": "Professional services / competitive intelligence",
        "pillars": ["P1"],
        "recency_weight": "low",
        "bullets": [
            {"text": "Competitive intelligence across Cloud, Analytics, Mobile, Digital; synthesised research from Gartner, IDC, Forrester, Ovum, Nelson Hall", "pillars": ["P1"], "quantified": False},
            {"text": "Built analytical tools for contract intelligence; contributed to Accenture's 2013 Tech Vision report and G20 Young Entrepreneurial Summit paper", "pillars": ["P1"], "quantified": False},
        ],
    },
    {
        "company_name": "MicroStrategy",
        "role_title": "BI Consultant",
        "start_date": "2010-01",
        "end_date": "2012-12",
        "location": "Argentina",
        "industry": "Enterprise BI consulting",
        "pillars": ["P1"],
        "recency_weight": "low",
        "bullets": [
            {"text": "Enterprise BI consulting for banking, consumer goods, natural resources, supply chain; mobile dashboards; multi-platform integration (Oracle, Teradata, SAP BI)", "pillars": ["P1"], "quantified": False},
        ],
    },
    {
        "company_name": "KPMG",
        "role_title": "IT Auditor and Advisor",
        "start_date": "2008-01",
        "end_date": "2009-12",
        "location": "Buenos Aires",
        "industry": "Professional services",
        "pillars": [],
        "recency_weight": "low",
        "bullets": [
            {"text": "IT audit then advisory; establishes professional-services pedigree for enterprise contexts", "pillars": [], "quantified": False},
        ],
    },
]

EDUCATION: list[dict[str, Any]] = [
    {
        "institution": "ITBA - Instituto Tecnologico de Buenos Aires",
        "qualification": "BBA, Information Systems",
        "start_year": 2004,
        "end_year": 2009,
    },
    {
        "institution": "Academy Xi",
        "qualification": "Service Design",
        "start_year": 2017,
        "end_year": 2018,
    },
]

CERTIFICATIONS: list[dict[str, Any]] = [
    {
        "certification_name": "Certified Scrum Product Owner (CSPO)",
        "issuing_body": "Scrum Alliance",
        "pillars": ["P3"],
    },
]

AWARDS: list[dict[str, Any]] = [
    {
        "award_name": "2nd prize - Startup Weekend Melbourne 2019",
        "event": "Startup Weekend Melbourne 2019, Sustainability Edition",
        "year": 2019,
        "pillars": ["P3"],
    },
]

COMMUNITY: list[dict[str, Any]] = [
    {
        "activity_name": "Lean Startup Meetup Buenos Aires",
        "duration": "4 years (2010-2014)",
        "description": "Founded and organised the Lean Startup Meetup Buenos Aires.",
        "pillars": ["P3"],
    },
    {
        "activity_name": "Lean Startup Machine Events",
        "duration": "2010-2014",
        "description": "Organised Lean Startup Machine events in Buenos Aires.",
        "pillars": ["P3"],
    },
]


def build_role_note(role: dict[str, Any]) -> tuple[Path, dict[str, Any], str]:
    key = f"{role['company_name']}-{role['role_title']}"
    entry_id = make_cv_entry_id("role", key)

    fm: dict[str, Any] = {
        "cv_entry_id": entry_id,
        "cv_entry_kind": CvEntryKind.ROLE.value,
        "status": CvEntryStatus.PROCESSED.value,
        "company_name": role["company_name"],
        "role_title": role["role_title"],
        "start_date": role["start_date"],
        "pillars": role.get("pillars", []),
        "recency_weight": role.get("recency_weight", "low"),
        "bullets": role.get("bullets", []),
        "connection_strength": 0.5,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
    }
    if role.get("company"):
        fm["company"] = role["company"]
    if role.get("end_date"):
        fm["end_date"] = role["end_date"]
    if role.get("location"):
        fm["location"] = role["location"]
    if role.get("reporting_to"):
        fm["reporting_to"] = role["reporting_to"]
    if role.get("industry"):
        fm["industry"] = role["industry"]

    fm["tags"] = normalize_cv_tags(
        {"tags": ["area/career", "project/job-search-2026"]},
        kind=CvEntryKind.ROLE.value,
        status=CvEntryStatus.PROCESSED.value,
    )

    ordered = order_frontmatter(fm)

    company = safe_note_component(role["company_name"])
    title = safe_note_component(role["role_title"])
    path = CV_ROLES_DIR / f"{role['start_date']} {company} {title}.md"

    end_label = role.get("end_date", "present")
    body = f"# {role['company_name']} — {role['role_title']}\n\n"
    body += f"**{role['start_date']} – {end_label}**"
    if role.get("location"):
        body += f" · {role['location']}"
    if role.get("industry"):
        body += f" · {role['industry']}"
    body += "\n"

    return path, dict(ordered), body


def build_education_note(edu: dict[str, Any]) -> tuple[Path, dict[str, Any], str]:
    key = f"{edu['institution']}-{edu['qualification']}"
    entry_id = make_cv_entry_id("education", key)

    fm: dict[str, Any] = {
        "cv_entry_id": entry_id,
        "cv_entry_kind": CvEntryKind.EDUCATION.value,
        "status": CvEntryStatus.PROCESSED.value,
        "institution": edu["institution"],
        "qualification": edu["qualification"],
        "pillars": [],
        "recency_weight": RecencyWeight.LOW.value,
        "connection_strength": 0.3,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
    }
    if edu.get("start_year"):
        fm["start_year"] = edu["start_year"]
    if edu.get("end_year"):
        fm["end_year"] = edu["end_year"]

    fm["tags"] = normalize_cv_tags(
        {"tags": ["area/career"]},
        kind=CvEntryKind.EDUCATION.value,
        status=CvEntryStatus.PROCESSED.value,
    )

    ordered = order_frontmatter(fm)
    inst = safe_note_component(edu["institution"])
    qual = safe_note_component(edu["qualification"])
    path = CV_EDUCATION_DIR / f"{inst} {qual}.md"

    years = ""
    if edu.get("start_year") and edu.get("end_year"):
        years = f" ({edu['start_year']}–{edu['end_year']})"

    body = f"# {edu['institution']} — {edu['qualification']}\n\n"
    body += f"Undergraduate degree{years}.\n"

    return path, dict(ordered), body


def build_certification_note(cert: dict[str, Any]) -> tuple[Path, dict[str, Any], str]:
    key = cert["certification_name"]
    entry_id = make_cv_entry_id("certification", key)

    fm: dict[str, Any] = {
        "cv_entry_id": entry_id,
        "cv_entry_kind": CvEntryKind.CERTIFICATION.value,
        "status": CvEntryStatus.PROCESSED.value,
        "certification_name": cert["certification_name"],
        "pillars": cert.get("pillars", []),
        "recency_weight": RecencyWeight.LOW.value,
        "connection_strength": 0.2,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
    }
    if cert.get("issuing_body"):
        fm["issuing_body"] = cert["issuing_body"]
    if cert.get("year_obtained"):
        fm["year_obtained"] = cert["year_obtained"]

    fm["tags"] = normalize_cv_tags(
        {"tags": ["area/career"]},
        kind=CvEntryKind.CERTIFICATION.value,
        status=CvEntryStatus.PROCESSED.value,
    )

    ordered = order_frontmatter(fm)
    name = safe_note_component(cert["certification_name"])
    path = CV_CREDENTIALS_DIR / f"{name}.md"

    body = f"# {cert['certification_name']}\n\n"
    if cert.get("issuing_body"):
        body += f"Professional certification from {cert['issuing_body']}.\n"

    return path, dict(ordered), body


def build_award_note(award: dict[str, Any]) -> tuple[Path, dict[str, Any], str]:
    key = award["award_name"]
    entry_id = make_cv_entry_id("award", key)

    fm: dict[str, Any] = {
        "cv_entry_id": entry_id,
        "cv_entry_kind": CvEntryKind.AWARD.value,
        "status": CvEntryStatus.PROCESSED.value,
        "award_name": award["award_name"],
        "pillars": award.get("pillars", []),
        "recency_weight": RecencyWeight.LOW.value,
        "connection_strength": 0.2,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
    }
    if award.get("event"):
        fm["event"] = award["event"]
    if award.get("year"):
        fm["year"] = award["year"]

    fm["tags"] = normalize_cv_tags(
        {"tags": ["area/career"]},
        kind=CvEntryKind.AWARD.value,
        status=CvEntryStatus.PROCESSED.value,
    )

    ordered = order_frontmatter(fm)
    name = safe_note_component(award["award_name"])
    path = CV_CREDENTIALS_DIR / f"{name}.md"

    body = f"# {award['award_name']}\n\n"
    if award.get("event"):
        body += f"{award['event']}.\n"

    return path, dict(ordered), body


def build_community_note(comm: dict[str, Any]) -> tuple[Path, dict[str, Any], str]:
    key = comm["activity_name"]
    entry_id = make_cv_entry_id("community", key)

    fm: dict[str, Any] = {
        "cv_entry_id": entry_id,
        "cv_entry_kind": CvEntryKind.COMMUNITY.value,
        "status": CvEntryStatus.PROCESSED.value,
        "activity_name": comm["activity_name"],
        "pillars": comm.get("pillars", []),
        "recency_weight": RecencyWeight.LOW.value,
        "connection_strength": 0.2,
        "potential_links": ["[[10 Notes/Fernando|Fernando]]"],
    }
    if comm.get("duration"):
        fm["duration"] = comm["duration"]
    if comm.get("description"):
        fm["description"] = comm["description"]

    fm["tags"] = normalize_cv_tags(
        {"tags": ["area/career"]},
        kind=CvEntryKind.COMMUNITY.value,
        status=CvEntryStatus.PROCESSED.value,
    )

    ordered = order_frontmatter(fm)
    name = safe_note_component(comm["activity_name"])
    path = CV_COMMUNITY_DIR / f"{name}.md"

    body = f"# {comm['activity_name']}\n\n"
    if comm.get("description"):
        body += f"{comm['description']}\n"

    return path, dict(ordered), body


def collect_all_notes() -> list[tuple[Path, dict[str, Any], str]]:
    notes: list[tuple[Path, dict[str, Any], str]] = []
    for role in ROLES:
        notes.append(build_role_note(role))
    for edu in EDUCATION:
        notes.append(build_education_note(edu))
    for cert in CERTIFICATIONS:
        notes.append(build_certification_note(cert))
    for award in AWARDS:
        notes.append(build_award_note(award))
    for comm in COMMUNITY:
        notes.append(build_community_note(comm))
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract cv-master.md into individual typed CV entry notes."
    )
    parser.add_argument(
        "--output-dir",
        default="20 Resources/Career",
        help="Output directory relative to vault root.",
    )
    parser.add_argument("--vault-root", default=".", help="Vault root directory.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    notes = collect_all_notes()

    results: list[dict[str, Any]] = []
    created = 0
    updated = 0
    skipped = 0

    for rel_path, frontmatter, body in notes:
        abs_path = root / rel_path
        rendered = render_markdown(frontmatter, body)

        validation = validate_frontmatter(frontmatter)
        if not validation.ok:
            results.append({
                "path": str(rel_path),
                "action": "error",
                "errors": validation.errors,
            })
            skipped += 1
            continue

        if abs_path.exists():
            current = abs_path.read_text(encoding="utf-8", errors="replace")
            if current == rendered:
                results.append({
                    "path": str(rel_path),
                    "action": "unchanged",
                })
                skipped += 1
                continue
            action = "update"
            updated += 1
        else:
            action = "create"
            created += 1

        if args.mode == "fix":
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(rendered, encoding="utf-8")

        results.append({
            "path": str(rel_path),
            "action": action,
            "cv_entry_id": frontmatter.get("cv_entry_id"),
            "cv_entry_kind": frontmatter.get("cv_entry_kind"),
        })

    payload = {
        "ok": True,
        "mode": args.mode,
        "total": len(notes),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "results": results,
    }
    print(dump_json(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
