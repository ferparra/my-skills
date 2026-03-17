# Brokerage Asset Schema

## Overview

`brokerage_asset_kind` is the supertag for derived asset notes. Each note represents one ticker symbol and is rebuilt from the typed activity ledger, not from ad hoc manual edits.

## Path Contract

- Notes: `20 Resources/Investments/Brokerage Assets/<ticker>.md`
- Base: `20 Resources/Investments/Brokerage Assets/Brokerage Assets.base`

Ticker symbol is the unique identity. Re-importing `AAA` activity updates `AAA.md`; it must not create sibling notes for the same symbol.

## Required Core Fields

| Field | Type | Purpose |
|---|---|---|
| `brokerage_asset_id` | string | Stable hash-backed asset identifier |
| `brokerage_asset_kind` | enum | Asset supertag and schema selector |
| `instrument_symbol` | string | Unique ticker symbol |
| `brokerage_providers` | list[string] | Providers contributing activity for the symbol |
| `first_activity_date` | `YYYY-MM-DD` | Earliest known activity date |
| `last_activity_date` | `YYYY-MM-DD` | Latest known activity date |
| `activity_count` | int | Number of contributing activity notes |
| `source_activity_signatures` | list[string] | Canonical activity lineage |
| `source_activity_count` | int | Count of contributing activity signatures |
| `tags` | list[string] | Must include asset type and kind tags |

## Optional Derived Fields

- `instrument_market`
- `instrument_kind`
- `last_trade_date`
- `trade_buy_count`
- `trade_sell_count`
- `distribution_count`
- `distribution_reinvestment_count`
- `currency`
- `last_unit_price`
- `estimated_open_quantity`
- `cumulative_net_cash_flow`
- `cumulative_fees`
- `cumulative_taxes`
- `review_status`

These are authoritative derived values. Re-syncs should replace stale derived values instead of merging them forward.

## Kind Taxonomy

### `listed_security`
- Default kind for exchange-traded assets with a ticker symbol.
- Includes ETFs and equities when the provider export does not distinguish them more precisely.

### `fund`
- Use when provider metadata or an explicit mapping identifies the symbol as a fund class rather than a generic listed security.

### `crypto`
- Use for tickered crypto assets in brokerage or exchange exports.

### `fx_pair`
- Use for currency-pair assets.

### `other`
- Use for real tickered assets that do not fit the simpler categories.

### `unknown`
- Last-resort fallback when a symbol exists but classification is still unclear.

## Tag Contract

Generated asset notes must include:

- `type/brokerage-asset`
- `brokerage-asset-kind/<brokerage_asset_kind>`
- one `brokerage-provider/<provider>` tag per contributing provider

## Aggregation Rules

- `activity_count` equals the number of typed activity notes for the symbol.
- `estimated_open_quantity` is derived as:
  - `trade_buy.quantity`
  - plus `distribution_reinvestment.quantity`
  - minus `trade_sell.quantity`
- `cumulative_net_cash_flow` is the signed sum of the contributing activity notes.
- `review_status` becomes `needs_review` when any contributing activity note needs review.
