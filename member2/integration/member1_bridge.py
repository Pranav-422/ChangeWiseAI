"""Member 1's data and simulator behind Member 2's input contract.

Only names and units are translated here; every inventory number comes from Member 1's simulator.

Interpretations to confirm with Member 1 (its tables have no such column):
  * planning_week = approval_week: the plan is made when the change is approved.
  * cancel_allowed_until is also the deadline for reducing or deferring an order.
  * Orders are reduced in steps of REDUCTION_STEP units, so the candidate space stays finite.
"""
from member1.engine.data_loader import as_int, as_num, to_records
from member1.engine.inventory import simulate_inventory as member1_simulate
from member1.engine.scenarios import SCENARIOS, load_scenario
from member1.engine.validation import validate_all_inputs

REDUCTION_STEP = 50
CHANGE_ID = "ECN-001"
BLOCKING = ("INVALID", "INSUFFICIENT_DATA")


def list_scenarios():
    return list(SCENARIOS)


def _flag(value):
    return int(bool(as_int(value)))


def _order(po):
    deadline = as_int(po["cancel_allowed_until"])
    return {
        "po_id": po["po_id"], "material_id": po["material_id"], "supplier_id": po["supplier_id"],
        "purchasing_group": po["purchasing_group"], "quantity": as_int(po["quantity"]),
        "order_week": as_int(po["order_week"]), "arrival_week": as_int(po["arrival_week"]),
        "status": str(po["po_status"]).upper(), "cancellable": int(deadline is not None),
        "cancel_deadline_week": deadline or 0, "change_deadline_week": deadline or 0,
        "max_deferral_weeks": as_int(po["maximum_defer_weeks"]),
        "max_reduction_qty": as_int(po["max_reduction_quantity"]), "reduction_lot": REDUCTION_STEP,
        "cancellation_fee": as_num(po["cancellation_fee"]), "reduction_fee": as_num(po["reduction_fee"]),
        "expedite_fee": as_num(po["expedite_fee"]), "reduction_fee_per_unit": 0, "expedite_fee_per_week": 0,
    }


def _supplier(row):
    lead, expedite = as_int(row["lead_time_weeks"]), _flag(row["expedite_available"])
    return {"supplier_id": row["supplier_id"], "status": str(row["supplier_status"]).upper(),
            "lead_time_weeks": lead, "expedite_available": expedite,
            "expedited_lead_time_weeks": as_int(row["expedited_lead_time_weeks"]) if expedite else lead,
            "accepts_reduction": 1}


def convert(tables, scenario_id, change_id=CHANGE_ID):
    """Member 1 tables -> Member 2 dataset. Member 1's blocking findings travel in validation_errors."""
    rows = {name: to_records(table) for name, table in tables.items()}
    change = next(c for c in rows["engineering_changes"] if c["change_id"] == change_id)
    pair = (change["part_number"], change["new_material_id"])
    # Orders and suppliers of other materials are outside this change.
    orders = [po for po in rows["purchase_orders"] if po["material_id"] in pair]
    groups = [g for g in rows["planning_groups"] if g["material_id"] in pair]
    used = {po["supplier_id"] for po in orders} | {g["supplier_id"] for g in groups}
    weekly = {}
    for row in rows["demand"]:
        if row["material_id"] in pair:
            weekly[as_int(row["week"])] = weekly.get(as_int(row["week"]), 0) + as_num(row["required_quantity"])
    found = validate_all_inputs(tables, change_id)["issues"]
    return {
        "scenario_id": scenario_id,
        "planning_week": as_int(change["approval_week"]),
        "horizon_weeks": len(weekly),
        "materials": [{"material_id": m["material_id"], "revision": m["revision"].removeprefix("Rev "),
                       "unit_cost": as_num(m["unit_cost"]), "status": m["material_status"],
                       "part_number": m["material_id"]} for m in rows["materials"] if m["material_id"] in pair],
        "inventory": [{"material_id": i["material_id"], "on_hand": as_int(i["on_hand"]),
                       "reserved": as_int(i["reserved"]), "safety_stock": as_int(i["safety_stock"])}
                      for i in rows["inventory"] if i["material_id"] in pair],
        "demand": [{"week": w, "quantity": int(q) if q == int(q) else q} for w, q in sorted(weekly.items())],
        "purchase_orders": [_order(po) for po in orders],
        "suppliers": [_supplier(s) for s in rows["suppliers"] if s["supplier_id"] in used],
        "supplier_materials": [{"supplier_id": g["supplier_id"], "material_id": g["material_id"], "qualified": 1}
                               for g in groups],  # the supplier status decides qualification
        "purchasing_authorizations": [
            {"purchasing_group": g["group_id"], "material_id": g["material_id"], "supplier_id": g["supplier_id"]}
            for g in groups if g["authorization_status"] == "Authorized"],
        "engineering_change": {
            "change_id": change["change_id"], "old_material_id": pair[0], "new_material_id": pair[1],
            "status": str(change["approval_status"]).upper(), "approval_week": as_int(change["approval_week"]),
            "effective_week": as_int(change["effective_week"]), "use_up_end_week": as_int(change["use_up_end_week"]),
            "interchangeable": _flag(change["interchangeability"]),
            # Member 1's policy after the effective week: Rev C first, Rev B covers the rest until its use-up end.
            "after_effective": "C_THEN_B", "run_out_supported": 0,
        },
        "validation_errors": [f"{i['code']} on {i['record']}: {i['description']}"
                              for i in found if i["status"] in BLOCKING],
    }


