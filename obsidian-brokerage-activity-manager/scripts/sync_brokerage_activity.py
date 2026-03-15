#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import polars as pl
import yaml
from pydantic import BaseModel, ConfigDict, Field

from brokerage_models import (
    BROKERAGE_FRONTMATTER_ORDER,
    BROKERAGE_NOTES_DIR,
    BROKERAGE_ASSET_FRONTMATTER_ORDER,
    BROKERAGE_ASSETS_DIR,
    BrokerageActivityKind,
    BrokerageActivityStatus,
    BrokerageAssetKind,
    BrokerageProvider,
    CashDirection,
    InstrumentKind,
    ReviewStatus,
    asset_relative_path,
    make_asset_id,
    dedupe_preserve,
    dump_json,
    load_markdown_note,
    make_activity_id,
    normalize_jsonable,
    normalize_asset_tags,
    normalize_tags,
    note_relative_path,
    note_title,
    order_frontmatter,
    order_asset_frontmatter,
    parse_symbol,
    provider_label,
    render_asset_markdown,
    render_markdown,
    stable_hash,
)

BETASHARES_EXPORT_COLUMNS = [
    "Effective Date",
    "Activity Type",
    "Gross",
    "Symbol",
    "Brokerage",
    "Price",
    "Quantity",
]

BETASHARES_COLUMN_MAP = {
    "activity_date": "Effective Date",
    "activity_type": "Activity Type",
    "amount": "Gross",
    "symbol": "Symbol",
    "brokerage": "Brokerage",
    "price": "Price",
    "quantity": "Quantity",
}

STAKE_ACTIVITY_XLSX_COLUMNS = [
    "Trade Date",
    "Settlement Date",
    "Symbol",
    "Name",
    "Side",
    "Trade Identifier",
    "Units",
    "Avg. Price",
    "Value",
    "Fees",
    "GST",
    "Total Value",
    "Currency",
]

STAKE_ACTIVITY_XLSX_SHEETS: dict[str, tuple[BrokerageProvider, str]] = {
    "Aus Equities": (BrokerageProvider.STAKE_AU, "ASX"),
    "Wall St Equities": (BrokerageProvider.STAKE_US, "US"),
}

CANONICAL_COLUMN_MAP = {
    "activity_date": "activity_date",
    "activity_type": "activity_type",
    "symbol": "symbol",
    "amount": "amount",
    "gross": "gross",
    "brokerage": "brokerage",
    "price": "price",
    "quantity": "quantity",
    "status": "status",
    "currency": "currency",
    "tax": "tax",
    "market": "market",
}

XLSX_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

COLUMN_ALIASES = {
    "activity_date": {
        "activity_date",
        "activity date",
        "date",
        "effective date",
        "completed at",
        "transaction date",
        "executed at",
        "created at",
    },
    "activity_type": {
        "activity_type",
        "activity type",
        "type",
        "transaction type",
        "description",
        "transaction description",
    },
    "symbol": {"symbol", "ticker", "stock", "instrument"},
    "amount": {
        "amount",
        "total",
        "gross",
        "gross amount",
        "net amount",
        "cash amount",
        "net proceeds",
    },
    "gross": {
        "gross",
        "gross amount",
        "value",
        "trade value",
    },
    "brokerage": {"brokerage", "commission", "fee", "fees"},
    "price": {"price", "unit price", "fill price"},
    "quantity": {"quantity", "units", "shares"},
    "status": {"status", "order status"},
    "currency": {"currency"},
    "tax": {"tax", "withholding tax"},
    "market": {"market", "exchange"},
}


class NormalizedActivityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: BrokerageProvider
    raw_activity_type: str
    activity_date: str
    activity_status: BrokerageActivityStatus

    instrument_symbol: str | None = None
    instrument_market: str | None = None
    instrument_kind: InstrumentKind = InstrumentKind.UNKNOWN
    currency: str = "AUD"

    gross_amount: float | None = None
    net_amount: float | None = None
    unit_price: float | None = None
    quantity: float | None = None
    fee_amount: float | None = None
    tax_amount: float | None = None

    brokerage_activity_kind: BrokerageActivityKind
    cash_direction: CashDirection
    review_status: ReviewStatus = ReviewStatus.OK

    source_signature: str
    source_file: str
    source_row_hash: str


class MergedActivityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: BrokerageProvider
    raw_activity_type: str
    activity_date: str
    activity_status: BrokerageActivityStatus

    instrument_symbol: str | None = None
    instrument_market: str | None = None
    instrument_kind: InstrumentKind = InstrumentKind.UNKNOWN
    currency: str = "AUD"

    gross_amount: float | None = None
    net_amount: float | None = None
    unit_price: float | None = None
    quantity: float | None = None
    fee_amount: float | None = None
    tax_amount: float | None = None

    brokerage_activity_kind: BrokerageActivityKind
    cash_direction: CashDirection
    review_status: ReviewStatus = ReviewStatus.OK

    source_signature: str
    source_files: list[str] = Field(default_factory=list)
    source_row_hashes: list[str] = Field(default_factory=list)
    source_file_count: int = 1
    source_row_count: int = 1
    merge_count: int = 1


@dataclass
class ExistingLedgerNote:
    path: Path
    frontmatter: dict[str, Any]
    text: str


@dataclass
class AssetAggregate:
    symbol: str
    records: list[MergedActivityRecord]


@dataclass
class InputBatch:
    provider: BrokerageProvider
    df: pl.DataFrame
    mapping: dict[str, str]
    source_file: str
    duplicate_rows_removed: int = 0


def normalize_column_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[_/]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_activity_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        raise ValueError("activity date is empty")

    candidates = [text.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate).date().isoformat()
        except ValueError:
            pass

    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y",
        "%d %B %Y",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unsupported activity date format: {text!r}")


def parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"expected number, got boolean {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in {"", "-", "—", "N/A"}:
        return None
    text = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    if not text:
        return None
    return float(text)


def parse_money(value: Any) -> tuple[float | None, bool]:
    if value in (None, ""):
        return None, False
    if isinstance(value, bool):
        raise ValueError(f"expected money value, got boolean {value!r}")
    if isinstance(value, (int, float)):
        amount = float(value)
        return amount, amount < 0

    raw = str(value).strip()
    if raw in {"", "-", "—", "N/A"}:
        return None, False

    had_explicit_sign = any(token in raw for token in ("+", "-", "(", ")"))
    negative = False
    text = raw
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        negative = True
        text = text[1:]

    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None, had_explicit_sign
    amount = float(text)
    return (-amount if negative else amount), had_explicit_sign


def parse_currency(value: Any, default_currency: str) -> str:
    text = str(value or "").strip().upper()
    if len(text) == 3 and text.isalpha():
        return text
    return default_currency.upper()


