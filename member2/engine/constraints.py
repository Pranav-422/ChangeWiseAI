"""Seven hard rules. A plan that breaks any of them is rejected, whatever it costs.

Every check_* function takes (plan, data) and returns a list of reason records. The action-level
halves (`action_violations`) are also what the generator uses to decide which actions are eligible,
so generation and filtering can never disagree.
"""
from collections import Counter

EDITABLE_PO = {"OPEN", "CONFIRMED"}
IN_HAND_PO = {"SHIPPED", "RECEIVED", "CANCELLED"}  # already executed: no purchasing decision left
PO_STATUSES = EDITABLE_PO | IN_HAND_PO

REV_B_PO_ACTIONS = {"REDUCE_REV_B_PO", "CANCEL_REV_B_PO", "DEFER_REV_B_PO"}
REV_C_PO_ACTIONS = {"EXPEDITE_REV_C_PO", "DEFER_REV_C_PO", "ALTERNATE_SUPPLIER"}
PO_ACTIONS = REV_B_PO_ACTIONS | REV_C_PO_ACTIONS
CHANGEOVER_ACTIONS = {"CONTINUE_REV_B", "SHIFT_EFFECTIVE_WEEK"}
KNOWN_ACTIONS = PO_ACTIONS | CHANGEOVER_ACTIONS | {"CREATE_REV_B_PO"}

# Timing actions exclude each other; so do the two ways of setting the changeover moment.
_EXCLUSIVE_GROUPS = (
    {"DEFER_REV_B_PO"}, {"REDUCE_REV_B_PO"},
    {"EXPEDITE_REV_C_PO", "DEFER_REV_C_PO", "ALTERNATE_SUPPLIER"},
)


def reason(rule, code, description):
    return {"rule": rule, "code": code, "description": description}


def find(rows, key, value):
    return next((row for row in rows if row.get(key) == value), None)


def po_of(action, data):
    return find(data["purchase_orders"], "po_id", action.get("po_id"))


def earliest_arrival(po, supplier, expedited=False):
    lead = supplier["expedited_lead_time_weeks" if expedited else "lead_time_weeks"]
    return po["order_week"] + lead


def alternate_arrival(po, supplier, data):
    """A new supplier cannot receive the order before today."""
    return max(po["order_week"], data["planning_week"]) + supplier["lead_time_weeks"]


def _actions(plan, *names):
    return [a for a in plan["actions"] if a["action"] in names]


# Rule 1 ----------------------------------------------------------------------------------------

def _supplier_reasons(supplier_id, material_id, data):
    rule = "SUPPLIER_QUALIFICATION"
    supplier = find(data["suppliers"], "supplier_id", supplier_id)
    if supplier is None:
        return [reason(rule, "UNKNOWN_SUPPLIER", f"Supplier {supplier_id} does not exist.")]
    if supplier["status"] == "BLOCKED":
        return [reason(rule, "BLOCKED_SUPPLIER", f"Supplier {supplier_id} is blocked.")]
    qualified = any(
        row["supplier_id"] == supplier_id and row["material_id"] == material_id and row["qualified"]
        for row in data["supplier_materials"])
    if supplier["status"] != "APPROVED" or not qualified:
        return [reason(rule, "UNQUALIFIED_SUPPLIER",
                       f"Supplier {supplier_id} is not approved and qualified for {material_id}.")]
    return []


def po_supplier_reasons(po, data, supplier_id=None):
    """Rule 1 for one purchase order that the plan keeps."""
    if po["status"] in IN_HAND_PO:
        return []
    return _supplier_reasons(supplier_id or po["supplier_id"], po["material_id"], data)


def affected_orders(data):
    """Orders of the two materials in this change. Anything else cannot make a plan infeasible."""
    change = data["engineering_change"]
    return [po for po in data["purchase_orders"]
            if po["material_id"] in (change["old_material_id"], change["new_material_id"])]


def check_supplier_qualification(plan, data):
    cancelled = {a["po_id"] for a in _actions(plan, "CANCEL_REV_B_PO")}
    moved = {a["po_id"]: a["supplier_id"] for a in _actions(plan, "ALTERNATE_SUPPLIER")}
    found = []
    for po in affected_orders(data):
        if po["po_id"] not in cancelled:
            found += po_supplier_reasons(po, data, moved.get(po["po_id"]))
    for action in _actions(plan, "CREATE_REV_B_PO"):
        found += _supplier_reasons(
            action["supplier_id"], data["engineering_change"]["old_material_id"], data)
    return found


