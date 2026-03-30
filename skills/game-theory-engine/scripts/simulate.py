#!/usr/bin/env python3
"""
Game Theory Engine — Monte Carlo Simulation Script

Runs Monte Carlo simulations over a game-theoretic scenario to produce
expected value distributions, sensitivity analysis, and convergence
diagnostics. Designed for Deep mode invocations.

Usage:
    python simulate.py --scenario '{"decision":...}' --iterations 10000 --output /tmp/out.json
    python simulate.py --scenario-file scenario.json --iterations 10000 --output /tmp/out.json
"""

import argparse
import json
import sys
import math
import random
from collections import defaultdict
from typing import Any


def parse_args():
    parser = argparse.ArgumentParser(description="Game Theory Monte Carlo Simulator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scenario", type=str, help="Scenario JSON as string")
    group.add_argument("--scenario-file", type=str, help="Path to scenario JSON file")
    parser.add_argument("--iterations", type=int, default=10000, help="Number of Monte Carlo iterations")
    parser.add_argument("--output", type=str, required=True, help="Output JSON file path")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    return parser.parse_args()


def load_scenario(args) -> dict:
    if args.scenario:
        return json.loads(args.scenario)
    with open(args.scenario_file, "r") as f:
        return json.load(f)


def validate_scenario(scenario: dict) -> None:
    required = ["decision", "options", "players", "payoffs"]
    missing = [k for k in required if k not in scenario]
    if missing:
        raise ValueError(f"Scenario missing required fields: {missing}")
    if not scenario["options"]:
        raise ValueError("Scenario must have at least one option")
    if not scenario["players"]:
        raise ValueError("Scenario must have at least one player")


def perturb_payoff(value: float, noise_std: float = 1.5) -> float:
    """Add Gaussian noise to a payoff value, clamped to [-10, 10]."""
    return max(-10.0, min(10.0, value + random.gauss(0, noise_std)))


def compute_composite(payoff_dict: dict, weights: dict | None = None) -> float:
    """Compute weighted composite from material/social/temporal payoffs."""
    if weights is None:
        weights = {"material": 0.4, "social": 0.3, "temporal": 0.3}
    total = 0.0
    for dim, default_w in weights.items():
        total += payoff_dict.get(dim, 0.0) * default_w
    return total


def compute_power_weighted_ev(
    option: str,
    players: list[dict],
    payoffs: dict,
    decision_maker: str | None = None,
) -> float:
    """
    Compute expected value of an option weighted by player power.
    The decision-maker's payoff is weighted at 2x to reflect that
    their utility is the primary objective.
    """
    total = 0.0
    weight_sum = 0.0
    for player in players:
        pid = player["id"]
        power = player.get("power", 0.5)
        if pid == decision_maker:
            power *= 2.0  # decision-maker's utility is primary
        player_payoffs = payoffs.get(pid, {}).get(option, {})
        composite = compute_composite(player_payoffs)
        total += composite * power
        weight_sum += power
    return total / weight_sum if weight_sum > 0 else 0.0