def infer_activity_kind(raw_activity_type: str) -> BrokerageActivityKind:
    key = normalize_column_name(raw_activity_type)
    if "distribution reinvest" in key or "dividend reinvest" in key or key == "drp":
        return BrokerageActivityKind.DISTRIBUTION_REINVESTMENT
    if "distribution" in key or "dividend" in key:
        return BrokerageActivityKind.DISTRIBUTION
    if "buy" in key:
        return BrokerageActivityKind.TRADE_BUY
    if "sell" in key:
        return BrokerageActivityKind.TRADE_SELL
    if "deposit" in key or "transfer in" in key or "cash in" in key:
        return BrokerageActivityKind.CASH_DEPOSIT
    if "withdraw" in key or "transfer out" in key or "cash out" in key:
        return BrokerageActivityKind.CASH_WITHDRAWAL
    if "tax" in key or "withholding" in key:
        return BrokerageActivityKind.TAX
    if "interest" in key:
        return BrokerageActivityKind.CASH_INTEREST
    if "foreign exchange" in key or key == "fx" or "currency conversion" in key:
        return BrokerageActivityKind.FX
    if "split" in key or "merge" in key or "consolidation" in key:
        return BrokerageActivityKind.CORPORATE_ACTION
    if "fee" in key or "commission" in key or "brokerage" in key:
        return BrokerageActivityKind.FEE
    return BrokerageActivityKind.ADJUSTMENT


def infer_activity_status(value: Any) -> BrokerageActivityStatus:
    text = normalize_column_name(value)
    if not text:
        return BrokerageActivityStatus.COMPLETED
    if "cancel" in text:
        return BrokerageActivityStatus.CANCELLED
    if "pend" in text:
        return BrokerageActivityStatus.PENDING
    if "fail" in text or "reject" in text:
        return BrokerageActivityStatus.FAILED
    if any(keyword in text for keyword in ("complete", "executed", "filled", "settled", "success")):
        return BrokerageActivityStatus.COMPLETED
    return BrokerageActivityStatus.UNKNOWN


def expected_sign_for_kind(kind: BrokerageActivityKind) -> int:
    if kind in {
        BrokerageActivityKind.TRADE_BUY,
        BrokerageActivityKind.DISTRIBUTION_REINVESTMENT,
        BrokerageActivityKind.CASH_WITHDRAWAL,
        BrokerageActivityKind.FEE,
        BrokerageActivityKind.TAX,
    }:
        return -1
    if kind in {
        BrokerageActivityKind.TRADE_SELL,
        BrokerageActivityKind.DISTRIBUTION,
        BrokerageActivityKind.CASH_DEPOSIT,
        BrokerageActivityKind.CASH_INTEREST,
    }:
        return 1
    return 0


def normalize_signed_amount(
    kind: BrokerageActivityKind,
    amount: float | None,
    *,
    had_explicit_sign: bool,
) -> float | None:
    if amount is None:
        return None
    if had_explicit_sign:
        return round(amount, 8)
    sign = expected_sign_for_kind(kind)
    if sign == 0:
        return round(amount, 8)
    return round(abs(amount) * sign, 8)


def infer_cash_direction(
    kind: BrokerageActivityKind,
    net_amount: float | None,
) -> CashDirection:
    sign = expected_sign_for_kind(kind)
    if sign > 0:
        return CashDirection.INFLOW
    if sign < 0:
        return CashDirection.OUTFLOW
    if net_amount is None or abs(net_amount) < 1e-9:
        return CashDirection.NEUTRAL
    return CashDirection.INFLOW if net_amount > 0 else CashDirection.OUTFLOW


def infer_instrument_kind(
    kind: BrokerageActivityKind,
    instrument_symbol: str | None,
) -> InstrumentKind:
    if kind == BrokerageActivityKind.FX:
        return InstrumentKind.FX
    if instrument_symbol:
        return InstrumentKind.LISTED_SECURITY
    if kind in {
        BrokerageActivityKind.CASH_DEPOSIT,
        BrokerageActivityKind.CASH_WITHDRAWAL,
        BrokerageActivityKind.FEE,
        BrokerageActivityKind.TAX,
        BrokerageActivityKind.CASH_INTEREST,
    }:
        return InstrumentKind.CASH
    return InstrumentKind.UNKNOWN


def infer_review_status(
    kind: BrokerageActivityKind,
    status: BrokerageActivityStatus,
    instrument_symbol: str | None,
) -> ReviewStatus:
    if status != BrokerageActivityStatus.COMPLETED:
        return ReviewStatus.NEEDS_REVIEW
    if kind == BrokerageActivityKind.ADJUSTMENT:
        return ReviewStatus.NEEDS_REVIEW
    if kind in {
        BrokerageActivityKind.TRADE_BUY,
        BrokerageActivityKind.TRADE_SELL,
        BrokerageActivityKind.DISTRIBUTION,
        BrokerageActivityKind.DISTRIBUTION_REINVESTMENT,
        BrokerageActivityKind.CORPORATE_ACTION,
    } and not instrument_symbol:
        return ReviewStatus.NEEDS_REVIEW
    return ReviewStatus.OK


def canonical_number(value: float | None, *, digits: int = 8) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def normalize_quantity_for_storage(
    kind: BrokerageActivityKind,
    quantity: float | None,
) -> float | None:
    if quantity is None:
        return None
    if kind in {
        BrokerageActivityKind.TRADE_BUY,
        BrokerageActivityKind.TRADE_SELL,
        BrokerageActivityKind.DISTRIBUTION_REINVESTMENT,
    }:
        return abs(quantity)
    return quantity


def load_column_map(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.startswith("{"):
        payload = json.loads(candidate)
    else:
        path = Path(candidate)
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("column map must be a JSON/YAML object")
    return {str(key): str(val) for key, val in payload.items()}


def resolve_alias_mapping(
    columns: list[str],
    *,
    required_fields: set[str],
) -> dict[str, str]:
    normalized = {normalize_column_name(column): column for column in columns}
    mapping: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            column = normalized.get(normalize_column_name(alias))
            if column:
                mapping[field] = column
                break
    if required_fields - set(mapping):
        return {}
    return mapping


def resolve_explicit_mapping(
    columns: list[str],
    column_map: dict[str, str],
) -> dict[str, str]:
    available = set(columns)
    missing = [column for column in column_map.values() if column not in available]
    if missing:
        raise ValueError(f"column map references missing columns: {missing}")
    return column_map


def dedupe_activity_frame(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    unique_df = df.unique(maintain_order=True)
    duplicate_rows_removed = df.height - unique_df.height
    return unique_df, duplicate_rows_removed


def column_index_from_ref(cell_ref: str) -> int:
    letters = "".join(char for char in str(cell_ref) if char.isalpha()).upper()
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - 64)
    return max(index - 1, 0)


def parse_xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find("a:is", XLSX_NS)
        if inline is None:
            return ""
        return "".join(node.text or "" for node in inline.iterfind(".//a:t", XLSX_NS))

    value = cell.find("a:v", XLSX_NS)
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value.text)]
    if cell_type == "b":
        return value.text == "1"
    return value.text


