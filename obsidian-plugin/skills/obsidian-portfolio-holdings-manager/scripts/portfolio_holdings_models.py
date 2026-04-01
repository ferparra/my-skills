#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

FRONTMATTER_DELIM = "\n---\n"

BROKERAGE_ACTIVITY_GLOB = "20 Resources/Investments/Brokerage Activity/**/*.md"
CURRENT_HOLDINGS_DIR = Path("20 Resources/Investments/Portfolio Holdings")
CURRENT_HOLDINGS_GLOB = "20 Resources/Investments/Portfolio Holdings/*.md"
CURRENT_HOLDINGS_BASE_PATH = CURRENT_HOLDINGS_DIR / "Portfolio Holdings.base"
HOLDINGS_HISTORY_DIR = Path("20 Resources/Investments/Portfolio Holdings History")
HOLDINGS_HISTORY_GLOB = "20 Resources/Investments/Portfolio Holdings History/*.md"
HOLDINGS_HISTORY_BASE_PATH = HOLDINGS_HISTORY_DIR / "Portfolio Holdings History.base"

CURRENT_FRONTMATTER_ORDER = [
    "portfolio_holding_id",
    "portfolio_holding_kind",
    "instrument_symbol",
    "instrument_market",
    "instrument_kind",
    "brokerage_providers",
    "first_activity_date",
    "last_activity_date",
    "last_trade_date",
    "activity_count",
    "trade_buy_count",
    "trade_sell_count",
    "distribution_count",
    "distribution_reinvestment_count",
    "current_quantity",
    "currency",
    "cumulative_net_cash_flow",
    "cumulative_fees",
    "cumulative_taxes",
    "review_status",
    "source_activity_signatures",
    "source_activity_count",
    "tags",
]

HISTORY_FRONTMATTER_ORDER = [
    "portfolio_holding_id",
    "portfolio_holding_kind",
    "instrument_symbol",
    "instrument_market",
    "brokerage_providers",
    "first_snapshot_date",
    "last_snapshot_date",
    "snapshot_count",
    "current_quantity",
    "max_quantity",
    "min_quantity",
    "review_status",
    "source_activity_signatures",
    "source_activity_count",
    "tags",
]


class PortfolioHoldingKind(StrEnum):
    CURRENT_POSITION = "current_position"
    HOLDING_HISTORY = "holding_history"


class ReviewStatus(StrEnum):
    OK = "ok"
    NEEDS_REVIEW = "needs_review"


@dataclass
class NoteParts:
    path: Path
    frontmatter: dict[str, Any]
    body: str
    text: str


class PortfolioHoldingFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    portfolio_holding_id: str
    portfolio_holding_kind: PortfolioHoldingKind
    instrument_symbol: str
    instrument_market: str | None = None
    instrument_kind: str | None = None
    brokerage_providers: list[str] = Field(default_factory=list)
    first_activity_date: str
    last_activity_date: str
    last_trade_date: str | None = None
    activity_count: int = Field(ge=1)
    trade_buy_count: int = Field(ge=0)
    trade_sell_count: int = Field(ge=0)
    distribution_count: int = Field(ge=0)
    distribution_reinvestment_count: int = Field(ge=0)
    current_quantity: float | None = None
    currency: str = "AUD"
    cumulative_net_cash_flow: float | None = None
    cumulative_fees: float | None = None
    cumulative_taxes: float | None = None
    review_status: ReviewStatus = ReviewStatus.OK
    source_activity_signatures: list[str] = Field(default_factory=list)
    source_activity_count: int = Field(ge=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("instrument_symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: Any) -> str:
        return str(value).strip().upper()

    @field_validator("instrument_market", "instrument_kind", "currency", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("brokerage_providers", "source_activity_signatures", "tags", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: Any) -> list[str]:
        return dedupe_preserve(listify_strings(value))


class PortfolioHoldingHistoryFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    portfolio_holding_id: str
    portfolio_holding_kind: PortfolioHoldingKind
    instrument_symbol: str
    instrument_market: str | None = None
    brokerage_providers: list[str] = Field(default_factory=list)
    first_snapshot_date: str
    last_snapshot_date: str
    snapshot_count: int = Field(ge=1)
    current_quantity: float | None = None
    max_quantity: float | None = None
    min_quantity: float | None = None
    review_status: ReviewStatus = ReviewStatus.OK
    source_activity_signatures: list[str] = Field(default_factory=list)
    source_activity_count: int = Field(ge=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("instrument_symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: Any) -> str:
        return str(value).strip().upper()

    @field_validator("instrument_market", mode="before")
    @classmethod
    def normalize_optional_market(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("brokerage_providers", "source_activity_signatures", "tags", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: Any) -> list[str]:
        return dedupe_preserve(listify_strings(value))


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def stable_hash(value: Any, *, length: int = 12) -> str:
    payload = json.dumps(normalize_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:length]


def make_holding_id(symbol: str, kind: PortfolioHoldingKind | str) -> str:
    return f"ph-{stable_hash({'symbol': str(symbol).upper(), 'kind': str(kind)})}"


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find(FRONTMATTER_DELIM, 4)
    if end == -1:
        return {}, text
    payload = yaml.safe_load(text[4:end]) or {}
    if not isinstance(payload, dict):
        raise ValueError("frontmatter must deserialize to a mapping")
    body = text[end + len(FRONTMATTER_DELIM):]
    return normalize_jsonable(payload), body


def load_markdown_note(path: Path) -> NoteParts:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    return NoteParts(path=path, frontmatter=frontmatter, body=body, text=text)


def dedupe_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def listify_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if text in {"", "-", "—", "N/A"}:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def canonical_number(value: float | None, *, digits: int = 8) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def provider_label(provider: str) -> str:
    labels = {
        "betashares": "Betashares",
        "stake_au": "Stake AU",
        "stake_us": "Stake US",
        "generic_csv": "Generic CSV",
    }
    text = str(provider).strip()
    return labels.get(text, text.replace("_", " ").title())


def normalize_provider_labels(providers: Iterable[str]) -> list[str]:
    return [provider_label(provider) for provider in dedupe_preserve(providers)]


def required_tags(providers: Iterable[str], kind: PortfolioHoldingKind | str) -> list[str]:
    provider_tags = [f"brokerage-provider/{provider}" for provider in dedupe_preserve(providers)]
    return dedupe_preserve(
        [
            "type/portfolio-holding",
            f"portfolio-holding-kind/{PortfolioHoldingKind(str(kind)).value}",
            *provider_tags,
        ]
    )


def current_relative_path(symbol: str) -> Path:
    clean = str(symbol).strip().upper()
    return CURRENT_HOLDINGS_DIR / f"{clean}.md"


def history_relative_path(symbol: str) -> Path:
    clean = str(symbol).strip().upper()
    return HOLDINGS_HISTORY_DIR / f"{clean} Holdings History.md"


def format_money(amount: float | None, currency: str) -> str | None:
    if amount is None:
        return None
    return f"{currency} {amount:,.2f}"


def format_number(value: float | None, *, digits: int = 8) -> str | None:
    if value is None:
        return None
    rendered = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return rendered or "0"


def order_frontmatter(frontmatter: dict[str, Any], order: list[str]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in order:
        if key in frontmatter and frontmatter[key] not in (None, [], {}):
            ordered[key] = frontmatter[key]
    for key in sorted(frontmatter):
        if key in ordered or frontmatter[key] in (None, [], {}):
            continue
        ordered[key] = frontmatter[key]
    return ordered


def render_markdown(frontmatter: dict[str, Any], body: str, *, order: list[str]) -> str:
    frontmatter_text = yaml.safe_dump(
        order_frontmatter(frontmatter, order),
        sort_keys=False,
        allow_unicode=False,
        width=1000,
    ).strip()
    return f"---\n{frontmatter_text}\n---\n\n{body.lstrip()}"
