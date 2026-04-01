# Semantic Color Palette

Colors encode meaning in Excalidraw diagrams. Use this palette consistently.

## Primary Colors

| Role | Hex | Usage |
|------|-----|-------|
| **Start/Entry** | `#FF9900` | Process entry points, triggers, initial state |
| **End/Complete** | `#00CC66` | Terminal states, success, completion |
| **Decision** | `#FFCC00` | Decision diamonds, branching logic |
| **AI/Agent** | `#9966FF` | AI-driven steps, agent actions |
| **Error/Risk** | `#FF3333` | Error paths, warnings, failure states |
| **Data/Storage** | `#3399FF` | Data stores, databases, caches |
| **Human/Manual** | `#FFB366` | Human-in-the-loop, manual steps |
| **Default/Neutral** | `#E8E8E8` | Background containers, neutral states |
| **Accent/Text** | `#1E1E1E` | Stroke color, primary text |

## Usage Guidelines

- Use `strokeColor` for borders/outlines
- Use `backgroundColor` for fills
- Use `transparent` for text-only elements
- Text color should contrast with background (use dark on light, light on dark)
- Limit to 3-4 colors per diagram for clarity

## Examples

**Process flow**:
- Start: Orange rectangle
- Steps: Light gray rectangles
- Decision: Yellow diamond
- End: Green rectangle
- Error: Red rectangle

**System architecture**:
- Services: Blue rectangles
- Data stores: Blue with darker stroke
- External APIs: Purple rectangles
- Users: Orange ellipses
