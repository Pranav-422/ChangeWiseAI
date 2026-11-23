"""Near-tie detection and planner escalation.

Interpretation to be confirmed by the team (all of it configurable under `near_tie`):
  * "less than 5% or Rs 5,000": either test is enough.
  * Boundaries are strict: exactly 5% or exactly Rs 5,000 is not a near-tie.
  * The percentage denominator is the lower of the two E + C values. If it is zero only the
    absolute test applies.
"""
from .config import load_config
from .optimizer import objective


def calculate_cost_difference(plan_a, plan_b, denominator="lower"):
    a, b = plan_a["secondary_cost"], plan_b["secondary_cost"]
    difference = round(abs(a - b), 2)
    base = min(a, b) if denominator == "lower" else max(a, b)
    return {"absolute": difference, "percent": difference / base if base else None}


def is_near_tie(plan_a, plan_b, config):
    if plan_a["shortage_units"] != 0 or plan_b["shortage_units"] != 0:
        return False
    policy = config["near_tie"]
    difference = calculate_cost_difference(plan_a, plan_b, policy["denominator"])
    return (difference["absolute"] < policy["absolute"]
            or (difference["percent"] is not None and difference["percent"] < policy["percent"]))


def detect_near_ties(ranked_plans, config=None):
    """Compare the leading plan with every other plan.

    Only ties with the leader can change the decision, so ties further down are not reported.
    Redundant look-alikes of another plan are not competitors.
    """
    config = config or load_config()
    plans = [p for p in ranked_plans if not p.get("redundant_of")]
    if len(plans) < 2 or plans[0]["shortage_units"] != 0:
        return []
    leader = plans[0]
    return [
        {"plan_a": leader["plan_id"], "plan_b": other["plan_id"],
         "secondary_cost_a": leader["secondary_cost"], "secondary_cost_b": other["secondary_cost"],
         **calculate_cost_difference(leader, other, config["near_tie"]["denominator"])}
        for other in plans[1:] if is_near_tie(leader, other, config)
    ]


def escalation(code, message, plan_ids=(), evidence=()):
    return {"code": code, "message": message, "plan_ids": list(plan_ids), "evidence": list(evidence),
            "status": "PLANNER_REVIEW_REQUIRED"}


def create_escalation_record(plans, near_ties=()):
    """NEAR_TIE record for the competing plans; the evidence is kept, nothing is resolved here."""
    return escalation(
        "NEAR_TIE",
        f"{len(plans)} zero-shortage plans have nearly equal excess + action cost.",
        [p["plan_id"] for p in plans], near_ties)


def residual_shortage_record(plan):
    return escalation("RESIDUAL_SHORTAGE",
                      f"The best feasible plan still leaves {objective(plan)[0]} units of demand unmet.",
                      [plan["plan_id"]])
