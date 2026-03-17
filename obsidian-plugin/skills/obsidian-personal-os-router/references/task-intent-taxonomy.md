# Task Intent Taxonomy

## Intent Classes

- `planetary_task_management`
  - Keywords: planetary tasks, planetary task, planetary tasks base, task_kind, task kind, task schema, periodic planning and tasks hub, closure signal, maneuver board, jira sync
- `exercise_kind_management`
  - Keywords: exercise kind, exercise_kind, exercise schema, exercise library base, exercise library, progressive overload, exercise selection, training guiding principles, Strong CSV, Strong export, Strong workouts, sync Strong, mobility drill, warm-up flow
- `portfolio_holdings_management`
  - Keywords: portfolio holdings, portfolio holdings base, portfolio holdings.base, portfolio holdings history, portfolio holdings history base, portfolio holdings history.base, current holdings, current portfolio positions, actual holdings, active holding, holdings timeline, holdings history, position history
- `brokerage_activity_management`
  - Keywords: betashares, stake, brokerage activity, brokerage csv, brokerage export, transaction history, trade history, dividend log, distribution reinvestment, investment ledger, portfolio ledger, brokerage_activity_kind, brokerage_asset_kind, brokerage assets base, ticker asset, asset registry
- `notebooklm_base`
  - Keywords: notebooklm base, notebook lm base, notebooklm frontmatter, notebooklm metadata, notebooklm notebooks base
- `key_dates_base`
  - Keywords: key dates, key dates.base, key dates base, key date base, date-link base
- `interweave`
  - Keywords: interweave, enrich, link, weave, wikilink, clipping
- `pit_snapshot`
  - Keywords: pit, point-in-time, point in time, snapshot, pit_status
- `weekly_feedback`
  - Keywords: weekly, review, synthesis, periodic, control plane
- `zettel_management`
  - Keywords: zettel, zettel_kind, zettel_id, zettel schema, connection strength, score zettels, migrate zettels, fleeting capture, promote note, evergreen note, litnote, atomic note, hub synthesis, knowledge note
- `memory_capture`
  - Keywords: memory, insight, friction, pattern, durable note
- `token_guard`
  - Keywords: token, context window, budget, compaction, trim

## Classification Rule

- Choose the first high-confidence class by keyword hit.
- Evaluate `planetary_task_management` before `weekly_feedback` so task/base work is not misclassified as generic periodic review.
- Evaluate `exercise_kind_management` before `interweave` or `token_guard` so exercise-schema requests do not fall through to generic resource routing.
- Evaluate `exercise_kind_management` before `token_guard` for Strong CSV requests so workout-log imports stay on the explicit exercise schema path.
- Evaluate `portfolio_holdings_management` before `brokerage_activity_management` so current-position and holdings-base requests do not get absorbed by the raw-import workflow.
- Evaluate `portfolio_holdings_management` before `token_guard` so active-holding reconciliation lands on the derived holdings workflow.
- Evaluate `brokerage_activity_management` before `interweave` or `token_guard` so brokerage-export and investment-ledger requests resolve to the typed import workflow.
- Evaluate `zettel_management` before `memory_capture` — "zettel" is a more specific signal than "memory" or "capture".
- Fall back to `token_guard` when uncertain.
