#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portfolio_holdings_models import (
    BROKERAGE_ACTIVITY_GLOB,
    CURRENT_FRONTMATTER_ORDER,
    CURRENT_HOLDINGS_DIR,
    HOLDINGS_HISTORY_DIR,
    HISTORY_FRONTMATTER_ORDER,
    PortfolioHoldingFrontmatter,
    PortfolioHoldingHistoryFrontmatter,
    PortfolioHoldingKind,
    ReviewStatus,
    canonical_number,
    current_relative_path,
    dedupe_preserve,
    format_money,
    format_number,
    history_relative_path,
    listify_strings,
    load_markdown_note,
    make_holding_id,
    normalize_provider_labels,
    parse_number,
    provider_label,
    render_markdown,
    required_tags,
)

BUY_LIKE_KINDS = {"trade_buy", "distribution_reinvestment"}
SELL_LIKE_KINDS = {"trade_sell"}
TRADE_KINDS = {"trade_buy", "trade_sell"}
COUNTED_KINDS = {"trade_buy", "trade_sell", "distribution", "distribution_reinvestment"}


@dataclass
class ActivityRecord:
    source_signature: str
    activity_date: str
    activity_kind: str
    brokerage_provider: str
    instrument_symbol: str
    instrument_market: str | None
    instrument_kind: str | None
    currency: str
    net_amount: float | None
    quantity: float | None
    fee_amount: float | None
    tax_amount: float | None
    review_status: str
    relative_path: str


@dataclass
class ExistingNote:
    path: Path
    frontmatter: dict[str, Any]
    text: str


@dataclass
class HoldingEvent:
    record: ActivityRecord
    quantity_delta: float
    closing_quantity: float


def normalized_activity_quantity(record: ActivityRecord) -> float | None:
    quantity = parse_number(record.quantity)
    if quantity is None:
        return None
    if record.activity_kind in BUY_LIKE_KINDS | SELL_LIKE_KINDS:
        return abs(quantity)
    return quantity


def quantity_delta(record: ActivityRecord) -> float:
    quantity = normalized_activity_quantity(record)
    if quantity is None:
        return 0.0
    if record.activity_kind in BUY_LIKE_KINDS:
        return quantity
    if record.activity_kind in SELL_LIKE_KINDS:
        return -quantity
    if record.activity_kind in {"corporate_action", "adjustment"}:
        return quantity
    return 0.0


def load_activity_records(root: Path, *, activity_glob: str) -> list[ActivityRecord]:
    records: list[ActivityRecord] = []
    for path in sorted(root.glob(activity_glob)):
        note = load_markdown_note(path)
        frontmatter = note.frontmatter
        symbol = str(frontmatter.get("instrument_symbol") or "").strip().upper()
        activity_status = str(frontmatter.get("activity_status") or "completed").strip().lower()
        if not symbol or activity_status != "completed":
            continue
        activity_kind = str(frontmatter.get("brokerage_activity_kind") or "").strip()
        if activity_kind not in COUNTED_KINDS | {"corporate_action", "adjustment"}:
            continue
        records.append(
            ActivityRecord(
                source_signature=str(frontmatter["source_signature"]),
                activity_date=str(frontmatter["activity_date"]),
                activity_kind=activity_kind,
                brokerage_provider=str(frontmatter["brokerage_provider"]),
                instrument_symbol=symbol,
                instrument_market=(str(frontmatter.get("instrument_market")).strip().upper() if frontmatter.get("instrument_market") else None),
                instrument_kind=(str(frontmatter.get("instrument_kind")).strip().lower() if frontmatter.get("instrument_kind") else None),
                currency=str(frontmatter.get("currency") or "AUD").strip().upper(),
                net_amount=parse_number(frontmatter.get("net_amount")),
                quantity=parse_number(frontmatter.get("quantity")),
                fee_amount=parse_number(frontmatter.get("fee_amount")),
                tax_amount=parse_number(frontmatter.get("tax_amount")),
                review_status=str(frontmatter.get("review_status") or ReviewStatus.OK.value),
                relative_path=str(path.relative_to(root)),
            )
        )
    records.sort(key=lambda item: (item.activity_date, item.activity_kind, item.source_signature))
    return records


def build_note_registry(root: Path, directory: Path) -> tuple[dict[str, ExistingNote], dict[str, list[str]]]:
    registry: dict[str, ExistingNote] = {}
    collisions: dict[str, list[str]] = defaultdict(list)
    full_dir = root / directory
    if not full_dir.exists():
        return registry, {}
    for path in sorted(full_dir.glob("*.md")):
        note = load_markdown_note(path)
        symbol = str(note.frontmatter.get("instrument_symbol") or "").strip().upper()
        if not symbol:
            continue
        relative = str(path.relative_to(root))
        collisions[symbol].append(relative)
        if symbol not in registry:
            registry[symbol] = ExistingNote(path=path, frontmatter=dict(note.frontmatter), text=note.text)
    duplicates = {symbol: paths for symbol, paths in collisions.items() if len(paths) > 1}
    return registry, duplicates


