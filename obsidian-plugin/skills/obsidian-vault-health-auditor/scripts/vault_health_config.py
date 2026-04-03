"""Configuration constants for vault health auditor."""
from __future__ import annotations

import re
from typing import Final

# Regex patterns
WIKILINK_RE: Final[re.Pattern[str]] = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ZETTEL_ID_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{14})$")

# Delimiters
FRONTMATTER_DELIM: Final[str] = "\n---\n"

# Kind field to expected directory mapping
KIND_DIRECTORY_MAP: Final[dict[str, str]] = {
    "person_kind": "People/",
    "exercise_kind": "20 Resources/Exercises/",
    "brokerage_activity_kind": "20 Resources/Investments/Brokerage Activity/",
    "portfolio_holding_kind": "20 Resources/Investments/Portfolio Holdings/",
    "cv_entry_kind": "20 Resources/Career/",
    "zettel_kind": "30 Zettelkasten/",
    "key_date_kind": "20 Resources/Key Dates/",
    "planetary_task_kind": "20 Resources/Planetary Tasks/",
}

# Known kind taxonomies
KNOWN_KINDS: Final[dict[str, set[str]]] = {
    "person_kind": {
        "manager", "collaborator", "stakeholder", "customer_contact",
        "mentor", "author", "acquaintance",
    },
    "exercise_kind": {
        "hypertrophy", "strength", "mobility_drill", "warmup_flow", "exercise_brief",
    },
    "brokerage_activity_kind": {
        "trade_buy", "trade_sell", "distribution", "distribution_reinvestment",
        "cash_deposit", "cash_withdrawal", "fee", "tax", "fx", "adjustment", "cash_interest",
    },
    "cv_entry_kind": {
        "role", "education", "certification", "award", "community",
    },
    "zettel_kind": {
        "atomic", "literature", "project", "archive",
    },
    "key_date_kind": {
        "birthday", "anniversary", "deadline", "milestone", "holiday",
    },
    "planetary_task_kind": {
        "habit", "chore", "deep_work", "review", "meeting",
    },
    "portfolio_holding_kind": {
        "current_position", "closed_position", "watchlist",
    },
}

# Health thresholds
STALE_THRESHOLD_DAYS: Final[int] = 90
ZOMBIE_THRESHOLD_DAYS: Final[int] = 180
MIN_CONNECTION_STRENGTH: Final[float] = 2.0
