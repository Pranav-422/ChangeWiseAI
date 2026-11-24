from engine.scenarios import SCENARIOS, load_scenario
from engine.inventory import simulate_from_data
from engine.severity import calculate_severity_score, classify_severity, rank_exceptions


def test_bands():
    assert [classify_severity(s) for s in (90, 75, 60, 50, 30, 25, 10)] == \
        ["CRITICAL", "CRITICAL", "HIGH", "HIGH", "MEDIUM", "MEDIUM", "LOW"]


def test_score_formula():
    # 100 x (0.5 x 1.0 + 0.3 x min(1, 300000/100000) + 0.2 x (8-6+1)/8) = 87.5
    e = {"exception_type": "PRODUCTION_SHORTAGE", "financial_impact": 300000, "week": 6}
    assert calculate_severity_score(e, 8) == 87.5


def test_sooner_is_more_urgent():
    early = {"exception_type": "PRODUCTION_SHORTAGE", "financial_impact": 1000, "week": 2}
    late = {**early, "week": 8}
    assert calculate_severity_score(early, 8) > calculate_severity_score(late, 8)


def test_shortage_outranks_scrap(data):
    r = simulate_from_data(load_scenario("rev_c_supplier_delay", data))
    types = [e["exception_type"] for e in r["exceptions"]]
    assert types[0] == "PRODUCTION_SHORTAGE" and r["exceptions"][0]["severity_level"] == "CRITICAL"
    assert types.index("REV_B_SCRAP_RISK") > types.index("PRODUCTION_SHORTAGE")
    assert [e["severity_rank"] for e in r["exceptions"]] == list(range(1, len(types) + 1))


def test_ranking_is_deterministic_on_ties():
    rows = [{"exception_id": i, "severity_score": 50.0, "week": 3} for i in ("B", "A", "C")]
    assert [e["exception_id"] for e in rank_exceptions(rows)] == ["A", "B", "C"]


def test_exception_ids_unique_and_contract_fields(data):
    for name in SCENARIOS:
        ex = simulate_from_data(load_scenario(name, data))["exceptions"]
        assert len({e["exception_id"] for e in ex}) == len(ex)
        for e in ex:
            assert {"exception_id", "exception_type", "severity_score", "severity_level", "severity_rank",
                    "owner_role", "recommended_action", "description", "status"} <= set(e)
            assert 0 <= e["severity_score"] <= 100


def test_base_scenario_only_flags_scrap(data):
    ex = simulate_from_data(data)["exceptions"]
    assert [e["exception_type"] for e in ex] == ["REV_B_SCRAP_RISK"]
    assert ex[0]["financial_impact"] == 92000 and ex[0]["severity_level"] == "HIGH"


def test_blocking_data_issue_outranks_scrap(data):
    ex = simulate_from_data(load_scenario("missing_records", data))["exceptions"]
    assert ex[0]["exception_type"] == "DATA_INSUFFICIENT" and ex[0]["severity_level"] == "CRITICAL"
