from member2.evaluation import metrics
from member2.evaluation.baselines import run_baseline_a, run_baseline_b
from member2.evaluation.comparison import compare_configurations
from member2.reference.simulator import simulate_inventory
from .helpers import CONFIG, SCENARIOS, base


def test_baseline_a_is_the_untouched_changeover():
    row = run_baseline_a(base(), simulate_inventory, CONFIG)
    assert (row["shortage_units"], row["rev_b_leftover"], row["excess_value"]) == (0, 250, 100000)
    assert all(w["rev_b_usage"] == 0 for w in row["weekly"] if w["week"] >= 6)


def test_baseline_b_consumes_rev_b_first_and_stops_at_use_up():
    row = run_baseline_b(base(), simulate_inventory, CONFIG)
    assert (row["shortage_units"], row["rev_b_leftover"], row["excess_value"]) == (0, 50, 20000)
    assert all(w["rev_b_usage"] == 100 for w in row["weekly"] if w["week"] <= 7)
    assert all(w["rev_b_usage"] == 0 for w in row["weekly"] if w["week"] > 7)


def test_shortage_weeks_in_the_delay_scenario():
    data = SCENARIOS["REV_C_DELAY"]()
    assert run_baseline_a(data, simulate_inventory, CONFIG)["shortage_weeks"] == [6, 7, 8]
    assert run_baseline_b(data, simulate_inventory, CONFIG)["shortage_weeks"] == [8]


def test_comparison_uses_one_demand_for_all_three_and_never_loses():
    for name in ("BASE", "REV_C_DELAY", "EXCESS_REV_B"):
        rows = compare_configurations(SCENARIOS[name](), CONFIG, simulate_inventory)
        assert [r["configuration"] for r in rows] == ["BASELINE_A", "BASELINE_B", "CHANGEWISE"]
        assert len({tuple(w["demand"] for w in r["weekly"]) for r in rows}) == 1
        key = [(r["shortage_units"], r["secondary_cost"]) for r in rows]
        assert key[2] <= min(key[:2])  # both baselines are members of the candidate set


def test_comparison_without_a_plan():
    blocked = compare_configurations(SCENARIOS["REV_C_SUPPLIER_BLOCKED"](), CONFIG, simulate_inventory)
    assert [r["configuration"] for r in blocked] == ["BASELINE_A", "BASELINE_B"]
    assert all(r["hard_rule_violations"] > 0 for r in blocked)
    assert compare_configurations(SCENARIOS["DATE_CONFLICT"](), CONFIG, simulate_inventory) == []


def test_reconciliation_metric_detects_a_bad_balance():
    weekly = run_baseline_a(base(), simulate_inventory, CONFIG)["weekly"]
    assert metrics.inventory_reconciliation([weekly])["value"] == 1
    broken = [dict(w) for w in weekly]
    broken[3]["rev_b_closing"] += 1
    assert metrics.inventory_reconciliation([broken])["value"] < 1


def test_external_metrics_are_pending_until_evidence_arrives():
    assert {m["status"] for m in metrics.external_metrics()} == {"PENDING"}
    row = metrics.external_metrics({"what_if_mapping_accuracy": {"value": 0.9, "evidence": "run 3"}})
    assert [m["value"] for m in row if m["status"] == "REPORTED"] == [0.9]