def read_xlsx_shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall("a:si", XLSX_NS):
        values.append("".join(node.text or "" for node in item.iterfind(".//a:t", XLSX_NS)))
    return values


def rows_to_records(rows: list[list[Any]]) -> list[dict[str, Any]]:
    header: list[str] | None = None
    records: list[dict[str, Any]] = []
    for row in rows:
        if not any(str(value or "").strip() for value in row):
            continue
        if header is None:
            header = [str(value or "").strip() for value in row]
            continue
        padded = list(row) + [""] * max(len(header) - len(row), 0)
        record: dict[str, Any] = {}
        has_value = False
        for idx, column in enumerate(header):
            if not column:
                continue
            value = padded[idx] if idx < len(padded) else ""
            if isinstance(value, str):
                value = value.strip()
            if value not in (None, ""):
                has_value = True
            record[column] = value
        if has_value:
            records.append(record)
    return records


def read_xlsx_sheets(input_path: Path) -> dict[str, list[dict[str, Any]]]:
    with ZipFile(input_path) as archive:
        shared_strings = read_xlsx_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: (
                rel.attrib["Target"].lstrip("/")
                if rel.attrib["Target"].startswith("/")
                else str(Path("xl") / rel.attrib["Target"])
            )
            for rel in rels
        }

        sheets: dict[str, list[dict[str, Any]]] = {}
        sheets_root = workbook.find("a:sheets", XLSX_NS)
        if sheets_root is None:
            return sheets

        rel_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for sheet in sheets_root:
            sheet_name = sheet.attrib["name"]
            target = rel_map[sheet.attrib[rel_key]]
            xml_root = ET.fromstring(archive.read(target))
            sheet_data = xml_root.find("a:sheetData", XLSX_NS)
            parsed_rows: list[list[Any]] = []
            if sheet_data is not None:
                for row in sheet_data.findall("a:row", XLSX_NS):
                    row_cells: dict[int, Any] = {}
                    max_index = -1
                    for cell in row.findall("a:c", XLSX_NS):
                        index = column_index_from_ref(cell.attrib.get("r", ""))
                        max_index = max(max_index, index)
                        row_cells[index] = parse_xlsx_cell_value(cell, shared_strings)
                    if row_cells:
                        parsed_rows.append([row_cells.get(idx, "") for idx in range(max_index + 1)])
            sheets[sheet_name] = rows_to_records(parsed_rows)
        return sheets


def normalize_optional_number(value: Any) -> float | None:
    number = parse_number(value)
    if number is None or abs(number) < 1e-9:
        return None
    return number


def transform_stake_activity_rows(
    rows: list[dict[str, Any]],
    *,
    market: str,
) -> list[dict[str, Any]]:
    transformed: list[dict[str, Any]] = []
    for row in rows:
        total_value = parse_number(row.get("Total Value"))
        gross_value = parse_number(row.get("Value"))
        symbol = str(row.get("Symbol") or "").strip()
        side = str(row.get("Side") or "").strip()
        if not any(
            [
                str(row.get("Trade Date") or "").strip(),
                symbol,
                side,
                total_value is not None,
                gross_value is not None,
            ]
        ):
            continue
        transformed.append(
            {
                "activity_date": row.get("Trade Date"),
                "activity_type": side,
                "symbol": symbol,
                "amount": abs(total_value) if total_value is not None else None,
                "gross": abs(gross_value) if gross_value is not None else abs(total_value) if total_value is not None else None,
                "brokerage": normalize_optional_number(row.get("Fees")),
                "price": row.get("Avg. Price"),
                "quantity": row.get("Units"),
                "status": "completed",
                "currency": row.get("Currency"),
                "tax": normalize_optional_number(row.get("GST")),
                "market": market,
            }
        )
    return transformed


def canonical_mapping(columns: list[str]) -> dict[str, str]:
    return {field: column for field, column in CANONICAL_COLUMN_MAP.items() if column in set(columns)}


def read_stake_activity_workbook(
    input_path: Path,
    *,
    requested_provider: str,
) -> list[InputBatch]:
    if requested_provider not in {
        "auto",
        BrokerageProvider.STAKE_AU.value,
        BrokerageProvider.STAKE_US.value,
    }:
        raise ValueError("Stake investment activity workbooks support only auto, stake_au, or stake_us provider selection")

    sheets = read_xlsx_sheets(input_path)
    batches: list[InputBatch] = []
    required_headers = {"Trade Date", "Symbol", "Side", "Units", "Total Value", "Currency"}
    for sheet_name, (provider, market) in STAKE_ACTIVITY_XLSX_SHEETS.items():
        if requested_provider not in {"auto", provider.value}:
            continue
        rows = sheets.get(sheet_name, [])
        if not rows:
            continue
        available_headers = set(rows[0].keys())
        if required_headers - available_headers:
            continue
        transformed = transform_stake_activity_rows(rows, market=market)
        if not transformed:
            continue
        df, duplicate_rows_removed = dedupe_activity_frame(pl.DataFrame(transformed))
        batches.append(
            InputBatch(
                provider=provider,
                df=df,
                mapping=canonical_mapping(list(df.columns)),
                source_file=f"{input_path.name}::{sheet_name}",
                duplicate_rows_removed=duplicate_rows_removed,
            )
        )

    if not batches:
        raise ValueError("could not detect supported Stake activity sheets in workbook")
    return batches


def detect_provider(
    columns: list[str],
    *,
    requested_provider: str,
    column_map: dict[str, str] | None,
) -> tuple[BrokerageProvider, dict[str, str]]:
    normalized_columns = {normalize_column_name(column): column for column in columns}
    betashares_matches = all(
        normalize_column_name(column) in normalized_columns
        for column in BETASHARES_EXPORT_COLUMNS
    )

    if requested_provider == BrokerageProvider.BETASHARES.value:
        if not betashares_matches:
            raise ValueError("requested provider betashares but export headers do not match")
        return BrokerageProvider.BETASHARES, BETASHARES_COLUMN_MAP

    if requested_provider == BrokerageProvider.STAKE_AU.value:
        mapping = column_map and resolve_explicit_mapping(columns, column_map)
        if mapping:
            return BrokerageProvider.STAKE_AU, mapping
        inferred = resolve_alias_mapping(columns, required_fields={"activity_date", "activity_type", "amount"})
        if not inferred:
            raise ValueError("could not infer Stake AU column mapping")
        return BrokerageProvider.STAKE_AU, inferred

    if requested_provider == BrokerageProvider.STAKE_US.value:
        mapping = column_map and resolve_explicit_mapping(columns, column_map)
        if mapping:
            return BrokerageProvider.STAKE_US, mapping
        inferred = resolve_alias_mapping(columns, required_fields={"activity_date", "activity_type", "amount"})
        if not inferred:
            raise ValueError("could not infer Stake US column mapping")
        return BrokerageProvider.STAKE_US, inferred

    if requested_provider == BrokerageProvider.GENERIC_CSV.value:
        if column_map:
            return BrokerageProvider.GENERIC_CSV, resolve_explicit_mapping(columns, column_map)
        inferred = resolve_alias_mapping(columns, required_fields={"activity_date", "activity_type", "amount"})
        if not inferred:
            raise ValueError("generic_csv requires --column-map or canonical column names")
        return BrokerageProvider.GENERIC_CSV, inferred

    if betashares_matches:
        return BrokerageProvider.BETASHARES, BETASHARES_COLUMN_MAP

    if column_map:
        return BrokerageProvider.GENERIC_CSV, resolve_explicit_mapping(columns, column_map)

    inferred = resolve_alias_mapping(columns, required_fields={"activity_date", "activity_type", "amount"})
    if inferred:
        return BrokerageProvider.STAKE_AU, inferred

    raise ValueError("could not detect provider; pass --provider or --column-map explicitly")


