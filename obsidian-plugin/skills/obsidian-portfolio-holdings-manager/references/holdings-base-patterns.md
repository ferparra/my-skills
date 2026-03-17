# Holdings Base Patterns

## Portfolio Holdings.base

Folder filter:

- `file.inFolder("20 Resources/Investments/Portfolio Holdings")`
- `portfolio_holding_kind == "current_position"`

Useful views:

- `Active Holdings`
  - filter `current_quantity > 0`
  - sort by `instrument_symbol`, providers, quantity, and last activity
- `Flat Or Exited`
  - filter `current_quantity <= 0`
  - keep closed positions visible without deleting notes
- `Review Queue`
  - filter `review_status == "needs_review"` or `current_quantity < 0`

Useful formulas:

- provider label mapping `stake_au` -> `Stake AU`
- provider label mapping `stake_us` -> `Stake US`
- provider label mapping `betashares` -> `Betashares`
- holding badge for `active`, `flat`, or `review`

## Portfolio Holdings History.base

Folder filter:

- `file.inFolder("20 Resources/Investments/Portfolio Holdings History")`
- `portfolio_holding_kind == "holding_history"`

Useful views:

- `Holdings History`
  - sort by symbol, providers, snapshot count, and last snapshot
- `Review Queue`
  - filter `review_status == "needs_review"` or `current_quantity < 0`

Useful fields:

- `snapshot_count`
- `current_quantity`
- `max_quantity`
- `min_quantity`
- `last_snapshot_date`
