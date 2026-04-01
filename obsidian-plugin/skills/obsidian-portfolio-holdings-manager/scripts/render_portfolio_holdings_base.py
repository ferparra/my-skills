#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from portfolio_holdings_models import CURRENT_HOLDINGS_BASE_PATH


def build_base_config() -> dict[str, object]:
    return {
        "filters": {
            "and": [
                'file.ext == "md"',
                'file.inFolder("20 Resources/Investments/Portfolio Holdings")',
                'portfolio_holding_kind == "current_position"',
            ]
        },
        "formulas": {
            "provider_label": 'if(brokerage_providers, brokerage_providers.join(", ").replace("stake_au", "Stake AU").replace("stake_us", "Stake US").replace("betashares", "Betashares"), "")',
            "holding_badge": 'if(current_quantity > 0, "active", if(current_quantity < 0, "review", "flat"))',
            "review_badge": 'if(review_status == "needs_review", "review", "ok")',
        },
        "properties": {
            "instrument_symbol": {"displayName": "Symbol"},
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
            "current_quantity": {"displayName": "Current Quantity"},
            "currency": {"displayName": "Currency"},
            "cumulative_net_cash_flow": {"displayName": "Net Cash Flow"},
            "cumulative_fees": {"displayName": "Fees"},
            "cumulative_taxes": {"displayName": "Taxes"},
            "review_status": {"displayName": "Review"},
            "formula.provider_label": {"displayName": "Providers"},
            "formula.holding_badge": {"displayName": "Holding"},
            "formula.review_badge": {"displayName": "Review"},
        },
        "views": [
            {
                "type": "table",
                "name": "Active Holdings",
                "filters": {"and": ['current_quantity > 0']},
                "order": [
                    "instrument_symbol",
                    "formula.provider_label",
                    "current_quantity",
                    "cumulative_net_cash_flow",
                    "last_activity_date",
                    "formula.holding_badge",
                    "formula.review_badge",
                ],
                "summaries": {
                    "current_quantity": "Sum",
                    "cumulative_net_cash_flow": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Flat Or Exited",
                "filters": {"and": ['current_quantity <= 0']},
                "order": [
                    "instrument_symbol",
                    "formula.provider_label",
                    "current_quantity",
                    "last_trade_date",
                    "formula.holding_badge",
                    "formula.review_badge",
                ],
            },
            {
                "type": "table",
                "name": "Review Queue",
                "filters": {"or": ['review_status == "needs_review"', "current_quantity < 0"]},
                "order": [
                    "instrument_symbol",
                    "current_quantity",
                    "formula.provider_label",
                    "last_activity_date",
                    "formula.review_badge",
                ],
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Portfolio Holdings.base file.")
    parser.add_argument("--output", default=str(CURRENT_HOLDINGS_BASE_PATH))
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
