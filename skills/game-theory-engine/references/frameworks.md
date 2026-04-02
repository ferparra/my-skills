# Game Theory Frameworks Reference

Quick-reference for selecting the right framework. Read this during
Phase 1 (Problem Formalisation) to classify the game.

---

## Framework Selection Matrix

| Situation | Framework | Solution Concept |
|-----------|-----------|-----------------|
| Clear choices, each player picks independently | Normal form game | Dominant strategy / Nash equilibrium |
| Players move in sequence, can observe prior moves | Extensive form game | Subgame perfect equilibrium (backward induction) |
| Players don't know others' payoffs | Bayesian game | Bayesian Nash equilibrium |
| Players interact repeatedly over time | Repeated game | Folk theorem / trigger strategies |
| Players can form binding agreements | Cooperative game | Core / Shapley value |
| One player designs the rules | Mechanism design | Incentive compatibility |
| Population-level strategy dynamics | Evolutionary game | Evolutionarily stable strategy |
| Players signal private information | Signaling game | Perfect Bayesian equilibrium |
| Multiple equilibria, need to coordinate | Coordination game | Focal point / Schelling point |
| One player commits first | Stackelberg game | Stackelberg equilibrium |

---

## Key Solution Concepts

### Dominant Strategy
A strategy that's best regardless of what others do. If one exists,
it's the answer — no simulation needed. Check for this first; it
short-circuits everything.

### Nash Equilibrium
A strategy profile where no player can improve by unilaterally changing.
Multiple equilibria can exist. To select among them:
1. Pareto dominance: pick the equilibrium where no one is worse off
2. Risk dominance: pick the one that's safer under uncertainty
3. Focal point: pick the one that's "obvious" given shared context

### Subgame Perfect Equilibrium
For sequential games: solve by backward induction from the final move.
Eliminates non-credible threats (promises/threats that wouldn't be
rational to carry out). Important for negotiations and staged decisions.

### Bayesian Nash Equilibrium
When players have private information (types). Each player's strategy
is a best response to the expected strategies of others, given beliefs
about their types. Useful for hiring decisions, negotiations where you
don't know the other side's walkaway price.

### Mechanism Design (Reverse Game Theory)
Instead of solving a game, design the rules to produce a desired outcome.
Applicable when the decision-maker has authority to structure the
interaction. Key constraint: incentive compatibility (the rules must
make truthful behaviour optimal).

---

## Common Real-World Patterns

### The Prisoner's Dilemma
Both sides benefit from cooperation, but each has incentive to defect.
Appears in: price wars, arms races, team free-riding, shared resources.
**Resolution levers**: repeated interaction, reputation, enforceable
contracts, changing payoffs.

### The Coordination Game
Multiple equilibria, everyone benefits from coordinating on the same
one. Appears in: technology adoption, team norms, scheduling.
**Resolution levers**: communication, focal points, leadership.

### The Principal-Agent Problem
The principal delegates to an agent whose interests diverge. Information
asymmetry means the principal can't perfectly monitor.
Appears in: employer-employee, investor-manager, client-vendor.
**Resolution levers**: incentive alignment, monitoring, reputation,
bonding.

### The Ultimatum Game
One player proposes a split, the other accepts or both get nothing.
Reveals that fairness norms override pure EV maximisation.
**Key insight**: offers below ~30% are routinely rejected even though
accepting any positive amount is "rational". Model social payoffs.

### Chicken / Hawk-Dove
Two players on collision course, each hoping the other swerves first.
Appears in: deadline standoffs, territory disputes, escalation dynamics.
**Resolution levers**: commitment devices, signaling, asymmetric stakes.

### The Stag Hunt
Cooperation yields the best outcome, but only if both cooperate.
Safer to defect (hunt hare) alone. Trust is the key variable.
Appears in: ambitious joint projects, high-trust partnerships.
**Resolution levers**: trust-building, incremental commitment, penalties.

---

## Payoff Estimation Heuristics

When assigning -10 to +10 payoffs from qualitative descriptions:

| Signal | Material | Social | Temporal |
|--------|----------|--------|----------|
| "Life-changing upside" | +8 to +10 | — | — |
| "Significant career boost" | +5 to +7 | +3 to +5 | — |
| "Moderate improvement" | +2 to +4 | +1 to +3 | — |
| "Neutral" | 0 | 0 | 0 |
| "Uncomfortable but survivable" | -2 to -4 | -2 to -4 | -1 to -3 |
| "Serious downside" | -5 to -7 | -4 to -6 | -3 to -5 |
| "Catastrophic" | -8 to -10 | -7 to -10 | -7 to -10 |

For temporal payoffs specifically:
- "Buys time / preserves options": +3 to +5
- "Burns a bridge / irreversible": -5 to -8
- "Short-term pain, long-term gain": material -3, temporal +5

---

## When NOT to Use Game Theory

Not every decision is a strategic interaction. Game theory adds value
when there are multiple agents with potentially misaligned incentives.
It adds less value for:

- Pure optimisation problems (one agent, no strategic interaction)
- Decisions driven entirely by personal values (where do I want to live?)
- Situations with no meaningful uncertainty

In these cases, the engine should still work — it just collapses to
a simpler decision-theoretic framework (expected utility maximisation)
rather than a full game-theoretic model.
