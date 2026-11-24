import pytest

from member3.application.access_control import NotAllowed, User
from member3.services import action_tracker_service as tracker
from member3.services import audit_service, planning_service
from member3.services.approval_service import decide
from .conftest import PLANNER

BUYER = User("Ravi", "Purchasing")


@pytest.fixture
def approved(planned, member1, member2):
    run = planned()
    decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "ok", plan_id=run["result"]["recommended_plan_id"])
    return run


def test_actions_get_owners(approved):
    items = tracker.list_items(approved["run_id"])
    assert {(i["summary"], i["owner_role"], i["status"]) for i in items} == {
        ("Run Rev B out through W7", "Quality", "OPEN"), ("Reduce PO-001 by 50", "Purchasing", "OPEN")}


def test_rejection_creates_no_actions(planned, member1, member2):
    run = planned()
    decide(run["run_id"], "REJECTED", PLANNER, member1, member2, "no")
    assert tracker.list_items(run["run_id"]) == []


def test_only_the_owner_or_planner_moves_an_action(approved):
    items = {i["owner_role"]: i["action_id"] for i in tracker.list_items(approved["run_id"])}
    assert tracker.advance(items["Purchasing"], BUYER) == "IN_PROGRESS"
    with pytest.raises(NotAllowed):
        tracker.advance(items["Quality"], BUYER)
    assert tracker.advance(items["Quality"], PLANNER) == "IN_PROGRESS"


def test_status_runs_forward_and_stops(approved):
    action = tracker.list_items(approved["run_id"])[0]["action_id"]
    assert [tracker.advance(action, PLANNER), tracker.advance(action, PLANNER)] == ["IN_PROGRESS", "DONE"]
    with pytest.raises(tracker.InvalidTransition):
        tracker.advance(action, PLANNER)
    assert [e["payload"]["to"] for e in audit_service.history(event_type="ACTION_STATUS")] == ["DONE", "IN_PROGRESS"]


def test_lifecycle_to_closed(approved):
    assert planning_service.change_stage("BASE") == 3
    with pytest.raises(tracker.InvalidTransition):
        tracker.close_change(approved["run_id"], PLANNER)
    for item in tracker.list_items(approved["run_id"]):
        tracker.advance(item["action_id"], PLANNER)
        tracker.advance(item["action_id"], PLANNER)
    assert planning_service.change_stage("BASE") == 4
    with pytest.raises(NotAllowed):
        tracker.close_change(approved["run_id"], BUYER)
    tracker.close_change(approved["run_id"], PLANNER)
    assert planning_service.change_stage("BASE") == 5
    with pytest.raises(tracker.InvalidTransition):
        tracker.close_change(approved["run_id"], PLANNER)


def test_unknown_action():
    with pytest.raises(LookupError):
        tracker.advance("ACT-NONE", PLANNER)


def test_every_engine_action_has_an_owner():
    from member2.engine.constraints import KNOWN_ACTIONS
    from member3.settings import load_settings
    assert KNOWN_ACTIONS - {"CREATE_REV_B_PO"} <= set(load_settings()["owners"])