def build_events(records: list[ActivityRecord]) -> list[HoldingEvent]:
    events: list[HoldingEvent] = []
    running_quantity = 0.0
    for record in records:
        running_quantity = round(running_quantity + quantity_delta(record), 8)
        events.append(
            HoldingEvent(
                record=record,
                quantity_delta=round(quantity_delta(record), 8),
                closing_quantity=running_quantity,
            )
        )
    return events


def build_current_frontmatter(symbol: str, records: list[ActivityRecord], events: list[HoldingEvent]) -> dict[str, Any]:
    providers = dedupe_preserve(record.brokerage_provider for record in records)
    latest_market = next((record.instrument_market for record in reversed(records) if record.instrument_market), None)
    latest_kind = next((record.instrument_kind for record in reversed(records) if record.instrument_kind), None)
    latest_currency = next((record.currency for record in reversed(records) if record.currency), "AUD")
    last_trade_date = next((record.activity_date for record in reversed(records) if record.activity_kind in TRADE_KINDS), None)
    current_quantity = events[-1].closing_quantity if events else 0.0
    review_status = (
        ReviewStatus.NEEDS_REVIEW.value
        if any(record.review_status == ReviewStatus.NEEDS_REVIEW.value for record in records) or current_quantity < 0
        else ReviewStatus.OK.value
    )
    return {
        "portfolio_holding_id": make_holding_id(symbol, PortfolioHoldingKind.CURRENT_POSITION),
        "portfolio_holding_kind": PortfolioHoldingKind.CURRENT_POSITION.value,
        "instrument_symbol": symbol,
        "instrument_market": latest_market,
        "instrument_kind": latest_kind,
        "brokerage_providers": providers,
        "first_activity_date": records[0].activity_date,
        "last_activity_date": records[-1].activity_date,
        "last_trade_date": last_trade_date,
        "activity_count": len(records),
        "trade_buy_count": sum(record.activity_kind == "trade_buy" for record in records),
        "trade_sell_count": sum(record.activity_kind == "trade_sell" for record in records),
        "distribution_count": sum(record.activity_kind == "distribution" for record in records),
        "distribution_reinvestment_count": sum(record.activity_kind == "distribution_reinvestment" for record in records),
        "current_quantity": canonical_number(current_quantity),
        "currency": latest_currency,
        "cumulative_net_cash_flow": canonical_number(sum(record.net_amount or 0.0 for record in records)),
        "cumulative_fees": canonical_number(sum(record.fee_amount or 0.0 for record in records)) or None,
        "cumulative_taxes": canonical_number(sum(record.tax_amount or 0.0 for record in records)) or None,
        "review_status": review_status,
        "source_activity_signatures": [record.source_signature for record in records],
        "source_activity_count": len(records),
        "tags": required_tags(providers, PortfolioHoldingKind.CURRENT_POSITION),
    }


def build_history_frontmatter(symbol: str, records: list[ActivityRecord], events: list[HoldingEvent]) -> dict[str, Any]:
    providers = dedupe_preserve(record.brokerage_provider for record in records)
    latest_market = next((record.instrument_market for record in reversed(records) if record.instrument_market), None)
    quantities = [event.closing_quantity for event in events] or [0.0]
    current_quantity = quantities[-1]
    review_status = (
        ReviewStatus.NEEDS_REVIEW.value
        if any(record.review_status == ReviewStatus.NEEDS_REVIEW.value for record in records) or current_quantity < 0
        else ReviewStatus.OK.value
    )
    return {
        "portfolio_holding_id": make_holding_id(symbol, PortfolioHoldingKind.HOLDING_HISTORY),
        "portfolio_holding_kind": PortfolioHoldingKind.HOLDING_HISTORY.value,
        "instrument_symbol": symbol,
        "instrument_market": latest_market,
        "brokerage_providers": providers,
        "first_snapshot_date": events[0].record.activity_date,
        "last_snapshot_date": events[-1].record.activity_date,
        "snapshot_count": len(events),
        "current_quantity": canonical_number(current_quantity),
        "max_quantity": canonical_number(max(quantities)),
        "min_quantity": canonical_number(min(quantities)),
        "review_status": review_status,
        "source_activity_signatures": [record.source_signature for record in records],
        "source_activity_count": len(records),
        "tags": required_tags(providers, PortfolioHoldingKind.HOLDING_HISTORY),
    }


