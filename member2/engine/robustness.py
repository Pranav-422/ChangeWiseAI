"""Nine-scenario stress test: Rev C lead time +0/+1/+2 weeks by demand -10%/0/+10%.

Supplementary evidence only. It never changes the lexicographic ranking.
"""
from itertools import product

from .config import load_config
from .constraints import IN_HAND_PO
from .escalation import escalation
from .planner import apply_plan_actions, run_simulation


def generate_stress_scenarios(config=None):
    policy = (config or load_config())["robustness"]
    return [
        {"scenario_id": f"LT+{lead}_D{demand * 100:+.0f}%", "lead_time_shock": lead, "demand_shock": demand}
        for lead, demand in product(policy["lead_time_shocks"], policy["demand_shocks"])
    ]


def apply_shock(data, scenario):
    """Shock an isolated scenario copy in place: scale demand, delay undelivered Rev C orders."""
    for row in data["demand"]:
        row["quantity"] = round(row["quantity"] * (1 + scenario["demand_shock"]))
    for po in data["purchase_orders"]:
        if (po["material_id"] == data["engineering_change"]["new_material_id"]
                and po["status"] not in IN_HAND_PO):
            po["arrival_week"] += scenario["lead_time_shock"]
    return data


def run_plan_under_stress(plan, scenario, data, simulation_engine):
    result = run_simulation(apply_shock(apply_plan_actions(plan, data), scenario), simulation_engine)
    return {**scenario, "shortage_units": result["total_shortage"],
            "excess_value": result["total_excess_value"],
            "zero_shortage": result["total_shortage"] == 0}


def calculate_robustness(results):
    if not results:
        raise ValueError("robustness needs at least one stress result")
    passed = sum(r["zero_shortage"] for r in results)
    return {"numerator": passed, "denominator": len(results), "ratio": passed / len(results),
            "display": f"{passed}/{len(results)}", "scenarios": results}


def compare_plan_robustness(plans, data, simulation_engine, config=None):
    """Same scenarios for every plan. Returns {plan_id: robustness record}."""
    scenarios = generate_stress_scenarios(config)
    return {
        plan["plan_id"]: calculate_robustness(
            [run_plan_under_stress(plan, s, data, simulation_engine) for s in scenarios])
        for plan in plans
    }


def check_robustness_escalation(plans, config=None):
    """Escalate when the recommended plan is fragile and a near-tie alternative is sturdier.

    `plans` are recommendation records, best first.
    """
    if not plans or not plans[0]["robustness"]:
        return None
    config = config or load_config()
    leader = plans[0]
    threshold_num, threshold_den = config["robustness"]["escalation_threshold"]
    mine = leader["robustness"]
    if mine["numerator"] * threshold_den >= threshold_num * mine["denominator"]:
        return None
    rivals = {t["plan_b"] for t in leader["near_ties"]}
    better = [p for p in plans[1:] if p["plan_id"] in rivals and p["robustness"]
              and p["robustness"]["numerator"] > mine["numerator"]]
    if not better:
        return None
    return escalation(
        "LOW_ROBUSTNESS",
        f"{leader['plan_id']} survives only {mine['display']} stress runs; a near-tie plan survives more.",
        [leader["plan_id"]] + [p["plan_id"] for p in better],
        [{"plan_id": p["plan_id"], "robustness": p["robustness"]["display"]} for p in [leader] + better])
