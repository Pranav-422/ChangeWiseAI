import pandas as pd
import pytest

from conftest import edit, week
from engine.inventory import (allocate_component_usage, calculate_available_stock, calculate_closing_stock,
                              calculate_weekly_receipts)


def reconciled(result):
    return all(r["rev_b_reconciled"] and r["rev_c_reconciled"] for r in calculate_closing_stock(result))


def no_negative(result):
    return all(w[f"rev_{r}_closing"] >= 0 for w in result["weeks"] for r in "bc")


# ---------- base scenario, hand-checked ----------

def test_base_scenario_matches_hand_calculation(run):
    r = run()
    assert r["validation_status"] == "VALID"
    assert [w["rev_b_closing"] for w in r["weeks"]] == [420, 320, 420, 300, 280, 280, 280, 280]
    assert [w["rev_c_closing"] for w in r["weeks"]] == [0, 0, 0, 0, 0, 350, 200, 50]
    assert r["total_shortage_units"] == 0
    ex = r["excess"]
    assert ex["rev_b_scrap_units"] == 230 and ex["rev_b_scrap_from_safety_stock"] == 30
    assert ex["rev_b_scrap_value"] == 92000 and ex["rev_c_excess_value"] == 0 and r["excess_value"] == 92000
    assert ex["average_weekly_demand"] == 121.25
    assert reconciled(r)


def test_spec_output_keys_present(run):
    w = week(run(), 1)
    for k in ("week", "rev_b_opening", "rev_b_receipts", "rev_b_usage", "rev_b_closing", "rev_c_opening",
              "rev_c_receipts", "rev_c_usage", "rev_c_closing", "shortage", "rev_b_reserved", "rev_b_available",
              "rev_b_safety_stock", "rev_b_unmet", "rev_c_unmet"):
        assert k in w
    assert w["rev_b_opening"] == 500 and w["rev_b_usage"] == 80 and w["rev_b_closing"] == 420


# ---------- the 14 required edge cases ----------

def test_01_no_incoming_purchase_orders(run, data):
    r = run(purchase_orders=data["purchase_orders"].iloc[0:0])
    # Rev B usable = 500 - 50 reserved - 30 safety = 420 vs 520 demand in W1-W5; Rev C never arrives.
    assert week(r, 5)["shortage"] == 100 and r["shortage"]["first_shortage_week"] == 5
    assert r["total_shortage_units"] == 100 + 450 and reconciled(r)


def test_02_po_arrives_on_time(run):
    r = run()
    assert week(r, 3)["rev_b_receipts"] == 200 and week(r, 5)["rev_b_receipts"] == 100
    assert week(r, 6)["rev_c_receipts"] == 500 and r["total_shortage_units"] == 0


def test_03_supplier_delivery_delayed(run):
    r = run(lead_time_shift=2)
    assert week(r, 6)["shortage"] == 150 and week(r, 7)["shortage"] == 150 and week(r, 8)["rev_c_receipts"] == 500
    assert r["total_shortage_units"] == 300 and r["shortage"]["affected_materials"] == ["MAT-102"]


def test_04_insufficient_rev_b(run, data):
    r = run(inventory=edit(data["inventory"], "material_id", "MAT-101", on_hand=100))
    assert week(r, 1)["rev_b_usage"] == 20 and week(r, 1)["shortage"] == 60   # 100 - 50 reserved - 30 safety
    assert no_negative(r) and reconciled(r)


def test_05_insufficient_rev_c(run, data):
    r = run(purchase_orders=edit(data["purchase_orders"], "po_id", "PO-003", quantity=200))
    assert [week(r, n)["shortage"] for n in (6, 7, 8)] == [0, 120, 150]   # 200 - 20 safety = 180 usable
    assert week(r, 8)["rev_c_closing"] == 20


def test_06_rev_b_use_up_deadline_reached(run):
    r = run({"use_up_end_week": 3})
    assert all(w["rev_b_usage"] == 0 for w in r["weeks"][3:])           # never used after W3
    assert week(r, 4)["shortage"] == 120 and week(r, 5)["shortage"] == 120 and week(r, 4)["applicable_revision"] is None
    assert r["excess"]["rev_b_post_use_up_receipts"] == 100              # PO-002 arrives W5, after use-up end
    assert r["validation_status"] == "NEEDS_REVIEW"


