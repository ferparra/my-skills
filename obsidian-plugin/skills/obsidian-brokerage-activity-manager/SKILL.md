---
name: obsidian-brokerage-activity-manager
version: 1.0.0
dependencies: []
pipeline:
  inputs:
    - name: input_file
      type: file
      required: false
      description: Path to brokerage export CSV/XLSX
    - name: provider
      type: string
      required: false
      default: auto
      description: Brokerage provider (auto, betashares, stake_au, stake_us, generic_csv)
    - name: mode
      type: string
      required: false
      default: check
      description: Mode (check or fix)
  outputs:
    - name: brokerage_activity_notes
      type: file
      path: "20 Resources/Investments/Brokerage Activity/{date}/{slug}.md"
      description: Normalized activity notes
    - name: brokerage_assets_notes
      type: file
      path: "20 Resources/Investments/Brokerage Assets/{symbol}.md"
      description: Derived asset notes
    - name: activity_base
      type: file
      path: "20 Resources/Investments/Brokerage Activity/Brokerage Activity.base"
      description: Activity ledger Base
    - name: assets_base
      type: file
      path: "20 Resources/Investments/Brokerage Assets/Brokerage Assets.base"
      description: Asset registry Base
    - name: sync_report
      type: json
      path: ".skills/brokerage-sync-report.json"
      description: Import/deduplication report
description: Parse, normalize, validate, and sync brokerage activity exports into typed Obsidian notes and Bases. Use for Betashares, Stake, CSV/XLSX exports, transaction histories, dividends, and idempotent import workflows for stock brokerage records.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Brokerage Activity Manager

## Overview

Run this skill when brokerage exports need typed vault surfaces instead of a CSV pasted into an inbox note. `brokerage_activity_kind` is the supertag for economic events, while `brokerage_asset_kind` is the supertag for ticker-indexed asset notes derived from those events. The two surfaces stay synchronized through one idempotent import path.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate investment notes when the tooling is unavailable.

### 2. Read Only the Required Surface

```bash
obsidian read path="20 Resources/Investments/Brokerage Activity/Brokerage Activity.base"
obsidian read path="20 Resources/Investments/Brokerage Assets/Brokerage Assets.base"
qmd query "brokerage activity investment ledger dividends portfolio" -c resources -l 8
qmd query "Betashares Stake brokerage dividends trading" -c inbox -l 5
```

Default read scope stays inside:

- `20 Resources/Investments/Brokerage Activity/**/*.md`
- `20 Resources/Investments/Brokerage Activity/Brokerage Activity.base`
- `20 Resources/Investments/Brokerage Assets/*.md`
- `20 Resources/Investments/Brokerage Assets/Brokerage Assets.base`
- brokerage export files explicitly named in the request
- any inbox capture note the user points to for context

### 3. Validate Existing Ledger Notes

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/validate_brokerage_activity.py \
  --glob "20 Resources/Investments/Brokerage Activity/**/*.md"
```

Review invalid frontmatter and duplicate `source_signature` collisions before importing anything new.

Validate the derived asset surface too:

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/validate_brokerage_assets.py \
  --glob "20 Resources/Investments/Brokerage Assets/*.md"
```

### 4. Dry-Run the Import

```bash
uvx --from python --with polars --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/sync_brokerage_activity.py \
  --input "brokerage-export.csv" \
  --provider auto \
  --mode check
```

The sync script:

- detects known providers from headers
- normalizes provider rows into one typed activity schema
- merges duplicate rows through `source_signature` instead of creating duplicate notes
- preserves stable note paths so reruns are idempotent
- derives one asset note per ticker symbol and keeps it aligned with the current activity surface
- warns when a date-windowed activity workbook has no earlier ledger history, because derived current holdings may omit pre-window positions
- supports future providers through canonical column names or an explicit `--column-map`

### 5. Apply the Import

```bash
uvx --from python --with polars --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/sync_brokerage_activity.py \
  --input "brokerage-export.csv" \
  --provider auto \
  --mode fix
```

When provider detection is too weak, pass an explicit mapping:

```bash
uvx --from python --with polars --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/sync_brokerage_activity.py \
  --input "future-broker.csv" \
  --provider generic_csv \
  --column-map '{"activity_date":"Executed At","activity_type":"Description","symbol":"Ticker","amount":"Net Amount","price":"Unit Price","quantity":"Units","status":"Status","currency":"Currency","brokerage":"Brokerage"}' \
  --mode fix
```

