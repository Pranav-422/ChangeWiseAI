import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from member2.engine.data_loader import LIST_TABLES, load_json, load_sqlite
from member2.engine.pipeline import evaluate_custom_plan, replay_matches, run_optimization
from member2.reference.scenarios import EXPECTED_ESCALATIONS
from member2.reference.simulator import simulate_inventory
from .helpers import CANCEL, CONFIG, EXPEDITE, REDUCE_200, SCENARIOS, base, config, find_po

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
INPUT = Draft202012Validator(load_json(CONTRACTS / "input_schema.json"))
OUTPUT = Draft202012Validator(load_json(CONTRACTS / "output_schema.json"))


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_routing_and_output_contract(name):
    result = run_optimization(SCENARIOS[name](), CONFIG)
    assert {e["code"] for e in result["escalations"]} == EXPECTED_ESCALATIONS[name]
    OUTPUT.validate(json.loads(json.dumps(result)))
    assert result["requires_planner_review"] == bool(EXPECTED_ESCALATIONS[name])


def test_input_contract():
    INPUT.validate(base())
    assert not INPUT.is_valid(SCENARIOS["MISSING_RECORD"]())


def test_base_recommendation():
    result = run_optimization(base(), CONFIG)
    best = result["recommendations"][0]
    assert best["summary"] == "Run Rev B out through W7; Reduce PO-001 by 50"
    assert (best["shortage_units"], best["excess_value"], best["action_cost"]) == (0, 0, 1250)
    assert [r["rank"] for r in result["recommendations"]] == [1, 2, 3]
    assert [row["effective_week"] for row in result["effective_week_comparison"]] == [5, 6, 7]


def test_invalid_data_yields_no_plan_and_keeps_errors():
    result = run_optimization(SCENARIOS["MISSING_RECORD"](), CONFIG)
    assert result["decision"] == "INVALID_DATA" and result["recommended_plan_id"] is None
    assert result["recommendations"] == result["ranked_plans"] == []
    assert "PO-003" in result["escalations"][0]["evidence"][0]["description"]


def test_no_feasible_plan_keeps_rejections():
    result = run_optimization(SCENARIOS["REV_C_SUPPLIER_BLOCKED"](), CONFIG)
    assert result["decision"] == "NO_FEASIBLE_PLAN" and result["recommendations"] == []
    assert all(p["rejection_reasons"] for p in result["rejected_plans"])


def test_no_purchase_orders_at_all():
    data = base()
    data["purchase_orders"] = []
    result = run_optimization(data, CONFIG)
    assert {e["code"] for e in result["escalations"]} == {"RESIDUAL_SHORTAGE"}


def test_low_robustness_escalation_end_to_end():
    """Two near-tie plans where the cheaper one is fragile: PO-001 can only be cut by 200, for a fee
    just below the value of the leftover stock it avoids."""
    data = base()
    data["materials"][0]["unit_cost"] = 10
    find_po(data, "PO-001").update(reduction_lot=200, reduction_fee_per_unit=1)
    result = run_optimization(data, CONFIG)
    assert {"NEAR_TIE", "LOW_ROBUSTNESS"} <= {e["code"] for e in result["escalations"]}


def test_replay_reproduces_and_detects_changes():
    data = base()
    result = run_optimization(data, CONFIG)
    assert replay_matches(result, data, CONFIG)
    data["inventory"][0]["on_hand"] += 1
    assert not replay_matches(result, data, CONFIG)


def test_planner_modified_plan_uses_the_same_rules():
    good = evaluate_custom_plan([REDUCE_200, EXPEDITE], base(), CONFIG)
    assert good["feasibility"] == "FEASIBLE" and good["secondary_cost"] == 37000
    assert evaluate_custom_plan([CANCEL, REDUCE_200], base(), CONFIG)["feasibility"] == "REJECTED"
    assert evaluate_custom_plan([{"action": "DELETE_EVERYTHING"}], base(), CONFIG)["feasibility"] == "REJECTED"


def test_simulator_is_replaceable():
    calls = []

    def member1_simulator(**kwargs):
        calls.append(1)
        return simulate_inventory(**kwargs)
    result = run_optimization(base(), config(), member1_simulator)
    assert result["simulator"].endswith("member1_simulator")
    assert len(calls) == result["counts"]["feasible"] + 3 * 9  # candidates + top three x nine shocks


def test_sqlite_round_trip(tmp_path):
    data, path = base(), tmp_path / "plan.db"
    with closing(sqlite3.connect(path)) as db:
        tables = {t: data[t] for t in LIST_TABLES}
        tables["engineering_change"] = [data["engineering_change"]]
        tables["scenario"] = [{k: data[k] for k in ("scenario_id", "planning_week", "horizon_weeks")}]
        for table, rows in tables.items():
            columns = list(rows[0])
            db.execute(f"CREATE TABLE {table} ({', '.join(columns)})")
            db.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(columns))})",
                           [tuple(r[c] for c in columns) for r in rows])
        db.commit()
    assert load_sqlite(path) == data