def read_activity_csv(csv_path: Path) -> tuple[pl.DataFrame, int]:
    df = pl.read_csv(
        csv_path,
        try_parse_dates=False,
        null_values=["", " ", "—"],
    )
    return dedupe_activity_frame(df)


def read_input_batches(
    input_path: Path,
    *,
    requested_provider: str,
    column_map: dict[str, str] | None,
) -> list[InputBatch]:
    suffix = input_path.suffix.lower()
    if suffix == ".xlsx":
        return read_stake_activity_workbook(
            input_path,
            requested_provider=requested_provider,
        )

    if suffix != ".csv":
        raise ValueError(f"unsupported input format: {input_path.suffix}")

    df, duplicate_rows_removed = read_activity_csv(input_path)
    provider, mapping = detect_provider(
        list(df.columns),
        requested_provider=requested_provider,
        column_map=column_map,
    )
    return [
        InputBatch(
            provider=provider,
            df=df,
            mapping=mapping,
            source_file=input_path.name,
            duplicate_rows_removed=duplicate_rows_removed,
        )
    ]


def get_value(row: dict[str, Any], mapping: dict[str, str], field: str) -> Any:
    column = mapping.get(field)
    if not column:
        return None
    return row.get(column)


def build_source_signature(payload: dict[str, Any]) -> str:
    return stable_hash(payload, length=16)


def build_row_hash(source_file: str, row: dict[str, Any]) -> str:
    return stable_hash({"source_file": source_file, "row": normalize_jsonable(row)}, length=16)


def normalize_row(
    row: dict[str, Any],
    *,
    provider: BrokerageProvider,
    mapping: dict[str, str],
    source_file: str,
    default_currency: str,
) -> NormalizedActivityRecord:
    raw_activity_type = str(get_value(row, mapping, "activity_type") or "").strip()
    if not raw_activity_type:
        raise ValueError("activity_type is required")

    activity_date = parse_activity_date(get_value(row, mapping, "activity_date"))
    activity_kind = infer_activity_kind(raw_activity_type)
    activity_status = infer_activity_status(get_value(row, mapping, "status"))

    symbol, market_from_symbol = parse_symbol(get_value(row, mapping, "symbol"))
    market_from_column = get_value(row, mapping, "market")
    instrument_market = (
        str(market_from_column).strip().upper()
        if market_from_column not in (None, "")
        else market_from_symbol
    )

    amount_raw, had_amount_sign = parse_money(get_value(row, mapping, "amount"))
    gross_raw, _ = parse_money(get_value(row, mapping, "gross"))
    fee_raw, _ = parse_money(get_value(row, mapping, "brokerage"))
    tax_raw, _ = parse_money(get_value(row, mapping, "tax"))

    fee_amount = abs(fee_raw) if fee_raw is not None else None
    tax_amount = abs(tax_raw) if tax_raw is not None else None
    net_amount = normalize_signed_amount(
        activity_kind,
        amount_raw,
        had_explicit_sign=had_amount_sign,
    )

    gross_amount = abs(gross_raw) if gross_raw is not None else abs(amount_raw) if amount_raw is not None else None
    currency = parse_currency(get_value(row, mapping, "currency"), default_currency)
    unit_price = parse_number(get_value(row, mapping, "price"))
    raw_quantity = parse_number(get_value(row, mapping, "quantity"))
    quantity = normalize_quantity_for_storage(activity_kind, raw_quantity)
    instrument_kind = infer_instrument_kind(activity_kind, symbol)
    cash_direction = infer_cash_direction(activity_kind, net_amount)
    review_status = infer_review_status(activity_kind, activity_status, symbol)

    source_signature = build_source_signature(
        {
            "provider": provider.value,
            "activity_date": activity_date,
            "activity_kind": activity_kind.value,
            "activity_status": activity_status.value,
            "instrument_symbol": symbol,
            "instrument_market": instrument_market,
            "currency": currency,
            "gross_amount": canonical_number(gross_amount),
            "net_amount": canonical_number(net_amount),
            "unit_price": canonical_number(unit_price),
            "quantity": canonical_number(raw_quantity),
            "fee_amount": canonical_number(fee_amount),
            "tax_amount": canonical_number(tax_amount),
        }
    )

    return NormalizedActivityRecord(
        provider=provider,
        raw_activity_type=raw_activity_type,
        activity_date=activity_date,
        activity_status=activity_status,
        instrument_symbol=symbol,
        instrument_market=instrument_market,
        instrument_kind=instrument_kind,
        currency=currency,
        gross_amount=canonical_number(gross_amount),
        net_amount=canonical_number(net_amount),
        unit_price=canonical_number(unit_price),
        quantity=canonical_number(quantity),
        fee_amount=canonical_number(fee_amount),
        tax_amount=canonical_number(tax_amount),
        brokerage_activity_kind=activity_kind,
        cash_direction=cash_direction,
        review_status=review_status,
        source_signature=source_signature,
        source_file=source_file,
        source_row_hash=build_row_hash(source_file, row),
    )


def normalize_records(
    df: pl.DataFrame,
    *,
    provider: BrokerageProvider,
    mapping: dict[str, str],
    source_file: str,
    default_currency: str,
) -> list[NormalizedActivityRecord]:
    records: list[NormalizedActivityRecord] = []
    for row in df.to_dicts():
        records.append(
            normalize_row(
                row,
                provider=provider,
                mapping=mapping,
                source_file=source_file,
                default_currency=default_currency,
            )
        )
    return records


