# Provider Mapping

## Supported Inputs

### `betashares`

Detected from the exact export header:

```text
Effective Date,Activity Type,Gross,Symbol,Brokerage,Price,Quantity
```

Current mapping:

- `Effective Date` -> `activity_date`
- `Activity Type` -> `activity_type`
- `Gross` -> `amount`
- `Symbol` -> `symbol`
- `Brokerage` -> `brokerage`
- `Price` -> `price`
- `Quantity` -> `quantity`

### `stake_au`

Detected through alias families rather than one brittle header set. Common aliases include:

- `activity_date`: `date`, `completed at`, `transaction date`, `executed at`
- `activity_type`: `type`, `activity type`, `transaction type`, `description`
- `symbol`: `symbol`, `ticker`, `stock`
- `amount`: `amount`, `total`, `net amount`, `cash amount`
- `price`: `price`, `unit price`, `fill price`
- `quantity`: `quantity`, `units`, `shares`
- `status`: `status`, `order status`
- `currency`: `currency`
- `brokerage`: `brokerage`, `commission`, `fee`
- `tax`: `tax`, `withholding tax`

If those aliases are insufficient, fall back to `--provider generic_csv --column-map ...`.

### `stake_us`

Uses the same alias families as `stake_au` for CSV-style exports when the provider is selected explicitly.

Stake's `Investment Activity` workbook is also supported directly from `.xlsx` input when it includes:

- `Aus Equities` -> imported as `stake_au`
- `Wall St Equities` -> imported as `stake_us`

The workbook rows are normalized from:

- `Trade Date` -> `activity_date`
- `Side` -> `activity_type`
- `Symbol` -> `symbol`
- `Value` -> `gross`
- `Total Value` -> `amount`
- `Avg. Price` -> `price`
- `Units` -> `quantity`
- `Fees` -> `brokerage`
- `GST` -> `tax`
- `Currency` -> `currency`

For workbook imports, the market is set deterministically from the sheet identity:

- `Aus Equities` -> `ASX`
- `Wall St Equities` -> `US`

## Future Providers

Use one of these paths:

1. Canonical CSV columns:

```text
activity_date,activity_type,symbol,amount,price,quantity,status,currency,brokerage,tax,market
```

2. Explicit mapping:

```bash
--column-map '{"activity_date":"Executed At","activity_type":"Description","symbol":"Ticker","amount":"Net Amount","price":"Unit Price","quantity":"Units","status":"Status","currency":"Currency","brokerage":"Brokerage","tax":"Tax"}'
```

The mapping accepts a JSON object directly or a path to a JSON or YAML file.

## Activity-Type Mapping

The sync script classifies activity text in this order:

1. `distribution_reinvestment`
2. `distribution`
3. `trade_buy`
4. `trade_sell`
5. `cash_deposit`
6. `cash_withdrawal`
7. `fee`
8. `tax`
9. `cash_interest`
10. `fx`
11. `corporate_action`
12. `adjustment`

Add a dedicated mapping before broadening a fallback rule. The goal is stable, narrow enums rather than clever fuzzy guesses.
