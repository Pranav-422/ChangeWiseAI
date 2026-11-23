"""Shared mixed-integer model data for the OR-Tools and PuLP solvers.

Both solvers choose from the same menus as the enumerator (so hard rules hold by construction) and
encode the same consumption policy as the agreed inventory rules:
  * one changeover option, one option per purchase order;
  * weekly balance for each revision, stock >= 0, unmet demand is lost;
  * Rev C is used only when no usable Rev B is left, shortage only when no usable stock is left.
Every returned plan is re-simulated by the planner, so solver arithmetic is never reported.
"""
from ..engine.action_generator import make_plan
from ..engine.constraints import find
from ..engine.cost_calculator import COVERAGE_WEEKS, calculate_action_cost
from ..engine.planner import apply_plan_actions

MONEY_SCALE = 100  # rupees to paise, so money stays integral


def _whole(value, name):
    if value != int(value):
        raise ValueError(f"solver needs whole units; {name} is {value}")
    return int(value)


def build_model_inputs(data, menus):
    change = data["engineering_change"]
    rev_b, rev_c = change["old_material_id"], change["new_material_id"]
    demand = [(row["week"], _whole(row["quantity"], f"demand W{row['week']}"))
              for row in sorted(data["demand"], key=lambda r: r["week"])]
    weeks = [w for w, _ in demand]
    use_up = change["use_up_end_week"]

    changeovers = []
    for actions in menus["changeovers"]:
        plan = make_plan(actions, data)
        start, run_out = plan["effective_week"], plan["consumption_policy"] == "RUN_OUT"
        changeovers.append({
            "actions": actions,
            "b_ok": [w <= use_up and (w < start or run_out) for w in weeks],
            "c_ok": [w >= start for w in weeks],
        })

    orders = []
    for po in data["purchase_orders"]:
        if po["po_id"] not in menus["po_menus"]:
            continue  # cancelled, received or another material: no receipts in this model
        options = []
        for actions in menus["po_menus"][po["po_id"]]:
            changed = find(apply_plan_actions(make_plan(actions, data), data)["purchase_orders"],
                           "po_id", po["po_id"])
            options.append({
                "actions": actions, "quantity": _whole(changed["quantity"], po["po_id"]),
                "slot": weeks.index(changed["arrival_week"]) if changed["arrival_week"] in weeks else None,
                "cost": round(calculate_action_cost(actions, data)["total"] * MONEY_SCALE),
            })
        orders.append({"is_b": po["material_id"] == rev_b, "options": options})

    stock = {i["material_id"]: _whole(i["on_hand"] - i["reserved"], i["material_id"])
             for i in data["inventory"]}
    unit = {m["material_id"]: round(m["unit_cost"] * MONEY_SCALE) for m in data["materials"]}
    total_demand = sum(q for _, q in demand)
    supply = stock[rev_b] + stock[rev_c] + sum(
        max((o["quantity"] for o in order["options"]), default=0) for order in orders)
    return {
        "demand": [q for _, q in demand], "changeovers": changeovers, "orders": orders,
        "stock_b": stock[rev_b], "stock_c": stock[rev_c],
        "unit_b": unit[rev_b], "unit_c": unit[rev_c],
        "horizon": len(weeks),
        "coverage_total": COVERAGE_WEEKS * total_demand,  # = horizon x (4 weeks of average demand)
        "big_m": supply + total_demand + 1,
    }


def chosen_actions(inputs, changeover_index, option_indexes):
    actions = list(inputs["changeovers"][changeover_index]["actions"])
    for order, pick in zip(inputs["orders"], option_indexes):
        actions += order["options"][pick]["actions"]
    return actions


def solvable(inputs):
    return all(order["options"] for order in inputs["orders"])
