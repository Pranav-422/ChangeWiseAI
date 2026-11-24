from copy import deepcopy

import pytest

from member2.engine.action_generator import (
    build_menus, combination_count, generate_candidate_plans, make_plan, validate_action_combinations,
)
from member2.engine.constraints import check_contradictions, validate_plan
from member2.engine.planner import apply_plan_actions
from .helpers import (
    CANCEL, CONFIG, EXPEDITE, REDUCE_200, REDUCE_50, RUN_OUT, SCENARIOS, TO_W5, base, config, find_po,
)


def test_complete_and_unique():
    out = generate_candidate_plans(base(), CONFIG)
    ids = [p["plan_id"] for p in out["plans"]]
    assert len(ids) == len(set(ids))
    enumerated = [p for p in out["plans"] if p["source"] == "ENUMERATION"]
    # 4 changeovers x PO-001 (5 reductions x 2 timings + cancel) x PO-003 (3) x PO-004 (4)
    assert len(enumerated) == out["combination_count"] == 4 * 11 * 3 * 4
    assert {p["effective_week"] for p in enumerated} == {5, 6, 7}


def test_deterministic_and_input_preserved():
    data = base()
    before = deepcopy(data)
    assert generate_candidate_plans(data, CONFIG) == generate_candidate_plans(base(), CONFIG)
    assert data == before


def test_plan_id_ignores_action_order():
    data = base()
    assert make_plan([CANCEL, EXPEDITE], data)["plan_id"] == make_plan([EXPEDITE, CANCEL], data)["plan_id"]


@pytest.mark.parametrize("name", ["BASE", "EXCESS_REV_B", "ALTERNATE_SUPPLIER", "UNAUTHORIZED_GROUP"])
def test_enumerated_plans_obey_rules_and_probes_do_not(name):
    data = SCENARIOS[name]()
    for plan in generate_candidate_plans(data, CONFIG)["plans"]:
        expected = "REJECTED" if plan["source"] == "PROBE" else "FEASIBLE"
        assert validate_plan(plan, data)["feasibility"] == expected, plan


def test_no_negative_quantities():
    data = base()
    for plan in generate_candidate_plans(data, CONFIG)["plans"]:
        if plan["source"] == "ENUMERATION":
            assert all(po["quantity"] >= 0 for po in apply_plan_actions(plan, data)["purchase_orders"])


def test_skipped_actions_carry_reasons():
    skipped = generate_candidate_plans(base(), CONFIG)["skipped_actions"]
    found = {(s["action"]["action"], r["code"]) for s in skipped for r in s["reasons"]}
    assert ("ALTERNATE_SUPPLIER", "BLOCKED_SUPPLIER") in found          # deck P4
    assert ("CONTINUE_REV_B", "REV_B_AFTER_USE_UP") in found            # deck P5
    assert ("CREATE_REV_B_PO", "NEW_REV_B_PO_AFTER_APPROVAL") in found
    assert ("EXPEDITE_REV_C_PO", "EXPEDITE_BELOW_LEAD_TIME") in found


@pytest.mark.parametrize("actions", [
    [CANCEL, REDUCE_50],
    [REDUCE_50, REDUCE_200],
    [TO_W5, RUN_OUT],
    [EXPEDITE, {"action": "DEFER_REV_C_PO", "po_id": "PO-003", "weeks": 1}],
    [EXPEDITE, {"action": "ALTERNATE_SUPPLIER", "po_id": "PO-003", "supplier_id": "S3"}],
])
def test_contradictions_dropped(actions):
    plan = make_plan(actions, base())
    assert check_contradictions(plan)
    kept, dropped = validate_action_combinations([plan])
    assert kept == [] and dropped[0]["plan_id"] == plan["plan_id"]


def test_duplicates_dropped():
    plan = make_plan([CANCEL], base())
    kept, dropped = validate_action_combinations([plan, dict(plan)])
    assert len(kept) == 1 and dropped[0]["reason"] == "DUPLICATE"


def test_space_limit_is_enforced():
    out = generate_candidate_plans(base(), config(action_space={"max_candidates": 10}))
    assert out["truncated"] and all(p["source"] == "PROBE" for p in out["plans"])


def test_weeks_configurable():
    menus = build_menus(base(), config(action_space={"effective_weeks": [6]}))
    assert combination_count(menus) == 2 * 11 * 3 * 4  # original week or run-out


def test_not_interchangeable_removes_run_out():
    data = base()
    data["engineering_change"]["interchangeable"] = 0
    assert [RUN_OUT] not in build_menus(data, CONFIG)["changeovers"]


def test_zero_combinations_when_an_order_has_no_option():
    assert combination_count(build_menus(SCENARIOS["REV_C_SUPPLIER_BLOCKED"](), CONFIG)) == 0


def test_infeasible_arrival_cannot_be_kept():
    data = base()
    find_po(data, "PO-003")["arrival_week"] = 5  # ordered W0, lead time 6
    menu = build_menus(data, CONFIG)["po_menus"]["PO-003"]
    assert [] not in menu
    assert [{"action": "DEFER_REV_C_PO", "po_id": "PO-003", "weeks": 1}] in menu
