# Routing Map

## Routes

- `obsidian-planetary-tasks-manager`
  - Trigger: planetary tasks, planetary tasks base, task kind, task schema, Periodic Planning and Tasks Hub, closure signal, maneuver board, jira sync
  - Goal: standardize planetary task frontmatter, validate `task_kind`, and maintain `Planetary Tasks.base` plus the periodic planning hub views without losing task interweaving
  - QMD collections: `periodic` (weekly/daily notes and task notes), `projects` (linked project anchors), optional `entities` when tasks point to people or companies

- `obsidian-exercise-kind-manager`
  - Trigger: exercise kind, exercise schema, exercise library base, Exercise Library.base, exercise selection, progressive overload, training guiding principles, Strong CSV, Strong export, Strong workouts, mobility drill, warm-up flow
  - Goal: standardize exercise note frontmatter, validate `exercise_kind`, sync Strong CSV workout history without duplicate managed sections, parse progression metrics, and maintain `20 Resources/Exercises/Exercise Library.base`
  - QMD collections: `resources` (exercise notes and fitness resources), `inbox` (`00 Inbox/Training guiding principles.md`)

- `obsidian-portfolio-holdings-manager`
  - Trigger: portfolio holdings, Portfolio Holdings.base, Portfolio Holdings History.base, current holdings, actual holdings, active holding, holdings timeline, holdings history, position history
  - Goal: derive current and historical holdings from typed brokerage activity notes, maintain both holdings Bases, and fail validation when a symbol-backed current or history note is missing or stale
  - QMD collections: `resources` (holdings notes, history notes, brokerage activity notes), `inbox` (valuation captures or import-adjacent checks)

- `obsidian-brokerage-activity-manager`
  - Trigger: Betashares, Stake, brokerage activity, brokerage CSV, brokerage export, transaction history, trade history, dividend log, distribution reinvestment, investment ledger, portfolio ledger, `brokerage_activity_kind`, `brokerage_asset_kind`, `Brokerage Activity.base`, `Brokerage Assets.base`
  - Goal: standardize brokerage activity notes and ticker-indexed asset notes, validate both typed schemas, merge duplicate import rows idempotently, and maintain `20 Resources/Investments/Brokerage Activity/Brokerage Activity.base` plus `20 Resources/Investments/Brokerage Assets/Brokerage Assets.base`
  - QMD collections: `resources` (investment notes and ledger notes), `inbox` (capture notes or pasted activity logs)

- `obsidian-notebooklm-bases-manager`
  - Trigger: notebooklm base, notebook lm base, notebooklm frontmatter, notebook lm metadata
  - Goal: maintain NotebookLM notebook metadata and `.base` views with deterministic frontmatter validation
  - QMD collections: `inbox` (NotebookLM source notes and capture notes), `notes` (durable MOCs and lane hubs)

- `obsidian-key-dates-base-manager`
  - Trigger: key dates, key dates base, key dates.base, date-link base
  - Goal: maintain `10 Notes/Key Dates.base` formulas and date-note links with path/existence checks
  - QMD collections: `periodic` (weekly/monthly/yearly notes), `inbox` (daily notes by date)

- `obsidian-interweave-engine` (PIT priority)
  - Trigger: PIT, point-in-time, snapshot, pit_status
  - Goal: keep PIT notes highly retrievable via concept/context interweaving
  - QMD collections: `notes` (link targets — durable concepts), `clippings` (external source material)

- `obsidian-interweave-engine`
  - Trigger: interweave, link, enrich, clipping, wikilink, frontmatter
  - Goal: improve recall and graph quality without reducing source density
  - QMD collections: `notes` (link targets — durable concepts), `clippings` (external source material)

- `obsidian-weekly-feedback-loop`
  - Trigger: weekly synthesis, weekly review, control plane, periodic checks
  - Goal: verify closure signals and planning continuity
  - QMD collections: `periodic` (week/day notes), `inbox` (recent daily captures)

- `obsidian-zettel-manager`
  - Trigger: zettel, zettel_kind, zettel_id, zettel schema, connection_strength, score zettels, migrate zettels, fleeting capture, promote note, evergreen note, litnote, atomic note, hub synthesis, knowledge note
  - Goal: validate and normalise zettel frontmatter, classify zettel_kind, score connection_strength from link graph, and promote fleeting captures to durable notes
  - QMD collections: `notes` (10 Notes/ — primary zettel store), `inbox` (00 Inbox/ — fleeting capture staging)

- `obsidian-agent-memory-capture`
  - Trigger: insight capture, friction pattern, reusable memory
  - Goal: convert execution residue into durable memory notes
  - QMD collections: `notes` (duplicate/merge check), `inbox` (candidate notes being promoted)

- `obsidian-token-budget-guard`
  - Trigger: token budget, context budget, compaction, broad retrieval
  - Goal: block oversized read sets before context inflation
  - QMD collections: `all` (broad scoped search, noise-excluded)

## QMD Collection Reference

| Collection | Folders | Use |
|---|---|---|
| `inbox` | `00 Inbox/` | Unprocessed captures, daily notes |
| `notes` | `10 Notes/`, `Resilience/`, `Personal/` | Durable zettels, core knowledge |
| `projects` | `10 Projects/`, `Projects/` | Active + legacy project notes |
| `resources` | `20 Resources/`, `Resources/` | External references |
| `clippings` | `Clippings/` | Web clippings awaiting processing |
| `periodic` | `Periodic/` | Weekly/daily/monthly planning |
| `entities` | `People/`, `Companies/`, `Products/` | Person and org lookups |
| `archive` | `Archive/` | Historical notes |
| `all` | All above (noise excluded) | Broad cross-vault discovery |

## Domain Hub Reference

The vault knowledge layer is organized into 15 domains under `10 Notes/`. Each domain and subdomain has a `_hub.md` navigation file.

| Domain | Subdomains | Primary Skill |
|---|---|---|
| Agentic Systems | Architecture, Context, Platforms, Observability | zettel-manager, interweave |
| Data Engineering | Platform, Pipelines, Analytics | zettel-manager |
| Software Engineering | Python, DevOps, Foundations | zettel-manager |
| Work and Career | Employer, Career Architecture, Sprint | planetary-tasks, zettel-manager |
| Health and Performance | Training, Nutrition, Supplements, Biomarkers, Recovery | exercise-kind, zettel-manager |
| Philosophy and Psychology | Stoicism, Depth Psychology, Rationalism, Literature, Core Concepts | zettel-manager, interweave |
| Personal Development | Values and Identity, Expressive Writing, Learning Science, Thinking Models | zettel-manager |
| Relationships | Partnership, Family, Social | people-kind, zettel-manager |
| Financial Stewardship | Portfolio, Strategy, Subscriptions | brokerage-activity, portfolio-holdings |
| Knowledge Management | Vault Infrastructure, Agent Memory, Processing | zettel-manager |
| Productivity | Planning, Goals and Habits, Projects | planetary-tasks, weekly-feedback |
| Home and Living | IoT, Kitchen, Server | zettel-manager |
| Recreation | Chess, Music, Outdoors, Media | zettel-manager |
| Security and Privacy | Personal, Agentic | zettel-manager |
| Reading | Clippings | interweave |

Hub navigation entry point: `10 Notes/Domain Hubs for Vault Retrieval.md`

## Shared Read Budget

- Max files: 5
- Max chars: 22000
- Max snippets: 12