def merge_records(records: list[NormalizedActivityRecord]) -> tuple[list[MergedActivityRecord], int]:
    grouped: dict[str, list[NormalizedActivityRecord]] = defaultdict(list)
    for record in records:
        grouped[record.source_signature].append(record)

    merged: list[MergedActivityRecord] = []
    merge_reductions = 0
    for signature, bucket in grouped.items():
        merge_reductions += max(len(bucket) - 1, 0)
        first = bucket[0]
        source_files = dedupe_preserve(item.source_file for item in bucket)
        source_row_hashes = dedupe_preserve(item.source_row_hash for item in bucket)
        merged.append(
            MergedActivityRecord(
                provider=first.provider,
                raw_activity_type=first.raw_activity_type,
                activity_date=first.activity_date,
                activity_status=first.activity_status,
                instrument_symbol=first.instrument_symbol,
                instrument_market=first.instrument_market,
                instrument_kind=first.instrument_kind,
                currency=first.currency,
                gross_amount=first.gross_amount,
                net_amount=first.net_amount,
                unit_price=first.unit_price,
                quantity=first.quantity,
                fee_amount=first.fee_amount,
                tax_amount=first.tax_amount,
                brokerage_activity_kind=first.brokerage_activity_kind,
                cash_direction=first.cash_direction,
                review_status=first.review_status,
                source_signature=signature,
                source_files=source_files,
                source_row_hashes=source_row_hashes,
                source_file_count=len(source_files),
                source_row_count=len(source_row_hashes),
                merge_count=max(len(bucket), len(source_files), len(source_row_hashes), 1),
            )
        )

    merged.sort(
        key=lambda item: (
            item.activity_date,
            item.instrument_symbol or "",
            item.brokerage_activity_kind.value,
            item.source_signature,
        )
    )
    return merged, merge_reductions


def record_from_frontmatter(frontmatter: dict[str, Any]) -> MergedActivityRecord:
    activity_kind = BrokerageActivityKind(str(frontmatter["brokerage_activity_kind"]))
    quantity = normalize_quantity_for_storage(
        activity_kind,
        parse_number(frontmatter.get("quantity")),
    )
    return MergedActivityRecord(
        provider=BrokerageProvider(str(frontmatter["brokerage_provider"])),
        raw_activity_type=str(frontmatter.get("raw_activity_type") or ""),
        activity_date=str(frontmatter["activity_date"]),
        activity_status=BrokerageActivityStatus(str(frontmatter.get("activity_status", "completed"))),
        instrument_symbol=(str(frontmatter.get("instrument_symbol")).strip().upper() if frontmatter.get("instrument_symbol") else None),
        instrument_market=(str(frontmatter.get("instrument_market")).strip().upper() if frontmatter.get("instrument_market") else None),
        instrument_kind=InstrumentKind(str(frontmatter.get("instrument_kind", InstrumentKind.UNKNOWN.value))),
        currency=parse_currency(frontmatter.get("currency"), "AUD"),
        gross_amount=canonical_number(parse_number(frontmatter.get("gross_amount"))),
        net_amount=canonical_number(parse_number(frontmatter.get("net_amount"))),
        unit_price=canonical_number(parse_number(frontmatter.get("unit_price"))),
        quantity=canonical_number(quantity),
        fee_amount=canonical_number(parse_number(frontmatter.get("fee_amount"))),
        tax_amount=canonical_number(parse_number(frontmatter.get("tax_amount"))),
        brokerage_activity_kind=activity_kind,
        cash_direction=CashDirection(str(frontmatter.get("cash_direction", CashDirection.NEUTRAL.value))),
        review_status=ReviewStatus(str(frontmatter.get("review_status", ReviewStatus.OK.value))),
        source_signature=str(frontmatter["source_signature"]),
        source_files=listify_strings(frontmatter.get("source_files")),
        source_row_hashes=listify_strings(frontmatter.get("source_row_hashes")),
        source_file_count=safe_int(frontmatter.get("source_file_count"), 1),
        source_row_count=safe_int(frontmatter.get("source_row_count"), 1),
        merge_count=safe_int(frontmatter.get("merge_count"), 1),
    )


def build_registry(
    root: Path,
    notes_dir: Path,
) -> tuple[dict[str, ExistingLedgerNote], dict[str, list[str]]]:
    registry: dict[str, ExistingLedgerNote] = {}
    collisions: dict[str, list[str]] = defaultdict(list)

    directory = root / notes_dir
    if not directory.exists():
        return registry, {}

    for path in sorted(directory.glob("**/*.md")):
        note = load_markdown_note(path)
        signature = str(note.frontmatter.get("source_signature") or "").strip()
        if not signature:
            continue
        relative = str(path.relative_to(root))
        collisions[signature].append(relative)
        if signature not in registry:
            registry[signature] = ExistingLedgerNote(
                path=path,
                frontmatter=dict(note.frontmatter),
                text=note.text,
            )

    duplicate_signatures = {
        signature: paths
        for signature, paths in collisions.items()
        if len(paths) > 1
    }
    return registry, duplicate_signatures


def build_asset_registry(root: Path, assets_dir: Path) -> tuple[dict[str, ExistingLedgerNote], dict[str, list[str]]]:
    registry: dict[str, ExistingLedgerNote] = {}
    collisions: dict[str, list[str]] = defaultdict(list)

    directory = root / assets_dir
    if not directory.exists():
        return registry, {}

    for path in sorted(directory.glob("*.md")):
        note = load_markdown_note(path)
        symbol = str(note.frontmatter.get("instrument_symbol") or "").strip().upper()
        if not symbol:
            continue
        relative = str(path.relative_to(root))
        collisions[symbol].append(relative)
        if symbol not in registry:
            registry[symbol] = ExistingLedgerNote(
                path=path,
                frontmatter=dict(note.frontmatter),
                text=note.text,
            )

    duplicate_symbols = {
        symbol: paths
        for symbol, paths in collisions.items()
        if len(paths) > 1
    }
    return registry, duplicate_symbols


def infer_export_window(input_path: Path) -> tuple[str, str] | None:
    match = re.search(r"(?P<start>\d{4}-\d{2}-\d{2})[-_](?P<end>\d{4}-\d{2}-\d{2})", input_path.stem)
    if not match:
        return None
    return match.group("start"), match.group("end")


def earliest_registry_activity_date(registry: dict[str, ExistingLedgerNote], *, provider: str | None = None) -> str | None:
    dates = [
        str(note.frontmatter.get("activity_date") or "").strip()
        for note in registry.values()
        if str(note.frontmatter.get("activity_date") or "").strip()
        and (provider is None or str(note.frontmatter.get("brokerage_provider") or "").strip() == provider)
    ]
    return min(dates) if dates else None


def make_partial_window_warning(
    *,
    input_path: Path,
    registry: dict[str, ExistingLedgerNote],
    providers: list[str],
) -> str | None:
    if input_path.suffix.lower() != ".xlsx":
        return None

    export_window = infer_export_window(input_path)
    if export_window is None:
        return None

    start_date, end_date = export_window
    providers_without_prior_history = [
        provider
        for provider in providers
        if (earliest_registry_activity_date(registry, provider=provider) or "9999-12-31") >= start_date
    ]
    if not providers_without_prior_history:
        return None

    rendered_providers = ", ".join(f"`{provider_label(provider)}`" for provider in providers_without_prior_history)
    return (
        f"Input `{input_path.name}` appears to cover only `{start_date}` to `{end_date}` and the existing "
        f"brokerage ledger has no {rendered_providers} activity earlier than `{start_date}`. Current holdings "
        f"derived from this ledger may omit pre-window positions for those providers; import older history or "
        f"reconcile against a current valuation "
        f"before trusting actual holdings."
    )


