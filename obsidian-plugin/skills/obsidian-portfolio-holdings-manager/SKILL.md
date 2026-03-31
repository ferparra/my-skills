---
name: obsidian-portfolio-holdings-manager
version: 1.0.0
dependencies:
  - obsidian-brokerage-activity-manager
pipeline:
  inputs:
    - name: mode
      type: string
      required: false
      default: check
      description: Mode (check or fix)
  outputs:
    - name: holdings_notes
      type: file
      path: "20 Resources/Investments/Portfolio Holdings/{symbol}.md"
      description: Current holdings notes
    - name: holdings_history_notes
      type: file
      path: "20 Resources/Investments/Portfolio Holdings History/{symbol}.md"
      description: Per-symbol holdings history notes
    - name: holdings_base
      type: file
      path: "20 Resources/Investments/Portfolio Holdings/Portfolio Holdings.base"
      description: Current holdings Base
    - name: holdings_history_base
      type: file
      path: "20 Resources/Investments/Portfolio Holdings History/Portfolio Holdings History.base"
      description: Holdings history Base
    - name: holdings_report
      type: json
      path: ".skills/holdings-report.json"
      description: Holdings sync report
description: Derive current and historical portfolio holdings in this Obsidian vault from typed brokerage activity notes. Use when requests mention actual holdings, current portfolio positions, historical holdings, holdings timelines, position history, portfolio holdings Bases, or rebuilding holdings after brokerage activity imports under `20 Resources/Investments/Brokerage Activity/**/*.md`.
metadata:
  openclaw:
    os: [darwin]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Portfolio Holdings Manager

## Overview

Use this skill after brokerage activity has already been synced into typed activity notes. It maintains two derived surfaces:

- current holdings notes in `20 Resources/Investments/Portfolio Holdings/*.md`
- per-symbol holdings history notes in `20 Resources/Investments/Portfolio Holdings History/*.md`

Read `references/holdings-schema.md` for the canonical note contracts and `references/holdings-base-patterns.md` for the Base layouts.

## Workflow

### 1. Confirm Dependencies

```bash
obsidian --help
qmd status
uvx --version
```

Fail fast if any dependency is missing. Do not mutate holdings notes when the tooling is unavailable.

### 2. Read Only the Required Surface

```bash
obsidian read path="20 Resources/Investments/Brokerage Activity/Brokerage Activity.base"
obsidian read path="20 Resources/Investments/Portfolio Holdings/Portfolio Holdings.base"
obsidian read path="20 Resources/Investments/Portfolio Holdings History/Portfolio Holdings History.base"
qmd query "portfolio holdings position history brokerage activity" -c resources -l 8
```

Default read scope stays inside:

- `20 Resources/Investments/Brokerage Activity/**/*.md`
- `20 Resources/Investments/Portfolio Holdings/*.md`
- `20 Resources/Investments/Portfolio Holdings History/*.md`
- the two Holdings `.base` files

### 3. Dry-Run the Holdings Sync

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-portfolio-holdings-manager/scripts/sync_portfolio_holdings.py \
  --mode check
```

The sync script:

- reads completed symbol-linked brokerage activity notes
- rebuilds current holdings from the full activity ledger, not just the last import file
- produces one current holdings note per symbol
- produces one per-symbol holdings history note with running quantity snapshots
- marks negative closing quantities as `needs_review`
- preserves flat or exited symbols as notes so Bases can separate active and inactive positions without data loss

### 4. Apply the Holdings Sync

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-portfolio-holdings-manager/scripts/sync_portfolio_holdings.py \
  --mode fix
```

### 5. Render the Bases

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-portfolio-holdings-manager/scripts/render_portfolio_holdings_base.py \
  --output "20 Resources/Investments/Portfolio Holdings/Portfolio Holdings.base"

uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-portfolio-holdings-manager/scripts/render_portfolio_holdings_history_base.py \
  --output "20 Resources/Investments/Portfolio Holdings History/Portfolio Holdings History.base"
```

### 6. Re-Validate and Verify

```bash
uvx --from python --with pydantic --with pyyaml python \
  .skills/obsidian-portfolio-holdings-manager/scripts/validate_portfolio_holdings.py

obsidian read path="20 Resources/Investments/Portfolio Holdings/Portfolio Holdings.base"
obsidian read path="20 Resources/Investments/Portfolio Holdings History/Portfolio Holdings History.base"
obsidian unresolved total
```

Treat validation as a hard gate. The validator reconciles every completed brokerage-activity symbol against the derived current/history notes and fails when:

- a symbol-backed current holding note is missing
- a symbol-backed holdings history note is missing
- `current_quantity` drifts from the ledger-derived closing quantity
- `source_activity_count` drifts from the underlying brokerage activity ledger

## Holding Rules

- Treat `trade_buy` and `distribution_reinvestment` as positive quantity deltas.
- Treat `trade_sell` as a negative quantity delta, even when legacy notes store negative sell quantities.
- Treat `distribution` as cash-only activity with no quantity delta.
- Carry forward `corporate_action` and `adjustment` quantities when they exist, and keep review visible.
- Aggregate providers per symbol so Betashares, Stake AU, and Stake US can coexist in one holdings note.

## Guardrails

- Use brokerage activity notes as the canonical source, not raw broker files.
- Prefer one current holdings note per symbol.
- Prefer one holdings history note per symbol.
- Fail the workflow if any symbol present in completed brokerage activity is missing from current holdings or holdings history.
- Preserve non-owned frontmatter fields on existing holdings notes.
- Do not delete holdings notes just because a symbol is currently flat; let the Base filter exited positions.
- Keep provider labels human-readable in note bodies and Bases.

## References

- `references/holdings-schema.md` - current and history note contracts
- `references/holdings-base-patterns.md` - Base views, formulas, and filters
