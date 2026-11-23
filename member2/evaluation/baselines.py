"""Baselines A and B, on the same inputs and the same simulator as the proposed plan."""
from ..engine.action_generator import make_plan
from ..engine.constraints import validate_plan
from ..engine.planner import apply_plan_actions, run_simulation
from ..engine.robustness import calculate_robustness, generate_stress_scenarios, run_plan_under_stress

ASSUMPTIONS = {
    "BASELINE_A": [
        "Original effective week, purchase orders, lead times and demand.",
        "Rev B is used before the effective week and Rev C from it; no corrective action.",
    ],
    "BASELINE_B": [
        "Simplified SAP-style discontinuation logic; it does not reproduce SAP functionality.",
        "Rev B is consumed first until it runs out or reaches its use-up end, then Rev C.",
        "Rev C is not used before the original effective week; no order is changed.",
    ],
}


def _run_baseline(name, actions, data, simulate, config):
    plan = {**make_plan(actions, data, "BASELINE"), "plan_id": name}
    result = run_simulation(apply_plan_actions(plan, data), simulate)
    stress = [run_plan_under_stress(plan, s, data, simulate) for s in generate_stress_scenarios(config)]
    return {
        "configuration": name,
        "assumptions": ASSUMPTIONS[name],
        "weekly": result["weekly"],
        "shortage_units": result["total_shortage"],
        "shortage_weeks": [w["week"] for w in result["weekly"] if w["shortage"] > 0],
        "rev_b_leftover": result["rev_b_leftover"],
        "rev_c_closing": result["rev_c_closing"],
        "excess_value": result["total_excess_value"],
        "action_cost": 0,
        "secondary_cost": result["total_excess_value"],
        "hard_rule_violations": len(validate_plan(plan, data, result)["rejection_reasons"]),
        "robustness": calculate_robustness(stress),
    }


def run_baseline_a(data, simulate, config):
    return _run_baseline("BASELINE_A", [], data, simulate, config)


def run_baseline_b(data, simulate, config):
    use_up = data["engineering_change"]["use_up_end_week"]
    return _run_baseline("BASELINE_B", [{"action": "CONTINUE_REV_B", "through_week": use_up}],
                         data, simulate, config)
