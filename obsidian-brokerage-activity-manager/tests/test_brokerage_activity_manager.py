#!/usr/bin/env python3
"""Tests for obsidian-brokerage-activity-manager scripts.

Run with:
    uvx --from python --with polars --with pydantic --with pyyaml --with pytest pytest \
        .skills/obsidian-brokerage-activity-manager/tests/test_brokerage_activity_manager.py -v
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).parent.parent / "assets" / "fixtures"

sys.path.insert(0, str(SCRIPTS_DIR))

from brokerage_models import BROKERAGE_ASSETS_DIR, BROKERAGE_NOTES_DIR, load_markdown_note
from render_brokerage_activity_base import build_base_config
from render_brokerage_assets_base import build_asset_base_config
from sync_brokerage_activity import run_sync


def excel_column_name(index: int) -> str:
    value = index + 1
    output = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        output = chr(65 + remainder) + output
    return output


def build_sheet_xml(rows: list[list[object]]) -> str:
    rendered_rows: list[str] = []
    for row_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_idx, value in enumerate(row):
            if value in (None, ""):
                continue
            ref = f"{excel_column_name(col_idx)}{row_idx}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
        rendered_rows.append(f'<row r="{row_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rendered_rows)}</sheetData>"
        "</worksheet>"
    )


def write_stake_activity_workbook(
    path: Path,
    *,
    au_rows: list[list[object]] | None = None,
    us_rows: list[list[object]] | None = None,
) -> None:
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Aus Equities" sheetId="1" r:id="rId1"/>'
        '<sheet name="Wall St Equities" sheetId="2" r:id="rId2"/>'
        "</sheets>"
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        '<Relationship Id="rId2" Target="worksheets/sheet2.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="xl/workbook.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    au_rows = au_rows or [
        [
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
        ],
        [
            "2026-01-20",
            "2026-01-22",
            "MVB ",
            "VanEck Australian Banks ETF",
            "Sell",
            "247420121",
            -100,
            42.05,
            -4205,
            2.73,
            0.27,
            -4202,
            "AUD",
        ],
    ]
    us_rows = us_rows or [
        [
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
            "AUD/USD rate",
        ],
        [
            "2026-02-13",
            "2026-02-17",
            "GOOG ",
            "Alphabet Inc.",
            "Buy",
            "4128096108",
            6,
            309.59,
            1857.57,
            3,
            0,
            1860.57,
            "USD",
            "$1.413",
        ],
    ]

    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(au_rows))
        archive.writestr("xl/worksheets/sheet2.xml", build_sheet_xml(us_rows))


def test_betashares_sync_is_idempotent(tmp_path: Path) -> None:
    csv_path = tmp_path / "betashares-activity.csv"
    shutil.copy(FIXTURES_DIR / "betashares-activity.csv", csv_path)

    first = run_sync(
        root=tmp_path,
        input_path=csv_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    notes_dir = tmp_path / BROKERAGE_NOTES_DIR
    created_files = sorted(notes_dir.glob("**/*.md"))
    asset_files = sorted((tmp_path / BROKERAGE_ASSETS_DIR).glob("*.md"))
    assert first["provider"] == "betashares"
    assert first["created"] == 4
    assert first["asset_created"] == 1
    assert first["exact_duplicate_rows_removed"] == 1
    assert len(created_files) == 4
    assert len(asset_files) == 1

    reinvestment_note = next(path for path in created_files if "distribution-reinvestment" in path.name)
    note = load_markdown_note(reinvestment_note)
    assert note.frontmatter["brokerage_activity_kind"] == "distribution_reinvestment"
    assert note.frontmatter["instrument_symbol"] == "AAA"
    assert note.frontmatter["net_amount"] == -181.22
    assert note.frontmatter["source_row_count"] == 1
    assert note.frontmatter["asset_note"] == "[[20 Resources/Investments/Brokerage Assets/AAA|AAA]]"
    deposit_note = load_markdown_note(
        next(path for path in created_files if "cash-deposit" in path.name)
    )
    assert deposit_note.frontmatter["activity_status"] == "completed"
    assert deposit_note.frontmatter["review_status"] == "ok"
    sell_note = load_markdown_note(next(path for path in created_files if "trade-sell" in path.name))
    assert sell_note.frontmatter["quantity"] > 0
    aaa_asset = load_markdown_note(next(path for path in asset_files if path.name == "AAA.md"))
    assert aaa_asset.frontmatter["brokerage_asset_kind"] == "listed_security"
    assert aaa_asset.frontmatter["activity_count"] == 3
    assert aaa_asset.frontmatter["trade_sell_count"] == 1
    assert aaa_asset.frontmatter["distribution_count"] == 1
    assert aaa_asset.frontmatter["distribution_reinvestment_count"] == 1
    assert aaa_asset.frontmatter["estimated_open_quantity"] < 0

    snapshot = {
        str(path.relative_to(tmp_path)): path.read_text(encoding="utf-8")
        for path in created_files
    }
    snapshot.update(
        {
            str(path.relative_to(tmp_path)): path.read_text(encoding="utf-8")
            for path in asset_files
        }
    )

    second = run_sync(
        root=tmp_path,
        input_path=csv_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    assert second["created"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 4
    assert second["asset_created"] == 0
    assert second["asset_updated"] == 0
    assert second["asset_unchanged"] == 1
    assert snapshot == {
        str(path.relative_to(tmp_path)): path.read_text(encoding="utf-8")
        for path in sorted(notes_dir.glob("**/*.md")) + sorted((tmp_path / BROKERAGE_ASSETS_DIR).glob("*.md"))
    }


def test_stake_alias_mapping_autodetects_and_normalizes(tmp_path: Path) -> None:
    csv_path = tmp_path / "stake-activity.csv"
    shutil.copy(FIXTURES_DIR / "stake-activity.csv", csv_path)

    result = run_sync(
        root=tmp_path,
        input_path=csv_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    notes = sorted((tmp_path / BROKERAGE_NOTES_DIR).glob("**/*.md"))
    assets = sorted((tmp_path / BROKERAGE_ASSETS_DIR).glob("*.md"))
    assert result["provider"] == "stake_au"
    assert result["created"] == 3
    assert result["asset_created"] == 1
    assert len(notes) == 3
    assert len(assets) == 1

    buy_note_path = next(path for path in notes if "trade-buy" in path.name)
    buy_note = load_markdown_note(buy_note_path)
    assert buy_note.frontmatter["instrument_symbol"] == "IVV"
    assert buy_note.frontmatter["net_amount"] == -97.0
    assert buy_note.frontmatter["fee_amount"] == 1.0
    assert buy_note.frontmatter["brokerage_provider"] == "stake_au"
    ivv_asset = load_markdown_note(assets[0])
    assert ivv_asset.frontmatter["instrument_symbol"] == "IVV"
    assert ivv_asset.frontmatter["activity_count"] == 2


def test_stake_investment_activity_workbook_imports_au_and_us(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "investment-activity.xlsx"
    write_stake_activity_workbook(xlsx_path)

    result = run_sync(
        root=tmp_path,
        input_path=xlsx_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    notes = sorted((tmp_path / BROKERAGE_NOTES_DIR).glob("**/*.md"))
    assets = sorted((tmp_path / BROKERAGE_ASSETS_DIR).glob("*.md"))
    assert result["provider"] == "multiple"
    assert result["providers"] == ["stake_au", "stake_us"]
    assert result["created"] == 2
    assert result["asset_created"] == 2
    assert len(notes) == 2
    assert len(assets) == 2

    au_note = load_markdown_note(next(path for path in notes if path.stem.startswith("2026-01-20 MVB trade-sell")))
    assert au_note.frontmatter["brokerage_provider"] == "stake_au"
    assert au_note.frontmatter["instrument_market"] == "ASX"
    assert au_note.frontmatter["quantity"] == 100
    assert au_note.frontmatter["gross_amount"] == 4205
    assert au_note.frontmatter["net_amount"] == 4202
    assert au_note.frontmatter["fee_amount"] == 2.73
    assert au_note.frontmatter["tax_amount"] == 0.27

    us_note = load_markdown_note(next(path for path in notes if path.stem.startswith("2026-02-13 GOOG trade-buy")))
    assert us_note.frontmatter["brokerage_provider"] == "stake_us"
    assert us_note.frontmatter["instrument_market"] == "US"
    assert us_note.frontmatter["net_amount"] == -1860.57
    assert us_note.frontmatter["gross_amount"] == 1857.57
    assert us_note.frontmatter["fee_amount"] == 3
    assert us_note.frontmatter["currency"] == "USD"

    goog_asset = load_markdown_note(next(path for path in assets if path.name == "GOOG.md"))
    assert goog_asset.frontmatter["brokerage_providers"] == ["stake_us"]
    mvb_asset = load_markdown_note(next(path for path in assets if path.name == "MVB.md"))
    assert mvb_asset.frontmatter["brokerage_providers"] == ["stake_au"]


def test_date_windowed_workbook_warns_when_no_prior_history_exists(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "INVESTMENT_ACTIVITY_2025-07-01-2026-03-12.xlsx"
    write_stake_activity_workbook(xlsx_path)

    result = run_sync(
        root=tmp_path,
        input_path=xlsx_path,
        mode="check",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    assert any(
        "Current holdings derived from this ledger may omit pre-window positions" in warning
        and "`2025-07-01`" in warning
        for warning in result["warnings"]
    )


def test_date_windowed_workbook_warns_when_only_other_provider_has_prior_history(tmp_path: Path) -> None:
    csv_path = tmp_path / "older-betashares.csv"
    csv_path.write_text(
        "Effective Date,Activity Type,Gross,Symbol,Brokerage,Price,Quantity\n"
        "14/09/2024,Deposit,$1000.00,\u2014,,,\n",
        encoding="utf-8",
    )
    run_sync(
        root=tmp_path,
        input_path=csv_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    xlsx_path = tmp_path / "INVESTMENT_ACTIVITY_2025-07-01-2026-03-12.xlsx"
    write_stake_activity_workbook(xlsx_path)

    result = run_sync(
        root=tmp_path,
        input_path=xlsx_path,
        mode="check",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    assert any("`Stake AU`" in warning and "`Stake US`" in warning for warning in result["warnings"])


def test_stake_workbook_normalizes_symbol_name_pairs_to_canonical_ticker(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "stake-symbol-name.xlsx"
    write_stake_activity_workbook(
        xlsx_path,
        au_rows=[
            [
                "Trade Date",
                "Settlement Date",
                "Symbol",
                "Side",
                "Trade Identifier",
                "Units",
                "Avg. Price",
                "Value",
                "Fees",
                "GST",
                "Total Value",
                "Currency",
            ],
        ],
        us_rows=[
            [
                "Trade Date",
                "Settlement Date",
                "Symbol",
                "Side",
                "Trade Identifier",
                "Units",
                "Avg. Price",
                "Value",
                "Fees",
                "GST",
                "Total Value",
                "Currency",
                "AUD/USD rate",
            ],
            [
                "2021-08-13",
                "2021-08-17",
                "NVDA - NVIDIA Corporation",
                "Buy",
                "756460999",
                "0.44526571",
                "449.17",
                "200",
                "0",
                "0",
                "200",
                "USD",
                "$1.389",
            ],
        ],
    )

    result = run_sync(
        root=tmp_path,
        input_path=xlsx_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    assert result["created"] == 1
    assert (tmp_path / BROKERAGE_ASSETS_DIR / "NVDA.md").exists()
    assert not (tmp_path / BROKERAGE_ASSETS_DIR / "NVDA - NVIDIA CORPORATION.md").exists()
    note = load_markdown_note(next((tmp_path / BROKERAGE_NOTES_DIR).glob("**/*.md")))
    assert note.frontmatter["instrument_symbol"] == "NVDA"


def test_asset_registry_rebuilds_from_existing_and_new_provider_activity(tmp_path: Path) -> None:
    csv_path = tmp_path / "betashares-activity.csv"
    shutil.copy(FIXTURES_DIR / "betashares-activity.csv", csv_path)
    run_sync(
        root=tmp_path,
        input_path=csv_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    xlsx_path = tmp_path / "investment-activity.xlsx"
    write_stake_activity_workbook(
        xlsx_path,
        au_rows=[
            [
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
            ],
            [
                "2026-08-11",
                "2026-08-13",
                "AAA ",
                "BetaShares Australian High Interest Cash ETF",
                "Sell",
                "999000111",
                -10,
                50.14,
                -501.4,
                2.73,
                0.27,
                -498.4,
                "AUD",
            ],
        ],
        us_rows=[
            [
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
                "AUD/USD rate",
            ],
        ],
    )

    run_sync(
        root=tmp_path,
        input_path=xlsx_path,
        mode="fix",
        requested_provider="auto",
        notes_dir=BROKERAGE_NOTES_DIR,
        default_currency="AUD",
        column_map=None,
    )

    aaa_asset = load_markdown_note(tmp_path / BROKERAGE_ASSETS_DIR / "AAA.md")
    assert aaa_asset.frontmatter["brokerage_providers"] == ["betashares", "stake_au"]


def test_render_base_contains_core_views() -> None:
    config = build_base_config()
    assert config["filters"]["and"][2] == 'brokerage_activity_kind != ""'
    view_names = [view["name"] for view in config["views"]]
    assert view_names == [
        "Activity Ledger",
        "Trade Flow",
        "Distributions",
        "Cash Movements",
        "Review Queue",
    ]


def test_render_asset_base_contains_core_views() -> None:
    config = build_asset_base_config()
    assert config["filters"]["and"][2] == 'brokerage_asset_kind != ""'
    view_names = [view["name"] for view in config["views"]]
    assert view_names == [
        "Asset Registry",
        "Income Assets",
        "Trading Assets",
        "Review Queue",
    ]
