#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


INVENTORY_PATTERN = re.compile(
    r"^\d+\.\s+\[(.+?)\]\((https://notebooklm\.google\.com/notebook/[^)]+)\)\s*$",
    re.MULTILINE,
)
SUMMARY_PATTERN = re.compile(
    r"^#\s+(.+?)\n(https://notebooklm\.google\.com/notebook/\S+)\n(.*?)(?=^#\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)

COMMON_TAGS = [
    "type/note",
    "status/processing",
    "area/development/learning",
]

LANE_CONFIG = {
    "ai-systems": {
        "topic_tag": "resource/topic/ai",
        "concept_link": "[[10 Projects/AI Research/AI and LLM Application Development Map|AI and LLM Application Development Map]]",
        "context_link": "[[10 Projects/Job Search 2026/Job Search 2026 Hub|Job Search 2026 Hub]]",
        "professional": True,
        "life": False,
    },
    "strategic-judgment": {
        "topic_tag": "resource/topic/history",
        "concept_link": "[[10 Notes/History doesn't repeat itself, but it sure ryhmes|History doesn't repeat itself, but it sure ryhmes]]",
        "context_link": "[[00 Inbox/Top 10 questions]]",
        "professional": True,
        "life": True,
    },
    "philosophy-meaning": {
        "topic_tag": "resource/topic/philosophy",
        "concept_link": "[[00 Inbox/Top 10 questions]]",
        "context_link": "[[10 Notes/Fernando|Fernando's Hub]]",
        "professional": False,
        "life": True,
    },
    "health-resilience": {
        "topic_tag": "resource/topic/health",
        "concept_link": "[[00 Inbox/Goal - Achieve Elite Physical Fitness]]",
        "context_link": "[[10 Notes/One-page Weekly Planner]]",
        "professional": False,
        "life": True,
    },
    "pkm-operations": {
        "topic_tag": "resource/topic/pkm",
        "concept_link": "[[00 Inbox/pkm-systems|PKM Systems]]",
        "context_link": "[[Periodic/Periodic Planning and Tasks Hub|Periodic Planning and Tasks Hub]]",
        "professional": True,
        "life": True,
    },
    "unassigned": {
        "topic_tag": "resource/topic/ai",
        "concept_link": "[[00 Inbox/NotebookLM map|NotebookLM map]]",
        "context_link": "[[10 Notes/Fernando|Fernando's Hub]]",
        "professional": False,
        "life": False,
    },
}

LANE_KEYWORDS = {
    "pkm-operations": [
        "pkm",
        "knowledge management",
        "second brain",
        "note taking",
        "notebooklm",
        "vault retrieval",
    ],
    "ai-systems": [
        "ai",
        "agent",
        "llm",
        "large language model",
        "analytics engineering",
        "data engineering",
        "mlops",
        "python",
        "git",
        "causal ai",
        "technical assessment",
        "adk",
        "statistical learning",
        "logical reasoning",
        "linux kernel",
        "analytics",
        "model",
        "neuro-symbolic",
        "category theory",
    ],
    "strategic-judgment": [
        "history",
        "1848",
        "china",
        "cycle",
        "commons",
        "decision",
        "strategic",
        "leadership",
        "global order",
        "market",
        "investing",
        "economic",
        "rome",
        "republic",
        "weimar",
        "gilded age",
        "systems",
        "commoncog",
        "agency",
        "governance",
        "behavioral",
        "fertility",
    ],
    "philosophy-meaning": [
        "dostoevsky",
        "marcus aurelius",
        "zhuangzi",
        "siddhartha",
        "frankl",
        "logotherapy",
        "stoic",
        "stoicism",
        "buddhism",
        "consciousness",
        "self",
        "meaning",
        "existential",
        "faith",
        "memento mori",
        "virtue",
        "moral",
        "christian",
        "philosophy",
        "justice",
        "freedom",
    ],
    "health-resilience": [
        "sleep",
        "circadian",
        "metabolism",
        "adipose",
        "clinical",
        "anatomy",
        "testosterone",
        "mitochond",
        "protein",
        "muscle",
        "hypertrophy",
        "resilience",
        "stress",
        "fitness",
        "healthspan",
        "microbiota",
        "peptide",
        "thermoregulation",
        "rest",
        "recovery",
        "rucking",
        "biogenesis",
        "allergy",
        "disease",
        "diet",
        "sleeping brain",
        "cooking",
        "calorie",
        "respiratory",
    ],
}


def clean_title(title: str) -> str:
    cleaned = title.strip()
    while cleaned.startswith("#"):
        cleaned = cleaned[1:].strip()
    return cleaned


def normalize_lookup_key(value: str) -> str:
    value = clean_title(value).lower()
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if ch.isalnum())


