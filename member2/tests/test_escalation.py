import pytest

from member2.engine.escalation import (
    calculate_cost_difference, create_escalation_record, detect_near_ties, is_near_tie,
)
from .helpers import CONFIG, config, plan


def tie(a, b, cfg=CONFIG, shortage=(0, 0)):
    return is_near_tie(plan("A", shortage[0], a), plan("B", shortage[1], b), cfg)


def test_official_example():
    assert tie(37000, 38000)


@pytest.mark.parametrize("a,b,expected", [
    (37000, 41999, True),        # 4,999 apart
    (37000, 42000, False),       # exactly 5,000 and above 5%
    (200000, 209999, True),      # 9,999 apart but below 5%
    (200000, 210000, False),     # exactly 5% of the lower value
    (0, 4999, True),             # no percentage possible, absolute test only
    (0, 5000, False),
])
def test_boundaries_are_strict(a, b, expected):
    assert tie(a, b) is expected
    assert tie(b, a) is expected


def test_only_zero_shortage_plans():
    assert not tie(100, 100, shortage=(0, 1))
    assert not tie(100, 100, shortage=(1, 1))


def test_settings_are_configurable():
    assert not tie(37000, 38000, config(near_tie={"percent": 0.001, "absolute": 500}))
    # 10,200 is 5.1% of 200,000 but 4.85% of 210,200
    assert not tie(200000, 210200)
    assert tie(200000, 210200, config(near_tie={"denominator": "higher"}))


def test_difference_evidence():
    assert calculate_cost_difference(plan("A", 0, 200), plan("B", 0, 250)) == {"absolute": 50, "percent": 0.25}


def test_detects_every_rival_of_the_leader_and_keeps_evidence():
    ranked = [plan("A", 0, 37000), plan("B", 0, 38000), plan("C", 0, 40000), plan("D", 0, 90000)]
    ties = detect_near_ties(ranked, CONFIG)
    assert [(t["plan_a"], t["plan_b"], t["absolute"]) for t in ties] == [("A", "B", 1000), ("A", "C", 3000)]
    record = create_escalation_record(ranked[:3], ties)
    assert record["code"] == "NEAR_TIE" and record["plan_ids"] == ["A", "B", "C"]
    assert record["evidence"] == ties and record["status"] == "PLANNER_REVIEW_REQUIRED"


def test_no_ties_when_the_leader_has_a_shortage():
    assert detect_near_ties([plan("A", 5, 1), plan("B", 5, 1)], CONFIG) == []


def test_redundant_lookalikes_are_not_rivals():
    padded = {**plan("B", 0, 37000), "redundant_of": "A"}
    assert detect_near_ties([plan("A", 0, 37000), padded], CONFIG) == []
