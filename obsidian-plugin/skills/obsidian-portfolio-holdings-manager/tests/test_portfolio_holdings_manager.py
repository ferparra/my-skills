#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
BROKERAGE_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "obsidian-brokerage-activity-manager" / "scripts"
sys.path.insert(0, str(BROKERAGE_SCRIPTS_DIR))

from portfolio_holdings_models import CURRENT_HOLDINGS_DIR, HOLDINGS_HISTORY_DIR, load_markdown_note
from reconcile_portfolio_valuation import run_reconciliation
from render_portfolio_holdings_base import build_base_config as build_current_base_config
from render_portfolio_holdings_history_base import build_base_config as build_history_base_config
from sync_portfolio_holdings import run_sync
from validate_portfolio_holdings import reconcile_against_activity


def write_note(path: Path, frontmatter: dict[str, object], body: str = "# Fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False, width=1000).strip()
    path.write_text(f"---\n{payload}\n---\n\n{body}", encoding="utf-8")


def test_sync_portfolio_holdings_builds_current_and_history_notes(tmp_path: Path) -> None:
    activity_dir = tmp_path / "20 Resources/Investments/Brokerage Activity/2026"
    notes = [
        (
            "2026-01-10 AAA trade-buy ba-buy000001.md",
            {
                "brokerage_activity_kind": "trade_buy",
                "brokerage_provider": "betashares",
                "activity_date": "2026-01-10",
                "activity_status": "completed",
                "instrument_symbol": "AAA",
                "instrument_market": "AU",
                "instrument_kind": "listed_security",
                "currency": "AUD",
                "net_amount": -5000,
                "quantity": 100,
                "review_status": "ok",
                "source_signature": "sig-buy-1",
            },
        ),
        (
            "2026-02-10 AAA distribution ba-dist000001.md",
            {
                "brokerage_activity_kind": "distribution",
                "brokerage_provider": "betashares",
                "activity_date": "2026-02-10",
                "activity_status": "completed",
                "instrument_symbol": "AAA",
                "instrument_market": "AU",
                "instrument_kind": "listed_security",
                "currency": "AUD",
                "net_amount": 20,
                "review_status": "ok",
                "source_signature": "sig-dist-1",
            },
        ),
        (
            "2026-02-11 AAA distribution-reinvestment ba-drp0000001.md",
            {
                "brokerage_activity_kind": "distribution_reinvestment",
                "brokerage_provider": "betashares",
                "activity_date": "2026-02-11",
                "activity_status": "completed",
                "instrument_symbol": "AAA",
                "instrument_market": "AU",
                "instrument_kind": "listed_security",
                "currency": "AUD",
                "net_amount": -20,
                "quantity": 0.4,
                "review_status": "ok",
                "source_signature": "sig-drp-1",
            },
        ),
        (
            "2026-03-10 AAA trade-sell ba-sell000001.md",
            {
                "brokerage_activity_kind": "trade_sell",
                "brokerage_provider": "stake_au",
                "activity_date": "2026-03-10",
                "activity_status": "completed",
                "instrument_symbol": "AAA",
                "instrument_market": "ASX",
                "instrument_kind": "listed_security",
                "currency": "AUD",
                "net_amount": 510,
                "quantity": -10,
                "fee_amount": 2.73,
                "tax_amount": 0.27,
                "review_status": "ok",
                "source_signature": "sig-sell-1",
            },
        ),
    ]
    for file_name, frontmatter in notes:
        write_note(activity_dir / file_name, frontmatter)

    result = run_sync(root=tmp_path, mode="fix")

    assert result["symbols"] == 1
    assert result["activity_records"] == 4
    assert result["current_created"] == 1
    assert result["history_created"] == 1

    current_note = load_markdown_note(tmp_path / CURRENT_HOLDINGS_DIR / "AAA.md")
    assert current_note.frontmatter["brokerage_providers"] == ["betashares", "stake_au"]
    assert current_note.frontmatter["activity_count"] == 4
    assert current_note.frontmatter["current_quantity"] == 90.4
    assert current_note.frontmatter["trade_sell_count"] == 1

    history_note = load_markdown_note(tmp_path / HOLDINGS_HISTORY_DIR / "AAA Holdings History.md")
    assert history_note.frontmatter["snapshot_count"] == 4
    assert history_note.frontmatter["current_quantity"] == 90.4
    assert history_note.frontmatter["max_quantity"] == 100.4


def test_render_base_contains_core_views() -> None:
    current_config = build_current_base_config()
    assert current_config["filters"]["and"][2] == 'portfolio_holding_kind == "current_position"'
    assert [view["name"] for view in current_config["views"]] == [
        "Active Holdings",
        "Flat Or Exited",
        "Review Queue",
    ]

    history_config = build_history_base_config()
    assert history_config["filters"]["and"][2] == 'portfolio_holding_kind == "holding_history"'
    assert [view["name"] for view in history_config["views"]] == [
        "Holdings History",
        "Review Queue",
    ]


def test_sync_portfolio_holdings_builds_stake_us_nvda_position(tmp_path: Path) -> None:
    activity_dir = tmp_path / "20 Resources/Investments/Brokerage Activity/2026"
    notes = [
        (
            "2026-01-15 NVDA trade-buy stakeus000001.md",
            {
                "brokerage_activity_kind": "trade_buy",
                "brokerage_provider": "stake_us",
                "activity_date": "2026-01-15",
                "activity_status": "completed",
                "instrument_symbol": "NVDA",
                "instrument_market": "NASDAQ",
                "instrument_kind": "listed_security",
                "currency": "USD",
                "net_amount": -1200,
                "quantity": 10,
                "review_status": "ok",
                "source_signature": "sig-nvda-buy-1",
            },
        ),
        (
            "2026-02-20 NVDA trade-sell stakeus000002.md",
            {
                "brokerage_activity_kind": "trade_sell",
                "brokerage_provider": "stake_us",
                "activity_date": "2026-02-20",
                "activity_status": "completed",
                "instrument_symbol": "NVDA",
                "instrument_market": "NASDAQ",
                "instrument_kind": "listed_security",
                "currency": "USD",
                "net_amount": 375,
                "quantity": -2.5,
                "review_status": "ok",
                "source_signature": "sig-nvda-sell-1",
            },
        ),
    ]
    for file_name, frontmatter in notes:
        write_note(activity_dir / file_name, frontmatter)

    result = run_sync(root=tmp_path, mode="fix")

    assert result["symbols"] == 1
    current_note = load_markdown_note(tmp_path / CURRENT_HOLDINGS_DIR / "NVDA.md")
    assert current_note.frontmatter["brokerage_providers"] == ["stake_us"]
    assert current_note.frontmatter["instrument_market"] == "NASDAQ"
    assert current_note.frontmatter["currency"] == "USD"
    assert current_note.frontmatter["current_quantity"] == 7.5


def test_validate_portfolio_holdings_flags_missing_symbol_backed_notes(tmp_path: Path) -> None:
    activity_dir = tmp_path / "20 Resources/Investments/Brokerage Activity/2026"
    write_note(
        activity_dir / "2026-01-15 NVDA trade-buy stakeus000001.md",
        {
            "brokerage_activity_kind": "trade_buy",
            "brokerage_provider": "stake_us",
            "activity_date": "2026-01-15",
            "activity_status": "completed",
            "instrument_symbol": "NVDA",
            "instrument_market": "NASDAQ",
            "instrument_kind": "listed_security",
            "currency": "USD",
            "net_amount": -1200,
            "quantity": 10,
            "review_status": "ok",
            "source_signature": "sig-nvda-buy-1",
        },
    )

    reconciliation = reconcile_against_activity(tmp_path)

    assert reconciliation["ledger_symbols"] == 1
    assert reconciliation["missing_current_symbols"] == ["NVDA"]
    assert reconciliation["missing_history_symbols"] == ["NVDA"]


def test_reconciliation_snapshot_updates_current_quantity_and_snapshot_only_symbols(tmp_path: Path) -> None:
    activity_dir = tmp_path / "20 Resources/Investments/Brokerage Activity/2023"
    for file_name, frontmatter in [
        (
            "2023-04-12 NVDA trade-buy ba-nvda000001.md",
            {
                "brokerage_activity_kind": "trade_buy",
                "brokerage_provider": "stake_us",
                "activity_date": "2023-04-12",
                "activity_status": "completed",
                "instrument_symbol": "NVDA",
                "instrument_market": "US",
                "instrument_kind": "listed_security",
                "currency": "USD",
                "net_amount": -59.29,
                "quantity": 7.19222356,
                "review_status": "ok",
                "source_signature": "sig-nvda-ledger-1",
            },
        ),
        (
            "2023-04-12 BN trade-buy ba-bn000001.md",
            {
                "brokerage_activity_kind": "trade_buy",
                "brokerage_provider": "stake_us",
                "activity_date": "2023-04-12",
                "activity_status": "completed",
                "instrument_symbol": "BN",
                "instrument_market": "US",
                "instrument_kind": "listed_security",
                "currency": "USD",
                "net_amount": -1000.0,
                "quantity": 69.53373253,
                "review_status": "ok",
                "source_signature": "sig-bn-ledger-1",
            },
        ),
    ]:
        write_note(activity_dir / file_name, frontmatter)

    valuation_note = tmp_path / "00 Inbox/Stake Portfolio Valuation 2026-03-12.md"
    valuation_note.parent.mkdir(parents=True, exist_ok=True)
    valuation_note.write_text(
        """---
report_type: portfolio_valuation
statement_date: 2026-03-12
source_file: '[[00 Inbox/PORTFOLIO_VALUATION_2026-03-12-2026-03-12.xlsx]]'
---

# Stake Portfolio Valuation - 2026-03-12

## Wall St Equities

| Symbol | Name | Weighting | Units | Mkt. Price | Mkt. Value (US$) | Mkt. Value (A$) |
| --- | --- | --- | --- | --- | --- | --- |
| BN | Brookfield Corp | 2.71% | 86.07287823 | 38.76 | US$3,336.18 | A$4,710.36 |
| GPRO | GoPro, Inc. | 0.00% | 1 | 0.738 | US$0.74 | A$1.04 |
| NVDA | NVIDIA Corporation | 39.48% | 264.9766027 | 183.14 | US$48,527.82 | A$68,516.48 |
""",
        encoding="utf-8",
    )

    reconciliation = run_reconciliation(tmp_path, note_glob="00 Inbox/**/*.md", mode="fix")
    assert reconciliation["ok"] is True
    assert reconciliation["reconciled_symbols"] == 3

    sync_result = run_sync(root=tmp_path, mode="fix")
    assert sync_result["ok"] is True

    nvda_current = load_markdown_note(tmp_path / CURRENT_HOLDINGS_DIR / "NVDA.md")
    assert nvda_current.frontmatter["current_quantity"] == 264.9766027

    bn_current = load_markdown_note(tmp_path / CURRENT_HOLDINGS_DIR / "BN.md")
    assert bn_current.frontmatter["current_quantity"] == 86.07287823

    gpro_current = load_markdown_note(tmp_path / CURRENT_HOLDINGS_DIR / "GPRO.md")
    assert gpro_current.frontmatter["current_quantity"] == 1
