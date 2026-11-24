"""What-if runs. Parameters change an isolated copy; every number comes from Member 2."""
from copy import deepcopy

from ..ai.what_if_parser import INVALID, OK, UNSUPPORTED, create_scenario_request, validate_what_if_parameters
from ..application.access_control import require
from ..database.connection import transaction
from ..database.repositories import records
from . import audit_service

_COMPARED = ("shortage_units", "excess_value", "action_cost", "secondary_cost")


def apply_parameters(dataset, parameters, member2):
    """Isolated scenario copy. A Rev C delay also lengthens its suppliers' lead times, so the engine
    cannot simply expedite the delay away."""
    data = deepcopy(dataset)
    data["scenario_id"] = f"{dataset['scenario_id']}:{parameters['scenario_id']}"
    delay = parameters["lead_time_delta"]
    member2.shock(data, delay, parameters["demand_change_percent"])
    if delay:
        rev_c = data["engineering_change"]["new_material_id"]
        sources = {p["supplier_id"] for p in data["purchase_orders"]
                   if p["material_id"] == rev_c and p["status"] in ("OPEN", "CONFIRMED")}
        for supplier in data["suppliers"]:
            if supplier["supplier_id"] in sources:
                supplier["lead_time_weeks"] += delay
                supplier["expedited_lead_time_weeks"] += delay
    if parameters["effective_week"]:
        data["engineering_change"]["effective_week"] = parameters["effective_week"]
    if parameters["supplier_block"]:
        for supplier in data["suppliers"]:
            if supplier["supplier_id"] == parameters["supplier_block"]:
                supplier["status"] = "BLOCKED"
    return data


def _reduction(parameters):
    change = parameters["po_quantity_change"]
    return change and {"action": "REDUCE_REV_B_PO", "po_id": change["po_id"], "quantity": -change["quantity_delta"]}


def _best(result, member2, data, reduction):
    """Best plan of the scenario; with a requested reduction, the best ranked plan that contains it."""
    if not reduction:
        return result["recommendations"][0] if result["recommendations"] else None
    plan = next((p for p in result["ranked_plans"] if reduction in p["actions"]), None)
    return member2.evaluate(plan["actions"], data) if plan else None


def submit_scenario_to_optimizer(parameters, run, member2, user, question=""):
    """Run a confirmed scenario. Returns {"status", "message", "comparison", "result", "plan"}."""
    require(user, "RUN_WHAT_IF")
    problems = validate_what_if_parameters(parameters, run["dataset"])
    if problems:
        return {"status": INVALID, "message": " ".join(problems)}
    parameters = create_scenario_request(parameters, records.new_id("WHATIF"))
    reduction = _reduction(parameters)
    if reduction and (reduction["quantity"] <= 0 or not reduction["po_id"]):
        return {"status": UNSUPPORTED, "message": "Only reductions of a named Rev B order are supported."}
    data = apply_parameters(run["dataset"], parameters, member2)
    if not member2.input_problems(data) and reduction:
        broken = member2.action_problems(reduction, data)
        if broken:
            return {"status": "HARD_RULE_VIOLATION", "message": " ".join(r["description"] for r in broken)}
    config = member2.config_for_week(parameters["effective_week"]) if parameters["effective_week"] else None
    result = member2.optimize(data, config)
    plan = _best(result, member2, data, reduction)
    outcome = {"status": OK, "message": "", "parameters": parameters, "result": result, "plan": plan,
               "comparison": compare_scenario_results(run["result"], result, plan)}
    with transaction() as db:
        records.insert(db, "what_if_requests", request_id=parameters["scenario_id"], run_id=run["run_id"],
                       question=question, parameters=parameters, result=outcome, created_by=user.name,
                       created_at=records.now())
        audit_service.append(db, "WHAT_IF_RUN", parameters["scenario_id"], user, {
            "run_id": run["run_id"], "question": question, "parameters": parameters,
            "decision": result["decision"], "input_hash": result["input_hash"]})
    return outcome


def compare_scenario_results(base, alternative, alternative_plan=None):
    """Side-by-side of two engine outputs. Missing plans stay None instead of becoming zero."""
    before = base["recommendations"][0] if base["recommendations"] else None
    after = alternative_plan or (alternative["recommendations"][0] if alternative["recommendations"] else None)
    rows = [{"measure": "decision", "base": base["decision"], "alternative": alternative["decision"], "change": None},
            {"measure": "plan", "base": before and before["summary"], "alternative": after and after["summary"],
             "change": None}]
    for key in _COMPARED:
        b, a = before and before[key], after and after[key]
        rows.append({"measure": key, "base": b, "alternative": a,
                     "change": a - b if a is not None and b is not None else None})
    rows.append({"measure": "robustness", "base": before and before["robustness"]["display"],
                 "alternative": after and after["robustness"]["display"], "change": None})
    return rows


def describe_comparison(rows):
    """Template sentence built only from the comparison rows."""
    by = {r["measure"]: r for r in rows}
    if by["shortage_units"]["alternative"] is None:
        return f"No plan is recommended in this scenario ({by['decision']['alternative'].replace('_', ' ').lower()})."
    parts = []
    for key, label, unit in (("shortage_units", "Shortage", " units"), ("secondary_cost", "Excess + action cost", " rupees")):
        row = by[key]
        if row["change"] is None:
            parts.append(f"{label} is {row['alternative']:g}{unit}; the base case has no plan to compare with.")
        elif row["change"]:
            parts.append(f"{label} changes from {row['base']:g} to {row['alternative']:g}{unit}.")
        else:
            parts.append(f"{label} stays at {row['base']:g}{unit}.")
    same = by["plan"]["base"] == by["plan"]["alternative"]
    parts.append("The best plan stays the same." if same else f"The best plan becomes: {by['plan']['alternative']}.")
    return " ".join(parts)