def merge_frontmatter(existing: dict[str, Any] | None, desired: dict[str, Any], order: list[str]) -> dict[str, Any]:
    existing = existing or {}
    owned = set(order)
    preserved = {key: value for key, value in existing.items() if key not in owned}
    merged = {**preserved, **desired}
    merged["brokerage_providers"] = desired["brokerage_providers"]
    merged["source_activity_signatures"] = desired["source_activity_signatures"]
    merged["source_activity_count"] = desired["source_activity_count"]
    merged["tags"] = dedupe_preserve([*listify_strings(existing.get("tags")), *desired["tags"]])
    if desired["portfolio_holding_kind"] == PortfolioHoldingKind.CURRENT_POSITION.value:
        PortfolioHoldingFrontmatter.model_validate(merged)
    else:
        PortfolioHoldingHistoryFrontmatter.model_validate(merged)
    return merged


def current_note_body(frontmatter: dict[str, Any], events: list[HoldingEvent]) -> str:
    symbol = str(frontmatter["instrument_symbol"])
    currency = str(frontmatter.get("currency", "AUD"))
    lines = [
        f"# {symbol}",
        "",
        "Derived current portfolio holding note.",
        "",
        "## Summary",
        f"- Symbol: `{symbol}`",
    ]
    if frontmatter.get("instrument_market"):
        lines.append(f"- Market: `{frontmatter['instrument_market']}`")
    if frontmatter.get("instrument_kind"):
        lines.append(f"- Instrument: `{frontmatter['instrument_kind']}`")
    lines.append(
        "- Providers: "
        + ", ".join(f"`{label}`" for label in normalize_provider_labels(frontmatter["brokerage_providers"]))
    )
    lines.extend(
        [
            f"- First Activity: `{frontmatter['first_activity_date']}`",
            f"- Last Activity: `{frontmatter['last_activity_date']}`",
            f"- Last Trade: `{frontmatter['last_trade_date']}`" if frontmatter.get("last_trade_date") else "- Last Trade: `n/a`",
            f"- Current Quantity: {format_number(frontmatter.get('current_quantity')) or '0'}",
            f"- Cumulative Net Cash Flow: {format_money(frontmatter.get('cumulative_net_cash_flow'), currency) or 'n/a'}",
            f"- Cumulative Fees: {format_money(frontmatter.get('cumulative_fees'), currency) or 'n/a'}",
            f"- Cumulative Taxes: {format_money(frontmatter.get('cumulative_taxes'), currency) or 'n/a'}",
            f"- Review Status: `{frontmatter['review_status']}`",
            f"- History: [[{history_relative_path(symbol).with_suffix('').as_posix()}|{symbol} Holdings History]]",
            "",
            "## Recent Activity",
        ]
    )
    for event in list(reversed(events))[:5]:
        delta = format_number(event.quantity_delta)
        closing = format_number(event.closing_quantity)
        file_name = Path(event.record.relative_path).stem
        lines.append(
            f"- [[{Path(event.record.relative_path).with_suffix('').as_posix()}|{file_name}]]"
            f" - `{event.record.activity_kind}` - delta `{delta or '0'}` - closing `{closing or '0'}`"
        )
    return "\n".join(lines) + "\n"


