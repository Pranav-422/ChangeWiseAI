"""Deterministic weekly Rev B / Rev C inventory simulator - the single source of truth for Members 2 and 3.

ALLOCATION POLICY (agreed contract; see reports/integration_contract.md)
 1. Receipts arrive at the START of their week and can be used that week.
 2. Reserved stock is held for its reservation (service kits) for the whole horizon: never used for production,
    never counted as scrap.     available = on_hand - reserved
 3. Safety stock is a protected floor: production may use only  usable = max(0, available - safety_stock).
    Demand that would need safety stock is recorded as unmet demand (shortage), not taken from safety stock.
 4. Revision rules for week t (E = effective week, U = Rev B use-up end week):
      t <  E and t <= U : Rev B only (Rev C is not yet released)
      t >= E            : Rev C first; if interchangeable and t <= U, Rev B covers what Rev C cannot
      t <  E and t >  U : no permitted revision -> all demand unmet (REVISION_GAP)
    Rev C replaces Rev B one-for-one. Rev B is never consumed after U.
 5. Lead time: a receipt cannot arrive before order_week + lead time (expedited lead time if the PO is
    expedited and the supplier offers it). An earlier arrival is moved to the earliest feasible week and flagged.
    Receipts from Blocked / Unqualified suppliers are excluded and flagged.
 6. closing = opening + receipts - usage, never negative; next opening = closing.
 7. Unmet demand = demand - Rev B usage - Rev C usage, once per week (no double counting).
Stress parameters: lead_time_shift delays every new-revision receipt by N weeks; demand_multiplier scales weekly
demand (rounded half up to whole units).
"""
import hashlib
import json
import math

from . import CONFIG, ENGINE_VERSION
from .data_loader import as_int, as_num, to_records
from .excess import calculate_rev_b_scrap_value, calculate_rev_c_excess_value, calculate_total_excess
from .severity import build_exceptions
from .shortage import calculate_shortage_summary
from .validation import RECEIVABLE_PO_STATUSES, Status, issue, validate_engineering_change, worst_status


def calculate_available_stock(on_hand, reserved) -> int:
    if on_hand < 0 or reserved < 0:
        raise ValueError("on_hand and reserved must be non-negative")
    return max(0, on_hand - reserved)


def calculate_weekly_receipts(purchase_orders, week: int, material_id: str | None = None) -> int:
    """Units of receivable POs arriving in `week` (uses `effective_arrival_week` when present)."""
    total = 0
    for po in to_records(purchase_orders):
        if po.get("po_status") not in RECEIVABLE_PO_STATUSES:
            continue
        if material_id is not None and po.get("material_id") != material_id:
            continue
        arrival = po.get("effective_arrival_week")
        if as_int(arrival if arrival is not None else po.get("arrival_week")) == week:
            total += as_int(po.get("quantity")) or 0
    return total


def allocate_component_usage(demand: int, revision_rules: dict) -> dict:
    """Split one week's demand between Rev B (old) and Rev C (new) per allocation policy rule 4.

    revision_rules: week, effective_week, use_up_end_week, interchangeable, usable_old, usable_new.
    """
    r = revision_rules
    old_ok, new_ok = r["week"] <= r["use_up_end_week"], r["week"] >= r["effective_week"]
    if new_ok:
        order = ["new"] + (["old"] if old_ok and r.get("interchangeable") else [])
    else:
        order = ["old"] if old_ok else []
    use, remaining = {"old": 0, "new": 0}, demand
    for rev in order:
        use[rev] = min(remaining, max(0, r[f"usable_{rev}"]))
        remaining -= use[rev]
    return {"old_usage": use["old"], "new_usage": use["new"], "unmet": remaining,
            "applicable_revision": "C" if new_ok else ("B" if old_ok else None)}


def calculate_closing_stock(simulation: dict) -> list[dict]:
    """Reconcile every week: closing = opening + receipts - usage >= 0 and next opening = this closing."""
    out, prev = [], {"b": None, "c": None}
    for w in simulation["weeks"]:
        row = {"week": w["week"]}
        for rev in "bc":
            closing = w[f"rev_{rev}_opening"] + w[f"rev_{rev}_receipts"] - w[f"rev_{rev}_usage"]
            row[f"rev_{rev}_closing"] = closing
            row[f"rev_{rev}_reconciled"] = (closing == w[f"rev_{rev}_closing"] and closing >= 0
                                            and (prev[rev] is None or prev[rev] == w[f"rev_{rev}_opening"]))
            prev[rev] = closing
        out.append(row)
    return out