# Rule 2 ----------------------------------------------------------------------------------------

def check_rev_b_use_up(plan, data, simulation=None):
    rule, change = "REV_B_USE_UP", data["engineering_change"]
    last = change["use_up_end_week"]
    found = []
    for action in _actions(plan, "CONTINUE_REV_B"):
        if not change.get("run_out_supported", 1):
            found.append(reason(rule, "RUN_OUT_NOT_SUPPORTED",
                                "The simulator decides Rev B use after the effective week by itself."))
        if not change["interchangeable"]:
            found.append(reason(rule, "NOT_INTERCHANGEABLE",
                                "Rev B may not be used after the effective week."))
        if action["through_week"] > last:
            found.append(reason(rule, "REV_B_AFTER_USE_UP",
                                f"Rev B use in W{action['through_week']} is after use-up end W{last}."))
    for action in _actions(plan, "SHIFT_EFFECTIVE_WEEK"):
        if action["to_week"] < data["planning_week"]:
            found.append(reason(rule, "EFFECTIVE_IN_PAST",
                                f"Effective week W{action['to_week']} is before the planning week."))
    for row in (simulation or {}).get("weekly", []):
        if row["week"] > last and row["rev_b_usage"] > 0:
            found.append(reason(
                rule, "REV_B_AFTER_USE_UP",
                f"Simulation consumes {row['rev_b_usage']} Rev B in W{row['week']}, after W{last}."))
    return found


# Rule 3 ----------------------------------------------------------------------------------------

def po_arrival_reasons(po, data):
    """Rule 3 for one order kept on its current date with its current supplier."""
    supplier = find(data["suppliers"], "supplier_id", po["supplier_id"])
    if po["status"] not in EDITABLE_PO or not supplier:
        return []
    earliest = earliest_arrival(po, supplier)
    if po["arrival_week"] >= earliest:
        return []
    return [reason("SUPPLIER_LEAD_TIME", "IMPOSSIBLE_ARRIVAL",
                   f"{po['po_id']} arrives W{po['arrival_week']}, earliest feasible is W{earliest}.")]


def check_supplier_lead_time(plan, data):
    rule, found = "SUPPLIER_LEAD_TIME", []
    touched = {a["po_id"] for a in _actions(plan, "EXPEDITE_REV_C_PO", "ALTERNATE_SUPPLIER",
                                            "CANCEL_REV_B_PO")}
    deferred = {a["po_id"]: a["weeks"] for a in _actions(plan, "DEFER_REV_B_PO", "DEFER_REV_C_PO")}
    for po in affected_orders(data):
        if po["po_id"] not in touched:
            arrival = po["arrival_week"] + deferred.get(po["po_id"], 0)
            found += po_arrival_reasons({**po, "arrival_week": arrival}, data)
    for action in _actions(plan, "EXPEDITE_REV_C_PO"):
        po = po_of(action, data)
        supplier = po and find(data["suppliers"], "supplier_id", po["supplier_id"])
        if not supplier:
            continue  # rule 1 or rule 4 already reports the missing record
        if not supplier["expedite_available"]:
            found.append(reason(rule, "EXPEDITE_NOT_AVAILABLE",
                                f"Supplier {supplier['supplier_id']} does not offer expedite."))
            continue
        arrival = po["arrival_week"] - action["weeks"]
        earliest = max(earliest_arrival(po, supplier, expedited=True), data["planning_week"])
        if arrival < earliest:
            found.append(reason(
                rule, "EXPEDITE_BELOW_LEAD_TIME",
                f"{po['po_id']} cannot arrive in W{arrival}; expedited earliest is W{earliest}."))
    for action in _actions(plan, "ALTERNATE_SUPPLIER"):
        po = po_of(action, data)
        supplier = find(data["suppliers"], "supplier_id", action["supplier_id"])
        horizon = max(d["week"] for d in data["demand"])
        if po and supplier and alternate_arrival(po, supplier, data) > horizon:
            found.append(reason(
                rule, "ALTERNATE_TOO_LATE",
                f"{action['supplier_id']} cannot deliver {po['po_id']} inside the horizon."))
    return found


