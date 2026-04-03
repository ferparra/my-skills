# Annotation Schema Specification

Version 1.0. This schema is the stable interface between SVG references, SVG
generation, and the deterministic SVG-to-Excalidraw transform. It does NOT
change when reference SVGs are regenerated.

---

## 1. Required Comments

### DIAGRAM_TYPE

First child element of `<svg>`. Machine-readable type slug matching the filename
slug.

```xml
<!-- DIAGRAM_TYPE: hub_spoke -->
```

Valid values: `big_picture_timeline`, `bounded_context_map`, `cloud_cluster`,
`concept_map`, `convergence`, `design_level_aggregate`, `erd`, `fan_out`,
`hub_spoke`, `iterative_cycle`, `layered_architecture`, `mind_map`, `pipeline`,
`process_level_flow`, `sequence`, `service_blueprint`, `stock_and_flow`,
`swimlane`, `system_control`, `systems_thinking`, `tree`, `uml_state_machine`.

### TOPOLOGY

Second child element. Describes the graph structure in plain text.

```xml
<!-- TOPOLOGY: Star topology with 1 central hub and 5 spoke nodes. 6 nodes, 5 bidirectional edges (10 directed). Spokes are isolated from each other. -->
```

Must include:
- Topology shape (star, linear, tree, DAG, cycle, layered, etc.)
- Node count
- Edge count (clarify directed vs bidirectional if applicable)
- Notable structural features (isolation constraints, parallel forks, etc.)

---

## 2. `<desc>` Element

Natural language summary for LLM consumption. Placed after the TOPOLOGY comment.

```xml
<desc>A hub-and-spoke communication pattern showing a central coordinator.
A Central Hub connects bidirectionally to 5 spoke nodes...</desc>
```

Requirements:
- 2-4 sentences
- Describe the diagram's content, purpose, and key relationships
- Name all nodes and their roles
- Mention notable constraints or patterns

---

## 3. `<g>` Group Attributes

Every visual element must be wrapped in a `<g>` group.

### Required Attributes

| Attribute            | Value                                        | Notes                          |
|----------------------|----------------------------------------------|--------------------------------|
| `id`                 | Unique kebab-case string                     | See naming conventions below   |
| `role`               | `"img"` or `"heading"`                       | `"heading"` only for title     |
| `aria-label`         | Human-readable description                   | Full sentence preferred        |
| `data-semantic-role` | One of the vocabulary values                 | See vocabulary table below     |

### Example

```xml
<g id="node-api-gateway"
   role="img"
   aria-label="Central Hub: API Gateway with load balancing"
   data-semantic-role="node"
   data-downstream="node-auth-service,node-billing-service"
   data-upstream="node-web-client,node-mobile-app">
  <!-- visual content here -->
</g>
```

---

## 4. Node Attributes

Applied to any `<g>` with a node-like semantic role: `node`, `stock`, `entity`,
`state`, `initial-state`, `final-state`, `aggregate-root`, `value-object`,
`cloud`, `auxiliary`.

| Attribute          | Format                            | Description                          |
|--------------------|-----------------------------------|--------------------------------------|
| `data-upstream`    | Comma-separated node IDs          | Nodes that feed into this node       |
| `data-downstream`  | Comma-separated node IDs          | Nodes this node feeds into           |

- Omit the attribute entirely if there are no connections in that direction.
  Do not use an empty string.
- IDs must reference existing `<g>` elements in the same SVG.

---

## 5. Edge Attributes

Applied to any `<g>` with an edge-like semantic role: `edge`, `relationship`,
`transition`, `flow`.

| Attribute    | Format          | Description                     |
|--------------|-----------------|---------------------------------|
| `data-from`  | Single node ID  | Source node of the connection   |
| `data-to`    | Single node ID  | Target node of the connection   |

- Both attributes are required on every edge group.
- IDs must reference existing node-like `<g>` elements.

---

## 6. Domain-Specific Attributes

Optional attributes used by specific diagram types.