def history_note_body(frontmatter: dict[str, Any], events: list[HoldingEvent]) -> str:
    symbol = str(frontmatter["instrument_symbol"])
    lines = [
        f"# {symbol} Holdings History",
        "",
        "Derived holdings history note.",
        "",
        "## Summary",
        f"- Symbol: `{symbol}`",
    ]
    if frontmatter.get("instrument_market"):
        lines.append(f"- Market: `{frontmatter['instrument_market']}`")
    lines.append(
        "- Providers: "
        + ", ".join(f"`{label}`" for label in normalize_provider_labels(frontmatter["brokerage_providers"]))
    )
    lines.extend(
        [
            f"- First Snapshot: `{frontmatter['first_snapshot_date']}`",
            f"- Last Snapshot: `{frontmatter['last_snapshot_date']}`",
            f"- Snapshot Count: `{frontmatter['snapshot_count']}`",
            f"- Current Quantity: {format_number(frontmatter.get('current_quantity')) or '0'}",
            f"- Max Quantity: {format_number(frontmatter.get('max_quantity')) or '0'}",
            f"- Min Quantity: {format_number(frontmatter.get('min_quantity')) or '0'}",
            f"- Review Status: `{frontmatter['review_status']}`",
            f"- Current Note: [[{current_relative_path(symbol).with_suffix('').as_posix()}|{symbol}]]",
            "",
            "## Timeline",
            "",
            "| Date | Kind | Provider | Delta | Closing Quantity | Net Cash | Activity |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for event in events:
        currency = event.record.currency or "AUD"
        delta = format_number(event.quantity_delta) or "0"
        closing = format_number(event.closing_quantity) or "0"
        net_cash = format_money(event.record.net_amount, currency) or ""
        file_name = Path(event.record.relative_path).stem
        lines.append(
            f"| {event.record.activity_date} | `{event.record.activity_kind}` | `{provider_label(event.record.brokerage_provider)}` | {delta} | {closing} | {net_cash} | [[{Path(event.record.relative_path).with_suffix('').as_posix()}|{file_name}]] |"
        )
    return "\n".join(lines) + "\n"


def run_sync(
    *,
    root: Path,
    mode: str,
    activity_glob: str = BROKERAGE_ACTIVITY_GLOB,
) -> dict[str, Any]:
    records = load_activity_records(root, activity_glob=activity_glob)
    grouped: dict[str, list[ActivityRecord]] = defaultdict(list)
    for record in records:
        grouped[record.instrument_symbol].append(record)

    current_registry, current_collisions = build_note_registry(root, CURRENT_HOLDINGS_DIR)
    history_registry, history_collisions = build_note_registry(root, HOLDINGS_HISTORY_DIR)

    current_created = 0
    current_updated = 0
    current_unchanged = 0
    history_created = 0
    history_updated = 0
    history_unchanged = 0
    current_notes: list[dict[str, str]] = []
    history_notes: list[dict[str, str]] = []
    warnings: list[str] = []

    for symbol, paths in sorted(current_collisions.items()):
        warnings.append(f"Existing current holding collision for symbol `{symbol}`: {', '.join(paths)}")
    for symbol, paths in sorted(history_collisions.items()):
        warnings.append(f"Existing history holding collision for symbol `{symbol}`: {', '.join(paths)}")

    for symbol in sorted(grouped):
        symbol_records = grouped[symbol]
        events = build_events(symbol_records)

        desired_current = build_current_frontmatter(symbol, symbol_records, events)
        existing_current = current_registry.get(symbol)
        current_frontmatter = merge_frontmatter(existing_current.frontmatter if existing_current else None, desired_current, CURRENT_FRONTMATTER_ORDER)
        current_body = current_note_body(current_frontmatter, events)
        current_rendered = render_markdown(current_frontmatter, current_body, order=CURRENT_FRONTMATTER_ORDER)
        current_target = existing_current.path if existing_current else root / current_relative_path(symbol)
        current_relative = str(current_target.relative_to(root))

        if existing_current is None:
            current_status = "created"
            current_created += 1
        elif existing_current.text == current_rendered:
            current_status = "unchanged"
            current_unchanged += 1
        else:
            current_status = "updated"
            current_updated += 1

        if mode == "fix" and current_status != "unchanged":
            current_target.parent.mkdir(parents=True, exist_ok=True)
            current_target.write_text(current_rendered, encoding="utf-8")
        current_notes.append({"path": current_relative, "status": current_status})

        desired_history = build_history_frontmatter(symbol, symbol_records, events)
        existing_history = history_registry.get(symbol)
        history_frontmatter = merge_frontmatter(existing_history.frontmatter if existing_history else None, desired_history, HISTORY_FRONTMATTER_ORDER)
        history_body = history_note_body(history_frontmatter, events)
        history_rendered = render_markdown(history_frontmatter, history_body, order=HISTORY_FRONTMATTER_ORDER)
        history_target = existing_history.path if existing_history else root / history_relative_path(symbol)
        history_relative = str(history_target.relative_to(root))

        if existing_history is None:
            history_status = "created"
            history_created += 1
        elif existing_history.text == history_rendered:
            history_status = "unchanged"
            history_unchanged += 1
        else:
            history_status = "updated"
            history_updated += 1

        if mode == "fix" and history_status != "unchanged":
            history_target.parent.mkdir(parents=True, exist_ok=True)
            history_target.write_text(history_rendered, encoding="utf-8")
        history_notes.append({"path": history_relative, "status": history_status})

    return {
        "ok": True,
        "symbols": len(grouped),
        "activity_records": len(records),
        "current_created": current_created,
        "current_updated": current_updated,
        "current_unchanged": current_unchanged,
        "history_created": history_created,
        "history_updated": history_updated,
        "history_unchanged": history_unchanged,
        "current_notes": current_notes,
        "history_notes": history_notes,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync current and historical portfolio holdings from brokerage activity notes.")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    parser.add_argument("--activity-glob", default=BROKERAGE_ACTIVITY_GLOB)
    args = parser.parse_args()

    payload = run_sync(
        root=Path.cwd(),
        mode=args.mode,
        activity_glob=args.activity_glob,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
