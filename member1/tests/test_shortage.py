from conftest import week
from engine.shortage import calculate_shortage_summary


def test_spec_worked_example():
    weeks = [{"week": n, "shortage": s} for n, s in enumerate([0, 0, 10, 20], start=1)]
    s = calculate_shortage_summary(weeks, cost_per_unit=1000)
    assert (s["total_shortage_units"], s["first_shortage_week"], s["shortage_weeks"]) == (30, 3, 2)
    assert s["estimated_financial_impact"] == 30000 and s["shortage_week_list"] == [3, 4]


def test_no_shortage():
    s = calculate_shortage_summary([{"week": 1, "shortage": 0}])
    assert s["total_shortage_units"] == 0 and s["first_shortage_week"] is None and s["shortage_weeks"] == 0


def test_demand_usage_and_unmet_are_distinct_and_not_double_counted(run):
    # Effective W5 but Rev C arrives W6: in W5 Rev B (interchangeable) covers what Rev C cannot; demand x1.5 forces shortages
    r = run({"effective_week": 5}, demand_multiplier=1.5)
    for w in r["weeks"]:
        assert w["demand"] == w["rev_b_usage"] + w["rev_c_usage"] + w["shortage"]
        assert w["shortage"] == w["rev_b_unmet"] + w["rev_c_unmet"]
    assert r["total_shortage_units"] == sum(w["shortage"] for w in r["weeks"])


def test_affected_material_follows_applicable_revision(run):
    r = run(lead_time_shift=1)
    assert week(r, 6)["shortage"] == 150 and r["shortage"]["affected_materials"] == ["MAT-102"]
