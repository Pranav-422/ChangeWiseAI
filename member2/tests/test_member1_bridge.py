"""Member 2 on Member 1's real data and simulator."""
import json
import random
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from member1.engine.inventory import simulate_from_data
from member1.engine.scenarios import load_scenario
from member2.engine.action_generator import generate_candidate_plans, make_plan
from member2.engine.config import load_config
from member2.engine.data_loader import load_json
from member2.engine.pipeline import replay_matches, run_optimization
from member2.engine.planner import apply_plan_actions, evaluate_candidate_plan, run_simulation
from member2.engine.robustness import apply_shock
from member2.evaluation.comparison import compare_configurations
from member2.evaluation.run_all import MEMBER1_ESCALATIONS
from member2.evaluation.solver_check import check_solver_agreement
from member2.integration.member1_bridge import list_scenarios, load_dataset, simulate_inventory
from member2.solver import BACKENDS, SolverUnavailable, load_backend
from .helpers import find_po

CONFIG = load_config()
CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
PLANNABLE = ("base", "rev_c_supplier_delay", "excess_rev_b_orders")


def result_for(name):
    return run_optimization(load_dataset(name), CONFIG)


def test_configured_simulator_is_member1s():
    assert result_for("base")["simulator"] == "member2.integration.member1_bridge:simulate_inventory"


@pytest.mark.parametrize("name", [*PLANNABLE, "blocked_supplier"])
def test_no_action_equals_member1s_own_run(name):
    data = load_dataset(name)
    mine = run_simulation(apply_plan_actions(make_plan([], data), data), simulate_inventory)
    own = simulate_from_data(load_scenario(name), "ECN-001")
    assert mine["total_shortage"] == own["total_shortage_units"]
    assert mine["total_excess_value"] == own["excess_value"]
    assert mine["weekly"] == own["weeks"]


@pytest.mark.parametrize("lead", [0, 1, 2])
@pytest.mark.parametrize("demand", [-0.1, 0.0, 0.1])
def test_stress_shocks_equal_member1s_parameters(lead, demand):
    data = load_dataset("base")
    shocked = apply_shock(apply_plan_actions(make_plan([], data), data),
                          {"lead_time_shock": lead, "demand_shock": demand})
    mine = run_simulation(shocked, simulate_inventory)
    own = simulate_from_data(load_scenario("base"), "ECN-001", lead_time_shift=lead, demand_multiplier=1 + demand)
    assert (mine["total_shortage"], mine["total_excess_value"]) == (own["total_shortage_units"], own["excess_value"])


@pytest.mark.parametrize("name", list_scenarios())
def test_routing_and_contracts(name):
    result = result_for(name)
    assert {e["code"] for e in result["escalations"]} == MEMBER1_ESCALATIONS[name]
    Draft202012Validator(load_json(CONTRACTS / "output_schema.json")).validate(json.loads(json.dumps(result)))
    if name != "missing_records":
        Draft202012Validator(load_json(CONTRACTS / "input_schema.json")).validate(load_dataset(name))


def test_hand_checked_base_plan():
    """PO-001 cut by 200 for a flat 5,000; the 30 safety-stock units remain at 400 each."""
    best = result_for("base")["recommendations"][0]
    assert best["summary"] == "Reduce PO-001 by 200"
    assert (best["shortage_units"], best["excess_value"], best["action_cost"]) == (0, 12000, 5000)


def test_blocking_findings_of_member1_stop_planning():
    result = result_for("missing_records")
    text = " ".join(e["description"] for e in result["escalations"][0]["evidence"])
    assert result["decision"] == "INVALID_DATA" and "INV_MISSING_FOR_AFFECTED" in text and "SUP_LEAD_TIME_REQUIRED" in text


def test_unrelated_blocked_supplier_does_not_matter():
    """S3 is blocked and supplies only bolts here."""
    assert result_for("base")["counts"]["feasible"] > 0


def test_safety_and_reserved_stock_are_never_used():
    for plan in generate_candidate_plans(load_dataset("base"), CONFIG)["plans"][::97]:
        data = load_dataset("base")
        record = evaluate_candidate_plan(plan, simulate_inventory, data)
        if record["simulation"]:
            assert all(w["rev_b_closing"] >= 50 + 30 for w in record["simulation"]["weekly"] if w["rev_b_usage"])


def test_run_out_is_refused_not_simulated():
    data = load_dataset("base")
    record = evaluate_candidate_plan(make_plan([{"action": "CONTINUE_REV_B", "through_week": 5}], data),
                                     simulate_inventory, data)
    assert record["feasibility"] == "REJECTED" and record["rejection_reasons"][0]["code"] == "RUN_OUT_NOT_SUPPORTED"


def test_expedited_order_keeps_its_date_in_member1():
    data = load_dataset("base")
    plan = make_plan([{"action": "EXPEDITE_REV_C_PO", "po_id": "PO-003", "weeks": 1}], data)
    weekly = evaluate_candidate_plan(plan, simulate_inventory, data)["simulation"]["weekly"]
    assert [w["week"] for w in weekly if w["rev_c_receipts"]] == [5]


def test_input_is_not_modified_and_replay_matches():
    data = load_dataset("excess_rev_b_orders")
    before = deepcopy(data)
    result = run_optimization(data, CONFIG)
    assert data == before and replay_matches(result, data, CONFIG)


@pytest.mark.parametrize("name", PLANNABLE)
def test_proposal_never_loses_to_a_baseline(name):
    rows = compare_configurations(load_dataset(name), CONFIG)
    key = [(r["shortage_units"], r["secondary_cost"]) for r in rows]
    assert len(rows) == 3 and key[2] <= min(key[:2])


def agreement(data, backend):
    try:
        load_backend(backend)
    except SolverUnavailable as error:
        pytest.skip(str(error))
    row = next(r for r in check_solver_agreement(data, CONFIG, simulate_inventory) if r["backend"] == backend)
    assert row["agrees"], row


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("name", PLANNABLE)
def test_solver_equals_enumeration(backend, name):
    agreement(load_dataset(name), backend)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("seed", range(8))
def test_solver_equals_enumeration_on_random_data(backend, seed):
    """Overlapping revisions, safety stock and scarce supply exercise every allocation order."""
    rng, data = random.Random(seed), load_dataset("base")
    for row in data["demand"]:
        row["quantity"] = rng.randint(40, 170)
    for stock in data["inventory"]:
        stock.update(on_hand=rng.randint(60, 500), reserved=rng.randint(0, 40), safety_stock=rng.randint(0, 90))
    for material in data["materials"]:
        material["unit_cost"] = rng.randint(100, 900)
    data["engineering_change"].update(effective_week=rng.randint(4, 6), interchangeable=rng.randint(0, 1))
    data["engineering_change"]["use_up_end_week"] = rng.randint(data["engineering_change"]["effective_week"] - 1, 7)
    find_po(data, "PO-003").update(quantity=rng.randint(4, 12) * 50, arrival_week=rng.randint(6, 8))
    find_po(data, "PO-002").update(quantity=rng.randint(1, 6) * 50)
    agreement(data, backend)
