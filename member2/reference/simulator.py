"""TEMPORARY STAND-IN for Member 1's inventory simulator.

Member 1 owns inventory arithmetic. This file exists only so Member 2's engine and tests run
before Member 1's module is merged. Replace it through `simulator:` in config/optimization.yaml.

Agreed rules (solution plan, section 6): weekly buckets, receipts at the start of the week, stock
never below zero, unmet demand recorded as shortage and not back-ordered.

Consumption:
  week <  effective_week                       Rev B only
  week >= effective_week, policy CUTOVER       Rev C only
  week >= effective_week, policy RUN_OUT       Rev B first while week <= use_up_end_week, then Rev C
Rev B is never consumed after use_up_end_week.
"""

COVERAGE_WEEKS = 4


def simulate_inventory(materials, inventory, demand, purchase_orders, engineering_change):
    unit_cost = {m["material_id"]: m["unit_cost"] for m in materials}
    available = {i["material_id"]: i["on_hand"] - i["reserved"] for i in inventory}
    rev_b, rev_c = engineering_change["old_material_id"], engineering_change["new_material_id"]
    effective, use_up = engineering_change["effective_week"], engineering_change["use_up_end_week"]
    run_out = engineering_change.get("consumption_policy", "CUTOVER") == "RUN_OUT"

    stock = {rev_b: available[rev_b], rev_c: available[rev_c]}
    weekly = []
    for row in sorted(demand, key=lambda d: d["week"]):
        week, needed = row["week"], row["quantity"]
        opening = dict(stock)
        receipts = {
            m: sum(po["quantity"] for po in purchase_orders
                   if po["material_id"] == m and po["arrival_week"] == week
                   and po["status"] not in ("CANCELLED", "RECEIVED"))
            for m in (rev_b, rev_c)
        }
        for m in stock:
            stock[m] += receipts[m]

        b_allowed = week <= use_up and (week < effective or run_out)
        use_b = min(needed, stock[rev_b]) if b_allowed else 0
        use_c = min(needed - use_b, stock[rev_c]) if week >= effective else 0
        stock[rev_b] -= use_b
        stock[rev_c] -= use_c
        weekly.append({
            "week": week, "demand": needed,
            "rev_b_opening": opening[rev_b], "rev_b_receipts": receipts[rev_b],
            "rev_b_usage": use_b, "rev_b_closing": stock[rev_b],
            "rev_c_opening": opening[rev_c], "rev_c_receipts": receipts[rev_c],
            "rev_c_usage": use_c, "rev_c_closing": stock[rev_c],
            "shortage": needed - use_b - use_c,
        })

    average = sum(w["demand"] for w in weekly) / len(weekly)
    excess_b = stock[rev_b] * unit_cost[rev_b]
    excess_c = max(0, stock[rev_c] - COVERAGE_WEEKS * average) * unit_cost[rev_c]
    return {
        "weekly": weekly,
        "total_shortage": sum(w["shortage"] for w in weekly),
        "rev_b_leftover": stock[rev_b],
        "rev_c_closing": stock[rev_c],
        "average_weekly_demand": average,
        "excess_value_b": excess_b,
        "excess_value_c": excess_c,
        "total_excess_value": excess_b + excess_c,
    }
