# Holdings Schema

## Current Holdings Surface

- Path: `20 Resources/Investments/Portfolio Holdings/<SYMBOL>.md`
- Base: `20 Resources/Investments/Portfolio Holdings/Portfolio Holdings.base`
- Kind: `portfolio_holding_kind: current_position`

Required core fields:

- `portfolio_holding_id`
- `portfolio_holding_kind`
- `instrument_symbol`
- `brokerage_providers`
- `first_activity_date`
- `last_activity_date`
- `activity_count`
- `current_quantity`
- `review_status`
- `source_activity_signatures`
- `source_activity_count`
- `tags`

Helpful optional fields:

- `instrument_market`
- `instrument_kind`
- `last_trade_date`
- `currency`
- `cumulative_net_cash_flow`
- `cumulative_fees`
- `cumulative_taxes`

## Holdings History Surface

- Path: `20 Resources/Investments/Portfolio Holdings History/<SYMBOL> Holdings History.md`
- Base: `20 Resources/Investments/Portfolio Holdings History/Portfolio Holdings History.base`
- Kind: `portfolio_holding_kind: holding_history`

Required core fields:

- `portfolio_holding_id`
- `portfolio_holding_kind`
- `instrument_symbol`
- `brokerage_providers`
- `first_snapshot_date`
- `last_snapshot_date`
- `snapshot_count`
- `current_quantity`
- `review_status`
- `source_activity_signatures`
- `source_activity_count`
- `tags`

Helpful optional fields:

- `instrument_market`
- `max_quantity`
- `min_quantity`

## Quantity Rules

- `trade_buy` -> increase quantity by absolute units
- `distribution_reinvestment` -> increase quantity by absolute units
- `trade_sell` -> decrease quantity by absolute units
- `distribution` -> no quantity change
- `corporate_action` / `adjustment` -> include quantity when explicitly present and keep review visible

## Tag Contract

Generated holdings notes must include:

- `type/portfolio-holding`
- `portfolio-holding-kind/<kind>`
- one `brokerage-provider/<provider>` tag per contributing provider
