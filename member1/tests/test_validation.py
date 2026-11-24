import pandas as pd
import pytest

from conftest import edit
from engine.validation import (validate_all_inputs, validate_bom, validate_engineering_change, validate_inventory,
                               validate_materials, validate_purchase_orders, validate_suppliers)


def codes(result):
    return {i.code for i in result.issues if i.status.value != "VALID"}


def test_base_data_is_valid(data):
    v = validate_all_inputs(data, "ECN-001")
    assert v["status"] == "VALID" and v["ready_for_simulation"]


def test_unrelated_blocked_supplier_does_not_block_the_change(data):
    v = validate_all_inputs(data, "ECN-001")       # PO-005 for bolts is from blocked S3
    po5 = [i for i in v["issues"] if i["record"] == "PO-005"]
    assert po5 and all(i["status"] == "VALID" for i in po5)


def test_blocked_supplier_on_affected_po_needs_review(data):
    d = {**data, "suppliers": edit(data["suppliers"], "supplier_id", "S2", supplier_status="Blocked",
                                   restriction_note="quality hold")}
    v = validate_all_inputs(d, "ECN-001")
    assert v["status"] == "NEEDS_REVIEW" and v["ready_for_simulation"]
    assert any(i["code"] == "PO_RESTRICTED_SUPPLIER" and i["record"] == "PO-003" for i in v["issues"])


# ---- engineering change ----

@pytest.mark.parametrize("field", ["change_id", "part_number", "effective_week", "use_up_end_week", "interchangeability"])
def test_missing_change_field_is_insufficient_not_defaulted(data, change, field):
    r = validate_engineering_change({**change, field: None}, data["materials"])
    assert r.status.value == "INSUFFICIENT_DATA" and "ECN_MISSING_FIELD" in codes(r)


@pytest.mark.parametrize("update,code", [
    ({"part_number": "MAT-999"}, "ECN_UNKNOWN_PART"),
    ({"old_revision": "Rev A"}, "ECN_OLD_REVISION_MISMATCH"),
    ({"new_revision": "C"}, "ECN_INVALID_REVISION_FORMAT"),
    ({"new_revision": "Rev B"}, "ECN_REVISION_UNCHANGED"),
    ({"new_revision": "Rev D"}, "ECN_NEW_REVISION_MISMATCH"),
    ({"effective_week": 0}, "ECN_INVALID_EFFECTIVE_WEEK"),
    ({"use_up_end_week": "soon"}, "ECN_INVALID_USE_UP_WEEK"),
    ({"interchangeability": "maybe"}, "ECN_INVALID_INTERCHANGEABILITY"),
])
def test_invalid_change(data, change, update, code):
    r = validate_engineering_change({**change, **update}, data["materials"])
    assert r.status.value == "INVALID" and code in codes(r)


@pytest.mark.parametrize("update,code", [
    ({"use_up_end_week": 3}, "ECN_REVISION_GAP"),
    ({"use_up_end_week": 7, "interchangeability": 0}, "ECN_USE_UP_AFTER_EFFECTIVE"),
    ({"approval_status": "Pending"}, "ECN_NOT_APPROVED"),
])
def test_change_needs_review(data, change, update, code):
    r = validate_engineering_change({**change, **update}, data["materials"])
    assert r.status.value == "NEEDS_REVIEW" and code in codes(r)


# ---- materials / inventory / BOM ----

def test_materials(data):
    m = data["materials"]
    assert codes(validate_materials(pd.concat([m, m.iloc[[0]]]))) == {"MAT_DUPLICATE_ID"}
    assert "MAT_INVALID_UNIT_COST" in codes(validate_materials(edit(m, "material_id", "MAT-101", unit_cost=-1)))
    assert "MAT_INVALID_REVISION" in codes(validate_materials(edit(m, "material_id", "MAT-101", revision="B")))
    assert "MAT_UNKNOWN_STATUS" in codes(validate_materials(edit(m, "material_id", "MAT-101", material_status="Gone")))


def test_inventory(data):
    inv, mats = data["inventory"], data["materials"]
    assert "INV_INVALID_QUANTITY" in codes(validate_inventory(edit(inv, "material_id", "MAT-101", on_hand=-5), mats))
    assert "INV_INVALID_QUANTITY" in codes(validate_inventory(edit(inv, "material_id", "MAT-101", safety_stock=-1), mats))
    assert "INV_RESERVED_EXCEEDS_ON_HAND" in codes(validate_inventory(edit(inv, "material_id", "MAT-101", reserved=600), mats))
    assert "INV_UNKNOWN_MATERIAL" in codes(validate_inventory(edit(inv, "material_id", "MAT-101", material_id="X"), mats))


