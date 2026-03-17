#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brokerage_models import (
    BROKERAGE_ASSETS_DIR,
    BROKERAGE_NOTES_DIR,
    BrokerageActivityFrontmatter,
    BrokerageActivityKind,
    BrokerageActivityStatus,
    BrokerageProvider,
    CashDirection,
    InstrumentKind,
    ReviewStatus,
    dump_json,
    load_markdown_note,
    make_activity_id,
    normalize_tags,
    provider_label,
    render_markdown,
)
from sync_brokerage_activity import (
    aggregate_assets,
    activity_asset_link,
    build_frontmatter,
    canonical_number,
    build_asset_frontmatter,
    build_asset_registry,
    build_registry,
    merge_asset_frontmatter,
    note_relative_path,
    parse_number,
    record_from_frontmatter,
    render_asset_markdown,
    render_asset_note_body,
)


@dataclass
class ValuationPosition:
    symbol: str
    quantity: float
    provider: BrokerageProvider
    instrument_market: str
    currency: str


@dataclass
class ValuationSnapshot:
    note_path: Path
    statement_date: str
    source_file: str | None
    positions: dict[str, ValuationPosition]


SECTION_CONFIG = {
    "AU Equities": {
        "provider": BrokerageProvider.STAKE_AU,
        "instrument_market": "ASX",
        "currency": "AUD",
    },
    "Wall St Equities": {
        "provider": BrokerageProvider.STAKE_US,
        "instrument_market": "US",
        "currency": "USD",
    },
}


