#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from brokerage_models import BROKERAGE_BASE_PATH


def build_base_config() -> dict[str, object]:
    return {
        "filters": {
            "and": [
                'file.ext == "md"',
                'file.inFolder("20 Resources/Investments/Brokerage Activity")',
                'brokerage_activity_kind != ""',
            ]
        },
        "formulas": {
            "symbol_display": 'if(instrument_symbol, instrument_symbol, "CASH")',
            "activity_label": 'brokerage_activity_kind.replace("_", " ").title()',
            "provider_label": 'if(brokerage_provider == "stake_au", "Stake AU", if(brokerage_provider == "stake_us", "Stake US", if(brokerage_provider == "betashares", "Betashares", brokerage_provider.replace("_", " ").title())))',
            "cash_badge": 'if(cash_direction == "inflow", "In", if(cash_direction == "outflow", "Out", "Flat"))',
            "signed_units": 'if(quantity, if(brokerage_activity_kind == "trade_sell", quantity * -1, quantity), "")',
            "merge_badge": 'if(merge_count > 1, "merged", "single")',
            "review_badge": 'if(review_status == "needs_review", "review", "ok")',
            "source_files_label": 'if(source_files, source_files.join(", "), "")',
        },
        "properties": {
            "activity_date": {"displayName": "Date"},
            "activity_month": {"displayName": "Month"},
            "brokerage_activity_kind": {"displayName": "Kind"},
            "brokerage_provider": {"displayName": "Provider"},
            "instrument_symbol": {"displayName": "Symbol"},
            "asset_note": {"displayName": "Asset"},
            "instrument_market": {"displayName": "Market"},
            "instrument_kind": {"displayName": "Instrument"},
            "activity_status": {"displayName": "Status"},
            "net_amount": {"displayName": "Net Amount"},
            "gross_amount": {"displayName": "Gross Amount"},
            "quantity": {"displayName": "Units"},
            "unit_price": {"displayName": "Unit Price"},
            "fee_amount": {"displayName": "Fee"},
            "tax_amount": {"displayName": "Tax"},
            "cash_direction": {"displayName": "Cash Flow"},
            "merge_count": {"displayName": "Merge Count"},
            "review_status": {"displayName": "Review"},
            "source_files": {"displayName": "Source Files"},
            "formula.symbol_display": {"displayName": "Symbol"},
            "formula.activity_label": {"displayName": "Activity"},
            "formula.provider_label": {"displayName": "Provider"},
            "formula.cash_badge": {"displayName": "Flow"},
            "formula.signed_units": {"displayName": "Signed Units"},
            "formula.merge_badge": {"displayName": "Merge"},
            "formula.review_badge": {"displayName": "Review"},
            "formula.source_files_label": {"displayName": "Sources"},
        },
        "views": [
            {
                "type": "table",
                "name": "Activity Ledger",
                "groupBy": {"property": "activity_month", "direction": "DESC"},
                "order": [
                    "activity_date",
                    "formula.symbol_display",
                    "asset_note",
                    "formula.activity_label",
                    "net_amount",
                    "quantity",
                    "unit_price",
                    "formula.cash_badge",
                    "formula.provider_label",
                    "activity_status",
                    "formula.merge_badge",
                    "formula.review_badge",
                ],
                "summaries": {
                    "net_amount": "Sum",
                    "merge_count": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Trade Flow",
                "filters": {
                    "or": [
                        'brokerage_activity_kind == "trade_buy"',
                        'brokerage_activity_kind == "trade_sell"',
                    ]
                },
                "groupBy": {"property": "instrument_symbol", "direction": "ASC"},
                "order": [
                    "activity_date",
                    "instrument_symbol",
                    "asset_note",
                    "brokerage_activity_kind",
                    "quantity",
                    "formula.signed_units",
                    "unit_price",
                    "net_amount",
                    "fee_amount",
                    "formula.provider_label",
                    "activity_status",
                ],
                "summaries": {
                    "formula.signed_units": "Sum",
                    "net_amount": "Sum",
                    "fee_amount": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Distributions",
                "filters": {
                    "or": [
                        'brokerage_activity_kind == "distribution"',
                        'brokerage_activity_kind == "distribution_reinvestment"',
                    ]
                },
                "groupBy": {"property": "instrument_symbol", "direction": "ASC"},
                "order": [
                    "activity_date",
                    "instrument_symbol",
                    "asset_note",
                    "brokerage_activity_kind",
                    "net_amount",
                    "quantity",
                    "unit_price",
                    "formula.provider_label",
                    "merge_count",
                ],
                "summaries": {
                    "net_amount": "Sum",
                    "quantity": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Cash Movements",
                "filters": {
                    "or": [
                        'brokerage_activity_kind == "cash_deposit"',
                        'brokerage_activity_kind == "cash_withdrawal"',
                        'brokerage_activity_kind == "fee"',
                        'brokerage_activity_kind == "tax"',
                        'brokerage_activity_kind == "cash_interest"',
                        'brokerage_activity_kind == "fx"',
                        'brokerage_activity_kind == "adjustment"',
                    ]
                },
                "order": [
                    "activity_date",
                    "brokerage_activity_kind",
                    "net_amount",
                    "fee_amount",
                    "tax_amount",
                    "formula.cash_badge",
                    "formula.provider_label",
                    "formula.review_badge",
                ],
                "summaries": {
                    "net_amount": "Sum",
                    "fee_amount": "Sum",
                    "tax_amount": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Review Queue",
                "filters": {
                    "or": [
                        'review_status == "needs_review"',
                        'merge_count > 1',
                        'activity_status != "completed"',
                    ]
                },
                "order": [
                    "activity_date",
                    "formula.symbol_display",
                    "asset_note",
                    "brokerage_activity_kind",
                    "activity_status",
                    "formula.review_badge",
                    "merge_count",
                    "formula.source_files_label",
                ],
                "summaries": {
                    "merge_count": "Sum",
                },
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Brokerage Activity.base file.")
    parser.add_argument("--output", default=str(BROKERAGE_BASE_PATH))
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(build_base_config(), sort_keys=False, allow_unicode=False, width=1000),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