def test_bom(data):
    bom, mats = data["bom"], data["materials"]
    assert "BOM_UNKNOWN_MATERIAL" in codes(validate_bom(edit(bom, "bom_id", "BOM-003", child_material_id="X"), mats))
    assert "BOM_INVALID_QUANTITY" in codes(validate_bom(edit(bom, "bom_id", "BOM-003", quantity_per_parent=0), mats))
    assert "BOM_DUPLICATE_RELATIONSHIP" in codes(validate_bom(pd.concat([bom, bom.iloc[[2]].assign(bom_id="BOM-D")]), mats))
    loop = pd.concat([bom, bom.iloc[[0]].assign(bom_id="BOM-L", parent_material_id="SUB-201", child_material_id="PUMP-001")])
    assert "BOM_CYCLE" in codes(validate_bom(loop, mats))


# ---- purchase orders / suppliers ----

def test_purchase_orders(data):
    po, sup, grp = data["purchase_orders"], data["suppliers"], data["planning_groups"]
    check = lambda df: codes(validate_purchase_orders(df, sup, grp, {"MAT-101", "MAT-102"}))  # noqa: E731
    assert check(po) == set()
    assert "PO_DUPLICATE_ID" in check(pd.concat([po, po.iloc[[0]]]))
    assert "PO_INVALID_QUANTITY" in check(edit(po, "po_id", "PO-001", quantity=-10))
    assert "PO_UNKNOWN_SUPPLIER" in check(edit(po, "po_id", "PO-001", supplier_id="S9"))
    assert "PO_INVALID_ARRIVAL_WEEK" in check(edit(po, "po_id", "PO-001", arrival_week=0))
    assert "PO_INVALID_CANCEL_WINDOW" in check(edit(po, "po_id", "PO-001", cancel_allowed_until=9))
    assert "PO_UNKNOWN_PURCHASING_GROUP" in check(edit(po, "po_id", "PO-001", purchasing_group="PG-99"))
    assert "PO_GROUP_NOT_AUTHORIZED" in check(edit(po, "po_id", "PO-003", supplier_id="S3"))


def test_suppliers(data):
    sup = data["suppliers"]
    assert codes(validate_suppliers(sup)) == set()
    assert "SUP_UNKNOWN_STATUS" in codes(validate_suppliers(edit(sup, "supplier_id", "S1", supplier_status="Maybe")))
    assert "SUP_INVALID_LEAD_TIME" in codes(validate_suppliers(edit(sup, "supplier_id", "S1", lead_time_weeks=-1)))
    assert "SUP_RESTRICTION_NOT_EXPLICIT" in codes(validate_suppliers(edit(sup, "supplier_id", "S3", restriction_note=None)))


def test_missing_lead_time_on_affected_supplier_is_insufficient(data):
    sups = edit(data["suppliers"].astype({"lead_time_weeks": "Float64"}), "supplier_id", "S2", lead_time_weeks=None)
    v = validate_all_inputs({**data, "suppliers": sups}, "ECN-001")
    assert v["status"] == "INSUFFICIENT_DATA" and not v["ready_for_simulation"]


def test_issue_records_are_machine_readable(data, change):
    r = validate_engineering_change({**change, "effective_week": 0}, data["materials"]).to_dict()
    i = r["issues"][0]
    assert set(i) >= {"code", "status", "severity", "record", "description", "resolution"} and i["severity"] == "ERROR"


@pytest.mark.parametrize("week", [53, 58])
def test_week_beyond_calendar_is_invalid(data, change, week):
    r = validate_engineering_change({**change, "effective_week": week, "use_up_end_week": week - 1}, data["materials"])
    assert r.status.value == "INVALID" and "ECN_INVALID_EFFECTIVE_WEEK" in codes(r)


def test_rev_b_po_after_approval_is_flagged(data):
    pos = edit(data["purchase_orders"], "po_id", "PO-002", order_week=2)       # approval_week is 1
    v = validate_all_inputs({**data, "purchase_orders": pos}, "ECN-001")
    assert v["status"] == "NEEDS_REVIEW"
    assert any(i["code"] == "PO_CREATED_AFTER_APPROVAL" and i["record"] == "PO-002" for i in v["issues"])
