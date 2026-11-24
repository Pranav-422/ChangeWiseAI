"""Baseline A, Baseline B and ChangeWise side by side on one scenario."""
from ..engine.config import load_config, load_simulator
from ..engine.pipeline import run_optimization
from .baselines import run_baseline_a, run_baseline_b

PROPOSED = "CHANGEWISE"


def proposed_row(result):
    best = result["recommendations"][0]
    weekly = best["weekly"]
    return {
        "configuration": PROPOSED,
        "assumptions": ["Best feasible plan under the official lexicographic objective."],
        "weekly": weekly,
        "shortage_units": best["shortage_units"],
        "shortage_weeks": [w["week"] for w in weekly if w["shortage"] > 0],
        "rev_b_leftover": weekly[-1]["rev_b_closing"],
        "rev_c_closing": weekly[-1]["rev_c_closing"],
        "excess_value": best["excess_value"],
        "action_cost": best["action_cost"],
        "secondary_cost": best["secondary_cost"],
        "hard_rule_violations": 0 if best["feasibility"] == "FEASIBLE" else 1,
        "robustness": best["robustness"],
    }


def compare_configurations(data, config=None, simulate=None, result=None):
    """Rows for A, B and the proposal. The proposal row is absent when no plan is recommended."""
    config = config or load_config()
    simulate = simulate or load_simulator(config)
    result = result or run_optimization(data, config, simulate)
    if result["decision"] == "INVALID_DATA":
        return []
    rows = [run_baseline_a(data, simulate, config), run_baseline_b(data, simulate, config)]
    if result["recommendations"]:
        rows.append(proposed_row(result))
    return rows
