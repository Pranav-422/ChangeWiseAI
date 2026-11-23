"""Synthetic scenarios for development and evaluation (Member 1's dataset replaces them).

base() is the pump-assembly bracket Rev B -> Rev C case from the deck, expressed as input records.
Every other function changes only what its name says. EXPECTED_ESCALATIONS is derived by hand from
the records, not copied from engine output, so it can be used to score escalation routing.
"""

_PO_DEFAULTS = {
    "status": "OPEN", "cancellable": 1, "cancel_deadline_week": 3, "change_deadline_week": 3,
    "cancellation_fee": 0, "max_reduction_qty": 0, "reduction_lot": 0, "reduction_fee_per_unit": 0,
    "max_deferral_weeks": 0, "expedite_fee_per_week": 0,
}


def _po(po_id, material_id, supplier_id, quantity, order_week, arrival_week, **extra):
    return {"po_id": po_id, "material_id": material_id, "supplier_id": supplier_id,
            "purchasing_group": "PG1", "quantity": quantity, "order_week": order_week,
            "arrival_week": arrival_week, **_PO_DEFAULTS, **extra}


def base():
    return {
        "scenario_id": "BASE", "planning_week": 1, "horizon_weeks": 10,
        "materials": [
            {"material_id": "BRK-B", "revision": "B", "unit_cost": 400, "status": "PURCHASING_BLOCKED"},
            {"material_id": "BRK-C", "revision": "C", "unit_cost": 400, "status": "ACTIVE"},
        ],
        "inventory": [
            {"material_id": "BRK-B", "on_hand": 320, "reserved": 20, "safety_stock": 0},
            {"material_id": "BRK-C", "on_hand": 0, "reserved": 0, "safety_stock": 0},
        ],
        "demand": [{"week": w, "quantity": 100} for w in range(1, 11)],
        "purchase_orders": [
            _po("PO-001", "BRK-B", "S2", 350, 0, 4, cancellation_fee=5000, max_reduction_qty=200,
                reduction_lot=50, reduction_fee_per_unit=25, max_deferral_weeks=1),
            _po("PO-002", "BRK-B", "S2", 100, -3, 2, status="SHIPPED", cancellable=0),
            _po("PO-003", "BRK-C", "S1", 400, 0, 6, cancellation_fee=8000, max_deferral_weeks=1,
                expedite_fee_per_week=12000),
            _po("PO-004", "BRK-C", "S1", 300, 4, 10, cancellation_fee=3000, max_deferral_weeks=2,
                expedite_fee_per_week=9000),
        ],
        "suppliers": [
            {"supplier_id": "S1", "status": "APPROVED", "lead_time_weeks": 6,
             "expedite_available": 1, "expedited_lead_time_weeks": 5, "accepts_reduction": 1},
            {"supplier_id": "S2", "status": "APPROVED", "lead_time_weeks": 4,
             "expedite_available": 0, "expedited_lead_time_weeks": 4, "accepts_reduction": 1},
            {"supplier_id": "S3", "status": "BLOCKED", "lead_time_weeks": 3,
             "expedite_available": 0, "expedited_lead_time_weeks": 3, "accepts_reduction": 1},
        ],
        "supplier_materials": [
            {"supplier_id": "S1", "material_id": "BRK-C", "qualified": 1},
            {"supplier_id": "S2", "material_id": "BRK-B", "qualified": 1},
            {"supplier_id": "S3", "material_id": "BRK-C", "qualified": 1},
        ],
        "purchasing_authorizations": [
            {"purchasing_group": "PG1", "material_id": "BRK-B", "supplier_id": "S2"},
            {"purchasing_group": "PG1", "material_id": "BRK-C", "supplier_id": "S1"},
            {"purchasing_group": "PG1", "material_id": "BRK-C", "supplier_id": "S3"},
        ],
        "engineering_change": {
            "change_id": "ECN-1001", "parent_assembly": "PUMP-ASSY", "old_material_id": "BRK-B",
            "new_material_id": "BRK-C", "status": "APPROVED", "approval_week": 1,
            "effective_week": 6, "use_up_end_week": 7, "interchangeable": 1,
        },
        "validation_errors": [],
    }