def safe_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def listify_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def activity_asset_link(symbol: str) -> str:
    return f"[[20 Resources/Investments/Brokerage Assets/{symbol}|{symbol}]]"


def infer_asset_kind(records: list[MergedActivityRecord]) -> BrokerageAssetKind:
    instrument_kinds = {
        record.instrument_kind
        for record in records
        if record.instrument_kind != InstrumentKind.UNKNOWN
    }
    if InstrumentKind.CRYPTO in instrument_kinds:
        return BrokerageAssetKind.CRYPTO
    if InstrumentKind.FX in instrument_kinds:
        return BrokerageAssetKind.FX_PAIR
    if InstrumentKind.FUND in instrument_kinds:
        return BrokerageAssetKind.FUND
    if InstrumentKind.LISTED_SECURITY in instrument_kinds:
        return BrokerageAssetKind.LISTED_SECURITY
    if InstrumentKind.OTHER in instrument_kinds:
        return BrokerageAssetKind.OTHER
    return BrokerageAssetKind.UNKNOWN


def aggregate_assets(records: list[MergedActivityRecord]) -> list[AssetAggregate]:
    grouped: dict[str, list[MergedActivityRecord]] = defaultdict(list)
    for record in records:
        if not record.instrument_symbol:
            continue
        grouped[record.instrument_symbol.upper()].append(record)

    aggregates: list[AssetAggregate] = []
    for symbol, bucket in grouped.items():
        ordered = sorted(
            bucket,
            key=lambda record: (
                record.activity_date,
                record.brokerage_activity_kind.value,
                record.source_signature,
            ),
        )
        aggregates.append(AssetAggregate(symbol=symbol, records=ordered))
    aggregates.sort(key=lambda item: item.symbol)
    return aggregates


def build_frontmatter(record: MergedActivityRecord) -> dict[str, Any]:
    activity_year = int(record.activity_date[:4])
    activity_month = record.activity_date[:7]
    provider = record.provider.value
    activity_kind = record.brokerage_activity_kind.value
    return order_frontmatter(
        {
            "brokerage_activity_id": make_activity_id(record.source_signature),
            "brokerage_activity_kind": activity_kind,
            "brokerage_provider": provider,
            "raw_activity_type": record.raw_activity_type,
            "activity_date": record.activity_date,
            "activity_year": activity_year,
            "activity_month": activity_month,
            "activity_status": record.activity_status.value,
            "instrument_symbol": record.instrument_symbol,
            "instrument_market": record.instrument_market,
            "instrument_kind": record.instrument_kind.value,
            "asset_note": activity_asset_link(record.instrument_symbol) if record.instrument_symbol else None,
            "currency": record.currency,
            "gross_amount": record.gross_amount,
            "net_amount": record.net_amount,
            "unit_price": record.unit_price,
            "quantity": record.quantity,
            "fee_amount": record.fee_amount,
            "tax_amount": record.tax_amount,
            "cash_direction": record.cash_direction.value,
            "review_status": record.review_status.value,
            "source_signature": record.source_signature,
            "source_files": record.source_files,
            "source_file_count": record.source_file_count,
            "source_row_hashes": record.source_row_hashes,
            "source_row_count": record.source_row_count,
            "merge_count": record.merge_count,
            "tags": normalize_tags([], provider, activity_kind),
        }
    )


def merge_frontmatter(existing: dict[str, Any] | None, desired: dict[str, Any]) -> dict[str, Any]:
    existing = existing or {}
    owned = set(BROKERAGE_FRONTMATTER_ORDER)
    preserved = {key: value for key, value in existing.items() if key not in owned}
    merged = {**preserved, **desired}

    merged["source_files"] = dedupe_preserve(
        [*listify_strings(existing.get("source_files")), *desired["source_files"]]
    )
    merged["source_row_hashes"] = dedupe_preserve(
        [*listify_strings(existing.get("source_row_hashes")), *desired["source_row_hashes"]]
    )
    merged["source_file_count"] = len(merged["source_files"]) or 1
    merged["source_row_count"] = len(merged["source_row_hashes"]) or 1
    merged["merge_count"] = max(
        safe_int(existing.get("merge_count"), 1),
        safe_int(desired.get("merge_count"), 1),
        merged["source_file_count"],
        merged["source_row_count"],
        1,
    )
    merged["tags"] = normalize_tags(
        [*listify_strings(existing.get("tags")), *desired["tags"]],
        desired["brokerage_provider"],
        desired["brokerage_activity_kind"],
    )
    return order_frontmatter(merged)


def build_asset_frontmatter(aggregate: AssetAggregate) -> dict[str, Any]:
    records = aggregate.records
    first = records[0]
    ordered_by_date_desc = sorted(records, key=lambda record: record.activity_date, reverse=True)
    last_with_price = next((record for record in ordered_by_date_desc if record.unit_price is not None), None)
    last_trade = next(
        (
            record.activity_date
            for record in ordered_by_date_desc
            if record.brokerage_activity_kind in {BrokerageActivityKind.TRADE_BUY, BrokerageActivityKind.TRADE_SELL}
        ),
        None,
    )
    providers = dedupe_preserve(record.provider.value for record in records)
    trade_buy_count = sum(record.brokerage_activity_kind == BrokerageActivityKind.TRADE_BUY for record in records)
    trade_sell_count = sum(record.brokerage_activity_kind == BrokerageActivityKind.TRADE_SELL for record in records)
    distribution_count = sum(record.brokerage_activity_kind == BrokerageActivityKind.DISTRIBUTION for record in records)
    distribution_reinvestment_count = sum(
        record.brokerage_activity_kind == BrokerageActivityKind.DISTRIBUTION_REINVESTMENT
        for record in records
    )
    quantity_delta = 0.0
    quantity_seen = False
    for record in records:
        if record.quantity is None:
            continue
        if record.brokerage_activity_kind in {
            BrokerageActivityKind.TRADE_BUY,
            BrokerageActivityKind.DISTRIBUTION_REINVESTMENT,
        }:
            quantity_delta += record.quantity
            quantity_seen = True
        elif record.brokerage_activity_kind == BrokerageActivityKind.TRADE_SELL:
            quantity_delta -= record.quantity
            quantity_seen = True

    cumulative_net_cash_flow = sum(record.net_amount or 0.0 for record in records)
    cumulative_fees = sum(record.fee_amount or 0.0 for record in records)
    cumulative_taxes = sum(record.tax_amount or 0.0 for record in records)
    review_status = (
        ReviewStatus.NEEDS_REVIEW
        if any(record.review_status == ReviewStatus.NEEDS_REVIEW for record in records)
        else ReviewStatus.OK
    )
    instrument_market = next(
        (record.instrument_market for record in ordered_by_date_desc if record.instrument_market),
        None,
    )
    currency = next(
        (record.currency for record in ordered_by_date_desc if record.currency),
        "AUD",
    )
    asset_kind = infer_asset_kind(records)

    return order_asset_frontmatter(
        {
            "brokerage_asset_id": make_asset_id(aggregate.symbol),
            "brokerage_asset_kind": asset_kind.value,
            "instrument_symbol": aggregate.symbol,
            "instrument_market": instrument_market,
            "instrument_kind": first.instrument_kind.value,
            "brokerage_providers": providers,
            "first_activity_date": min(record.activity_date for record in records),
            "last_activity_date": max(record.activity_date for record in records),
            "last_trade_date": last_trade,
            "activity_count": len(records),
            "trade_buy_count": trade_buy_count,
            "trade_sell_count": trade_sell_count,
            "distribution_count": distribution_count,
            "distribution_reinvestment_count": distribution_reinvestment_count,
            "currency": currency,
            "last_unit_price": last_with_price.unit_price if last_with_price else None,
            "estimated_open_quantity": round(quantity_delta, 8) if quantity_seen else None,
            "cumulative_net_cash_flow": round(cumulative_net_cash_flow, 8),
            "cumulative_fees": round(cumulative_fees, 8) if cumulative_fees else None,
            "cumulative_taxes": round(cumulative_taxes, 8) if cumulative_taxes else None,
            "review_status": review_status.value,
            "source_activity_signatures": [record.source_signature for record in records],
            "source_activity_count": len(records),
            "tags": normalize_asset_tags([], providers, asset_kind.value),
        }
    )