def load_dataset(scenario_id):
    return convert(load_scenario(scenario_id), scenario_id)


def simulate_inventory(materials, inventory, demand, purchase_orders, engineering_change, suppliers):
    """Member 2's simulator call, answered by Member 1's simulator."""
    if engineering_change.get("consumption_policy") == "RUN_OUT":
        raise ValueError("Member 1's simulator has no run-out policy")
    change = engineering_change
    rev_c = change["new_material_id"]
    revision = {m["material_id"]: f"Rev {m['revision']}" for m in materials}
    lead = {s["supplier_id"]: s["lead_time_weeks"] for s in suppliers}
    result = member1_simulate(
        materials=[{"material_id": m["material_id"], "revision": revision[m["material_id"]],
                    "unit_cost": m["unit_cost"]} for m in materials],
        inventory=inventory,
        demand=[{"material_id": rev_c, "week": d["week"], "required_quantity": d["quantity"]} for d in demand],
        purchase_orders=[{
            "po_id": po["po_id"], "material_id": po["material_id"], "supplier_id": po["supplier_id"],
            "quantity": po["quantity"], "order_week": po["order_week"], "arrival_week": po["arrival_week"],
            "po_status": "Open" if po["status"] == "SHIPPED" else po["status"].title(),
            "expedited": int(po["arrival_week"] < po["order_week"] + lead[po["supplier_id"]]),
        } for po in purchase_orders],
        engineering_change={
            "change_id": change["change_id"], "part_number": change["old_material_id"], "new_material_id": rev_c,
            "old_revision": revision[change["old_material_id"]], "new_revision": revision[rev_c],
            "effective_week": change["effective_week"], "use_up_end_week": change["use_up_end_week"],
            "interchangeability": bool(change["interchangeable"]), "approval_status": "Approved"},
        suppliers=[{"supplier_id": s["supplier_id"], "supplier_status": s["status"].title(),
                    "lead_time_weeks": s["lead_time_weeks"], "expedite_available": s["expedite_available"],
                    "expedited_lead_time_weeks": s["expedited_lead_time_weeks"]} for s in suppliers],
        horizon_weeks=len(demand), plant_id=None)
    if not result["weeks"]:
        raise ValueError(f"Member 1 refused to simulate: {result['validation_status']}")
    excess = result["excess"]
    return {
        "weekly": result["weeks"],
        "total_shortage": result["total_shortage_units"],
        "rev_b_leftover": excess["rev_b_scrap_units"],
        "rev_c_closing": excess["rev_c_closing_units"],
        "average_weekly_demand": excess["average_weekly_demand"],
        "excess_value_b": excess["rev_b_scrap_value"],
        "excess_value_c": excess["rev_c_excess_value"],
        "total_excess_value": result["excess_value"],
        "exceptions": result["exceptions"],
        "simulation_id": result["simulation_id"],
        "horizon_weeks": result["horizon_weeks"],
    }
