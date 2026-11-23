from itertools import permutations

import pytest

from member2.engine.optimizer import (
    calculate_secondary_cost, compare_plans, mark_redundant, rank_feasible_plans, select_top_plans,
)
from .helpers import CANCEL, EXPEDITE, plan

P1, P2, P3 = plan("P1", 0, 37000), plan("P2", 0, 100000), plan("P3", 100, 5000)


@pytest.mark.parametrize("order", list(permutations([P1, P2, P3])))
def test_mandatory_worked_example(order):
    assert [p["plan_id"] for p in rank_feasible_plans(order)] == ["P1", "P2", "P3"]


def test_shortage_always_beats_cost():
    assert compare_plans(plan("A", 0, 10**9), plan("B", 1, 0)) == -1


def test_identical_objectives_are_broken_deterministically():
    fewer, more = plan("Z", 0, 10, [CANCEL]), plan("A", 0, 10, [CANCEL, EXPEDITE])
    assert [p["plan_id"] for p in rank_feasible_plans([more, fewer])] == ["Z", "A"]
    assert [p["plan_id"] for p in rank_feasible_plans([plan("B", 0, 1), plan("A", 0, 1)])] == ["A", "B"]
    assert compare_plans(P1, P1) == 0


def test_rejected_plans_are_not_ranked():
    rejected = {"plan_id": "P4", "feasibility": "REJECTED", "actions": []}
    assert [p["plan_id"] for p in rank_feasible_plans([rejected, P1])] == ["P1"]


def test_ranks_and_objectives_are_returned():
    ranked = rank_feasible_plans([P3, P2, P1])
    assert [(p["rank"], p["shortage_units"], p["secondary_cost"]) for p in ranked] == [
        (1, 0, 37000), (2, 0, 100000), (3, 100, 5000)]
    assert "rank" not in P1  # inputs untouched


def test_secondary_cost():
    assert calculate_secondary_cost(20000, 17000) == 37000


def test_redundant_lookalikes_stay_ranked_but_not_recommended():
    simple, padded = plan("A", 0, 10, [CANCEL]), plan("B", 0, 10, [CANCEL, EXPEDITE])
    dearer = plan("C", 0, 20, [CANCEL, EXPEDITE])
    ranked = mark_redundant(rank_feasible_plans([dearer, padded, simple]))
    assert [(p["plan_id"], p["redundant_of"]) for p in ranked] == [("A", None), ("B", "A"), ("C", None)]
    assert [p["plan_id"] for p in select_top_plans(ranked)] == ["A", "C"]


def test_select_limit():
    assert len(select_top_plans([P1, P2, P3], 2)) == 2
