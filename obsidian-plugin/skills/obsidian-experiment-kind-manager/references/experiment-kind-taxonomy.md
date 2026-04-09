# Experiment Kind Taxonomy

`experiment_kind` is the supertag — inspired by Tana's supertag concept. It is
the primary classifier that selects the schema contract, routes council
accountability, and determines domain tagging for each experiment note.

## Kind Registry

### `health`
**Council owner**: `sentinel`
**Domain tag**: `health-and-performance`
**Scope**: Body physiology, supplementation, sleep, nutrition, exercise protocols,
biomarkers, recovery, fasting, stress response.
**Examples**:
- Does 300mg Magnesium Glycinate before bed reduce sleep latency?
- What is the effect of 16:8 intermittent fasting on my HRV score?
- Does cold exposure for 3 minutes post-workout improve next-day energy?

---

### `cognitive`
**Council owner**: `philosopher`
**Domain tag**: `philosophy-and-psychology`
**Scope**: Learning systems, focus protocols, memory, reading retention, note-taking
methodologies, attention management, productivity systems.
**Examples**:
- Does Zettelkasten note-taking improve recall on weekly review?
- What is the effect of a 25-min Pomodoro cadence on sustained focus?
- Does pre-reading a chapter summary improve retention by 30%?

---

### `technical`
**Council owner**: `architect`
**Domain tag**: `agentic-systems`
**Scope**: Engineering workflows, tooling, automation, agentic systems, software
development practices, deployment pipelines, code review patterns.
**Examples**:
- Does switching to test-driven development reduce bug count per sprint?
- Does using Claude Opus for planning cut weekly review time in half?
- Does running daily vault indexing at 06:00 improve qmd query relevance?

---

### `social`
**Council owner**: `steward`
**Domain tag**: `relationships`
**Scope**: Relationship maintenance, communication patterns, network-building,
accountability structures, conflict resolution, collaboration styles.
**Examples**:
- Does weekly async check-ins with my manager improve alignment?
- Does sharing a personal learning goal with a friend increase accountability?
- What is the effect of monthly 1:1s with distant collaborators on relationship strength?

---

### `financial`
**Council owner**: `sentinel`
**Domain tag**: `financial-stewardship`
**Scope**: Investment strategies, spending behaviour, savings rate, portfolio
allocation, compound return optimisation, financial habit formation.
**Examples**:
- Does a weekly spending review reduce discretionary expenses by 10%?
- What is the return differential between passive and active ETF allocation over 12 months?
- Does automating savings on payday increase my savings rate?

---

### `creative`
**Council owner**: `philosopher`
**Domain tag**: `philosophy-and-psychology`
**Scope**: Writing output, artistic practice, creative rituals, content creation
cadence, creative block interventions, aesthetic exploration.
**Examples**:
- Does morning freewriting for 20 minutes increase the quality of my weekly note?
- What is the effect of working in silence vs. ambient music on writing output?
- Does publishing a weekly reflection increase my sense of creative completion?

---

### `philosophical`
**Council owner**: `philosopher`
**Domain tag**: `philosophy-and-psychology`
**Scope**: Beliefs, values, identity, mindset experiments, meaning-making practices,
stoic exercises, belief-updating protocols.
**Examples**:
- Does a weekly memento mori reflection shift my priority-setting?
- Does practising gratitude journaling for 30 days change my baseline mood assessment?
- What is the effect of deliberate uncertainty journaling on my decision confidence?

---

## Lifecycle Policy

```
hypothesis → design → running → paused → concluded → archived
```

| Transition | Who triggers | Validation check |
|---|---|---|
| `hypothesis` → `design` | Human intent | `metrics` must be defined |
| `design` → `running` | Human intent | `start_date` recommended |
| `running` → `paused` | Human intent | No constraint |
| `paused` → `running` | Human intent | No constraint |
| `* → concluded` | Human intent | `findings` required; `outcome` ≠ `ongoing` |
| `concluded` → `archived` | Human intent | No constraint |

**Guardrails:**
- Migrator never auto-transitions to `concluded` or `archived`.
- `outcome` defaults to `ongoing`; only the human sets a terminal outcome.
- `experiment_id` is stable once set — never auto-regenerated.

## Inference Heuristics (for migration)

The migrator uses these signals in priority order to infer kind:

1. Explicit `experiment_kind` field (highest priority)
2. `experiment-kind/{kind}` tag
3. Parent folder name
4. Keyword matching in `question` + `hypothesis` + `method` text
5. Fallback: `None` — ambiguous, requires human confirmation

Ambiguous notes are **skipped** in fix mode and reported with a warning.

## Council Routing Table

| Kind | Council Owner | Domain Tag |
|---|---|---|
| `health` | `sentinel` | `health-and-performance` |
| `cognitive` | `philosopher` | `philosophy-and-psychology` |
| `technical` | `architect` | `agentic-systems` |
| `social` | `steward` | `relationships` |
| `financial` | `sentinel` | `financial-stewardship` |
| `creative` | `philosopher` | `philosophy-and-psychology` |
| `philosophical` | `philosopher` | `philosophy-and-psychology` |

The Experiments hub (`10 Notes/Productivity/Experiments/`) sits under the
**Strategist's** Productivity domain — Strategist owns the experiment
_infrastructure_. `council_owner` on each note identifies the domain
_content_ accountable councillor.