def parse_inventory(path: Path) -> List[Dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    items = []
    for title, url in INVENTORY_PATTERN.findall(text):
        items.append({"title": clean_title(title), "url": url})
    return items


def parse_summaries(path: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    text = path.read_text(encoding="utf-8")
    by_url: Dict[str, Dict[str, str]] = {}
    by_title: Dict[str, Dict[str, str]] = {}
    for title, url, body in SUMMARY_PATTERN.findall(text):
        cleaned_title = clean_title(title)
        cleaned_body = body.strip()
        cleaned_body = re.sub(r"\n{3,}", "\n\n", cleaned_body)
        record = {
            "title": cleaned_title,
            "url": url.strip(),
            "summary": cleaned_body,
        }
        by_url[record["url"]] = record
        by_title[normalize_lookup_key(cleaned_title)] = record
    return by_url, by_title


def classify_lane(title: str, summary: str) -> str:
    title_lower = title.lower()
    summary_lower = summary.lower()
    scores = {lane: 0 for lane in LANE_KEYWORDS}

    for lane, keywords in LANE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in title_lower:
                scores[lane] += 3
            if summary_lower and keyword in summary_lower:
                scores[lane] += 1

    if "reads 2026 series" in title_lower or "reads 2026 series" in summary_lower:
        scores["philosophy-meaning"] += 2
        scores["strategic-judgment"] += 1
    if "technical assessment" in title_lower:
        scores["ai-systems"] += 4
    if "notebooklm" in title_lower:
        scores["pkm-operations"] += 4

    lane = max(scores, key=lambda item: scores[item])
    return lane if scores[lane] > 0 else "unassigned"


def connection_strength(summary: str) -> float:
    length = len(summary.strip())
    if length >= 500:
        return 0.68
    if length >= 200:
        return 0.62
    if length > 0:
        return 0.54
    return 0.42


def notebook_id(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def sanitize_filename(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", clean_title(title)).encode("ascii", "ignore").decode("ascii")
    ascii_title = re.sub(r"[^A-Za-z0-9]+", " ", ascii_title)
    ascii_title = re.sub(r"\s+", " ", ascii_title).strip()
    return ascii_title or "NotebookLM"


def note_path_for_title(title: str, output_dir: Path, url: str, used_paths: set[Path]) -> Path:
    stem = sanitize_filename(title)
    suffix = notebook_id(url)[:8]
    candidate = output_dir / f"{stem} {suffix}.md"
    used_paths.add(candidate)
    return candidate


def build_frontmatter(
    title: str,
    url: str,
    lane: str,
    summary: str,
    source_note: str,
    summary_source_note: str,
) -> Dict[str, Any]:
    lane_config = LANE_CONFIG[lane]
    potential_links = [
        "[[00 Inbox/NotebookLM map|NotebookLM map]]",
        source_note,
        "[[10 Notes/Fernando|Fernando's Hub]]",
        lane_config["concept_link"],
        lane_config["context_link"],
    ]
    if summary:
        potential_links.append(summary_source_note)

    deduped_links = list(dict.fromkeys(potential_links))

    frontmatter: Dict[str, Any] = {
        "aliases": [title],
        "tags": COMMON_TAGS + [lane_config["topic_tag"]],
        "type": "resource",
        "para_type": "resource",
        "notebooklm_note_kind": "notebook",
        "notebooklm_title": title,
        "notebooklm_url": url,
        "notebooklm_lane": lane,
        "notebooklm_professional_track": lane_config["professional"],
        "notebooklm_life_track": lane_config["life"],
        "notebooklm_source_note": source_note,
        "connection_strength": connection_strength(summary),
        "potential_links": deduped_links,
    }
    return frontmatter


def build_body(title: str, url: str, lane: str, summary: str, source_note: str, summary_source_note: str) -> str:
    lane_config = LANE_CONFIG[lane]
    summary_text = summary or (
        "Summary pending. This record was materialized from the raw inventory in "
        f"{source_note} and can be enriched from {summary_source_note} when a denser synthesis is available."
    )
    lines = [
        f"# {title}",
        "",
        "This NotebookLM record routes through [[00 Inbox/NotebookLM map|NotebookLM map]] toward "
        f"{lane_config['concept_link']} and {lane_config['context_link']}.",
        "",
        "## Summary",
        "",
        summary_text,
        "",
        "## NotebookLM",
        "",
        f"- NotebookLM URL: {url}",
        f"- Source note: {source_note}",
        f"- Synthesis note: {summary_source_note}",
        f"- Lane: `{lane}`",
        f"- Professional track: {'yes' if lane_config['professional'] else 'no'}",
        f"- Life track: {'yes' if lane_config['life'] else 'no'}",
        "",
        "#status/processing",
        "",
    ]
    return "\n".join(lines)


def render_note(frontmatter: Dict[str, Any], body: str) -> str:
    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{yaml_text}\n---\n\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize per-notebook Obsidian notes from NotebookLM inventory notes.",
    )
    parser.add_argument(
        "--inventory",
        default="00 Inbox/Notebook LM notebooks.md",
        help="Path to the raw NotebookLM inventory note.",
    )
    parser.add_argument(
        "--summaries",
        default="00 Inbox/My NotebookLM notebooks.md",
        help="Path to the longer-form NotebookLM synthesis note.",
    )
    parser.add_argument(
        "--output-dir",
        default="20 Resources/NotebookLM",
        help="Folder where per-notebook notes will be written.",
    )
    parser.add_argument(
        "--source-note",
        default="[[00 Inbox/Notebook LM notebooks|Notebook LM notebooks]]",
        help="Wikilink recorded in notebook frontmatter as the source note.",
    )
    parser.add_argument(
        "--summary-source-note",
        default="[[00 Inbox/My NotebookLM notebooks|My NotebookLM notebooks]]",
        help="Wikilink to the synthesis note for body references.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and classify notebooks without writing files.",
    )
    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    summary_path = Path(args.summaries)
    output_dir = Path(args.output_dir)

    inventory_items = parse_inventory(inventory_path)
    summary_by_url, summary_by_title = parse_summaries(summary_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    used_paths: set[Path] = set()
    written_paths: List[str] = []
    lane_counts = {lane: 0 for lane in LANE_CONFIG}

    for item in inventory_items:
        title = item["title"]
        url = item["url"]
        summary_record = summary_by_url.get(url) or summary_by_title.get(normalize_lookup_key(title))
        summary = summary_record["summary"] if summary_record else ""
        lane = classify_lane(title, summary)
        lane_counts[lane] += 1

        note_path = note_path_for_title(title, output_dir, url, used_paths)
        frontmatter = build_frontmatter(
            title=title,
            url=url,
            lane=lane,
            summary=summary,
            source_note=args.source_note,
            summary_source_note=args.summary_source_note,
        )
        body = build_body(
            title=title,
            url=url,
            lane=lane,
            summary=summary,
            source_note=args.source_note,
            summary_source_note=args.summary_source_note,
        )

        if not args.dry_run:
            note_path.write_text(render_note(frontmatter, body), encoding="utf-8")

        written_paths.append(str(note_path))

    payload = {
        "ok": True,
        "inventory_count": len(inventory_items),
        "written_count": len(written_paths),
        "output_dir": str(output_dir),
        "lane_counts": lane_counts,
        "paths": written_paths,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
