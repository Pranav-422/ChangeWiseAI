from copy import deepcopy

import pytest

from member2.engine.robustness import (
    apply_shock, calculate_robustness, check_robustness_escalation, compare_plan_robustness,
    generate_stress_scenarios, run_plan_under_stress,
)
from member2.reference.simulator import simulate_inventory
from .helpers import CONFIG, REDUCE_50, RUN_OUT, base, evaluate, find_po


def record(plan_id, passed, rivals=()):
    return {"plan_id": plan_id, "robustness": {"numerator": passed, "denominator": 9, "display": f"{passed}/9"},
            "near_ties": [{"plan_a": plan_id, "plan_b": r} for r in rivals]}


def test_nine_distinct_scenarios():
    scenarios = generate_stress_scenarios(CONFIG)
    assert len({s["scenario_id"] for s in scenarios}) == 9
    assert {(s["lead_time_shock"], s["demand_shock"]) for s in scenarios} == {
        (lead, demand) for lead in (0, 1, 2) for demand in (-0.1, 0.0, 0.1)}


def test_shock_changes_demand_and_undelivered_rev_c_only():
    data = apply_shock(base(), {"lead_time_shock": 2, "demand_shock": 0.1})
    assert {d["quantity"] for d in data["demand"]} == {110}
    assert find_po(data, "PO-003")["arrival_week"] == 8
    assert find_po(data, "PO-001")["arrival_week"] == find_po(base(), "PO-001")["arrival_week"]


def test_no_shock_equals_the_base_case():
    plan, data = evaluate([RUN_OUT, REDUCE_50]), base()
    before = deepcopy(data)
    result = run_plan_under_stress(plan, {"lead_time_shock": 0, "demand_shock": 0.0}, data, simulate_inventory)
    assert result["shortage_units"] == plan["shortage_units"]
    assert result["excess_value"] == plan["excess_value"]
    assert data == before


def test_hand_checked_score():
    """Run-out plan with 700 Rev B: only +2 weeks with +10% demand fails (770 needed by W7)."""
    plan = evaluate([RUN_OUT, REDUCE_50])
    score = compare_plan_robustness([plan], base(), simulate_inventory, CONFIG)[plan["plan_id"]]
    assert score["display"] == "8/9"
    failed = [s for s in score["scenarios"] if not s["zero_shortage"]]
    assert [(s["lead_time_shock"], s["demand_shock"], s["shortage_units"]) for s in failed] == [(2, 0.1, 70)]


def test_ratio():
    score = calculate_robustness([{"zero_shortage": i > 0} for i in range(9)])
    assert score["display"] == "8/9" and score["ratio"] == pytest.approx(0.8889, abs=1e-4)
    with pytest.raises(ValueError):
        calculate_robustness([])


def test_escalates_only_for_a_fragile_leader_with_a_sturdier_near_tie():
    assert check_robustness_escalation([record("A", 6, ["B"]), record("B", 8)], CONFIG)["plan_ids"] == ["A", "B"]
    assert check_robustness_escalation([record("A", 7, ["B"]), record("B", 9)], CONFIG) is None  # 7/9 is enough
    assert check_robustness_escalation([record("A", 6), record("B", 9)], CONFIG) is None         # not a near-tie
    assert check_robustness_escalation([record("A", 6, ["B"]), record("B", 6)], CONFIG) is None  # not sturdier
    assert check_robustness_escalation([], CONFIG) is None
