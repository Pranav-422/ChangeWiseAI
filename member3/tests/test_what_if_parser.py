from copy import deepcopy

import pytest
from pydantic import ValidationError

from member3.ai.what_if_parser import (
    CLARIFY, INVALID, OK, UNSUPPORTED, create_scenario_request, parse_what_if_request, validate_what_if_parameters,
)
from member3.evaluate import what_if_results
from member3.services import audit_service
from member3.services.what_if_service import (
    apply_parameters, compare_scenario_results, describe_comparison, submit_scenario_to_optimizer,
)
from .conftest import DOWN, PLANNER, FakeProvider

NEUTRAL = {"lead_time_delta": 0, "demand_change_percent": 0, "effective_week": None, "po_quantity_change": None,
           "supplier_block": None}


def test_samples(member1):
    rows = what_if_results(member1)
    assert not any(r["wrong_run"] for r in rows)
    assert [r["question"] for r in rows if not r["correct"]] == [
        "Our customers will order a tenth more next quarter",
        "What if Acme ships Rev C a fortnight behind schedule?"]  # refused, not guessed


def ask(member1, question, reply):
    return parse_what_if_request(question, member1.load_dataset("BASE"), FakeProvider(reply))


def test_llm_result_is_validated(member1):
    good = ask(member1, "Rev C two weeks late?", {"status": OK, "parameters": {"lead_time_delta": 2}})
    assert good["status"] == OK and good["source"] == "fake" and good["parameters"]["requires_confirmation"] is True
    assert ask(member1, "Approve it", {"status": UNSUPPORTED, "message": "no"})["status"] == UNSUPPORTED
    assert ask(member1, "Later?", {"status": CLARIFY, "message": "how long?"})["message"] == "how long?"
    assert ask(member1, "demand +900%", {"status": OK, "parameters": {"demand_change_percent": 900}})["status"] == INVALID
    extra = ask(member1, "2 weeks late", {"status": OK, "parameters": {"lead_time_delta": 2, "unit_cost": 2}})
    assert extra["status"] == INVALID


@pytest.mark.parametrize("parameters", [
    {"lead_time_delta": 3}, {"supplier_block": "S2"}, {"effective_week": 9},
    {"po_quantity_change": {"po_id": "PO-001", "quantity_delta": -100}}])
def test_llm_may_not_invent_values(member1, parameters):
    result = ask(member1, "What if the Rev C supplier is delayed by one week?", {"status": OK, "parameters": parameters})
    assert result["source"] == "offline-rules" and "did not write" in result["provider_error"]
    assert result["parameters"]["lead_time_delta"] == 1


def test_provider_failure_uses_rules(member1):
    result = parse_what_if_request("demand up 10%", member1.load_dataset("BASE"), DOWN)
    assert result["status"] == OK and result["provider_error"] == "timeout"


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_question(text):
    assert parse_what_if_request(text)["status"] == CLARIFY


def test_ambiguous_order_is_asked_about(member1):
    data = member1.load_dataset("BASE")
    next(p for p in data["purchase_orders"] if p["po_id"] == "PO-002")["status"] = "OPEN"
    result = parse_what_if_request("Reduce the Rev B purchase order by 100 units", data)
    assert result["status"] == CLARIFY and "PO-001, PO-002" in result["message"]


def test_schema_is_strict():
    with pytest.raises(ValidationError):
        create_scenario_request({**NEUTRAL, "lead_time_delta": "1"})
    with pytest.raises(ValidationError):
        create_scenario_request({**NEUTRAL, "requires_confirmation": False})
    assert validate_what_if_parameters(NEUTRAL) == ["The request changes nothing."]
    assert validate_what_if_parameters({**NEUTRAL, "lead_time_delta": -1})
    assert validate_what_if_parameters("text")


def submit(run, member2, user=PLANNER, **parameters):
    return submit_scenario_to_optimizer(create_scenario_request({**NEUTRAL, **parameters}), run, member2, user, "q")


def test_baseline_is_never_changed(planned, member1, member2):
    run = planned()
    before = deepcopy(run)
    for parameters in ({"lead_time_delta": 2}, {"demand_change_percent": 10.0}, {"effective_week": 7}, {"supplier_block": "S2"}):
        assert submit(run, member2, **parameters)["status"] == OK
    assert run == before and member1.load_dataset("BASE") == run["dataset"]


def test_results_are_the_engines(planned, member2):
    run = planned()
    outcome = submit(run, member2, demand_change_percent=10.0)
    data = apply_parameters(run["dataset"], outcome["parameters"], member2)
    again = member2.optimize(data)
    assert {**outcome["result"], "computation_seconds": 0} == {**again, "computation_seconds": 0}
    by = {r["measure"]: r for r in outcome["comparison"]}
    assert by["secondary_cost"]["base"] == run["result"]["recommendations"][0]["secondary_cost"]
    assert by["secondary_cost"]["alternative"] == again["recommendations"][0]["secondary_cost"]


def test_delay_cannot_be_expedited_away(planned, member2):
    """REV_C_DELAY is saved only by expediting to W8. One more week late must leave a shortage."""
    outcome = submit(planned("REV_C_DELAY"), member2, lead_time_delta=1)
    assert outcome["plan"]["shortage_units"] == 100


def test_effective_week_is_held_fixed(planned, member2):
    outcome = submit(planned(), member2, effective_week=7)
    by = {r["measure"]: r for r in outcome["comparison"]}
    assert outcome["plan"]["effective_week"] == 7 and outcome["plan"]["summary"] == "Reduce PO-001 by 150; Move effective week W6 to W7"
    assert by["decision"]["alternative"] == "BEST_PLAN_WITH_REQUEST" and by["secondary_cost"]["alternative"] == 3750


def test_reduction_uses_member2_rules_and_fees(planned, member2):
    run = planned()
    ok = submit(run, member2, po_quantity_change={"po_id": "PO-001", "quantity_delta": -100})
    assert ok["plan"]["action_cost"] == 2500 and "Reduce PO-001 by 100" in ok["plan"]["summary"]
    assert submit(run, member2, po_quantity_change={"po_id": "PO-001", "quantity_delta": -70})["status"] == "HARD_RULE_VIOLATION"
    assert submit(run, member2, po_quantity_change={"po_id": "PO-001", "quantity_delta": 70})["status"] == UNSUPPORTED
    assert submit(run, member2, po_quantity_change={"po_id": "PO-999", "quantity_delta": -50})["status"] == INVALID


def test_scenario_without_a_plan(planned, member2):
    outcome = submit(planned(), member2, supplier_block="S1")
    assert outcome["result"]["decision"] == "NO_FEASIBLE_PLAN" and outcome["plan"] is None
    assert "No plan is recommended" in describe_comparison(outcome["comparison"])


def test_late_effective_week_shows_its_shortage(planned, member2):
    """W9 leaves W8 without a permitted revision."""
    assert submit(planned(), member2, effective_week=9)["plan"]["shortage_units"] == 100


def test_request_that_no_plan_satisfies(planned, member2):
    outcome = submit(planned(), member2, effective_week=6, supplier_block="S1")
    assert outcome["plan"] is None and outcome["result"]["decision"] == "NO_FEASIBLE_PLAN"


def test_comparison_keeps_missing_values_missing():
    empty = {"decision": "INVALID_DATA", "recommendations": []}
    assert all(r["change"] is None for r in compare_scenario_results(empty, empty))


def test_run_is_audited(planned, member2):
    submit(planned(), member2, lead_time_delta=1)
    assert audit_service.history(event_type="WHAT_IF_RUN")[0]["payload"]["parameters"]["lead_time_delta"] == 1