# Rule 4 ----------------------------------------------------------------------------------------

def _po_window_reasons(action, data):
    rule, name, po = "PO_WINDOW", action["action"], po_of(action, data)
    if po is None:
        return [reason(rule, "UNKNOWN_PO", f"{action.get('po_id')} does not exist.")]
    po_id, now, change = po["po_id"], data["planning_week"], data["engineering_change"]
    expected = change["old_material_id" if name in REV_B_PO_ACTIONS else "new_material_id"]
    if po["material_id"] != expected:
        return [reason(rule, "WRONG_REVISION", f"{name} does not apply to {po_id}.")]
    if po["status"] not in EDITABLE_PO:
        return [reason(rule, "PO_NOT_EDITABLE", f"{po_id} is {po['status']}.")]

    found = []
    if name in ("CANCEL_REV_B_PO", "ALTERNATE_SUPPLIER"):  # resourcing cancels the original order
        if not po["cancellable"]:
            found.append(reason(rule, "NOT_CANCELLABLE", f"{po_id} cannot be cancelled."))
        elif now > po["cancel_deadline_week"]:
            found.append(reason(rule, "CANCEL_WINDOW_CLOSED",
                                f"{po_id} could be cancelled until W{po['cancel_deadline_week']}."))
        return found

    if now > po["change_deadline_week"]:
        found.append(reason(rule, "CHANGE_WINDOW_CLOSED",
                            f"{po_id} could be changed until W{po['change_deadline_week']}."))
    amount = action["quantity"] if name == "REDUCE_REV_B_PO" else action["weeks"]
    if amount <= 0:
        found.append(reason(rule, "NON_POSITIVE_CHANGE", f"{name} on {po_id} needs a positive value."))
    if name == "REDUCE_REV_B_PO":
        supplier = find(data["suppliers"], "supplier_id", po["supplier_id"])
        if supplier and not supplier["accepts_reduction"]:
            found.append(reason(rule, "SUPPLIER_REFUSES_REDUCTION",
                                f"Supplier {po['supplier_id']} does not accept reductions."))
        if amount > po["max_reduction_qty"] or amount > po["quantity"]:
            found.append(reason(
                rule, "REDUCTION_EXCEEDS_LIMIT",
                f"{po_id} may be reduced by at most {min(po['max_reduction_qty'], po['quantity'])}."))
        elif po["reduction_lot"] and amount % po["reduction_lot"]:
            found.append(reason(rule, "REDUCTION_NOT_A_LOT",
                                f"{po_id} reductions come in lots of {po['reduction_lot']}."))
    elif name in ("DEFER_REV_B_PO", "DEFER_REV_C_PO") and amount > po["max_deferral_weeks"]:
        found.append(reason(rule, "DEFERRAL_EXCEEDS_LIMIT",
                            f"{po_id} may be deferred by at most {po['max_deferral_weeks']} week(s)."))
    return found


def check_po_windows(plan, data):
    found = []
    for action in _actions(plan, *PO_ACTIONS):
        found += _po_window_reasons(action, data)
    return found


# Rule 5 ----------------------------------------------------------------------------------------

def check_purchasing_block(plan, data):
    change = data["engineering_change"]
    blocked = change["status"] == "APPROVED" and data["planning_week"] >= change["approval_week"]
    return [
        reason("PURCHASING_BLOCK", "NEW_REV_B_PO_AFTER_APPROVAL",
               f"{change['change_id']} is approved; no new Rev B purchase order is allowed.")
        for _ in _actions(plan, "CREATE_REV_B_PO") if blocked
    ]


# Rule 6 ----------------------------------------------------------------------------------------

