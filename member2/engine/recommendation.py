"""Planner-facing recommendation records."""
from collections import Counter

from .escalation import escalation
from .optimizer import select_top_plans


def describe_action(action):
    """Template wording from engine facts (Member 3's fallback text can reuse it)."""
    name, po = action["action"], action.get("po_id")
    return {
        "CONTINUE_REV_B": lambda: f"Run Rev B out through W{action['through_week']}",
        "SHIFT_EFFECTIVE_WEEK": lambda: f"Move effective week W{action['from_week']} to W{action['to_week']}",
        "REDUCE_REV_B_PO": lambda: f"Reduce {po} by {action['quantity']}",
        "CANCEL_REV_B_PO": lambda: f"Cancel {po}",
        "DEFER_REV_B_PO": lambda: f"Defer {po} by {action['weeks']} wk",
        "EXPEDITE_REV_C_PO": lambda: f"Expedite {po} by {action['weeks']} wk",
        "DEFER_REV_C_PO": lambda: f"Defer {po} by {action['weeks']} wk",
        "ALTERNATE_SUPPLIER": lambda: f"Move {po} to supplier {action['supplier_id']}",
        "CREATE_REV_B_PO": lambda: f"Create new Rev B PO at {action['supplier_id']}",
    }[name]()


def describe_plan(plan):
    return "; ".join(describe_action(a) for a in plan["actions"]) or "No change"


def format_recommendation(plan, near_ties=(), robustness=None, position=None):
    return {
        "plan_id": plan["plan_id"],
        "rank": position or plan["rank"],
        "overall_rank": plan["rank"],  # among all feasible plans, redundant look-alikes included
        "effective_week": plan["effective_week"],
        "consumption_policy": plan["consumption_policy"],
        "actions": plan["actions"],
        "summary": describe_plan(plan),
        "shortage_units": plan["shortage_units"],
        "excess_value": plan["excess_value"],
        "action_cost": plan["action_cost"],
        "action_cost_breakdown": plan["action_cost_breakdown"],
        "secondary_cost": plan["secondary_cost"],
        "feasibility": plan["feasibility"],
        "near_ties": [t for t in near_ties if plan["plan_id"] in (t["plan_a"], t["plan_b"])],
        "simulation_reference": plan["simulation_reference"],
        "robustness": robustness,
    }


def generate_recommendations(ranked_plans, limit=3, near_ties=(), robustness=None):
    return [format_recommendation(p, near_ties, (robustness or {}).get(p["plan_id"]), position)
            for position, p in enumerate(select_top_plans(ranked_plans, limit), 1)]


def generate_no_feasible_plan_response(rejected_plans):
    codes = Counter(r["code"] for p in rejected_plans for r in p["rejection_reasons"])
    return {
        "decision": "NO_FEASIBLE_PLAN",
        "escalation": escalation(
            "NO_FEASIBLE_PLAN", "Every candidate plan breaks at least one hard rule.",
            [p["plan_id"] for p in rejected_plans],
            [{"code": code, "count": count} for code, count in sorted(codes.items())]),
        "rejected_plans": rejected_plans,
    }


def effective_week_comparison(ranked_plans, weeks):
    """Best feasible plan for each effective week (the dashboard's W5 / W6 / W7 table)."""
    table = []
    for week in weeks:
        best = next((p for p in ranked_plans if p["effective_week"] == week), None)
        table.append({
            "effective_week": week,
            "plan_id": best and best["plan_id"],
            "summary": best and describe_plan(best),
            "shortage_units": best and best["shortage_units"],
            "excess_value": best and best["excess_value"],
            "action_cost": best and best["action_cost"],
            "secondary_cost": best and best["secondary_cost"],
        })
    return table
