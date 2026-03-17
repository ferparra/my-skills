#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

FRONTMATTER_DELIM = "\n---\n"
BROKERAGE_ACTIVITY_ID_RE = re.compile(r"^ba-[a-f0-9]{12}$")
BROKERAGE_ASSET_ID_RE = re.compile(r"^bs-[a-f0-9]{12}$")
ACTIVITY_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

BROKERAGE_NOTES_DIR = Path("20 Resources/Investments/Brokerage Activity")
BROKERAGE_NOTE_GLOB = "20 Resources/Investments/Brokerage Activity/**/*.md"
BROKERAGE_BASE_PATH = BROKERAGE_NOTES_DIR / "Brokerage Activity.base"
BROKERAGE_ASSETS_DIR = Path("20 Resources/Investments/Brokerage Assets")
BROKERAGE_ASSET_GLOB = "20 Resources/Investments/Brokerage Assets/*.md"
BROKERAGE_ASSET_BASE_PATH = BROKERAGE_ASSETS_DIR / "Brokerage Assets.base"

BROKERAGE_FRONTMATTER_ORDER = [
    "brokerage_activity_id",
    "brokerage_activity_kind",
    "brokerage_provider",
    "raw_activity_type",
    "activity_date",
    "activity_year",
    "activity_month",
    "activity_status",
    "instrument_symbol",
    "instrument_market",
    "instrument_kind",
    "asset_note",
    "currency",
    "gross_amount",
    "net_amount",
    "unit_price",
    "quantity",
    "fee_amount",
    "tax_amount",
    "cash_direction",
    "review_status",
    "source_signature",
    "source_files",
    "source_file_count",
    "source_row_hashes",
    "source_row_count",
    "merge_count",
    "tags",
]

BROKERAGE_ASSET_FRONTMATTER_ORDER = [
    "brokerage_asset_id",
    "brokerage_asset_kind",
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
    "currency",
    "last_unit_price",
    "estimated_open_quantity",
    "cumulative_net_cash_flow",
    "cumulative_fees",
    "cumulative_taxes",
    "review_status",
    "source_activity_signatures",
    "source_activity_count",
    "tags",
]


class BrokerageProvider(StrEnum):
    BETASHARES = "betashares"
    STAKE_AU = "stake_au"
    STAKE_US = "stake_us"
    GENERIC_CSV = "generic_csv"


class BrokerageActivityKind(StrEnum):
    TRADE_BUY = "trade_buy"
    TRADE_SELL = "trade_sell"
    DISTRIBUTION = "distribution"
    DISTRIBUTION_REINVESTMENT = "distribution_reinvestment"
    CASH_DEPOSIT = "cash_deposit"
    CASH_WITHDRAWAL = "cash_withdrawal"
    FEE = "fee"
    TAX = "tax"
    CASH_INTEREST = "cash_interest"
    FX = "fx"
    CORPORATE_ACTION = "corporate_action"
    ADJUSTMENT = "adjustment"


class BrokerageAssetKind(StrEnum):
    LISTED_SECURITY = "listed_security"
    FUND = "fund"
    CRYPTO = "crypto"
    FX_PAIR = "fx_pair"
    OTHER = "other"
    UNKNOWN = "unknown"


class BrokerageActivityStatus(StrEnum):
    COMPLETED = "completed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CashDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    NEUTRAL = "neutral"


class InstrumentKind(StrEnum):
    CASH = "cash"
    LISTED_SECURITY = "listed_security"
    FUND = "fund"
    CRYPTO = "crypto"
    FX = "fx"
    OTHER = "other"
    UNKNOWN = "unknown"


class ReviewStatus(StrEnum):
    OK = "ok"
    NEEDS_REVIEW = "needs_review"


@dataclass
class NoteParts:
    path: Path
    frontmatter: dict[str, Any]
    body: str
    text: str


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(str(value).strip())


class BrokerageActivityFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    brokerage_activity_id: str
    brokerage_activity_kind: BrokerageActivityKind
    brokerage_provider: BrokerageProvider
    raw_activity_type: str | None = None

    activity_date: str
    activity_year: int = Field(ge=1900, le=2100)
    activity_month: str
    activity_status: BrokerageActivityStatus = BrokerageActivityStatus.COMPLETED

    instrument_symbol: str | None = None
    instrument_market: str | None = None
    instrument_kind: InstrumentKind = InstrumentKind.UNKNOWN
    asset_note: str | None = None
    currency: str = "AUD"

    gross_amount: float | None = None
    net_amount: float | None = None
    unit_price: float | None = None
    quantity: float | None = None
    fee_amount: float | None = None
    tax_amount: float | None = None

    cash_direction: CashDirection = CashDirection.NEUTRAL
    review_status: ReviewStatus = ReviewStatus.OK

    source_signature: str
    source_files: list[str] = Field(default_factory=list)
    source_file_count: int = Field(default=1, ge=1)
    source_row_hashes: list[str] = Field(default_factory=list)
    source_row_count: int = Field(default=1, ge=1)
    merge_count: int = Field(default=1, ge=1)

    tags: list[str] = Field(default_factory=list)

    @field_validator("brokerage_activity_id")
    @classmethod
    def validate_activity_id(cls, value: str) -> str:
        text = str(value).strip()
        if not BROKERAGE_ACTIVITY_ID_RE.match(text):
            raise ValueError(
                "brokerage_activity_id must match 'ba-<12 lowercase hex chars>'"
            )
        return text

    @field_validator(
        "raw_activity_type",
        "instrument_symbol",
        "instrument_market",
        "asset_note",
        "source_signature",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        text = str(value or "AUD").strip().upper()
        return text or "AUD"

    @field_validator(
        "gross_amount",
        "net_amount",
        "unit_price",
        "quantity",
        "fee_amount",
        "tax_amount",
        mode="before",
    )
    @classmethod
    def coerce_optional_float(cls, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            raise ValueError(f"expected number, got boolean {value!r}")
        return float(value)

    @field_validator("source_files", "source_row_hashes", "tags", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [value]
        else:
            items = list(value)
        return dedupe_preserve(str(item).strip() for item in items if str(item).strip())

    @model_validator(mode="after")
    def validate_dates(self) -> "BrokerageActivityFrontmatter":
        parsed = parse_iso_date(self.activity_date)
        if parsed.year != self.activity_year:
            raise ValueError(
                f"activity_year {self.activity_year} does not match activity_date {self.activity_date}"
            )
        if not ACTIVITY_MONTH_RE.match(self.activity_month):
            raise ValueError("activity_month must match YYYY-MM")
        if self.activity_month != self.activity_date[:7]:
            raise ValueError(
                f"activity_month {self.activity_month} does not match activity_date {self.activity_date}"
            )
        return self

    @model_validator(mode="after")
    def validate_source_lists(self) -> "BrokerageActivityFrontmatter":
        if not self.source_signature:
            raise ValueError("source_signature is required")
        if not self.source_files:
            raise ValueError("source_files must contain at least one filename")
        if not self.source_row_hashes:
            raise ValueError("source_row_hashes must contain at least one row hash")
        if self.source_file_count != len(self.source_files):
            raise ValueError("source_file_count must match len(source_files)")
        if self.source_row_count != len(self.source_row_hashes):
            raise ValueError("source_row_count must match len(source_row_hashes)")
        minimum_merge = max(self.source_file_count, self.source_row_count, 1)
        if self.merge_count < minimum_merge:
            raise ValueError(
                "merge_count must be >= max(source_file_count, source_row_count, 1)"
            )
        return self

    @model_validator(mode="after")
    def validate_symbol_requirements(self) -> "BrokerageActivityFrontmatter":
        symbol_required = {
            BrokerageActivityKind.TRADE_BUY,
            BrokerageActivityKind.TRADE_SELL,
            BrokerageActivityKind.DISTRIBUTION,
            BrokerageActivityKind.DISTRIBUTION_REINVESTMENT,
            BrokerageActivityKind.CORPORATE_ACTION,
        }
        if self.brokerage_activity_kind in symbol_required and not self.instrument_symbol:
            raise ValueError(
                f"{self.brokerage_activity_kind.value} requires instrument_symbol"
            )
        return self

    @model_validator(mode="after")
    def validate_required_tags(self) -> "BrokerageActivityFrontmatter":
        missing = set(required_tags_for(self.brokerage_provider, self.brokerage_activity_kind)) - set(self.tags)
        if missing:
            raise ValueError(f"tags must include {sorted(missing)}")
        return self


class BrokerageAssetFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    brokerage_asset_id: str
    brokerage_asset_kind: BrokerageAssetKind
    instrument_symbol: str
    instrument_market: str | None = None
    instrument_kind: InstrumentKind = InstrumentKind.UNKNOWN
    brokerage_providers: list[BrokerageProvider] = Field(default_factory=list)

    first_activity_date: str
    last_activity_date: str
    last_trade_date: str | None = None

    activity_count: int = Field(ge=1)
    trade_buy_count: int = Field(default=0, ge=0)
    trade_sell_count: int = Field(default=0, ge=0)
    distribution_count: int = Field(default=0, ge=0)
    distribution_reinvestment_count: int = Field(default=0, ge=0)

    currency: str = "AUD"
    last_unit_price: float | None = None
    estimated_open_quantity: float | None = None
    cumulative_net_cash_flow: float | None = None
    cumulative_fees: float | None = None
    cumulative_taxes: float | None = None
    review_status: ReviewStatus = ReviewStatus.OK

    source_activity_signatures: list[str] = Field(default_factory=list)
    source_activity_count: int = Field(ge=1)

    tags: list[str] = Field(default_factory=list)

    @field_validator("brokerage_asset_id")
    @classmethod
    def validate_asset_id(cls, value: str) -> str:
        text = str(value).strip()
        if not BROKERAGE_ASSET_ID_RE.match(text):
            raise ValueError(
                "brokerage_asset_id must match 'bs-<12 lowercase hex chars>'"
            )
        return text

    @field_validator("instrument_symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: Any) -> str:
        text = str(value or "").strip().upper()
        if not text:
            raise ValueError("instrument_symbol is required")
        return text

    @field_validator("instrument_market", mode="before")
    @classmethod
    def normalize_optional_market(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_asset_currency(cls, value: Any) -> str:
        text = str(value or "AUD").strip().upper()
        return text or "AUD"

    @field_validator(
        "last_unit_price",
        "estimated_open_quantity",
        "cumulative_net_cash_flow",
        "cumulative_fees",
        "cumulative_taxes",
        mode="before",
    )
    @classmethod
    def coerce_asset_numbers(cls, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            raise ValueError(f"expected number, got boolean {value!r}")
        return float(value)

    @field_validator("source_activity_signatures", "tags", mode="before")
    @classmethod
    def coerce_asset_string_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [value]
        else:
            items = list(value)
        return dedupe_preserve(str(item).strip() for item in items if str(item).strip())

    @field_validator("brokerage_providers", mode="before")
    @classmethod
    def coerce_providers(cls, value: Any) -> list[BrokerageProvider]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [value]
        else:
            items = list(value)
        providers = [BrokerageProvider(str(item).strip()) for item in items if str(item).strip()]
        return list(dict.fromkeys(providers))

    @model_validator(mode="after")
    def validate_asset_dates(self) -> "BrokerageAssetFrontmatter":
        first = parse_iso_date(self.first_activity_date)
        last = parse_iso_date(self.last_activity_date)
        if first > last:
            raise ValueError("first_activity_date must be <= last_activity_date")
        if self.last_trade_date:
            trade = parse_iso_date(self.last_trade_date)
            if trade < first or trade > last:
                raise ValueError("last_trade_date must sit within the activity range")
        return self

    @model_validator(mode="after")
    def validate_asset_counts(self) -> "BrokerageAssetFrontmatter":
        if not self.source_activity_signatures:
            raise ValueError("source_activity_signatures must contain at least one signature")
        if self.source_activity_count != len(self.source_activity_signatures):
            raise ValueError("source_activity_count must match len(source_activity_signatures)")
        minimum_activity_count = (
            self.trade_buy_count
            + self.trade_sell_count
            + self.distribution_count
            + self.distribution_reinvestment_count
        )
        if self.activity_count < minimum_activity_count:
            raise ValueError("activity_count must cover all counted activity kinds")
        return self

    @model_validator(mode="after")
    def validate_asset_tags(self) -> "BrokerageAssetFrontmatter":
        missing = set(
            required_asset_tags_for(self.brokerage_providers, self.brokerage_asset_kind)
        ) - set(self.tags)
        if missing:
            raise ValueError(f"tags must include {sorted(missing)}")
        return self


def normalize_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return normalize_jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): normalize_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(normalize_jsonable(payload), indent=2, sort_keys=True)


def stable_hash(payload: Any, *, prefix: str | None = None, length: int = 12) -> str:
    raw = json.dumps(
        normalize_jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}" if prefix else digest


def make_activity_id(source_signature: str) -> str:
    return stable_hash({"source_signature": source_signature}, prefix="ba", length=12)


def make_asset_id(symbol: str) -> str:
    return stable_hash({"instrument_symbol": str(symbol).upper()}, prefix="bs", length=12)


def normalize_text_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_symbol(value: Any) -> tuple[str | None, str | None]:
    text = str(value or "").strip().upper()
    if text in {"", "-", "—", "N/A"}:
        return None, None
    name_joined = re.match(r"^(?P<symbol>[A-Z0-9.\-]+)\s[-–—]\s.+$", text)
    if name_joined:
        text = name_joined.group("symbol")
    market_qualified = re.match(r"^(?P<symbol>[A-Z0-9.\-]+)[:.](?P<market>[A-Z]{2,5})$", text)
    if market_qualified:
        return (
            market_qualified.group("symbol").strip() or None,
            market_qualified.group("market").strip() or None,
        )
    return text, None


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


def required_tags_for(
    provider: BrokerageProvider | str,
    activity_kind: BrokerageActivityKind | str,
) -> list[str]:
    provider_value = BrokerageProvider(str(provider)).value
    kind_value = BrokerageActivityKind(str(activity_kind)).value
    return [
        "type/brokerage-activity",
        f"brokerage-provider/{provider_value}",
        f"brokerage-activity-kind/{kind_value}",
    ]


def required_asset_tags_for(
    providers: Iterable[BrokerageProvider | str],
    asset_kind: BrokerageAssetKind | str,
) -> list[str]:
    provider_tags = [
        f"brokerage-provider/{BrokerageProvider(str(provider)).value}"
        for provider in providers
    ]
    kind_value = BrokerageAssetKind(str(asset_kind)).value
    return dedupe_preserve(
        [
            "type/brokerage-asset",
            f"brokerage-asset-kind/{kind_value}",
            *provider_tags,
        ]
    )


def normalize_tags(
    tags: Iterable[str],
    provider: BrokerageProvider | str,
    activity_kind: BrokerageActivityKind | str,
) -> list[str]:
    return dedupe_preserve([*tags, *required_tags_for(provider, activity_kind)])


def normalize_asset_tags(
    tags: Iterable[str],
    providers: Iterable[BrokerageProvider | str],
    asset_kind: BrokerageAssetKind | str,
) -> list[str]:
    return dedupe_preserve([*tags, *required_asset_tags_for(providers, asset_kind)])


def provider_label(provider: BrokerageProvider | str) -> str:
    provider_value = BrokerageProvider(str(provider)).value
    labels = {
        BrokerageProvider.BETASHARES.value: "Betashares",
        BrokerageProvider.STAKE_AU.value: "Stake AU",
        BrokerageProvider.STAKE_US.value: "Stake US",
        BrokerageProvider.GENERIC_CSV.value: "Generic CSV",
    }
    return labels.get(provider_value, provider_value.replace("_", " ").title())


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find(FRONTMATTER_DELIM, 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len(FRONTMATTER_DELIM):]
    payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise ValueError("Frontmatter must deserialize to a mapping")
    return normalize_jsonable(payload), body


def load_markdown_note(path: Path) -> NoteParts:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    return NoteParts(path=path, frontmatter=frontmatter, body=body, text=text)


def order_frontmatter(frontmatter: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in BROKERAGE_FRONTMATTER_ORDER:
        if key in frontmatter and frontmatter[key] not in (None, [], {}):
            ordered[key] = frontmatter[key]
    for key in sorted(frontmatter):
        if key in ordered or frontmatter[key] in (None, [], {}):
            continue
        ordered[key] = frontmatter[key]
    return ordered


def order_asset_frontmatter(frontmatter: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in BROKERAGE_ASSET_FRONTMATTER_ORDER:
        if key in frontmatter and frontmatter[key] not in (None, [], {}):
            ordered[key] = frontmatter[key]
    for key in sorted(frontmatter):
        if key in ordered or frontmatter[key] in (None, [], {}):
            continue
        ordered[key] = frontmatter[key]
    return ordered


def render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    ordered = order_frontmatter(frontmatter)
    frontmatter_text = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=False,
        width=1000,
    ).strip()
    body_text = body.rstrip() + "\n"
    return f"---\n{frontmatter_text}\n---\n\n{body_text}"


def render_asset_markdown(frontmatter: dict[str, Any], body: str) -> str:
    ordered = order_asset_frontmatter(frontmatter)
    frontmatter_text = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=False,
        width=1000,
    ).strip()
    body_text = body.rstrip() + "\n"
    return f"---\n{frontmatter_text}\n---\n\n{body_text}"


def safe_note_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", " ", value).strip()
    return re.sub(r"\s+", " ", cleaned) or "unknown"


def note_title(frontmatter: dict[str, Any]) -> str:
    symbol = frontmatter.get("instrument_symbol") or "Cash"
    kind = str(frontmatter["brokerage_activity_kind"]).replace("_", " ")
    return f"{frontmatter['activity_date']} {symbol} {kind}"


def note_relative_path(frontmatter: dict[str, Any]) -> Path:
    symbol = safe_note_component(str(frontmatter.get("instrument_symbol") or "cash"))
    kind = safe_note_component(str(frontmatter["brokerage_activity_kind"]).replace("_", "-"))
    filename = (
        f"{frontmatter['activity_date']} {symbol} {kind} "
        f"{frontmatter['brokerage_activity_id']}.md"
    )
    return BROKERAGE_NOTES_DIR / str(frontmatter["activity_year"]) / filename


def asset_relative_path(frontmatter: dict[str, Any]) -> Path:
    symbol = safe_note_component(str(frontmatter["instrument_symbol"]).upper())
    return BROKERAGE_ASSETS_DIR / f"{symbol}.md"


def validate_frontmatter(frontmatter: dict[str, Any]) -> tuple[bool, list[str]]:
    try:
        BrokerageActivityFrontmatter(**frontmatter)
    except ValidationError as exc:
        return False, [error["msg"] for error in exc.errors()]
    return True, []


def validate_asset_frontmatter(frontmatter: dict[str, Any]) -> tuple[bool, list[str]]:
    try:
        BrokerageAssetFrontmatter(**frontmatter)
    except ValidationError as exc:
        return False, [error["msg"] for error in exc.errors()]
    return True, []
