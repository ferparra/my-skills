# Visual Design Patterns

Each pattern maps a conceptual structure to a visual structure.

## Fan-Out (1-to-N Broadcast)

**When to use**: One source distributes to many targets (event broadcast, fan-out queue, multicast)

**Structure**:
- Single source element (left/top)
- Multiple target elements (right/bottom)
- Arrows from source to all targets

**Size tiers**: Source = Primary, Targets = Secondary

**Element count**: 3-10 elements

**Example**: Event emitter → multiple listeners

---

## Convergence (N-to-1 Aggregation)

**When to use**: Many sources aggregate into one target (merge, reduce, join)

**Structure**:
- Multiple source elements (left/top)
- Single target element (right/bottom)
- Arrows from all sources to target

**Size tiers**: Sources = Secondary, Target = Primary

**Element count**: 3-10 elements

**Example**: Multiple streams → aggregator → result

---

## Pipeline/Assembly Line

**When to use**: Linear transformation sequence (data pipeline, processing stages)

**Structure**:
- Horizontal left-to-right flow
- Equal-sized stages
- Arrows between each stage

**Size tiers**: All stages = Primary (unless one is Hero)

**Element count**: 3-8 stages

**Example**: Raw data → Clean → Transform → Validate → Store

---

## Tree (Hierarchical Breakdown)

**When to use**: Hierarchical decomposition, org chart, decision tree

**Structure**:
- Root at top
- Children below, connected by lines (not arrows if non-directional)
- Use lines + free-floating text, NOT boxes at every node

**Size tiers**: Root = Hero, L1 = Primary, L2+ = Secondary

**Element count**: 5-20 nodes

**Example**: Project → Phases → Tasks

---

## Spiral/Cycle (Iterative Process)

**When to use**: Loops, iterations, feedback cycles

**Structure**:
- Circular or spiral arrow path
- Stages arranged around the cycle
- Feedback arrow returns to start

**Size tiers**: All stages = Secondary

**Element count**: 3-6 stages

**Example**: Plan → Build → Test → Review → (loop)

---

## Cloud/Cluster (Loosely Related Concepts)

**When to use**: Related concepts without strict hierarchy or sequence

**Structure**:
- Elements grouped by proximity
- No or minimal arrows
- Use whitespace to create groupings

**Size tiers**: Mixed (important ones larger)

**Element count**: 4-12 elements

**Example**: Microservices in a domain

---

## Swimlane (Parallel Processes)

**When to use**: Multiple actors/systems performing parallel tasks

**Structure**:
- Horizontal lanes (use Frame elements for boundaries)
- Each lane represents one actor/system
- Vertical flow within lanes, horizontal arrows between lanes

**Size tiers**: Lane labels = Primary, steps = Secondary

**Element count**: 2-4 lanes, 3-8 steps per lane

**Example**: User actions | Frontend | Backend | Database

---

## Hub-and-Spoke (Central Coordinator)

**When to use**: Central element coordinates/connects peripheral elements

**Structure**:
- Central hub element (middle)
- Peripheral spoke elements (around hub)
- Arrows between hub and spokes (bidirectional if needed)

**Size tiers**: Hub = Hero, Spokes = Secondary

**Element count**: 1 hub + 4-8 spokes

**Example**: API Gateway → Services