| Attribute              | Diagram Types        | Format / Example                | Description                                      |
|------------------------|----------------------|---------------------------------|--------------------------------------------------|
| `data-cardinality`     | `erd`                | `"1:0..*"`, `"1:1..*"`         | Crow's Foot cardinality between entities         |
| `data-lane`            | `swimlane`           | `"customer"`, `"warehouse"`    | Lane assignment for a node                       |
| `data-layer`           | `layered_architecture` | `"presentation"`, `"domain"` | Layer assignment for a node                      |
| `data-visibility`      | `design_level_aggregate` | `"public"`, `"private"`    | Visibility of a method or field                  |
| `data-trigger`         | `uml_state_machine`  | `"timeout"`, `"user_click"`    | Event that triggers a transition                 |
| `data-entity-fields`   | `erd`                | `"id PK, name, email"`         | Comma-separated field list with key annotations  |
| `data-label`           | `erd`, `flow`, etc.  | `"PLACES"`, `"Prey Births"`    | Display label for a relationship or flow         |

---

## 7. `data-semantic-role` Vocabulary

### Core Roles

| Role          | Description                                                    |
|---------------|----------------------------------------------------------------|
| `node`        | A box, circle, or shape representing an entity or concept      |
| `edge`        | A line or arrow connecting two nodes                           |
| `annotation`  | Explanatory text or decoration not part of the graph structure |
| `label`       | Text label attached to a node or edge                          |
| `title`       | Diagram title group (usually paired with `role="heading"`)     |
| `legend`      | Legend or key explaining symbols, colors, or notation          |
| `container`   | A grouping rectangle that visually contains child nodes        |
| `layer`       | A horizontal band in a layered architecture diagram            |
| `lane`        | A vertical or horizontal swimlane                              |

### Domain-Specific Roles

| Role               | Diagram Types              | Description                                      |
|---------------------|---------------------------|--------------------------------------------------|
| `state`            | `uml_state_machine`        | A state node                                     |
| `initial-state`    | `uml_state_machine`        | Filled circle representing the start state       |
| `final-state`      | `uml_state_machine`        | Bullseye circle representing the end state       |
| `guard-condition`  | `uml_state_machine`        | Bracketed condition on a transition              |
| `transition`       | `uml_state_machine`        | A state-to-state edge (semantic alias for edge)  |
| `stock`            | `stock_and_flow`           | An accumulation (drawn as a rectangle)           |
| `flow`             | `stock_and_flow`           | A rate pipe connecting stocks or clouds          |
| `valve`            | `stock_and_flow`           | Diamond controlling a flow rate                  |
| `cloud`            | `stock_and_flow`           | A source or sink outside the system boundary     |
| `auxiliary`        | `stock_and_flow`           | An auxiliary variable influencing flows           |
| `entity`           | `erd`                      | An entity box with field list                    |
| `relationship`     | `erd`                      | An edge with cardinality notation                |
| `aggregate-root`   | `design_level_aggregate`   | DDD aggregate root box                           |
| `value-object`     | `design_level_aggregate`   | DDD value object box                             |

---

## 8. ID Naming Conventions

- All IDs are **kebab-case** (lowercase, hyphen-separated).
- Prefix with the semantic role:

| Prefix      | Used for                          | Example                      |
|-------------|-----------------------------------|------------------------------|
| `node-`     | Generic nodes                     | `node-api-gateway`           |
| `edge-`     | Generic edges                     | `edge-user-to-auth`          |
| `label-`    | Text labels                       | `label-request-count`        |
| `lane-`     | Swimlane backgrounds              | `lane-customer`              |
| `layer-`    | Architecture layers               | `layer-presentation`         |
| `stock-`    | System dynamics stocks            | `stock-prey-population`      |
| `flow-`     | System dynamics flows             | `flow-prey-births`           |
| `valve-`    | System dynamics valves            | `valve-prey-births`          |
| `cloud-`    | System dynamics sources/sinks     | `cloud-prey-source`          |
| `entity-`   | ER diagram entities               | `entity-customer`            |
| `state-`    | State machine states              | `state-idle`                 |
| `diagram-`  | Title and diagram-level groups    | `diagram-title`              |
| `annotation-` | Explanatory annotations         | `annotation-spoke-isolation` |
| `legend-`   | Legend groups                     | `legend-symbols`             |

- Edge IDs should encode the connection: `edge-{from}-to-{to}` (e.g.,
  `edge-user-to-auth`).
- Label IDs should describe their content: `label-{content}` (e.g.,
  `label-token-translation`).