def test_07_reserved_stock_never_consumed(run, data):
    r = run(inventory=edit(data["inventory"], "material_id", "MAT-101", on_hand=120, reserved=50, safety_stock=0))
    assert all(w["rev_b_closing"] >= 50 for w in r["weeks"])
    assert r["excess"]["rev_b_reserved_excluded"] == 50


def test_08_safety_stock_is_protected(run, data):
    r = run(inventory=edit(data["inventory"], "material_id", "MAT-101", on_hand=200, reserved=0, safety_stock=60))
    assert all(w["rev_b_closing"] >= 60 for w in r["weeks"][:5])
    assert week(r, 2)["shortage"] == 40                                   # 200-60 usable: 80 in W1, 60 in W2


def test_09_multiple_receipts_in_one_week(run, data):
    extra = data["purchase_orders"].iloc[[0]].assign(po_id="PO-099", quantity=50)
    r = run(purchase_orders=pd.concat([data["purchase_orders"], extra], ignore_index=True))
    assert week(r, 3)["rev_b_receipts"] == 250 and reconciled(r)


def test_10_zero_demand(run, data):
    r = run(demand=data["demand"].assign(required_quantity=0))
    assert all(w["rev_b_usage"] == 0 and w["rev_c_usage"] == 0 and w["shortage"] == 0 for w in r["weeks"])
    assert r["excess"]["rev_b_scrap_units"] == 500 - 50 + 300
    assert r["excess"]["rev_c_excess_value"] == 500 * 450                 # D = 0, so all Rev C is excess


def test_11_high_demand(run):
    r = run(demand_multiplier=3.0)
    assert r["total_shortage_units"] > 0 and no_negative(r) and reconciled(r)
    assert week(r, 1)["demand"] == 240


def test_12_missing_material(run):
    r = run({"part_number": "MAT-999"})
    assert r["validation_status"] == "INVALID" and r["weeks"] == []
    assert any(i["code"] == "ECN_UNKNOWN_PART" for i in r["issues"])


@pytest.mark.parametrize("bad", [0, -1, None, "W6", 6.5])
def test_13_invalid_effective_week(run, bad):
    r = run({"effective_week": bad})
    assert r["validation_status"] in ("INVALID", "INSUFFICIENT_DATA") and r["weeks"] == []


def test_14_insufficient_lead_time_data(run, data):
    sups = data["suppliers"].astype({"lead_time_weeks": "Float64"})
    r = run(suppliers=edit(sups, "supplier_id", "S2", lead_time_weeks=None))
    assert r["validation_status"] == "INSUFFICIENT_DATA"
    assert any(i["code"] == "SIM_MISSING_LEAD_TIME" for i in r["issues"])


# ---------- lead time, interchangeability, scrap guards ----------

def test_lead_time_violation_is_moved_and_flagged(run, data):
    r = run(purchase_orders=edit(data["purchase_orders"], "po_id", "PO-003", arrival_week=4))
    assert week(r, 4)["rev_c_receipts"] == 0 and week(r, 6)["rev_c_receipts"] == 500   # order W2 + lead 4
    assert any(i["code"] == "SIM_LEAD_TIME_VIOLATION" for i in r["issues"])


def test_expedited_po_uses_expedited_lead_time(run, data):
    pos = edit(data["purchase_orders"], "po_id", "PO-003", arrival_week=5, expedited=1)
    r = run({"effective_week": 5}, purchase_orders=pos)
    assert week(r, 5)["rev_c_receipts"] == 500 and r["validation_status"] == "VALID"


def test_restricted_supplier_receipts_excluded(run, data):
    r = run(suppliers=edit(data["suppliers"], "supplier_id", "S2", supplier_status="Blocked"))
    assert all(w["rev_c_receipts"] == 0 for w in r["weeks"]) and r["total_shortage_units"] == 450