def _variant(name):
    data = base()
    data["scenario_id"] = name
    return data


def find_po(data, po_id):
    return next(po for po in data["purchase_orders"] if po["po_id"] == po_id)


def rev_c_delay():
    data = _variant("REV_C_DELAY")
    find_po(data, "PO-003").update(order_week=3, arrival_week=9)
    return data


def rev_c_delay_no_expedite():
    data = rev_c_delay()
    data["scenario_id"] = "REV_C_DELAY_NO_EXPEDITE"
    data["suppliers"][0]["expedite_available"] = 0
    return data


def excess_rev_b():
    data = _variant("EXCESS_REV_B")
    find_po(data, "PO-001")["quantity"] = 700
    return data


def only_rev_c_supplier_blocked():
    data = _variant("REV_C_SUPPLIER_BLOCKED")
    data["suppliers"][0]["status"] = "BLOCKED"
    return data


def alternate_supplier():
    data = only_rev_c_supplier_blocked()
    data["scenario_id"] = "ALTERNATE_SUPPLIER"
    data["suppliers"].append(
        {"supplier_id": "S4", "status": "APPROVED", "lead_time_weeks": 6, "expedite_available": 0,
         "expedited_lead_time_weeks": 6, "accepts_reduction": 1})
    data["supplier_materials"].append({"supplier_id": "S4", "material_id": "BRK-C", "qualified": 1})
    data["purchasing_authorizations"].append(
        {"purchasing_group": "PG1", "material_id": "BRK-C", "supplier_id": "S4"})
    return data


def unauthorized_group():
    data = _variant("UNAUTHORIZED_GROUP")
    find_po(data, "PO-001")["purchasing_group"] = "PG9"
    return data


def date_conflict():
    data = _variant("DATE_CONFLICT")
    data["engineering_change"]["effective_week"] = 9
    return data


def missing_record():
    data = _variant("MISSING_RECORD")
    del find_po(data, "PO-003")["quantity"]
    return data


SCENARIOS = {
    "BASE": base,
    "REV_C_DELAY": rev_c_delay,
    "REV_C_DELAY_NO_EXPEDITE": rev_c_delay_no_expedite,
    "EXCESS_REV_B": excess_rev_b,
    "REV_C_SUPPLIER_BLOCKED": only_rev_c_supplier_blocked,
    "ALTERNATE_SUPPLIER": alternate_supplier,
    "UNAUTHORIZED_GROUP": unauthorized_group,
    "DATE_CONFLICT": date_conflict,
    "MISSING_RECORD": missing_record,
}

# Hand-derived: which escalation codes the official policy requires for each scenario.
EXPECTED_ESCALATIONS = {
    "BASE": {"NEAR_TIE"},                              # reduce 50 vs 100 differ by 1,250
    "REV_C_DELAY": set(),                              # 13,250 vs next best 22,250
    "REV_C_DELAY_NO_EXPEDITE": {"RESIDUAL_SHORTAGE"},  # W8 has no usable Rev B or Rev C
    "EXCESS_REV_B": set(),                             # cancel + both expedites, 26,000, no rival
    "REV_C_SUPPLIER_BLOCKED": {"NO_FEASIBLE_PLAN"},
    "ALTERNATE_SUPPLIER": {"NEAR_TIE"},                # same reductions, both Rev C POs moved to S4
    "UNAUTHORIZED_GROUP": set(),                       # PO-001 untouchable: 20,000 vs 29,000
    "DATE_CONFLICT": {"INVALID_DATA"},
    "MISSING_RECORD": {"INVALID_DATA"},
}