def parse_markdown_table(lines: list[str]) -> list[dict[str, str]]:
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(cell and set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        if header:
            rows.append(
                {
                    header[idx]: cells[idx] if idx < len(cells) else ""
                    for idx in range(len(header))
                }
            )
    return rows


def load_latest_snapshot(root: Path, *, note_glob: str) -> ValuationSnapshot | None:
    candidates: list[tuple[str, Path]] = []
    for path in sorted(root.glob(note_glob)):
        note = load_markdown_note(path)
        frontmatter = note.frontmatter
        if str(frontmatter.get("report_type") or "").strip() != "portfolio_valuation":
            continue
        statement_date = str(frontmatter.get("statement_date") or "").strip()
        if not statement_date:
            continue
        candidates.append((statement_date, path))

    if not candidates:
        return None

    _, path = max(candidates, key=lambda item: (item[0], str(item[1])))
    note = load_markdown_note(path)
    frontmatter = note.frontmatter
    statement_date = str(frontmatter["statement_date"]).strip()

    section_lines: dict[str, list[str]] = defaultdict(list)
    current_section: str | None = None
    for line in note.body.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue
        if current_section in SECTION_CONFIG:
            section_lines[current_section].append(line)

    positions: dict[str, ValuationPosition] = {}
    for section, config in SECTION_CONFIG.items():
        for row in parse_markdown_table(section_lines.get(section, [])):
            symbol = str(row.get("Symbol") or "").strip().upper()
            quantity = parse_number(row.get("Units"))
            if not symbol or quantity is None:
                continue
            positions[symbol] = ValuationPosition(
                symbol=symbol,
                quantity=canonical_number(quantity) or 0.0,
                provider=config["provider"],
                instrument_market=str(config["instrument_market"]),
                currency=str(config["currency"]),
            )

    return ValuationSnapshot(
        note_path=path.relative_to(root),
        statement_date=statement_date,
        source_file=str(frontmatter.get("source_file") or "").strip() or None,
        positions=positions,
    )


def current_quantities_from_registry(root: Path) -> dict[str, dict[str, Any]]:
    registry, _ = build_registry(root, BROKERAGE_NOTES_DIR)
    records_by_signature = {
        signature: record_from_frontmatter(existing.frontmatter)
        for signature, existing in registry.items()
    }
    quantities: dict[str, dict[str, Any]] = {}
    for aggregate in aggregate_assets(list(records_by_signature.values())):
        frontmatter = build_asset_frontmatter(aggregate)
        quantities[aggregate.symbol] = {
            "quantity": canonical_number(parse_number(frontmatter.get("estimated_open_quantity"))) or 0.0,
            "instrument_market": frontmatter.get("instrument_market"),
            "instrument_kind": frontmatter.get("instrument_kind"),
            "currency": frontmatter.get("currency"),
        }
    return quantities


def build_reconciliation_frontmatter(
    *,
    snapshot: ValuationSnapshot,
    position: ValuationPosition,
    ledger_quantity: float,
    instrument_market: str,
    instrument_kind: str,
    currency: str,
) -> dict[str, Any]:
    adjustment_quantity = canonical_number(position.quantity - ledger_quantity) or 0.0
    source_signature = json.dumps(
        {
            "reconciliation": "portfolio_valuation",
            "statement_date": snapshot.statement_date,
            "symbol": position.symbol,
            "provider": position.provider.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    source_signature = hashlib.sha1(source_signature.encode("utf-8")).hexdigest()[:16]
    row_hash_payload = json.dumps(
        {
            "statement_date": snapshot.statement_date,
            "symbol": position.symbol,
            "reported_quantity": position.quantity,
            "ledger_quantity": ledger_quantity,
            "source_note": str(snapshot.note_path),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    row_hash = hashlib.sha1(row_hash_payload.encode("utf-8")).hexdigest()[:16]
    frontmatter = {
        "brokerage_activity_id": make_activity_id(source_signature),
        "brokerage_activity_kind": BrokerageActivityKind.ADJUSTMENT.value,
        "brokerage_provider": position.provider.value,
        "raw_activity_type": "portfolio_valuation_reconciliation",
        "activity_date": snapshot.statement_date,
        "activity_year": int(snapshot.statement_date[:4]),
        "activity_month": snapshot.statement_date[:7],
        "activity_status": BrokerageActivityStatus.COMPLETED.value,
        "instrument_symbol": position.symbol,
        "instrument_market": instrument_market,
        "instrument_kind": instrument_kind,
        "asset_note": activity_asset_link(position.symbol),
        "currency": currency,
        "net_amount": 0.0,
        "quantity": adjustment_quantity,
        "cash_direction": CashDirection.NEUTRAL.value,
        "review_status": ReviewStatus.OK.value,
        "source_signature": source_signature,
        "source_files": [snapshot.note_path.name],
        "source_file_count": 1,
        "source_row_hashes": [row_hash],
        "source_row_count": 1,
        "merge_count": 1,
        "valuation_statement_date": snapshot.statement_date,
        "valuation_snapshot_note": snapshot.note_path.as_posix(),
        "reported_quantity": position.quantity,
        "ledger_quantity_before_adjustment": canonical_number(ledger_quantity),
        "tags": normalize_tags([], position.provider, BrokerageActivityKind.ADJUSTMENT),
    }
    BrokerageActivityFrontmatter.model_validate(frontmatter)
    return frontmatter


def render_reconciliation_body(frontmatter: dict[str, Any], *, snapshot: ValuationSnapshot) -> str:
    snapshot_link = Path(snapshot.note_path).with_suffix("").as_posix()
    lines = [
        f"# {frontmatter['activity_date']} {frontmatter['instrument_symbol']} adjustment",
        "",
        "Managed brokerage activity reconciliation note.",
        "",
        "## Reconciliation",
        f"- Kind: `{frontmatter['brokerage_activity_kind']}`",
        f"- Provider: `{provider_label(frontmatter['brokerage_provider'])}`",
        f"- Symbol: `{frontmatter['instrument_symbol']}`",
        f"- Market: `{frontmatter['instrument_market']}`",
        f"- Reported Quantity: `{frontmatter['reported_quantity']}`",
        f"- Ledger Quantity Before Adjustment: `{frontmatter['ledger_quantity_before_adjustment']}`",
        f"- Adjustment Quantity: `{frontmatter['quantity']}`",
        f"- Currency: `{frontmatter['currency']}`",
        f"- Snapshot: [[{snapshot_link}|{snapshot.note_path.stem}]]",
    ]
    if snapshot.source_file:
        lines.append(f"- Snapshot Source File: {snapshot.source_file}")
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


def rebuild_assets(
    root: Path,
    *,
    registry_frontmatters: dict[str, dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    asset_registry, _ = build_asset_registry(root, BROKERAGE_ASSETS_DIR)
    full_records = {
        signature: record_from_frontmatter(frontmatter)
        for signature, frontmatter in registry_frontmatters.items()
    }
    asset_aggregates = aggregate_assets(list(full_records.values()))
    asset_created = 0
    asset_updated = 0
    asset_unchanged = 0
    asset_notes: list[dict[str, str]] = []

    for aggregate in asset_aggregates:
        desired_frontmatter = build_asset_frontmatter(aggregate)
        existing_asset = asset_registry.get(aggregate.symbol)
        target_path = existing_asset.path if existing_asset else root / BROKERAGE_ASSETS_DIR / f"{aggregate.symbol}.md"
        merged_frontmatter = merge_asset_frontmatter(
            existing_asset.frontmatter if existing_asset else None,
            desired_frontmatter,
        )
        activity_paths = [
            str(note_relative_path(build_frontmatter(record)))
            for record in sorted(
                (
                    record_from_frontmatter(registry_frontmatters[signature])
                    for signature in merged_frontmatter["source_activity_signatures"]
                ),
                key=lambda item: item.activity_date,
                reverse=True,
            )
        ]
        rendered = render_asset_markdown(
            merged_frontmatter,
            render_asset_note_body(merged_frontmatter, activity_paths),
        )
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
        "asset_created": asset_created,
        "asset_updated": asset_updated,
        "asset_unchanged": asset_unchanged,
        "asset_notes": asset_notes,
    }


def run_reconciliation(root: Path, *, note_glob: str, mode: str, tolerance: float = 1e-6) -> dict[str, Any]:
    snapshot = load_latest_snapshot(root, note_glob=note_glob)
    if snapshot is None:
        return {
            "ok": False,
            "error": "portfolio_valuation_snapshot_not_found",
            "note_glob": note_glob,
        }

    registry, registry_collisions = build_registry(root, BROKERAGE_NOTES_DIR)
    ledger_quantities = current_quantities_from_registry(root)
    note_results: list[dict[str, Any]] = []
    registry_frontmatters = {signature: dict(existing.frontmatter) for signature, existing in registry.items()}

    for position in snapshot.positions.values():
        ledger_state = ledger_quantities.get(position.symbol, {})
        ledger_quantity = canonical_number(parse_number(ledger_state.get("quantity"))) or 0.0
        if abs(position.quantity - ledger_quantity) <= tolerance:
            continue

        instrument_market = str(ledger_state.get("instrument_market") or position.instrument_market)
        instrument_kind = str(ledger_state.get("instrument_kind") or InstrumentKind.LISTED_SECURITY.value)
        currency = str(ledger_state.get("currency") or position.currency)
        frontmatter = build_reconciliation_frontmatter(
            snapshot=snapshot,
            position=position,
            ledger_quantity=ledger_quantity,
            instrument_market=instrument_market,
            instrument_kind=instrument_kind,
            currency=currency,
        )
        body = render_reconciliation_body(frontmatter, snapshot=snapshot)
        rendered = render_markdown(frontmatter, body)
        existing = registry.get(frontmatter["source_signature"])
        target_path = existing.path if existing else root / note_relative_path(frontmatter)
        relative_path = str(target_path.relative_to(root))
        if existing is None:
            status = "created"
        elif existing.text == rendered:
            status = "unchanged"
        else:
            status = "updated"

        if mode == "fix" and status != "unchanged":
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(rendered, encoding="utf-8")

        registry_frontmatters[frontmatter["source_signature"]] = dict(frontmatter)
        note_results.append(
            {
                "symbol": position.symbol,
                "path": relative_path,
                "status": status,
                "reported_quantity": position.quantity,
                "ledger_quantity_before_adjustment": ledger_quantity,
                "adjustment_quantity": frontmatter["quantity"],
            }
        )

    asset_result = rebuild_assets(root, registry_frontmatters=registry_frontmatters, mode=mode)
    return {
        "ok": True,
        "statement_date": snapshot.statement_date,
        "snapshot_note": str(snapshot.note_path),
        "snapshot_positions": len(snapshot.positions),
        "registry_collisions": registry_collisions,
        "reconciled_symbols": len(note_results),
        "notes": note_results,
        **asset_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile brokerage holdings against the latest portfolio valuation snapshot.")
    parser.add_argument("--note-glob", default="00 Inbox/**/*.md")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    args = parser.parse_args()

    payload = run_reconciliation(Path.cwd(), note_glob=args.note_glob, mode=args.mode)
    print(dump_json(payload))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
