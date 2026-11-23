"""Plan evaluation. Inventory arithmetic belongs to Member 1's simulator, which is passed in."""
from copy import deepcopy

from .constraints import alternate_arrival, find, validate_plan
from .cost_calculator import calculate_action_cost, calculate_excess_value
from .optimizer import calculate_secondary_cost

_RESULT_FIELDS = ("weekly", "total_shortage", "rev_b_leftover", "rev_c_closing",
                  "average_weekly_demand", "total_excess_value")


class SimulatorContractError(ValueError):
    """Member 1's simulator returned something the agreed contract does not allow."""


def apply_plan_actions(plan, baseline_data):
    """Return an isolated scenario copy with the plan applied. The baseline is never touched."""
    data = deepcopy(baseline_data)
    change = data["engineering_change"]
    change["effective_week"] = plan["effective_week"]
    change["consumption_policy"] = plan["consumption_policy"]
    for action in plan["actions"]:
        name = action["action"]
        po = find(data["purchase_orders"], "po_id", action.get("po_id"))
        if name == "REDUCE_REV_B_PO":
            if action["quantity"] > po["quantity"]:
                raise ValueError(f"{po['po_id']}: reduction would make the quantity negative")
            po["quantity"] -= action["quantity"]
        elif name == "CANCEL_REV_B_PO":
            po.update(quantity=0, status="CANCELLED")
        elif name in ("DEFER_REV_B_PO", "DEFER_REV_C_PO"):
            po["arrival_week"] += action["weeks"]
        elif name == "EXPEDITE_REV_C_PO":
            po["arrival_week"] -= action["weeks"]
        elif name == "ALTERNATE_SUPPLIER":
            supplier = find(data["suppliers"], "supplier_id", action["supplier_id"])
            po.update(supplier_id=action["supplier_id"],
                      arrival_week=alternate_arrival(po, supplier, data))
        elif name not in ("SHIFT_EFFECTIVE_WEEK", "CONTINUE_REV_B"):
            raise ValueError(f"cannot apply action {name}")
    return data


def run_simulation(data, simulation_engine):
    """Call Member 1 and check the answer against the contract and the official excess formula."""
    result = simulation_engine(
        materials=data["materials"], inventory=data["inventory"], demand=data["demand"],
        purchase_orders=data["purchase_orders"], engineering_change=data["engineering_change"])
    missing = [field for field in _RESULT_FIELDS if field not in result]
    if missing:
        raise SimulatorContractError(f"simulator result lacks {', '.join(missing)}")
    change = data["engineering_change"]
    cost = {m["material_id"]: m["unit_cost"] for m in data["materials"]}
    expected = calculate_excess_value(
        result["rev_b_leftover"], cost[change["old_material_id"]],
        result["rev_c_closing"], cost[change["new_material_id"]], result["average_weekly_demand"])
    if abs(expected - result["total_excess_value"]) > 0.01:
        raise SimulatorContractError(
            f"simulator excess {result['total_excess_value']} != official formula {expected}")
    return result


def create_plan_evaluation_record(plan, result, validation, action_cost=None):
    record = {**plan, "feasibility": validation["feasibility"],
              "rejection_reasons": validation["rejection_reasons"],
              "simulation_reference": None, "simulation": None}
    if result is None:
        return record
    excess, cost = result["total_excess_value"], action_cost["total"]
    record.update(
        shortage_units=result["total_shortage"],
        excess_value=excess,
        action_cost=cost,
        action_cost_breakdown=action_cost,
        secondary_cost=calculate_secondary_cost(excess, cost),
        simulation_reference=f"SIM-{plan['plan_id']}",
        simulation=result,
    )
    return record


def evaluate_candidate_plan(plan, simulation_engine, baseline_data):
    """Rules first; a plan that breaks one is never simulated, so it can carry no tempting numbers."""
    validation = validate_plan(plan, baseline_data)
    if validation["feasibility"] == "REJECTED":
        return create_plan_evaluation_record(plan, None, validation)
    result = run_simulation(apply_plan_actions(plan, baseline_data), simulation_engine)
    validation = validate_plan(plan, baseline_data, result)  # adds the simulated Rev B usage check
    cost = calculate_action_cost(plan["actions"], baseline_data)
    return create_plan_evaluation_record(plan, result, validation, cost)


def evaluate_all_candidates(plans, simulation_engine, baseline_data):
    return [evaluate_candidate_plan(plan, simulation_engine, baseline_data) for plan in plans]