def test_interchangeable_rev_b_covers_early_effective_week(run):
    r = run({"effective_week": 4})                      # Rev C not here until W6; Rev B allowed to W5
    assert week(r, 4)["rev_b_usage"] == 120 and week(r, 5)["rev_b_usage"] == 120
    assert r["total_shortage_units"] == 0
    r2 = run({"effective_week": 4, "interchangeability": False})
    assert week(r2, 4)["shortage"] == 120 and week(r2, 5)["shortage"] == 120


def test_deferring_rev_b_po_past_use_up_cannot_hide_scrap(run, data):
    base = run()["excess"]["rev_b_scrap_units"]
    deferred = run(purchase_orders=edit(data["purchase_orders"], "po_id", "PO-002", arrival_week=12))
    assert deferred["excess"]["rev_b_post_use_up_receipts"] == 100
    assert deferred["excess"]["rev_b_scrap_units"] == base               # same 100 units, now unusable later


def test_cancelled_po_is_not_received(run, data):
    r = run(purchase_orders=edit(data["purchase_orders"], "po_id", "PO-001", po_status="Cancelled"))
    assert week(r, 3)["rev_b_receipts"] == 0


# ---------- determinism and isolation ----------

def test_identical_inputs_give_identical_results(run):
    a, b = run(), run()
    assert a == b and a["simulation_id"] == b["simulation_id"]


def test_row_order_does_not_change_result(run, data):
    shuffled = data["purchase_orders"].sample(frac=1, random_state=7)
    assert run(purchase_orders=shuffled)["input_snapshot_hash"] == run()["input_snapshot_hash"]


def test_different_scenario_gives_different_hash(run):
    assert run()["input_snapshot_hash"] != run(lead_time_shift=1)["input_snapshot_hash"]


def test_inputs_are_not_mutated(run, data):
    before = {k: v.copy() for k, v in data.items()}
    run(lead_time_shift=2, demand_multiplier=1.1)
    for k in data:
        pd.testing.assert_frame_equal(data[k], before[k])


# ---------- unit functions ----------

def test_calculate_available_stock():
    assert calculate_available_stock(500, 50) == 450 and calculate_available_stock(10, 20) == 0
    with pytest.raises(ValueError):
        calculate_available_stock(-1, 0)


def test_calculate_weekly_receipts(data):
    assert calculate_weekly_receipts(data["purchase_orders"], 3, "MAT-101") == 200
    assert calculate_weekly_receipts(data["purchase_orders"], 6) == 500


def test_allocate_component_usage_gap_week():
    out = allocate_component_usage(100, {"week": 5, "effective_week": 6, "use_up_end_week": 4,
                                         "interchangeable": True, "usable_old": 999, "usable_new": 999})
    assert out == {"old_usage": 0, "new_usage": 0, "unmet": 100, "applicable_revision": None}


def test_bad_stress_parameters_raise(run):
    with pytest.raises(ValueError):
        run(demand_multiplier=-0.5)
    with pytest.raises(ValueError):
        run(lead_time_shift=1.5)


def test_unknown_change_id_raises_clear_error(data):
    from engine.inventory import simulate_from_data
    with pytest.raises(KeyError, match="ECN-404"):
        simulate_from_data(data, "ECN-404")


@pytest.mark.parametrize("bad", [0, -1, 2.5])
def test_bad_horizon_raises(run, bad):
    with pytest.raises(ValueError):
        run(horizon_weeks=bad)


def test_other_plant_rows_are_ignored_by_default(run, data):
    other = data["inventory"].iloc[[0]].assign(inventory_id="INV-X", plant_id="PUMP-PLANT-02",
                                               on_hand=9999, inventory_date="2026-12-31")
    dem = data["demand"].iloc[[0]].assign(demand_id="D-X", plant_id="PUMP-PLANT-02", required_quantity=500)
    r = run(inventory=pd.concat([data["inventory"], other]), demand=pd.concat([data["demand"], dem]))
    assert week(r, 1)["rev_b_opening"] == 500 and week(r, 1)["demand"] == 80
