"""Deterministic wording from engine facts. Used whenever the LLM is absent, fails or is not verified.

Each template takes the facts package of claim_verifier.build_verified_facts and returns text, or an
empty string when it does not apply. Nothing is filled in with placeholder values.
"""
from member2.evaluation.run_all import rupees


def _plan(facts):
    return facts["plans"].get(facts["recommended_plan_id"])


def _weeks(weeks):
    return ", ".join(f"W{w}" for w in weeks)


def ecn_summary(facts):
    c = facts["change"]
    if None in (c["change_id"], c["old"], c["new"], c["effective_week"], c["use_up_end_week"]):
        return "The engineering-change record is incomplete."
    return (f"{c['change_id']} replaces {c['old']} with {c['new']}. The effective week is W{c['effective_week']} "
            f"and the use-up end is W{c['use_up_end_week']}.")


def bom_impact_summary(facts):
    assemblies = facts["change"]["assemblies"]
    if not assemblies:
        return "No finished assembly uses the changed material."
    return f"Finished assemblies affected: {', '.join(assemblies)}."


def inventory_summary(facts):
    i = facts["inventory"]
    if i["rev_b_available"] is None:
        return "Inventory was not simulated."
    receipts = "; ".join(f"{r['units']} units of Rev {r['revision']} receipts in W{r['week']}" for r in i["receipts"])
    demand = sorted(set(i["demand_by_week"].values()))
    per_week = (f"Weekly demand is {demand[0]} units." if len(demand) == 1
                else f"Weekly demand is between {demand[0]} units and {demand[-1]} units.")
    return (f"Opening stock is {i['rev_b_available']} units of Rev B and {i['rev_c_available']} units of Rev C. "
            f"{per_week}" + (f" Expected: {receipts}." if receipts else " No receipts are scheduled."))


def shortage_warning(facts):
    i = facts["inventory"]
    if not i["shortage"]:
        return "Without corrective action there is no shortage." if i["shortage"] == 0 else ""
    return (f"Without corrective action the shortage is {i['shortage']} units, in "
            f"{_weeks(i['shortage_by_week'])}.")


def excess_warning(facts):
    excess = facts["inventory"]["excess"]
    return f"Without corrective action the excess value is {rupees(excess)}." if excess else ""


def supplier_restriction(facts):
    return " ".join(f"Supplier {s} is {status.lower()}." for s, status in facts["suppliers"].items()
                    if status != "APPROVED")


def hard_rule_rejection(facts):
    rules = sorted({r for p in facts["rejected"] for r in p["rules"]})
    if not rules:
        return ""
    return f"{len(facts['rejected'])} rejected plans break these rules: " \
           f"{', '.join(r.replace('_', ' ').lower() for r in rules)}."


def critical_exceptions(facts):
    top = [e for e in facts["exceptions"] if e["band"] in ("Critical", "High")]
    return " ".join(f"{e['band']} exception {e['exception_id']}" + (f" in W{e['week']}" if e["week"] else "")
                    + f": {e['type'].replace('_', ' ').lower()}, impact {rupees(e['impact_rs'])}." for e in top) or "No critical or high exception was found."


def optimization_recommendation(facts):
    plan = _plan(facts)
    if not plan:
        return ""
    return (f"{facts['recommended_plan_id']} ranks first of {facts['counts']['feasible']} feasible plans. "
            f"Actions: {plan['actions']}. Its shortage is {plan['shortage']:g} units, excess value "
            f"{rupees(plan['excess'])} and action cost {rupees(plan['action_cost'])}, "
            f"{rupees(plan['secondary_cost'])} combined. Plans are ranked by shortage first, then by excess value "
            f"plus action cost.")


def near_tie_escalation(facts):
    record = next((e for e in facts["escalations"] if e["code"] == "NEAR_TIE"), None)
    if not record:
        return ""
    return f"Near-tie: the planner must choose between {', '.join(record['plan_ids'])}."


def residual_shortage(facts):
    if not any(e["code"] == "RESIDUAL_SHORTAGE" for e in facts["escalations"]):
        return ""
    return f"The best feasible plan still leaves a shortage of {_plan(facts)['shortage']:g} units."


def robustness_warning(facts):
    plan = _plan(facts)
    if not plan:
        return ""
    r = plan["robustness"]
    text = (f"{facts['recommended_plan_id']} has zero shortage in {r['zero_shortage_runs']}/{r['total_runs']} "
            f"stress runs.")
    for run in r["failed"]:
        demand = f"demand {run['demand_shock'] * 100:+.0f}%" if run["demand_shock"] else "unchanged demand"
        text += (f" Stress with lead time +{run['lead_time_shock']} wk and {demand}: "
                 f"shortage {run['shortage_units']:g} units.")
    if any(e["code"] == "LOW_ROBUSTNESS" for e in facts["escalations"]):
        text += " Robustness is below the limit and a near-tie plan is sturdier, so planner review is required."
    return text


def no_feasible_plan(facts):
    if facts["decision"] != "NO_FEASIBLE_PLAN":
        return ""
    return "No feasible plan exists: every candidate breaks at least one hard rule. The case goes to the planner."


def invalid_data(facts):
    if facts["decision"] != "INVALID_DATA":
        return ""
    return "Input records are invalid or conflicting, so no plan was generated. The data owner must correct them."


def approval_summary(facts):
    plan = _plan(facts)
    if not plan:
        return "There is nothing to approve."
    owners = ", ".join(plan["owners"]) or "no team"
    state = "The planner has recorded an approval." if facts["approved"] else "Nothing is approved until the planner decides."
    return f"Action owners: {owners}. {state}"


SECTIONS = {
    "Engineering change": (ecn_summary, bom_impact_summary),
    "Inventory impact": (inventory_summary, shortage_warning, excess_warning),
    "Recommendation": (invalid_data, no_feasible_plan, optimization_recommendation, residual_shortage),
    "Risks": (critical_exceptions, supplier_restriction, hard_rule_rejection),
    "Robustness": (robustness_warning, near_tie_escalation),
    "Planner decision": (approval_summary,),
}


def render_sections(facts):
    """{title: text}; sections with nothing to say are left out."""
    rendered = {title: " ".join(filter(None, (t(facts) for t in templates))) for title, templates in SECTIONS.items()}
    return {title: text for title, text in rendered.items() if text}
