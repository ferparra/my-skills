#!/usr/bin/env python3
"""Classify user intent to one of 22 diagram types."""

import argparse
import json
import sys

DIAGRAM_KEYWORDS = {
    "pipeline": ["pipeline", "etl", "data flow", "sequential", "assembly line", "ci/cd", "stages"],
    "swimlane": ["swimlane", "swim lane", "cross-functional", "parallel processes", "handoff"],
    "erd": ["erd", "entity relationship", "database schema", "data model", "tables", "foreign key"],
    "bounded_context_map": ["bounded context", "ddd context", "microservice boundary", "integration pattern"],
    "service_blueprint": ["service blueprint", "customer journey", "frontstage", "backstage", "touchpoint"],
    "convergence": ["convergence", "fan-in", "aggregat", "merge streams", "n-to-1"],
    "fan_out": ["fan-out", "fan out", "broadcast", "publish subscribe", "pub/sub", "1-to-n"],
    "iterative_cycle": ["cycle", "iterative", "sprint", "pdca", "loop", "agile"],
    "stock_and_flow": ["stock and flow", "system dynamics", "accumulator", "lotka", "predator prey"],
    "systems_thinking": ["systems thinking", "causal loop", "reinforcing loop", "balancing loop", "feedback"],
    "system_control": ["control system", "feedback control", "pid", "controller", "plant", "sensor"],
    "design_level_aggregate": ["aggregate", "ddd aggregate", "domain model", "value object", "aggregate root"],
    "concept_map": ["concept map", "knowledge map", "conceptual", "relationships between ideas"],
    "hub_spoke": ["hub and spoke", "hub-spoke", "central coordinator", "star topology"],
    "tree": ["tree", "hierarchy", "decomposition", "breakdown", "org chart"],
    "mind_map": ["mind map", "brainstorm", "radial", "central idea", "branches"],
    "big_picture_timeline": ["timeline", "milestones", "chronological", "event storming big picture"],
    "sequence": ["sequence", "message flow", "request response", "interaction", "lifeline"],
    "uml_state_machine": ["state machine", "state diagram", "transition", "fsm", "lifecycle"],
    "cloud_cluster": ["cloud", "cluster", "vpc", "service mesh", "microservices topology"],
    "layered_architecture": ["layered", "architecture layers", "presentation layer", "business logic"],
    "process_level_flow": ["process flow", "event storming process", "command event", "domain event flow"],
}


def classify(intent: str) -> dict[str, object]:
    """Classify intent text against the keyword map."""
    intent_lower = intent.lower()
    scores: dict[str, int] = {}

    for diagram_type, keywords in DIAGRAM_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in intent_lower)
        if hits > 0:
            scores[diagram_type] = hits

    if not scores:
        return {
            "diagram_type": "concept_map",
            "confidence": "low",
            "alternatives": [],
        }

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_type, best_hits = ranked[0]

    if best_hits >= 3:
        confidence = "high"
    elif best_hits == 2:
        confidence = "medium"
    else:
        confidence = "low"

    alternatives = [t for t, _ in ranked[1:4]]

    return {
        "diagram_type": best_type,
        "confidence": confidence,
        "alternatives": alternatives,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify user intent to a diagram type.")
    parser.add_argument("--intent", type=str, help="User's description of the diagram they want.")
    parser.add_argument("--list", action="store_true", help="Print all 22 diagram types.")
    args = parser.parse_args()

    if args.list:
        for dtype in sorted(DIAGRAM_KEYWORDS):
            print(dtype)
        return

    if not args.intent:
        parser.error("--intent is required unless --list is used.")

    result = classify(args.intent)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