def merge_asset_frontmatter(existing: dict[str, Any] | None, desired: dict[str, Any]) -> dict[str, Any]:
    existing = existing or {}
    owned = set(BROKERAGE_ASSET_FRONTMATTER_ORDER)
    preserved = {key: value for key, value in existing.items() if key not in owned}
    merged = {**preserved, **desired}
    merged["brokerage_providers"] = desired["brokerage_providers"]
    merged["source_activity_signatures"] = desired["source_activity_signatures"]
    merged["source_activity_count"] = desired["source_activity_count"]
    merged["activity_count"] = desired["activity_count"]
    merged["trade_buy_count"] = desired["trade_buy_count"]
    merged["trade_sell_count"] = desired["trade_sell_count"]
    merged["distribution_count"] = desired["distribution_count"]
    merged["distribution_reinvestment_count"] = desired["distribution_reinvestment_count"]
    merged["tags"] = normalize_asset_tags(
        [*listify_strings(existing.get("tags")), *desired["tags"]],
        merged["brokerage_providers"],
        desired["brokerage_asset_kind"],
    )
    return order_asset_frontmatter(merged)


def format_money(amount: float | None, currency: str) -> str | None:
    if amount is None:
        return None
    return f"{currency} {amount:,.2f}"


def format_number(value: float | None, *, digits: int = 8) -> str | None:
    if value is None:
        return None
    rendered = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return rendered or "0"


