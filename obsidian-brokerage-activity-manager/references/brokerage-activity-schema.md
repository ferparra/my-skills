# Brokerage Activity Schema

## Overview

`brokerage_activity_kind` is the ledger supertag. Every generated note must have exactly one kind value, and that value decides which fields are expected to be meaningful in the activity Base and the derived asset surface.

## Path Contract

- Notes: `20 Resources/Investments/Brokerage Activity/<year>/<date> <symbol-or-cash> <kind> <id>.md`
- Base: `20 Resources/Investments/Brokerage Activity/Brokerage Activity.base`

Keep note paths stable. Idempotent re-imports should update the existing note for the same `source_signature`, not create siblings.

## Required Core Fields

| Field | Type | Purpose |
|---|---|---|
| `brokerage_activity_id` | string | Stable hash-backed note identifier |
| `brokerage_activity_kind` | enum | Ledger supertag and schema selector |
| `brokerage_provider` | enum | Export source family |
| `activity_date` | `YYYY-MM-DD` | Event date used for pathing and Base grouping |
| `activity_year` | int | Folder convenience |
| `activity_month` | `YYYY-MM` | Base grouping convenience |
| `activity_status` | enum | Completed, pending, cancelled, failed, or unknown |
| `cash_direction` | enum | Inflow, outflow, or neutral |
| `source_signature` | string | Canonical dedupe key |
| `source_files` | list[string] | Import files contributing to this record |
| `source_row_hashes` | list[string] | Row-level trace for merged inputs |
| `merge_count` | int | Count of merged source surfaces |
| `tags` | list[string] | Must include type/provider/kind tags |

## Optional Financial Fields

- `instrument_symbol`
- `instrument_market`
- `instrument_kind`
- `asset_note`
- `currency`
- `gross_amount`
- `net_amount`
- `unit_price`
- `quantity`
- `fee_amount`
- `tax_amount`
- `raw_activity_type`
- `review_status`

Populate optional fields only when the export actually provides them or the mapping can infer them deterministically.

Current provider values:

- `betashares`
- `stake_au`
- `stake_us`
- `generic_csv`

## Kind Taxonomy

### `trade_buy`
- Executed buy activity.
- Usually `cash_direction: outflow`.
- Prefer `quantity`, `unit_price`, and `fee_amount` when present.

### `trade_sell`
- Executed sell activity.
- Usually `cash_direction: inflow`.
- Prefer `quantity`, `unit_price`, and `fee_amount` when present.

### `distribution`
- Cash distributions or dividends.
- May have no quantity or price.

### `distribution_reinvestment`
- Distribution automatically reinvested into units.
- Usually paired with a same-day `distribution`.

### `cash_deposit`
- External cash transferred into the brokerage account.
- No symbol is required.

### `cash_withdrawal`
- External cash transferred out of the brokerage account.
- No symbol is required.

### `fee`
- Brokerage, admin, FX, or other explicit fees when the export separates them.

### `tax`
- Withholding tax or similar explicit tax rows.

### `cash_interest`
- Interest paid on uninvested cash balances.

### `fx`
- Currency conversion or foreign exchange event.

### `corporate_action`
- Stock splits, consolidations, mergers, or ticker changes.

### `adjustment`
- Last-resort bucket for real rows that still need explicit mapping.
- Keep `review_status: needs_review`.

## Tag Contract

Generated notes must include:

- `type/brokerage-activity`
- `brokerage-provider/<brokerage_provider>`
- `brokerage-activity-kind/<brokerage_activity_kind>`

Do not strip extra tags that already exist on a previously imported note.

## Cross-Note Rule

When `instrument_symbol` exists, set `asset_note` to the canonical ticker note, for example:

- `[[20 Resources/Investments/Brokerage Assets/AAA|AAA]]`

This keeps the activity ledger connected to the ticker-level asset view.
