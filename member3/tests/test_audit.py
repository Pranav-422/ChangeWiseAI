import sqlite3
from contextlib import closing

import pytest

from member3.database.connection import transaction
from member3.services import audit_service, planning_service
from member3.services.approval_service import decide
from .conftest import PLANNER


def run_sql(path, *statements):
    with closing(sqlite3.connect(path)) as db:
        for statement in statements:
            db.execute(statement)
        db.commit()


def test_full_story_is_logged_in_order(planned, member1, member2):
    run = planned()
    decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "ok", plan_id=run["result"]["recommended_plan_id"])
    events = [e["event_type"] for e in reversed(audit_service.history())]
    assert events == ["ECN_RECEIVED", "ECN_CONFIRMED", "PLAN_GENERATED", "PLAN_APPROVED", "ACTION_CREATED", "ACTION_CREATED"]
    payload = audit_service.history(event_type="PLAN_GENERATED")[0]["payload"]
    assert payload["input_hash"] == run["input_hash"] and payload["engine_version"] and payload["recommended_plan_id"]
    assert audit_service.verify_chain() is None


@pytest.mark.parametrize("statement", ["UPDATE audit_log SET user_name = 'x'", "DELETE FROM audit_log"])
def test_log_is_append_only(planned, database, statement):
    planned()
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        run_sql(database, statement)


@pytest.mark.parametrize("tamper,broken", [
    ("UPDATE audit_log SET user_name = 'Mallory' WHERE seq = 2", 2), ("DELETE FROM audit_log WHERE seq = 2", 3),
    ("UPDATE audit_log SET payload = '{}' WHERE seq = 3", 3)])
def test_tampering_past_the_triggers_is_detected(planned, database, tamper, broken):
    planned()
    run_sql(database, "DROP TRIGGER audit_no_update", "DROP TRIGGER audit_no_delete", tamper)
    assert audit_service.verify_chain() == broken


def test_state_and_event_commit_together(database):
    with pytest.raises(RuntimeError):
        with transaction() as db:
            audit_service.append(db, "TEST", "X", PLANNER)
            raise RuntimeError("stop")
    assert audit_service.history() == []


@pytest.mark.parametrize("scenario", ["BASE", "REV_C_DELAY", "REV_C_SUPPLIER_BLOCKED", "MISSING_RECORD"])
def test_replay_reproduces(planned, member2, scenario):
    run = planned(scenario)
    assert audit_service.replay(run["run_id"], member2, PLANNER) == {
        "run_id": run["run_id"], "matches": True, "snapshot_intact": True}
    assert audit_service.history(event_type="RUN_REPLAYED")[0]["payload"]["matches"]


def test_replay_detects_changed_snapshot_and_changed_engine(planned, member1, member2, database):
    run = planned()

    def other_simulator(**kwargs):
        result = member1.simulate(**kwargs)
        return {**result, "total_shortage": result["total_shortage"] + 1}
    from member3.services.member2_adapter import Member2Adapter
    changed = audit_service.replay(run["run_id"], Member2Adapter(other_simulator), PLANNER)
    assert changed["snapshot_intact"] and not changed["matches"]
    run_sql(database, "UPDATE planning_runs SET dataset = replace(dataset, '\"on_hand\": 320', '\"on_hand\": 321')")
    assert audit_service.replay(run["run_id"], member2, PLANNER)["snapshot_intact"] is False


def test_failed_ai_text_is_preserved(planned):
    from member3.ai.fallback_templates import SECTIONS
    from .conftest import FakeProvider
    run = planned(provider=FakeProvider({"sections": {next(iter(SECTIONS)): "The fine is ₹5,00,000."}}))
    stored = planning_service.get_run(run["run_id"])["explanation"]
    assert stored["label"] == "TEMPLATE_GENERATED" and "fine" in stored["rejected_draft"]["Engineering change"]
    event = audit_service.history(event_type="PLAN_GENERATED")[0]["payload"]
    assert event["verification"]["status"] == "REJECTED" and event["verification"]["failures"]
