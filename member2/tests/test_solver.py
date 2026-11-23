import random

import pytest

from member2.engine.action_generator import build_menus, make_plan
from member2.engine.optimizer import objective
from member2.engine.pipeline import run_optimization
from member2.evaluation.solver_check import check_solver_agreement
from member2.reference.simulator import simulate_inventory
from member2.solver import BACKENDS, SolverUnavailable, first_available, load_backend
from .helpers import CONFIG, SCENARIOS, base, config, evaluate, find_po


def need(name):
    try:
        return load_backend(name)
    except SolverUnavailable as error:
        pytest.skip(str(error))


def agreement(data, backend):
    need(backend)
    row = next(r for r in check_solver_agreement(data, CONFIG, simulate_inventory) if r["backend"] == backend)
    assert row["agrees"], row


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("name", sorted(set(SCENARIOS) - {"DATE_CONFLICT", "MISSING_RECORD"}))
def test_solver_equals_enumeration(backend, name):
    agreement(SCENARIOS[name](), backend)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("seed", range(12))
def test_solver_equals_enumeration_on_random_data(backend, seed):
    """Uneven demand, unequal unit costs, and stock levels that force shortages and excess."""
    rng, data = random.Random(seed), base()
    for row in data["demand"]:
        row["quantity"] = rng.randint(40, 160)
    data["inventory"][0]["on_hand"] = rng.randint(20, 600)
    data["inventory"][1]["on_hand"] = rng.randint(0, 300)
    data["materials"][0]["unit_cost"] = rng.randint(100, 500)
    data["materials"][1]["unit_cost"] = rng.randint(100, 900)
    for po_id, week in (("PO-001", rng.randint(4, 6)), ("PO-003", rng.randint(6, 9)), ("PO-004", rng.randint(10, 11))):
        find_po(data, po_id).update(quantity=rng.randint(4, 14) * 50, arrival_week=week)
    agreement(data, backend)


@pytest.mark.parametrize("backend", BACKENDS)
def test_solver_lists_distinct_plans_in_order(backend):
    solver, data = need(backend), base()
    found = solver.solve(data, build_menus(data, CONFIG), limit=4)
    assert len({make_plan(a, data)["plan_id"] for a in found}) == 4
    scores = [objective(evaluate(a)) for a in found]
    assert scores == sorted(scores)


def test_pipeline_falls_back_to_the_solver_for_large_spaces():
    backend, _ = first_available("ortools")
    full = run_optimization(base(), CONFIG)
    small = run_optimization(base(), config(action_space={"max_candidates": 10}, solver={"max_solutions": 4}))
    assert small["method"] == f"SOLVER:{backend}"
    assert small["recommended_plan_id"] == full["recommended_plan_id"]


def test_unavailable_backend_is_reported_not_faked(monkeypatch):
    def refuse(name):
        raise SolverUnavailable(f"{name}: blocked")
    monkeypatch.setattr("member2.evaluation.solver_check.load_backend", refuse)
    rows = check_solver_agreement(base(), CONFIG, simulate_inventory)
    assert all(r["status"].startswith("UNAVAILABLE") and r["agrees"] is None for r in rows)