def check_purchasing_group(plan, data):
    found = []
    for action in _actions(plan, *PO_ACTIONS, "CREATE_REV_B_PO"):
        if action["action"] == "CREATE_REV_B_PO":
            group = action["purchasing_group"]
            material = data["engineering_change"]["old_material_id"]
            supplier = action["supplier_id"]
        else:
            po = po_of(action, data)
            if po is None:
                continue
            group, material = po["purchasing_group"], po["material_id"]
            supplier = action.get("supplier_id", po["supplier_id"])
        allowed = any(
            (row["purchasing_group"], row["material_id"], row["supplier_id"])
            == (group, material, supplier) for row in data["purchasing_authorizations"])
        if not allowed:
            found.append(reason(
                "PURCHASING_GROUP", "GROUP_NOT_AUTHORIZED",
                f"Group {group} is not authorized for {material} at supplier {supplier}."))
    return found


# Rule 7 ----------------------------------------------------------------------------------------

_REQUIRED = {
    "materials": ("material_id", "revision", "unit_cost"),
    "inventory": ("material_id", "on_hand", "reserved"),
    "demand": ("week", "quantity"),
    "purchase_orders": (
        "po_id", "material_id", "supplier_id", "purchasing_group", "quantity", "order_week",
        "arrival_week", "status", "cancellable", "cancel_deadline_week", "change_deadline_week",
        "cancellation_fee", "max_reduction_qty", "reduction_lot", "reduction_fee_per_unit",
        "max_deferral_weeks", "expedite_fee_per_week"),
    "suppliers": ("supplier_id", "status", "lead_time_weeks", "expedite_available",
                  "expedited_lead_time_weeks", "accepts_reduction"),
    "supplier_materials": ("supplier_id", "material_id", "qualified"),
    "purchasing_authorizations": ("purchasing_group", "material_id", "supplier_id"),
}
_REQUIRED_CHANGE = ("change_id", "old_material_id", "new_material_id", "status", "approval_week",
                    "effective_week", "use_up_end_week", "interchangeable")
_TEXT_FIELDS = {"material_id", "revision", "po_id", "supplier_id", "purchasing_group", "status",
                "change_id", "old_material_id", "new_material_id"}
_UNIQUE = {"materials": "material_id", "inventory": "material_id", "demand": "week",
           "purchase_orders": "po_id", "suppliers": "supplier_id"}


def _field_error(row, field):
    value = row.get(field)
    if value is None:
        return "is missing"
    if field in _TEXT_FIELDS:
        return None if isinstance(value, str) and value else "must be non-empty text"
    if not isinstance(value, (int, float)) or value != value:
        return "must be a number"
    if value < 0 and field != "order_week":
        return "must not be negative"
    return None


def input_errors(data):
    """Everything in the input that makes planning unsafe. Member 1's findings are kept verbatim."""
    found = [reason("INPUT_VALIDITY", "UPSTREAM_VALIDATION",
                    e if isinstance(e, str) else str(e.get("description", e)))
             for e in data.get("validation_errors", [])]

    def bad(code, text):
        found.append(reason("INPUT_VALIDITY", code, text))

    for table, fields in _REQUIRED.items():
        rows = data.get(table)
        if not isinstance(rows, list) or (not rows and table != "purchase_orders"):
            bad("MISSING_TABLE", f"{table} is missing or empty.")
            continue
        for index, row in enumerate(rows):
            for field in fields:
                error = _field_error(row, field)
                if error:
                    name = row.get(_UNIQUE.get(table), f"row {index}")
                    bad("INVALID_FIELD", f"{table} {name}: {field} {error}.")
    change = data.get("engineering_change") or {}
    for field in _REQUIRED_CHANGE:
        error = _field_error(change, field)
        if error:
            bad("INVALID_FIELD", f"engineering_change: {field} {error}.")
    if not isinstance(data.get("planning_week"), int):
        bad("INVALID_FIELD", "planning_week must be a whole number.")
    if found:
        return found  # the cross-checks below assume complete records

    for table, key in _UNIQUE.items():
        for value, count in Counter(row[key] for row in data[table]).items():
            if count > 1:
                bad("DUPLICATE_RECORD", f"{table} holds {count} rows for {key} {value}.")
    if change["effective_week"] > change["use_up_end_week"] + 1:
        bad("DATE_CONFLICT", f"No revision is permitted between Rev B use-up end W{change['use_up_end_week']} and "
                             f"effective week W{change['effective_week']}.")
    if change["status"] != "APPROVED":
        bad("CHANGE_NOT_APPROVED", f"{change['change_id']} is {change['status']}.")
    weeks = sorted(row["week"] for row in data["demand"])
    if weeks != list(range(weeks[0], weeks[0] + len(weeks))):
        bad("DEMAND_GAP", "Demand weeks are not consecutive.")
    materials = {row["material_id"] for row in data["materials"]}
    stocked = {row["material_id"] for row in data["inventory"]}
    for material in (change["old_material_id"], change["new_material_id"]):
        if material not in materials or material not in stocked:
            bad("UNKNOWN_MATERIAL", f"{material} has no material or inventory record.")
    for row in data["inventory"]:
        if row["reserved"] > row["on_hand"]:
            bad("STOCK_CONFLICT", f"{row['material_id']}: reserved stock exceeds stock on hand.")
    suppliers = {row["supplier_id"] for row in data["suppliers"]}
    for po in data["purchase_orders"]:
        if po["supplier_id"] not in suppliers:
            bad("UNKNOWN_SUPPLIER", f"{po['po_id']} refers to unknown supplier {po['supplier_id']}.")
        if po["material_id"] not in materials:
            bad("UNKNOWN_MATERIAL", f"{po['po_id']} refers to unknown material {po['material_id']}.")
        if po["status"] not in PO_STATUSES:
            bad("UNKNOWN_PO_STATUS", f"{po['po_id']} has unknown status {po['status']}.")
    return found


