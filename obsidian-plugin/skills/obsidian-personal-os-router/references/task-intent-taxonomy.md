# Task Intent Taxonomy

## Intent Classes

Route evaluation order matches the list below — first match wins.

- `key_dates_base`
  - Keywords: key dates, key dates.base, key dates base, key date base, date-link base, date link, mortgage review date, annual performance review, performance review date
- `planetary_task_management`
  - Keywords: planetary tasks, planetary task, planetary tasks base, task_kind, task kind, task schema, periodic planning and tasks hub, planning hub, maneuver board, jira sync, current sprint, project milestone, deliverable, company goals, ongoing goals
- `exercise_kind_management`
  - Keywords: exercise kind, exercise_kind, exercise schema, exercise library base, exercise library, progressive overload, exercise selection, training guiding principles, Strong CSV, Strong export, Strong workouts, sync Strong, mobility drill, warm-up flow, strength training, gym session, squat progression, fitness goals, training session, training history, workout
- `portfolio_holdings_management`
  - Keywords: portfolio holdings, portfolio holdings base, portfolio holdings.base, portfolio holdings history, current holdings, current portfolio positions, actual holdings, active holding, holdings timeline, holdings history, position history, how many units, rebalancing, investment portfolio, target percentage band, dhhf
- `brokerage_activity_management`
  - Keywords: betashares, brokerage activity, brokerage csv, brokerage export, transaction history, trade history, dividend log, distribution reinvestment, etf distribution, received a distribution, investment ledger, portfolio ledger, brokerage_activity_kind, brokerage_asset_kind, brokerage assets base, ticker asset, asset registry
- `notebooklm_base`
  - Keywords: notebooklm base, notebook lm base, notebooklm frontmatter, notebooklm metadata, notebooklm notebooks base, notebooklm notebooks, notebook list, ai notebook, notebooklm
- `pit_snapshot`
  - Keywords: pit, point-in-time, point in time, snapshot, pit_status
- `zettel_management`
  - Keywords: zettel, zettel_kind, zettel_id, zettel schema, connection strength, connection_strength, score zettels, migrate zettels, fleeting capture, promote note, evergreen note, litnote, atomic note, hub synthesis, rough idea note, permanent note, how should i file, file it in my note, zettel frontmatter, properly structured
- `weekly_feedback`
  - Keywords: weekly, weekly review, control plane, periodic note, periodic review, weekly note, what i accomplished, accomplished last week, still open, thread alignment, open closure signal, closure signal
- `interweave`
  - Keywords: interweave, wikilink, weave this, weave into, connect my, connect my reading, enrich, clipping, link this, frontmatter
- `memory_capture`
  - Keywords: memory, friction, routing mistake, same mistake, agent insight, durable note, key insight, debugging session, persist it, capture this
- `token_guard`
  - Keywords: token, context window, budget, compaction, trim

## Classification Rules

- Choose the first high-confidence class by keyword hit.
- Evaluate `key_dates_base` first — prevents the broad `"review"` keyword in `weekly_feedback` from stealing date-related intents (e.g. "annual performance review", "date link broken").
- Evaluate `planetary_task_management` before `weekly_feedback` so task/base work is not misclassified as generic periodic review.
- Evaluate `exercise_kind_management` before `interweave` or `token_guard` so exercise-schema and workout-log requests do not fall through to generic routing.
- Evaluate `portfolio_holdings_management` before `brokerage_activity_management` so current-position and holdings-base requests do not get absorbed by the raw-import workflow.
- Evaluate `brokerage_activity_management` before `interweave` or `token_guard` so brokerage-export and investment-ledger requests resolve to the typed import workflow.
- Evaluate `zettel_management` before `weekly_feedback` — "hub synthesis" and "fleeting capture" are zettel signals, not weekly-review signals.
- Evaluate `zettel_management` before `memory_capture` — "zettel" is a more specific signal than "memory" or "capture".
- Fall back to `token_guard` when uncertain.
