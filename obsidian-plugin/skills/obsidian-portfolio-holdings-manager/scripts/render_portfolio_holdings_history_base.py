#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from portfolio_holdings_models import HOLDINGS_HISTORY_BASE_PATH


def build_base_config() -> dict[str, object]:
    return {
        "filters": {
            "and": [
                'file.ext == "md"',
                'file.inFolder("20 Resources/Investments/Portfolio Holdings History")',
                'portfolio_holding_kind == "holding_history"',
            ]
        },
        "formulas": {
            "provider_label": 'if(brokerage_providers, brokerage_providers.join(", ").replace("stake_au", "Stake AU").replace("stake_us", "Stake US").replace("betashares", "Betashares"), "")',
            "review_badge": 'if(review_status == "needs_review", "review", "ok")',
        },
        "properties": {
            "instrument_symbol": {"displayName": "Symbol"},
            "instrument_market": {"displayName": "Market"},
            "brokerage_providers": {"displayName": "Providers"},
            "first_snapshot_date": {"displayName": "First Snapshot"},
            "last_snapshot_date": {"displayName": "Last Snapshot"},
            "snapshot_count": {"displayName": "Snapshots"},
            "current_quantity": {"displayName": "Current Quantity"},
            "max_quantity": {"displayName": "Max Quantity"},
            "min_quantity": {"displayName": "Min Quantity"},
            "review_status": {"displayName": "Review"},
            "formula.provider_label": {"displayName": "Providers"},
            "formula.review_badge": {"displayName": "Review"},
        },
        "views": [
            {
                "type": "table",
                "name": "Holdings History",
                "order": [
                    "instrument_symbol",
                    "formula.provider_label",
                    "snapshot_count",
                    "current_quantity",
                    "last_snapshot_date",
                    "formula.review_badge",
                ],
                "summaries": {
                    "snapshot_count": "Sum",
                },
            },
            {
                "type": "table",
                "name": "Review Queue",
                "filters": {"or": ['review_status == "needs_review"', "current_quantity < 0"]},
                "order": [
                    "instrument_symbol",
                    "current_quantity",
                    "min_quantity",
                    "last_snapshot_date",
                    "formula.provider_label",
                    "formula.review_badge",
                ],
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Portfolio Holdings History.base file.")
    parser.add_argument("--output", default=str(HOLDINGS_HISTORY_BASE_PATH))
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