### 6. Render the Bases

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/render_brokerage_activity_base.py \
  --output "20 Resources/Investments/Brokerage Activity/Brokerage Activity.base"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/render_brokerage_assets_base.py \
  --output "20 Resources/Investments/Brokerage Assets/Brokerage Assets.base"
```

The rendered Bases surface:

- an activity ledger, trade flow, distributions, cash movements, and review queue
- an asset registry keyed by ticker symbol, plus income, trading, and review views

### 7. Re-Validate and Verify

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/validate_brokerage_activity.py \
  --glob "20 Resources/Investments/Brokerage Activity/**/*.md"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-brokerage-activity-manager/scripts/validate_brokerage_assets.py \
  --glob "20 Resources/Investments/Brokerage Assets/*.md"

obsidian read path="20 Resources/Investments/Brokerage Activity/Brokerage Activity.base"
obsidian read path="20 Resources/Investments/Brokerage Assets/Brokerage Assets.base"
obsidian search query="brokerage_activity_kind" limit=20 total
obsidian search query="brokerage_asset_kind" limit=20 total
obsidian unresolved total
```

Treat import warnings as workflow gates. If a date-window warning says the ledger has no history before the workbook start date, do not trust downstream current holdings as complete until you either import older history or reconcile against a current valuation/holdings snapshot.

## Kind Rules

Use `references/brokerage-activity-schema.md` for the canonical note contract.

- `trade_buy`
  - Outflow activity for executed buys.
  - Keep `quantity` and `unit_price` when the export provides them.

- `trade_sell`
  - Inflow activity for executed sells.
  - Preserve `fee_amount` when brokerage is explicit.

- `distribution`
  - Cash distributions or dividends credited to the account.
  - Usually pair with a same-day `distribution_reinvestment` in DRP workflows.

- `distribution_reinvestment`
  - Outflow generated by a distribution reinvestment plan.
  - Keep share quantity and unit price when supplied.

- `cash_deposit` and `cash_withdrawal`
  - Pure account-level cash movements without a security leg.

- `fee`, `tax`, `cash_interest`
  - Cash-account adjustments that should remain queryable in the Base.

- `fx`, `corporate_action`, `adjustment`
  - Reserve for events that are real but not cleanly expressible as the simpler kinds.
  - Default `review_status` should remain `needs_review` until the mapping is explicit.

Use `references/brokerage-asset-schema.md` for the asset contract.

- `listed_security`
  - Default asset note kind for tickered securities in brokerage exports.
  - Path identity is the ticker symbol, so re-imports update `AAA.md`, `NDQ.md`, and similar notes instead of creating duplicates.

- `fund`, `crypto`, `fx_pair`, `other`, `unknown`
  - Reserve for future providers or richer instrument classification once the export surface supports it.

## Guardrails

- Treat `brokerage_activity_kind` as the supertag and schema selector for every generated note.
- Treat `brokerage_asset_kind` as the supertag and schema selector for every generated asset note.
- Prefer one canonical note per economic event, not one note per import file.
- Prefer one canonical asset note per ticker symbol.
- Deduplicate through stable `source_signature` values and merge `source_row_hashes` instead of duplicating notes.
- Keep asset notes derived from the current activity set; do not accumulate stale asset counters across re-syncs.
- Preserve non-owned frontmatter fields and manual tags on existing ledger notes when resyncing.
- Do not infer missing quantity, price, or ticker values when the export does not provide them.
- Prefer explicit `--column-map` input over brittle fuzzy parsing for unknown providers.
- Treat date-windowed activity workbooks as incremental ledger slices, not proof of complete current holdings, unless pre-window history is already in the vault or a current valuation reconciles the result.
- Keep each Base filtered to its typed folder and note surface only.

## References

- `references/brokerage-activity-schema.md` — canonical schema, note path rules, and `_kind` taxonomy
- `references/brokerage-asset-schema.md` — ticker-keyed asset schema and aggregation rules
- `references/provider-mapping.md` — provider detection, column aliases, and future-provider extension rules
- `scripts/brokerage_models.py` — source of truth for the Pydantic v2 schema
