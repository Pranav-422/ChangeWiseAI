from copy import deepcopy

import pytest

from member2.engine.action_generator import generate_candidate_plans, make_plan
from member2.engine.cost_calculator import calculate_action_cost
from member2.engine.planner import (
    SimulatorContractError, apply_plan_actions, evaluate_all_candidates, run_simulation,
)
from member2.reference.simulator import simulate_inventory
from .helpers import CANCEL, CONFIG, EXPEDITE, REDUCE_200, SCENARIOS, TO_W5, base, evaluate, find_po


@pytest.mark.parametrize("actions,shortage,excess,cost", [
    ([REDUCE_200, EXPEDITE], 0, 20000, 17000),   # deck P1
    ([], 0, 100000, 0),                          # deck P2
    ([TO_W5, CANCEL], 100, 0, 5000),             # deck P3
])
def test_deck_worked_example_is_reproduced_by_simulation(actions, shortage, excess, cost):
    record = evaluate(actions)
    assert (record["shortage_units"], record["excess_value"], record["action_cost"]) == (
        shortage, excess, cost)
    assert record["secondary_cost"] == excess + cost


def test_baseline_is_never_modified():
    data = base()
    before = deepcopy(data)
    evaluate_all_candidates(generate_candidate_plans(data, CONFIG)["plans"], simulate_inventory, data)
    assert data == before


def test_evaluation_order_does_not_matter():
    data = base()
    plans = generate_candidate_plans(data, CONFIG)["plans"][:60]
    forward = evaluate_all_candidates(plans, simulate_inventory, data)
    backward = evaluate_all_candidates(plans[::-1], simulate_inventory, data)[::-1]
    assert forward == backward


def test_actions_change_only_their_target():
    changed = apply_plan_actions(make_plan([REDUCE_200, EXPEDITE, TO_W5], base()), base())
    assert find_po(changed, "PO-001")["quantity"] == 150
    assert find_po(changed, "PO-003")["arrival_week"] == 5
    assert find_po(changed, "PO-004") == find_po(base(), "PO-004")
    assert changed["engineering_change"]["effective_week"] == 5


def test_alternate_supplier_arrives_after_its_own_lead_time_from_today():
    data = SCENARIOS["ALTERNATE_SUPPLIER"]()
    changed = apply_plan_actions(make_plan(
        [{"action": "ALTERNATE_SUPPLIER", "po_id": "PO-003", "supplier_id": "S4"}], data), data)
    assert find_po(changed, "PO-003")["arrival_week"] == 1 + 6


def test_costs_come_from_records():
    data = base()
    find_po(data, "PO-003")["expedite_fee_per_week"] = 777
    assert calculate_action_cost([EXPEDITE, CANCEL], data) == {
        "expedite": 777, "cancellation": 5000, "reduction": 0, "total": 5777}


def test_rejected_plans_are_not_simulated():
    record = evaluate([{**EXPEDITE, "weeks": 2}])
    assert record["feasibility"] == "REJECTED" and record["simulation"] is None
    assert "secondary_cost" not in record


def test_negative_quantity_is_impossible():
    with pytest.raises(ValueError):
        apply_plan_actions(make_plan([{**REDUCE_200, "quantity": 999}], base()), base())


def test_simulator_contract_is_enforced():
    with pytest.raises(SimulatorContractError, match="lacks"):
        run_simulation(base(), lambda **_: {"weekly": []})

    def wrong_excess(**kwargs):
        return {**simulate_inventory(**kwargs), "total_excess_value": 1}
    with pytest.raises(SimulatorContractError, match="official formula"):
        run_simulation(base(), wrong_excess)