def _snapshot_hash(payload: dict) -> str:
    def canon(v):
        if isinstance(v, list):    # row order must not change the hash
            return sorted((canon(x) for x in v), key=lambda x: json.dumps(x, sort_keys=True, default=str))
        if isinstance(v, dict):
            return {k: canon(x) for k, x in v.items()}
        if isinstance(v, float) and v.is_integer():   # SQLite 400.0 and CSV 400 are the same input
            return int(v)
        return v
    return hashlib.sha256(json.dumps(canon(payload), sort_keys=True, default=str).encode()).hexdigest()


def simulate_inventory(materials, inventory, demand, purchase_orders, engineering_change, suppliers=None, *,
                       horizon_weeks=None, lead_time_shift=0, demand_multiplier=1.0, average_weekly_demand=None,
                       plant_id=None, scenario_id="BASE") -> dict:
    """Simulate one engineering change week by week. Inputs are DataFrames or lists of dicts; nothing is mutated.

    Pass `suppliers` to enforce lead times and supplier status (Member 2 should always pass it).
    `average_weekly_demand` (D) defaults to mean weekly demand over the horizon after the demand multiplier;
    pass it explicitly to hold D fixed across candidate plans.
    """
    if as_int(lead_time_shift) is None:
        raise ValueError("lead_time_shift must be a whole number of weeks")
    if as_num(demand_multiplier) is None or demand_multiplier < 0:
        raise ValueError("demand_multiplier must be >= 0")
    horizon = CONFIG["horizon_weeks"] if horizon_weeks is None else as_int(horizon_weeks)
    if horizon is None or horizon < 1:
        raise ValueError("horizon_weeks must be a whole number >= 1")
    plant_id = CONFIG["plant_id"] if plant_id is None else plant_id
    change = dict(engineering_change)
    rows = {"materials": to_records(materials), "inventory": to_records(inventory), "demand": to_records(demand),
            "purchase_orders": to_records(purchase_orders), "suppliers": to_records(suppliers)}
    mats = {m["material_id"]: m for m in rows["materials"]}
    params = {"horizon_weeks": horizon, "lead_time_shift": lead_time_shift, "demand_multiplier": demand_multiplier,
              "average_weekly_demand": average_weekly_demand, "plant_id": plant_id, "scenario_id": scenario_id,
              "suppliers_checked": suppliers is not None}
    digest = _snapshot_hash({"inputs": rows, "change": change, "params": params, "engine_version": ENGINE_VERSION})
    result = {"simulation_id": f"SIM-{digest[:12]}", "change_id": change.get("change_id"), "scenario_id": scenario_id,
              "engine_version": ENGINE_VERSION, "input_snapshot_hash": digest, "horizon_weeks": horizon,
              "parameters": params, "old_material_id": change.get("part_number"),
              "new_material_id": change.get("new_material_id"), "effective_week": as_int(change.get("effective_week")),
              "use_up_end_week": as_int(change.get("use_up_end_week")), "weeks": [], "shortage": None, "excess": None,
              "total_shortage_units": None, "excess_value": None, "exceptions": []}

    ecn = validate_engineering_change(change, rows["materials"])
    issues = list(ecn.issues)

    def finish():
        result["validation_status"] = worst_status(i.status for i in issues).value
        result["issues"] = [i.model_dump(mode="json") for i in issues]
        result["exceptions"] = build_exceptions(result)
        return result

    if ecn.status in (Status.INVALID, Status.INSUFFICIENT_DATA):
        return finish()                      # cannot simulate a change whose core fields are wrong or missing

    old_id, new_id = change["part_number"], change["new_material_id"]
    eff, use_up = result["effective_week"], result["use_up_end_week"]
    interchangeable = bool(change["interchangeability"])
    mat_of = {"B": old_id, "C": new_id}

    stock = {}
    for rev, mid in mat_of.items():
        recs = sorted((r for r in rows["inventory"] if r.get("material_id") == mid
                       and r.get("plant_id") in (None, plant_id)),
                      key=lambda r: str(r.get("inventory_date") or ""))
        if not recs:
            issues.append(issue("INV_MISSING_FOR_AFFECTED", Status.INSUFFICIENT_DATA, mid,
                                f"No inventory record for {mid}; simulated as zero stock.", "Load the stock record."))
            recs = [{}]
        s = {k: as_int(recs[-1].get(k)) if recs[-1].get(k) is not None else 0
             for k in ("on_hand", "reserved", "safety_stock")}
        if any(v is None or v < 0 for v in s.values()):
            issues.append(issue("INV_INVALID_QUANTITY", Status.INVALID, mid, f"Invalid stock record {s}.",
                                "Correct the stock record."))
            return finish()
        stock[rev] = s

    weekly_req = {}
    for d in rows["demand"]:
        if d.get("material_id") not in (old_id, new_id) or d.get("plant_id") not in (None, plant_id):
            continue
        w, q = as_int(d.get("week")), as_num(d.get("required_quantity"))
        if w is None or w < 1 or q is None or q < 0:
            issues.append(issue("DEM_INVALID_ROW", Status.INVALID, d.get("demand_id"), f"Invalid demand row {d}.",
                                "Correct the demand record."))
            return finish()
        weekly_req[w] = weekly_req.get(w, 0) + q

    sups = {s["supplier_id"]: s for s in rows["suppliers"]} if suppliers is not None else None
    if sups is None:
        issues.append(issue("SIM_SUPPLIERS_NOT_CHECKED", Status.VALID, result["change_id"],
                            "Suppliers not supplied: lead times and supplier status were not enforced.",
                            "Pass suppliers to simulate_inventory."))
    receipts = []
    for po in rows["purchase_orders"]:
        mid, pid = po.get("material_id"), po.get("po_id")
        if mid not in (old_id, new_id) or po.get("po_status") not in RECEIVABLE_PO_STATUSES:
            continue
        qty, arrival = as_int(po.get("quantity")), as_int(po.get("arrival_week"))
        if qty is None or qty < 0 or arrival is None or arrival < 1:
            issues.append(issue("PO_INVALID_FOR_SIMULATION", Status.INVALID, pid, f"PO quantity/arrival invalid: {qty}, {arrival}.",
                                "Correct the PO."))
            continue
        if mid == new_id:
            arrival += lead_time_shift
        if sups is not None:
            s = sups.get(po.get("supplier_id"))
            if s is None:
                issues.append(issue("PO_UNKNOWN_SUPPLIER", Status.INVALID, pid, f"Supplier {po.get('supplier_id')} unknown.",
                                    "Fix the supplier reference."))
                continue
            if s.get("supplier_status") != "Approved":
                issues.append(issue("SIM_RESTRICTED_SUPPLIER_RECEIPT_EXCLUDED", Status.NEEDS_REVIEW, pid,
                                    f"{qty} units from {s.get('supplier_status')} supplier {s['supplier_id']} not counted as supply.",
                                    "Re-source this quantity from an approved supplier."))
                continue
            expedited = bool(as_int(po.get("expedited")))
            can_expedite = bool(as_int(s.get("expedite_available")))
            if expedited and not can_expedite:
                issues.append(issue("SIM_EXPEDITE_NOT_AVAILABLE", Status.NEEDS_REVIEW, pid,
                                    f"PO marked expedited but supplier {s['supplier_id']} does not offer expediting.",
                                    "Remove the expedite or change supplier."))
            lead = as_int(s.get("expedited_lead_time_weeks" if expedited and can_expedite else "lead_time_weeks"))
            order = as_int(po.get("order_week"))
            if lead is None:
                issues.append(issue("SIM_MISSING_LEAD_TIME", Status.INSUFFICIENT_DATA, pid,
                                    f"Supplier {s['supplier_id']} has no lead time; arrival W{arrival} unverified.",
                                    "Obtain the supplier lead time."))
            elif order is None:
                issues.append(issue("SIM_LEAD_TIME_UNVERIFIED", Status.NEEDS_REVIEW, pid,
                                    "PO has no order week; lead time cannot be verified.", "Record the PO order week."))
            elif arrival < order + lead:
                issues.append(issue("SIM_LEAD_TIME_VIOLATION", Status.NEEDS_REVIEW, pid,
                                    f"Arrival W{arrival} is earlier than order W{order} + lead {lead}; "
                                    f"simulated at W{order + lead}.", "Confirm a feasible date with the supplier.",
                                    week=order + lead))
                arrival = order + lead
        receipts.append({"po_id": pid, "material_id": mid, "quantity": qty, "effective_arrival_week": arrival,
                         "po_status": po.get("po_status")})

    on = {"B": stock["B"]["on_hand"], "C": stock["C"]["on_hand"]}
    leftover_free = None
    for week in range(1, horizon + 1):
        req = int(math.floor(weekly_req.get(week, 0) * demand_multiplier + 0.5))
        row, usable, rec = {"week": week, "demand": req}, {}, {}
        for rev in "BC":
            rec[rev] = calculate_weekly_receipts(receipts, week, mat_of[rev])
            available = calculate_available_stock(on[rev] + rec[rev], stock[rev]["reserved"])
            usable[rev] = max(0, available - stock[rev]["safety_stock"])
            r = rev.lower()
            row.update({f"rev_{r}_opening": on[rev], f"rev_{r}_receipts": rec[rev],
                        f"rev_{r}_reserved": stock[rev]["reserved"], f"rev_{r}_available": available,
                        f"rev_{r}_safety_stock": stock[rev]["safety_stock"], f"rev_{r}_usable": usable[rev]})
        alloc = allocate_component_usage(req, {"week": week, "effective_week": eff, "use_up_end_week": use_up,
                                               "interchangeable": interchangeable,
                                               "usable_old": usable["B"], "usable_new": usable["C"]})
        for rev, used in (("B", alloc["old_usage"]), ("C", alloc["new_usage"])):
            r = rev.lower()
            closing = on[rev] + rec[rev] - used
            if closing < 0:                  # cannot happen under the policy; guard against regressions
                raise AssertionError(f"negative closing stock for Rev {rev} in W{week}")
            row[f"rev_{r}_usage"], row[f"rev_{r}_closing"] = used, closing
            on[rev] = closing
        applicable = alloc["applicable_revision"]
        row.update(applicable_revision=applicable, shortage=alloc["unmet"],
                   rev_b_unmet=alloc["unmet"] if applicable != "C" else 0,
                   rev_c_unmet=alloc["unmet"] if applicable == "C" else 0)
        if applicable is None and req > 0:
            issues.append(issue("SIM_NO_PERMITTED_REVISION", Status.NEEDS_REVIEW, f"{result['change_id']}.W{week}",
                                f"W{week}: Rev B use-up ended W{use_up}, Rev C effective W{eff}; {req} units unmet.",
                                "Align use-up end and effective week.", week=week))
        result["weeks"].append(row)
        if week == use_up:
            leftover_free = max(0, on["B"] - stock["B"]["reserved"])

    if leftover_free is None:               # use-up end beyond horizon: measure at horizon end
        leftover_free = max(0, on["B"] - stock["B"]["reserved"])
        issues.append(issue("SIM_USE_UP_BEYOND_HORIZON", Status.VALID, result["change_id"],
                            f"Use-up end W{use_up} is after the W{horizon} horizon; Rev B leftover measured at W{horizon}.",
                            "Extend the horizon if needed."))
    # Rev B arriving after the use-up end can never be used, so deferring a Rev B PO cannot hide scrap.
    # leftover_free is taken at the end of week U, so these receipts are not in it: no double count.
    post_use_up = sum(p["quantity"] for p in receipts if p["material_id"] == old_id and p["effective_arrival_week"] > use_up)
    scrap_units = leftover_free + post_use_up
    rev_c_closing = max(0, on["C"] - stock["C"]["reserved"])
    d = (as_num(average_weekly_demand) if average_weekly_demand is not None
         else sum(w["demand"] for w in result["weeks"]) / horizon)
    cost_b, cost_c = as_num(mats[old_id]["unit_cost"]), as_num(mats[new_id]["unit_cost"])
    e_b = calculate_rev_b_scrap_value(scrap_units, cost_b)
    e_c = calculate_rev_c_excess_value(rev_c_closing, d, cost_c)
    result["shortage"] = calculate_shortage_summary(result["weeks"], mat_of)
    result["excess"] = {
        "rev_b_leftover_at_use_up_units": leftover_free,
        "rev_b_post_use_up_receipts": post_use_up,
        "rev_b_scrap_units": scrap_units,
        "rev_b_scrap_from_safety_stock": min(stock["B"]["safety_stock"], leftover_free),
        "rev_b_reserved_excluded": stock["B"]["reserved"],
        "rev_b_unit_cost": cost_b, "rev_b_scrap_value": e_b,
        "rev_c_closing_units": rev_c_closing, "average_weekly_demand": d,
        "coverage_weeks": CONFIG["coverage_weeks"], "rev_c_unit_cost": cost_c, "rev_c_excess_value": e_c,
        "total_excess_value": calculate_total_excess(e_b, e_c),
    }
    result["total_shortage_units"] = result["shortage"]["total_shortage_units"]
    result["excess_value"] = result["excess"]["total_excess_value"]
    result["receipts"] = receipts
    return finish()


def simulate_from_data(data: dict, change_id: str | None = None, **kwargs) -> dict:
    """Convenience wrapper: `data` is the dict from load_csv_data() / load_data_from_db()."""
    changes = to_records(data["engineering_changes"])
    change = next((c for c in changes if change_id is None or c["change_id"] == change_id), None)
    if change is None:
        raise KeyError(f"engineering change {change_id!r} not found")
    return simulate_inventory(data["materials"], data["inventory"], data["demand"], data["purchase_orders"],
                              change, data["suppliers"], **kwargs)
