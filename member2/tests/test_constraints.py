import pytest

from member2.engine.action_generator import make_plan
from member2.engine.constraints import check_rev_b_use_up, input_errors, validate_plan
from .helpers import (
    CANCEL, EXPEDITE, REDUCE_200, REDUCE_50, RUN_OUT, SCENARIOS, TO_W5, base, codes, find_po,
)


def check(actions, mutate=None):
    data = base()
    if mutate:
        mutate(data)
    return codes(validate_plan(make_plan(actions, data), data))


def supplier(data, sid):
    return next(s for s in data["suppliers"] if s["supplier_id"] == sid)


def test_clean_plan_is_feasible():
    data = base()
    record = validate_plan(make_plan([REDUCE_200, EXPEDITE], data), data)
    assert record["feasibility"] == "FEASIBLE" and record["rejection_reasons"] == []


# Rule 1
def test_blocked_supplier():
    assert "BLOCKED_SUPPLIER" in check(
        [{"action": "ALTERNATE_SUPPLIER", "po_id": "PO-003", "supplier_id": "S3"}])


def test_unqualified_supplier():
    def mutate(data):
        supplier(data, "S3")["status"] = "APPROVED"
        data["supplier_materials"][-1]["qualified"] = 0
    assert "UNQUALIFIED_SUPPLIER" in check(
        [{"action": "ALTERNATE_SUPPLIER", "po_id": "PO-003", "supplier_id": "S3"}], mutate)


def test_unrelated_blocked_supplier_is_harmless():
    assert supplier(base(), "S3")["status"] == "BLOCKED"
    assert check([]) == set()


def test_kept_order_at_blocked_supplier_is_a_purchase():
    assert "BLOCKED_SUPPLIER" in check([], lambda d: supplier(d, "S1").update(status="BLOCKED"))


def test_cancelling_at_blocked_supplier_is_allowed():
    assert check([CANCEL], lambda d: supplier(d, "S2").update(status="BLOCKED")) == set()


# Rule 2
def test_rev_b_after_use_up():
    assert "REV_B_AFTER_USE_UP" in check([{"action": "CONTINUE_REV_B", "through_week": 8}])
    assert "EFFECTIVE_AFTER_USE_UP" in check(
        [{"action": "SHIFT_EFFECTIVE_WEEK", "from_week": 6, "to_week": 8}])


def test_run_out_to_last_week_is_allowed():
    assert check([RUN_OUT]) == set()


def test_not_interchangeable():
    assert "NOT_INTERCHANGEABLE" in check(
        [RUN_OUT], lambda d: d["engineering_change"].update(interchangeable=0))


def test_simulated_usage_is_checked_too():
    simulation = {"weekly": [{"week": 8, "rev_b_usage": 5}]}
    assert check_rev_b_use_up({"actions": []}, base(), simulation)[0]["code"] == "REV_B_AFTER_USE_UP"


def test_shift_into_the_past():
    assert "EFFECTIVE_IN_PAST" in check([{**TO_W5, "to_week": 0}])


# Rule 3
def test_expedite_inside_lead_time_only():
    assert check([EXPEDITE]) == set()
    assert "EXPEDITE_BELOW_LEAD_TIME" in check([{**EXPEDITE, "weeks": 2}])


def test_expedite_needs_supplier_offer():
    assert "EXPEDITE_NOT_AVAILABLE" in check(
        [EXPEDITE], lambda d: supplier(d, "S1").update(expedite_available=0))


def test_expedite_cannot_arrive_in_the_past():
    def mutate(data):
        data["planning_week"] = 6
        find_po(data, "PO-003")["change_deadline_week"] = 9
    assert "EXPEDITE_BELOW_LEAD_TIME" in check([EXPEDITE], mutate)


def test_impossible_arrival_on_kept_order():
    assert "IMPOSSIBLE_ARRIVAL" in check([], lambda d: find_po(d, "PO-003").update(arrival_week=3))


