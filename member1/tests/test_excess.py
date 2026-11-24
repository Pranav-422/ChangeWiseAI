import pytest

from engine.excess import calculate_rev_b_scrap_value, calculate_rev_c_excess_value, calculate_total_excess


def test_spec_worked_example():
    e_b = calculate_rev_b_scrap_value(100, 400)
    e_c = calculate_rev_c_excess_value(500, 100, 450)
    assert (e_b, e_c, calculate_total_excess(e_b, e_c)) == (40000, 45000, 85000)


def test_rev_c_within_cover_is_not_excess():
    assert calculate_rev_c_excess_value(400, 100, 450) == 0
    assert calculate_rev_c_excess_value(300, 100, 450) == 0


@pytest.mark.parametrize("args", [(-1, 400), (10, -5)])
def test_negative_inputs_rejected(args):
    with pytest.raises(ValueError):
        calculate_rev_b_scrap_value(*args)


def test_same_d_across_plans(run):
    # Member 2 can pin D so every candidate plan uses the same demand assumption.
    a = run(average_weekly_demand=100)["excess"]
    b = run({"effective_week": 5}, average_weekly_demand=100)["excess"]
    assert a["average_weekly_demand"] == b["average_weekly_demand"] == 100
