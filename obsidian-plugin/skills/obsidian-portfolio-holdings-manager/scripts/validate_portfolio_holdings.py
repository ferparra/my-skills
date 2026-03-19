#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, TypedDict

from portfolio_holdings_models import (
    BROKERAGE_ACTIVITY_GLOB,
    CURRENT_HOLDINGS_GLOB,
    HOLDINGS_HISTORY_GLOB,
    PortfolioHoldingFrontmatter,
    PortfolioHoldingHistoryFrontmatter,
    load_markdown_note,
    parse_number,
)
from sync_portfolio_holdings import build_events, load_activity_records
from sync_portfolio_holdings import ActivityRecord


class NoteIndexEntry(TypedDict):
    path: str
    frontmatter: dict[str, Any]


def validate_glob(root: Path, glob_pattern: str, *, history: bool) -> tuple[int, list[dict[str, str]], dict[str, list[str]]]:
    checked = 0
    invalid: list[dict[str, str]] = []
    collisions: dict[str, list[str]] = defaultdict(list)
    model = PortfolioHoldingHistoryFrontmatter if history else PortfolioHoldingFrontmatter

    for path in sorted(root.glob(glob_pattern)):
        note = load_markdown_note(path)
        checked += 1
        symbol = str(note.frontmatter.get("instrument_symbol") or "").strip().upper()
        if symbol:
            collisions[symbol].append(str(path.relative_to(root)))
        try:
            model.model_validate(note.frontmatter)
        except Exception as exc:
            invalid.append({"path": str(path.relative_to(root)), "error": str(exc)})

    duplicates = {symbol: paths for symbol, paths in collisions.items() if len(paths) > 1}
    return checked, invalid, duplicates


def note_index(root: Path, glob_pattern: str) -> dict[str, NoteIndexEntry]:
    notes: dict[str, NoteIndexEntry] = {}
    for path in sorted(root.glob(glob_pattern)):
        note = load_markdown_note(path)
        symbol = str(note.frontmatter.get("instrument_symbol") or "").strip().upper()
        if symbol and symbol not in notes:
            notes[symbol] = {
                "path": str(path.relative_to(root)),
                "frontmatter": note.frontmatter,
            }
    return notes


def reconcile_against_activity(
    root: Path,
    *,
    activity_glob: str = BROKERAGE_ACTIVITY_GLOB,
    current_glob: str = CURRENT_HOLDINGS_GLOB,
    history_glob: str = HOLDINGS_HISTORY_GLOB,
) -> dict[str, object]:
    records_by_symbol: dict[str, list[ActivityRecord]] = defaultdict(list)
    for record in load_activity_records(root, activity_glob=activity_glob):
        records_by_symbol[record.instrument_symbol].append(record)

    current_notes = note_index(root, current_glob)
    history_notes = note_index(root, history_glob)

    missing_current_symbols: list[str] = []
    missing_history_symbols: list[str] = []
    current_quantity_mismatches: list[dict[str, object]] = []
    history_quantity_mismatches: list[dict[str, object]] = []
    current_activity_count_mismatches: list[dict[str, object]] = []
    history_activity_count_mismatches: list[dict[str, object]] = []

    for symbol in sorted(records_by_symbol):
        records = records_by_symbol[symbol]
        expected_count = len(records)
        expected_quantity = round(build_events(records)[-1].closing_quantity, 8)

        current_note = current_notes.get(symbol)
        if current_note is None:
            missing_current_symbols.append(symbol)
        else:
            current_frontmatter = current_note["frontmatter"]
            current_quantity = round(parse_number(current_frontmatter.get("current_quantity")) or 0.0, 8)
            current_count = int(parse_number(current_frontmatter.get("source_activity_count")) or 0)
            if current_quantity != expected_quantity:
                current_quantity_mismatches.append(
                    {
                        "symbol": symbol,
                        "path": current_note["path"],
                        "expected": expected_quantity,
                        "actual": current_quantity,
                    }
                )
            if current_count != expected_count:
                current_activity_count_mismatches.append(
                    {
                        "symbol": symbol,
                        "path": current_note["path"],
                        "expected": expected_count,
                        "actual": current_count,
                    }
                )

        history_note = history_notes.get(symbol)
        if history_note is None:
            missing_history_symbols.append(symbol)
        else:
            history_frontmatter = history_note["frontmatter"]
            history_quantity = round(parse_number(history_frontmatter.get("current_quantity")) or 0.0, 8)
            history_count = int(parse_number(history_frontmatter.get("source_activity_count")) or 0)
            if history_quantity != expected_quantity:
                history_quantity_mismatches.append(
                    {
                        "symbol": symbol,
                        "path": history_note["path"],
                        "expected": expected_quantity,
                        "actual": history_quantity,
                    }
                )
            if history_count != expected_count:
                history_activity_count_mismatches.append(
                    {
                        "symbol": symbol,
                        "path": history_note["path"],
                        "expected": expected_count,
                        "actual": history_count,
                    }
                )

    return {
        "ledger_symbols": len(records_by_symbol),
        "missing_current_symbols": missing_current_symbols,
        "missing_history_symbols": missing_history_symbols,
        "current_quantity_mismatches": current_quantity_mismatches,
        "history_quantity_mismatches": history_quantity_mismatches,
        "current_activity_count_mismatches": current_activity_count_mismatches,
        "history_activity_count_mismatches": history_activity_count_mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate portfolio holdings notes.")
    parser.add_argument("--activity-glob", default=BROKERAGE_ACTIVITY_GLOB)
    parser.add_argument("--glob-current", default=CURRENT_HOLDINGS_GLOB)
    parser.add_argument("--glob-history", default=HOLDINGS_HISTORY_GLOB)
    args = parser.parse_args()

    root = Path.cwd()
    current_checked, current_invalid, current_duplicates = validate_glob(root, args.glob_current, history=False)
    history_checked, history_invalid, history_duplicates = validate_glob(root, args.glob_history, history=True)
    reconciliation = reconcile_against_activity(
        root,
        activity_glob=args.activity_glob,
        current_glob=args.glob_current,
        history_glob=args.glob_history,
    )
    payload = {
        "ok": not current_invalid
        and not history_invalid
        and not current_duplicates
        and not history_duplicates
        and not reconciliation["missing_current_symbols"]
        and not reconciliation["missing_history_symbols"]
        and not reconciliation["current_quantity_mismatches"]
        and not reconciliation["history_quantity_mismatches"]
        and not reconciliation["current_activity_count_mismatches"]
        and not reconciliation["history_activity_count_mismatches"],
        "current_checked": current_checked,
        "history_checked": history_checked,
        "current_invalid": current_invalid,
        "history_invalid": history_invalid,
        "current_duplicate_symbols": current_duplicates,
        "history_duplicate_symbols": history_duplicates,
        **reconciliation,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
