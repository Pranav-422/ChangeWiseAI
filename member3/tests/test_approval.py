import pytest

from member3.application.access_control import NotAllowed, User
from member3.services import approval_service, audit_service, ecn_service, planning_service
from member3.services.approval_service import DecisionRefused, decide
from member3.services.ecn_service import NotReady
from .conftest import PLANNER


def top(run, position=0):
    return run["result"]["recommendations"][position]["plan_id"]


def test_planning_needs_a_confirmed_ecn(member1, member2, ecn_text):
    review = ecn_service.create_review(ecn_text, "BASE", member1, PLANNER)
    with pytest.raises(NotReady):
        planning_service.run_planning(review, member1, member2, PLANNER)


def test_incomplete_ecn_cannot_be_confirmed(member1, ecn_text):
    review = ecn_service.create_review(ecn_text.replace("Effective Week: W6", ""), "BASE", member1, PLANNER)
    with pytest.raises(NotReady):
        ecn_service.confirm(review, member1, PLANNER)
    with pytest.raises(NotReady):
        ecn_service.confirm(ecn_service.create_manual_review("BASE", member1, PLANNER), member1, PLANNER)


def test_correction_keeps_the_original_extraction(member1, ecn_text):
    review = ecn_service.create_review(ecn_text.replace("W6", "TBD"), "BASE", member1, PLANNER)
    assert ecn_service.update_fields(review, {"effective_week": 6}, member1, PLANNER)["validation_status"] == "VALID"
    stored = ecn_service.get_review(review)
    assert stored["fields"]["effective_week"] == 6 and stored["extraction"]["effective_week"] is None
    ecn_service.confirm(review, member1, PLANNER)
    for call in (lambda: ecn_service.update_fields(review, {"reason": "x"}, member1, PLANNER),
                 lambda: ecn_service.confirm(review, member1, PLANNER)):
        with pytest.raises(NotReady):
            call()
    with pytest.raises(ValueError):
        ecn_service.update_fields(review, {"unit_cost": 1}, member1, PLANNER)


def test_member1_conflict_blocks_confirmation(member1, ecn_text):
    review = ecn_service.create_review(ecn_text, "DATE_CONFLICT", member1, PLANNER)
    with pytest.raises(NotReady):
        ecn_service.confirm(review, member1, PLANNER)


def test_approve_recommended(planned, member1, member2):
    run = planned("REV_C_DELAY")  # not escalated: no comment needed
    decide(run["run_id"], "APPROVED", PLANNER, member1, member2, plan_id=top(run))
    saved = approval_service.get_decision(run["run_id"])
    assert saved["decision"] == "APPROVED" and saved["plan"]["plan_id"] == top(run) and not saved["modified"]


def test_comment_rules(planned, member1, member2):
    escalated, clear = planned("BASE"), planned("REV_C_DELAY")
    for run, plan in ((escalated, top(escalated)), (clear, top(clear, 1))):
        with pytest.raises(DecisionRefused, match="comment"):
            decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "  ", plan_id=plan)
    with pytest.raises(DecisionRefused, match="comment"):
        decide(clear["run_id"], "REJECTED", PLANNER, member1, member2)
    decide(escalated["run_id"], "APPROVED", PLANNER, member1, member2, "chosen for robustness", plan_id=top(escalated))


def test_only_the_planner_decides(planned, member1, member2):
    run = planned()
    for user in (User("P", "Purchasing"), User("V", "Viewer"), User(" ", "Planner")):
        with pytest.raises(NotAllowed):
            decide(run["run_id"], "APPROVED", user, member1, member2, "x", plan_id=top(run))
    assert approval_service.get_decision(run["run_id"]) is None


def test_one_final_decision(planned, member1, member2):
    run = planned()
    decide(run["run_id"], "REJECTED", PLANNER, member1, member2, "no")
    with pytest.raises(DecisionRefused, match="already"):
        decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "x", plan_id=top(run))
    assert len(audit_service.history(event_type="PLAN_APPROVED")) == 0


def test_unknown_and_rejected_plans_cannot_be_approved(planned, member1, member2):
    run = planned()
    for plan in ("PLAN-0000000000", run["result"]["rejected_plans"][0]["plan_id"], None):
        with pytest.raises(DecisionRefused):
            decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "x", plan_id=plan)
    with pytest.raises(DecisionRefused):
        decide(run["run_id"], "EXECUTED", PLANNER, member1, member2, "x")


def test_modified_plan_is_checked_by_member2(planned, member1, member2):
    run = planned()
    bad = [{"action": "REDUCE_REV_B_PO", "po_id": "PO-001", "quantity": 250}]
    assert approval_service.evaluate_modification(run["run_id"], bad, member2, PLANNER)["feasibility"] == "REJECTED"
    with pytest.raises(DecisionRefused, match="hard rule"):
        decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "x", modified_actions=bad)
    good = [{"action": "EXPEDITE_REV_C_PO", "po_id": "PO-003", "weeks": 1}]
    with pytest.raises(DecisionRefused, match="modified plan needs a comment"):
        decide(run["run_id"], "APPROVED", PLANNER, member1, member2, modified_actions=good)
    decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "safer", modified_actions=good)
    assert approval_service.get_decision(run["run_id"])["modified"] == 1
    assert audit_service.history(event_type="PLAN_MODIFIED")


def test_no_plan_to_approve(planned, member1, member2):
    for scenario in ("REV_C_SUPPLIER_BLOCKED", "MISSING_RECORD"):
        run = planned(scenario)
        for choice in ({"plan_id": None}, {"modified_actions": []}):
            with pytest.raises(DecisionRefused):
                decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "x", **choice)


def test_superseded_and_stale_runs_cannot_be_approved(planned, member1, member2, monkeypatch):
    old, new = planned(), planned()
    with pytest.raises(DecisionRefused, match="newer"):
        decide(old["run_id"], "APPROVED", PLANNER, member1, member2, "x", plan_id=top(old))
    changed = member1.load_dataset("BASE")
    changed["inventory"][0]["on_hand"] += 1
    monkeypatch.setattr(member1, "load_dataset", lambda s: changed)
    with pytest.raises(DecisionRefused, match="changed"):
        decide(new["run_id"], "APPROVED", PLANNER, member1, member2, "x", plan_id=top(new))


def test_pending_runs(planned, member1, member2):
    run = planned()
    planned("REV_C_SUPPLIER_BLOCKED")
    assert [r["run_id"] for r in approval_service.pending_runs()] == [run["run_id"]]
    decide(run["run_id"], "REJECTED", PLANNER, member1, member2, "no")
    assert approval_service.pending_runs() == []
