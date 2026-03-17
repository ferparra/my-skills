#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from brokerage_models import BROKERAGE_ASSET_BASE_PATH


def build_asset_base_config() -> dict[str, object]:
    return {
        "filters": {
            "and": [
                'file.ext == "md"',
                'file.inFolder("20 Resources/Investments/Brokerage Assets")',
                'brokerage_asset_kind != ""',
            ]
        },
        "formulas": {
            "provider_label": 'if(brokerage_providers, brokerage_providers.join(", ").replace("stake_au", "Stake AU").replace("stake_us", "Stake US").replace("betashares", "Betashares"), "")',
            "asset_label": 'brokerage_asset_kind.replace("_", " ").title()',
            "activity_span_days": '(date(last_activity_date) - date(first_activity_date)).days',
            "review_badge": 'if(review_status == "needs_review", "review", "ok")',
        },
        "properties": {
            "instrument_symbol": {"displayName": "Symbol"},
            "brokerage_asset_kind": {"displayName": "Kind"},
            "instrument_market": {"displayName": "Market"},
            "instrument_kind": {"displayName": "Instrument"},
            "brokerage_providers": {"displayName": "Providers"},
            "first_activity_date": {"displayName": "First Activity"},
            "last_activity_date": {"displayName": "Last Activity"},
            "last_trade_date": {"displayName": "Last Trade"},
            "activity_count": {"displayName": "Activity Count"},
            "trade_buy_count": {"displayName": "Buys"},
            "trade_sell_count": {"displayName": "Sells"},
            "distribution_count": {"displayName": "Distributions"},
            "distribution_reinvestment_count": {"displayName": "DRP Events"},
            "estimated_open_quantity": {"displayName": "Open Quantity"},
            "last_unit_price": {"displayName": "Last Unit Price"},
            "cumulative_net_cash_flow": {"displayName": "Net Cash Flow"},
            "cumulative_fees": {"displayName": "Fees"},
            "cumulative_taxes": {"displayName": "Taxes"},
            "review_status": {"displayName": "Review"},
            "formula.provider_label": {"displayName": "Providers"},
            "formula.asset_label": {"displayName": "Asset Kind"},
            "formula.activity_span_days": {"displayName": "Span Days"},
            "formula.review_badge": {"displayName": "Review"},
        },
        "views": [
            {
                "type": "table",
                "name": "Asset Registry",
                "order": [
                    "instrument_symbol",
                    "formula.asset_label",
                    "formula.provider_label",
                    "last_activity_date",
                    "estimated_open_quantity",
                    "cumulative_net_cash_flow",
                    "distribution_count",
                    "distribution_reinvestment_count",
                    "formula.review_badge",
                ],
                "summaries": {
                    "activity_count": "Sum",
                    "cumulative_net_cash_flow": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Income Assets",
                "filters": {
                    "or": [
                        'distribution_count > 0',
                        'distribution_reinvestment_count > 0',
                    ]
                },
                "order": [
                    "instrument_symbol",
                    "distribution_count",
                    "distribution_reinvestment_count",
                    "estimated_open_quantity",
                    "cumulative_net_cash_flow",
                    "last_activity_date",
                ],
                "summaries": {
                    "distribution_count": "Sum",
                    "distribution_reinvestment_count": "Sum",
                    "cumulative_net_cash_flow": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Trading Assets",
                "filters": {
                    "or": [
                        'trade_buy_count > 0',
                        'trade_sell_count > 0',
                    ]
                },
                "order": [
                    "instrument_symbol",
                    "trade_buy_count",
                    "trade_sell_count",
                    "last_trade_date",
                    "estimated_open_quantity",
                    "last_unit_price",
                    "cumulative_fees",
                ],
                "summaries": {
                    "trade_buy_count": "Sum",
                    "trade_sell_count": "Sum",
                    "cumulative_fees": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Review Queue",
                "filters": {
                    "or": [
                        'review_status == "needs_review"',
                        'estimated_open_quantity < 0',
                    ]
                },
                "order": [
                    "instrument_symbol",
                    "formula.review_badge",
                    "estimated_open_quantity",
                    "last_activity_date",
                    "formula.provider_label",
                ],
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Brokerage Assets.base file.")
    parser.add_argument("--output", default=str(BROKERAGE_ASSET_BASE_PATH))
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(build_asset_base_config(), sort_keys=False, allow_unicode=False, width=1000),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