def run_simulation(scenario: dict, iterations: int) -> dict:
    """Run Monte Carlo simulation and return results."""
    options = scenario["options"]
    players = scenario["players"]
    payoffs = scenario["payoffs"]
    uncertainties = scenario.get("uncertainties", [])

    # Identify decision-maker (first player, or one marked as such)
    decision_maker = None
    for p in players:
        if p.get("is_decision_maker", False):
            decision_maker = p["id"]
            break
    if decision_maker is None and players:
        decision_maker = players[0]["id"]

    # Determine noise level from uncertainty count
    base_noise = 1.0 + 0.3 * len(uncertainties)

    # Track EV samples per option
    ev_samples: dict[str, list[float]] = {opt: [] for opt in options}
    win_counts: dict[str, int] = {opt: 0 for opt in options}

    # Sensitivity: track which perturbation dimensions cause rank flips
    sensitivity_counts: dict[str, int] = defaultdict(int)

    for i in range(iterations):
        # Perturb payoffs
        perturbed_payoffs: dict = {}
        perturbed_dims: list[str] = []
        for pid, opts in payoffs.items():
            perturbed_payoffs[pid] = {}
            for opt, dims in opts.items():
                perturbed = {}
                for dim, val in dims.items():
                    new_val = perturb_payoff(float(val), noise_std=base_noise)
                    if abs(new_val - float(val)) > base_noise:
                        perturbed_dims.append(f"{pid}.{opt}.{dim}")
                    perturbed[dim] = new_val
                perturbed_payoffs[pid][opt] = perturbed

        # Compute EV for each option under perturbation
        evs = {}
        for opt in options:
            evs[opt] = compute_power_weighted_ev(opt, players, perturbed_payoffs, decision_maker)
            ev_samples[opt].append(evs[opt])

        # Track winner
        winner = max(evs, key=evs.get)
        win_counts[winner] += 1

        # Track sensitivity
        for dim in set(perturbed_dims):
            sensitivity_counts[dim] += 1

    # Compute statistics
    results: dict[str, Any] = {
        "decision": scenario["decision"],
        "iterations": iterations,
        "options": {},
        "ranking": [],
        "sensitivity": {},
        "convergence": {},
    }

    option_stats = []
    for opt in options:
        samples = ev_samples[opt]
        n = len(samples)
        mean = sum(samples) / n
        sorted_s = sorted(samples)
        median = sorted_s[n // 2]
        variance = sum((x - mean) ** 2 for x in samples) / n
        std = math.sqrt(variance)
        p5 = sorted_s[int(n * 0.05)]
        p95 = sorted_s[int(n * 0.95)]
        win_prob = win_counts[opt] / iterations

        stat = {
            "name": opt,
            "expected_value": round(mean, 3),
            "median": round(median, 3),
            "std": round(std, 3),
            "percentile_5": round(p5, 3),
            "percentile_95": round(p95, 3),
            "probability_optimal": round(win_prob, 4),
        }
        results["options"][opt] = stat
        option_stats.append((mean, opt, stat))

    # Sort by EV descending
    option_stats.sort(key=lambda x: -x[0])
    results["ranking"] = [
        {"rank": i + 1, "option": name, "expected_value": round(ev, 3), "probability_optimal": stat["probability_optimal"]}
        for i, (ev, name, stat) in enumerate(option_stats)
    ]

    # Top sensitivity drivers
    total_perturbations = sum(sensitivity_counts.values()) or 1
    top_sensitivity = sorted(sensitivity_counts.items(), key=lambda x: -x[1])[:10]
    results["sensitivity"] = {
        k: round(v / total_perturbations, 4) for k, v in top_sensitivity
    }

    # Convergence: check if rankings stabilise in the last 20% of iterations
    last_20_start = int(iterations * 0.8)
    last_20_winners = []
    for i in range(last_20_start, iterations):
        iter_evs = {opt: ev_samples[opt][i] for opt in options}
        last_20_winners.append(max(iter_evs, key=iter_evs.get))
    if last_20_winners:
        mode_winner = max(set(last_20_winners), key=last_20_winners.count)
        convergence_rate = last_20_winners.count(mode_winner) / len(last_20_winners)
    else:
        convergence_rate = 0.0
    results["convergence"] = {
        "converged": convergence_rate > 0.7,
        "convergence_rate": round(convergence_rate, 4),
        "dominant_option_in_tail": mode_winner if last_20_winners else None,
    }

    return results


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    scenario = load_scenario(args)
    validate_scenario(scenario)

    results = run_simulation(scenario, args.iterations)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary to stdout
    print(f"Simulation complete: {args.iterations} iterations")
    print(f"Ranking:")
    for r in results["ranking"]:
        print(f"  #{r['rank']}: {r['option']} (EV={r['expected_value']}, P(optimal)={r['probability_optimal']})")
    print(f"Convergence: {'Yes' if results['convergence']['converged'] else 'No'} "
          f"(rate={results['convergence']['convergence_rate']})")
    print(f"Full results written to: {args.output}")


if __name__ == "__main__":
    main()