def check_input_validity(plan, data):
    return input_errors(data)


# Plan structure (contradictions) -----------------------------------------------------------------

def check_contradictions(plan):
    """Actions that cannot coexist in one plan. Not a business rule, so not one of the seven."""
    found = []

    def bad(text):
        found.append(reason("PLAN_STRUCTURE", "CONTRADICTORY_ACTIONS", text))

    for action in plan["actions"]:
        if action["action"] not in KNOWN_ACTIONS:
            found.append(reason("PLAN_STRUCTURE", "UNKNOWN_ACTION", str(action["action"])))
    if len(_actions(plan, *CHANGEOVER_ACTIONS)) > 1:
        bad("The changeover moment is set more than once.")
    by_po = {}
    for action in _actions(plan, *PO_ACTIONS):
        by_po.setdefault(action["po_id"], []).append(action["action"])
    for po_id, names in by_po.items():
        if "CANCEL_REV_B_PO" in names and len(names) > 1:
            bad(f"{po_id} is cancelled and also changed.")
        for group in _EXCLUSIVE_GROUPS:
            if sum(name in group for name in names) > 1:
                bad(f"{po_id} has conflicting actions: {', '.join(sorted(names))}.")
    return found


def action_violations(action, data):
    """Hard rules for one action on its own (rule 1 for kept orders is plan-level)."""
    plan = {"actions": [action]}
    found = check_rev_b_use_up(plan, data) + check_po_windows(plan, data)
    if action["action"] in ("EXPEDITE_REV_C_PO", "ALTERNATE_SUPPLIER"):
        found += [r for r in check_supplier_lead_time(plan, data) if r["code"] != "IMPOSSIBLE_ARRIVAL"]
    found += check_purchasing_block(plan, data) + check_purchasing_group(plan, data)
    po = po_of(action, data)
    if action["action"] != "CANCEL_REV_B_PO" and po:
        found += po_supplier_reasons(po, data, action.get("supplier_id"))
    elif action["action"] == "CREATE_REV_B_PO":
        found += _supplier_reasons(
            action["supplier_id"], data["engineering_change"]["old_material_id"], data)
    return found


def validate_plan(plan, data, simulation=None):
    """Run every rule and keep every reason. Returns {"feasibility", "rejection_reasons"}."""
    reasons = check_input_validity(plan, data)
    if not reasons:
        reasons = check_contradictions(plan)
    if not reasons:
        reasons = (check_supplier_qualification(plan, data)
                   + check_rev_b_use_up(plan, data, simulation)
                   + check_supplier_lead_time(plan, data)
                   + check_po_windows(plan, data)
                   + check_purchasing_block(plan, data)
                   + check_purchasing_group(plan, data))
    return {"plan_id": plan.get("plan_id"),
            "feasibility": "REJECTED" if reasons else "FEASIBLE",
            "rejection_reasons": reasons}