def render_note_body(frontmatter: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# {note_title(frontmatter)}",
        "",
        "Managed brokerage activity note.",
        "",
        "## Activity",
    ]

    activity_fields = [
        ("Kind", f"`{frontmatter['brokerage_activity_kind']}`"),
        ("Provider", f"`{provider_label(frontmatter['brokerage_provider'])}`"),
        ("Status", f"`{frontmatter['activity_status']}`"),
        ("Raw Type", f"`{frontmatter.get('raw_activity_type')}`" if frontmatter.get("raw_activity_type") else None),
        ("Symbol", f"`{frontmatter.get('instrument_symbol')}`" if frontmatter.get("instrument_symbol") else "`cash`"),
        ("Asset", frontmatter.get("asset_note")),
        ("Market", f"`{frontmatter.get('instrument_market')}`" if frontmatter.get("instrument_market") else None),
        ("Currency", f"`{frontmatter.get('currency', 'AUD')}`"),
        ("Net Cash Impact", format_money(frontmatter.get("net_amount"), str(frontmatter.get("currency", "AUD")))),
        ("Quantity", format_number(frontmatter.get("quantity"))),
        ("Unit Price", format_money(frontmatter.get("unit_price"), str(frontmatter.get("currency", "AUD")))),
        ("Fee", format_money(frontmatter.get("fee_amount"), str(frontmatter.get("currency", "AUD")))),
        ("Tax", format_money(frontmatter.get("tax_amount"), str(frontmatter.get("currency", "AUD")))),
        ("Review Status", f"`{frontmatter.get('review_status', 'ok')}`"),
    ]
    for label, value in activity_fields:
        if value:
            lines.append(f"- {label}: {value}")

    lines.extend(
        [
            "",
            "## Import Trace",
            f"- Source signature: `{frontmatter['source_signature']}`",
            f"- Source files: {', '.join(f'`{name}`' for name in frontmatter['source_files'])}",
            f"- Source rows merged: `{frontmatter['source_row_count']}`",
            f"- Merge count: `{frontmatter['merge_count']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_asset_note_body(frontmatter: dict[str, Any], activity_paths: list[str]) -> str:
    symbol = str(frontmatter["instrument_symbol"])
    currency = str(frontmatter.get("currency", "AUD"))
    lines: list[str] = [
        f"# {symbol}",
        "",
        "Managed brokerage asset note.",
        "",
        "## Summary",
        f"- Kind: `{frontmatter['brokerage_asset_kind']}`",
        f"- Symbol: `{symbol}`",
    ]
    if frontmatter.get("instrument_market"):
        lines.append(f"- Market: `{frontmatter['instrument_market']}`")
    if frontmatter.get("brokerage_providers"):
        lines.append(
            "- Providers: "
            + ", ".join(f"`{provider_label(provider)}`" for provider in frontmatter["brokerage_providers"])
        )
    summary_fields = [
        ("First Activity", f"`{frontmatter['first_activity_date']}`"),
        ("Last Activity", f"`{frontmatter['last_activity_date']}`"),
        ("Last Trade", f"`{frontmatter.get('last_trade_date')}`" if frontmatter.get("last_trade_date") else None),
        ("Activity Count", f"`{frontmatter['activity_count']}`"),
        ("Estimated Open Quantity", format_number(frontmatter.get("estimated_open_quantity"))),
        ("Last Unit Price", format_money(frontmatter.get("last_unit_price"), currency)),
        ("Cumulative Net Cash Flow", format_money(frontmatter.get("cumulative_net_cash_flow"), currency)),
        ("Cumulative Fees", format_money(frontmatter.get("cumulative_fees"), currency)),
        ("Cumulative Taxes", format_money(frontmatter.get("cumulative_taxes"), currency)),
        ("Review Status", f"`{frontmatter['review_status']}`"),
    ]
    for label, value in summary_fields:
        if value:
            lines.append(f"- {label}: {value}")

    lines.extend(
        [
            "",
            "## Activity Mix",
            f"- Buys: `{frontmatter['trade_buy_count']}`",
            f"- Sells: `{frontmatter['trade_sell_count']}`",
            f"- Distributions: `{frontmatter['distribution_count']}`",
            f"- DRP Events: `{frontmatter['distribution_reinvestment_count']}`",
            "",
            "## Recent Activity",
        ]
    )
    for relative_path in activity_paths[:5]:
        file_name = Path(relative_path).stem
        lines.append(f"- [[{Path(relative_path).with_suffix('').as_posix()}|{file_name}]]")

    lines.extend(
        [
            "",
            "## Import Trace",
            f"- Source activity signatures: `{frontmatter['source_activity_count']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run_sync(
    *,
    root: Path,
    input_path: Path,
    mode: str,
    requested_provider: str,
    notes_dir: Path,
    default_currency: str,
    column_map: dict[str, str] | None,
) -> dict[str, Any]:
    batches = read_input_batches(
        input_path,
        requested_provider=requested_provider,
        column_map=column_map,
    )
    normalized: list[NormalizedActivityRecord] = []
    duplicate_rows_removed = 0
    providers = dedupe_preserve(batch.provider.value for batch in batches)
    for batch in batches:
        duplicate_rows_removed += batch.duplicate_rows_removed
        normalized.extend(
            normalize_records(
                batch.df,
                provider=batch.provider,
                mapping=batch.mapping,
                source_file=batch.source_file,
                default_currency=default_currency,
            )
        )
    merged, merge_reductions = merge_records(normalized)
    registry, registry_collisions = build_registry(root, notes_dir)
    asset_registry, asset_registry_collisions = build_asset_registry(root, BROKERAGE_ASSETS_DIR)

    full_asset_records: dict[str, MergedActivityRecord] = {}
    for signature, existing_note in registry.items():
        full_asset_records[signature] = record_from_frontmatter(existing_note.frontmatter)
    for record in merged:
        full_asset_records[record.source_signature] = record
    asset_aggregates = aggregate_assets(list(full_asset_records.values()))

    created = 0
    updated = 0
    unchanged = 0
    notes: list[dict[str, str]] = []
    asset_created = 0
    asset_updated = 0
    asset_unchanged = 0
    asset_notes: list[dict[str, str]] = []
    warnings: list[str] = []

    if duplicate_rows_removed:
        warnings.append(
            f"Removed {duplicate_rows_removed} exact duplicate row(s) before normalization."
        )
    if merge_reductions:
        warnings.append(
            f"Merged {merge_reductions} duplicate row(s) into canonical source signatures."
        )
    partial_window_warning = make_partial_window_warning(
        input_path=input_path,
        registry=registry,
        providers=providers,
    )
    if partial_window_warning:
        warnings.append(partial_window_warning)
    for signature, paths in sorted(registry_collisions.items()):
        warnings.append(
            f"Existing ledger collision for source_signature `{signature}`: {', '.join(paths)}"
        )
    for symbol, paths in sorted(asset_registry_collisions.items()):
        warnings.append(
            f"Existing asset collision for symbol `{symbol}`: {', '.join(paths)}"
        )

    for record in merged:
        desired_frontmatter = build_frontmatter(record)
        existing = registry.get(record.source_signature)
        target_path = existing.path if existing else root / note_relative_path(desired_frontmatter)
        merged_frontmatter = merge_frontmatter(
            existing.frontmatter if existing else None,
            desired_frontmatter,
        )
        body = render_note_body(merged_frontmatter)
        rendered = render_markdown(merged_frontmatter, body)
        relative_path = str(target_path.relative_to(root))

        if existing is None:
            status = "created"
            created += 1
        elif existing.text == rendered:
            status = "unchanged"
            unchanged += 1
        else:
            status = "updated"
            updated += 1

        if mode == "fix" and status != "unchanged":
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(rendered, encoding="utf-8")

        notes.append({"path": relative_path, "status": status})

    for aggregate in asset_aggregates:
        desired_frontmatter = build_asset_frontmatter(aggregate)
        existing_asset = asset_registry.get(aggregate.symbol)
        target_path = existing_asset.path if existing_asset else root / asset_relative_path(desired_frontmatter)
        merged_frontmatter = merge_asset_frontmatter(
            existing_asset.frontmatter if existing_asset else None,
            desired_frontmatter,
        )
        activity_paths = [
            str(note_relative_path(build_frontmatter(record)))
            for record in sorted(aggregate.records, key=lambda item: item.activity_date, reverse=True)
        ]
        body = render_asset_note_body(merged_frontmatter, activity_paths)
        rendered = render_asset_markdown(merged_frontmatter, body)
        relative_path = str(target_path.relative_to(root))

        if existing_asset is None:
            status = "created"
            asset_created += 1
        elif existing_asset.text == rendered:
            status = "unchanged"
            asset_unchanged += 1
        else:
            status = "updated"
            asset_updated += 1

        if mode == "fix" and status != "unchanged":
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(rendered, encoding="utf-8")

        asset_notes.append({"path": relative_path, "status": status})

    return {
        "ok": True,
        "provider": providers[0] if len(providers) == 1 else "multiple",
        "providers": providers,
        "input": str(input_path),
        "rows_read": len(normalized) + duplicate_rows_removed,
        "exact_duplicate_rows_removed": duplicate_rows_removed,
        "normalized_records": len(normalized),
        "source_signature_merges": merge_reductions,
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "asset_created": asset_created,
        "asset_updated": asset_updated,
        "asset_unchanged": asset_unchanged,
        "warnings": warnings,
        "notes": notes,
        "asset_notes": asset_notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import brokerage activity into typed Obsidian ledger notes.")
    parser.add_argument("--input", required=True, help="Path to the brokerage CSV or supported XLSX export")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    parser.add_argument(
        "--provider",
        choices=[
            "auto",
            BrokerageProvider.BETASHARES.value,
            BrokerageProvider.STAKE_AU.value,
            BrokerageProvider.STAKE_US.value,
            BrokerageProvider.GENERIC_CSV.value,
        ],
        default="auto",
    )
    parser.add_argument("--notes-dir", default=str(BROKERAGE_NOTES_DIR))
    parser.add_argument("--default-currency", default="AUD")
    parser.add_argument("--column-map", help="JSON string or path to JSON/YAML mapping canonical fields to export columns")
    args = parser.parse_args()

    try:
        payload = run_sync(
            root=Path.cwd(),
            input_path=Path(args.input),
            mode=args.mode,
            requested_provider=args.provider,
            notes_dir=Path(args.notes_dir),
            default_currency=args.default_currency,
            column_map=load_column_map(args.column_map),
        )
        print(dump_json(payload))
        return 0
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(dump_json({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
