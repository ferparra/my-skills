# Visual Heuristics

## Layout Rules

### Size Tiers

Use distinct size tiers to establish visual hierarchy:

- **Hero**: 300×150px — Most important element, visual anchor
- **Primary**: 180×90px — Key concepts
- **Secondary**: 120×60px — Supporting elements  
- **Small**: 60×40px — Minor details, markers

### Whitespace

- 1.5× element width between sibling elements
- 2× element width between groups
- Most important element gets 200px+ empty space around it

### Flow Direction

- **Left-to-right**: Default for sequences, processes
- **Top-to-bottom**: Hierarchies, trees
- **Radial**: Hub-and-spoke patterns

### Overlap & Spacing

- Max overlap: 15% of smaller element's area
- Min gap between elements: 20px
- Spacing consistency: CV < 0.5

## Quality Checklist

### 1. Depth & Evidence (Technical Diagrams)

- [ ] Research done (actual API names, data formats)
- [ ] Evidence artifacts present (code snippets, JSON payloads)
- [ ] Multi-zoom levels (summary + detail)
- [ ] Concrete over abstract

### 2. Conceptual

- [ ] Isomorphism test: visual structure mirrors concept behavior
- [ ] Argument test: diagram shows something text alone could not
- [ ] Variety: each major concept uses different visual pattern
- [ ] No uniform containers

### 3. Container Discipline

- [ ] <30% of text elements in containers
- [ ] Lines as structure (trees/timelines use lines + free text, not boxes)
- [ ] Typography hierarchy (size + color create hierarchy)

### 4. Structural

- [ ] Every relationship has an arrow or line
- [ ] Clear visual flow path
- [ ] Important elements are larger/more isolated

### 5. Technical (JSON Correctness)

- [ ] `text` contains only readable words
- [ ] `fontFamily: 3` (monospace) for all text
- [ ] `roughness: 0` for clean edges
- [ ] `opacity: 100` for all elements

### 6. Visual Validation (Render Required)

- [ ] Rendered to PNG and visually inspected
- [ ] No text overflow or clipping
- [ ] No overlapping elements (unless intentional)
- [ ] Even spacing
- [ ] Arrows land correctly on targets
- [ ] Text readable at export size
- [ ] Balanced composition (center of mass, quadrants)

## Anti-Patterns

| Anti-Pattern | Why It's Bad |
|-------------|-------------|
| 5 equal boxes with labels | Displays instead of arguing |
| Card grid layout | Uniform structure doesn't mirror conceptual differences |
| Icons decorating text | Shapes should BE the meaning |
| Same container for everything | No visual vocabulary |
| Everything in a box | Boxes should carry meaning, not be default |
| Generic labels ("Input", "Process") | Not educational; use real names |
| All same size | No hierarchy |
| High overlap (>15%) | Visual confusion |
| Inconsistent spacing | Looks unpolished |