# Rule 4
@pytest.mark.parametrize("action,code", [
    ({"action": "DEFER_REV_B_PO", "po_id": "PO-001", "weeks": 2}, "DEFERRAL_EXCEEDS_LIMIT"),
    ({**REDUCE_200, "quantity": 250}, "REDUCTION_EXCEEDS_LIMIT"),
    ({**REDUCE_200, "quantity": 70}, "REDUCTION_NOT_A_LOT"),
    ({**REDUCE_200, "quantity": -50}, "NON_POSITIVE_CHANGE"),
    ({"action": "CANCEL_REV_B_PO", "po_id": "PO-002"}, "PO_NOT_EDITABLE"),
    ({"action": "CANCEL_REV_B_PO", "po_id": "PO-003"}, "WRONG_REVISION"),
    ({"action": "CANCEL_REV_B_PO", "po_id": "PO-999"}, "UNKNOWN_PO"),
])
def test_po_limits(action, code):
    assert code in check([action])


def test_windows_are_inclusive_then_closed():
    def week(n):
        return lambda data: data.update(planning_week=n)
    assert check([CANCEL], week(3)) == check([REDUCE_50], week(3)) == set()
    assert "CANCEL_WINDOW_CLOSED" in check([CANCEL], week(4))
    assert "CHANGE_WINDOW_CLOSED" in check([REDUCE_50], week(4))


def test_not_cancellable_and_supplier_refusal():
    assert "NOT_CANCELLABLE" in check([CANCEL], lambda d: find_po(d, "PO-001").update(cancellable=0))
    assert "SUPPLIER_REFUSES_REDUCTION" in check(
        [REDUCE_50], lambda d: supplier(d, "S2").update(accepts_reduction=0))


# Rule 5
def test_purchasing_block_starts_at_approval():
    new_b = {"action": "CREATE_REV_B_PO", "supplier_id": "S2", "purchasing_group": "PG1", "quantity": 10}
    assert check([new_b]) == {"NEW_REV_B_PO_AFTER_APPROVAL"}
    assert check([new_b], lambda d: d["engineering_change"].update(approval_week=2)) == set()


# Rule 6
def test_purchasing_group():
    assert check([REDUCE_50], lambda d: find_po(d, "PO-001").update(purchasing_group="PG9")) == {
        "GROUP_NOT_AUTHORIZED"}


# Rule 7
@pytest.mark.parametrize("mutate,code", [
    (lambda d: find_po(d, "PO-003").pop("quantity"), "INVALID_FIELD"),
    (lambda d: find_po(d, "PO-003").update(quantity=-1), "INVALID_FIELD"),
    (lambda d: find_po(d, "PO-003").update(quantity="many"), "INVALID_FIELD"),
    (lambda d: find_po(d, "PO-003").update(quantity=float("nan")), "INVALID_FIELD"),
    (lambda d: d["demand"].clear(), "MISSING_TABLE"),
    (lambda d: d["demand"].pop(4), "DEMAND_GAP"),
    (lambda d: d["purchase_orders"].append(dict(d["purchase_orders"][0])), "DUPLICATE_RECORD"),
    (lambda d: d["engineering_change"].update(effective_week=8), "DATE_CONFLICT"),
    (lambda d: d["engineering_change"].update(status="DRAFT"), "CHANGE_NOT_APPROVED"),
    (lambda d: d["inventory"][0].update(reserved=999), "STOCK_CONFLICT"),
    (lambda d: find_po(d, "PO-003").update(supplier_id="S9"), "UNKNOWN_SUPPLIER"),
    (lambda d: find_po(d, "PO-003").update(status="LOST"), "UNKNOWN_PO_STATUS"),
    (lambda d: d["validation_errors"].append("BOM path broken"), "UPSTREAM_VALIDATION"),
])
def test_invalid_data(mutate, code):
    data = base()
    mutate(data)
    assert code in {e["code"] for e in input_errors(data)}


def test_all_reasons_are_kept():
    found = check([{**REDUCE_200, "quantity": 250}, {**EXPEDITE, "weeks": 2}],
                  lambda d: find_po(d, "PO-001").update(purchasing_group="PG9"))
    assert found == {"REDUCTION_EXCEEDS_LIMIT", "EXPEDITE_BELOW_LEAD_TIME", "GROUP_NOT_AUTHORIZED"}


def test_every_scenario_input_is_classified():
    bad = {n for n, build in SCENARIOS.items() if input_errors(build())}
    assert bad == {"DATE_CONFLICT", "MISSING_RECORD"}
