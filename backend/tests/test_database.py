"""Migrations, RLS, data migration and numerical parity on real PostgreSQL."""
import json
import uuid

import psycopg
import pytest
from psycopg import conninfo

from backend.app.core import database
from backend.app.integrations import member1_postgres
from member3.services import audit_service
from member3.services.member1_adapter import Member1Adapter
from member3.services.member2_adapter import Member2Adapter
from scripts.dev import local_postgres
from scripts.migration import apply_migrations, capture_baseline, common, import_postgres, verify_migration

from .conftest import ROLES, add_user, source_rows

READERS = {"ADMIN", "ENGINEERING", "PRODUCTION_PLANNER", "QUALITY"}


def as_user(url, user_id, sql, role="authenticated"):
    """Runs one statement the way PostgREST would for this user's token."""
    with psycopg.connect(url) as conn:
        conn.execute("SELECT set_config('request.jwt.claims', %s, true)", [json.dumps({"sub": user_id, "role": role})])
        conn.execute(f"SET LOCAL ROLE {role}")
        cursor = conn.execute(sql)
        return cursor.fetchall() if cursor.description else cursor.rowcount


@pytest.fixture
def people(url, db):
    return {role: add_user(db, role, role) for role in ROLES}


def test_every_table_has_rls(db):
    open_tables = db.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('core', 'app') "
                             "AND NOT rowsecurity").fetchall()
    assert open_tables == []


def test_anonymous_reads_nothing(url, db):
    tables = db.execute("SELECT schemaname || '.' || tablename FROM pg_tables WHERE schemaname IN ('core', 'app')").fetchall()
    assert len(tables) > 20
    for (table,) in tables:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_user(url, None, f"SELECT * FROM {table}", "anon")


def test_active_users_read_planning_data_and_others_do_not(url, db, people):
    for user_id in people.values():
        assert len(as_user(url, user_id, "SELECT * FROM core.materials")) == 9
    assert as_user(url, add_user(db, "ADMIN", "Gone", active=False), "SELECT * FROM core.materials") == []
    assert as_user(url, "00000000-0000-0000-0000-000000000009", "SELECT * FROM core.materials") == []


def test_documents_and_audit_follow_the_role(url, db, people, planned):
    planned()
    for role, user_id in people.items():
        for table in ("app.ecn_reviews", "app.document_metadata", "app.audit_log"):
            assert bool(as_user(url, user_id, f"SELECT * FROM {table}")) == (role in READERS), (role, table)


def test_profiles_are_private(url, people):
    for role, user_id in people.items():
        rows = as_user(url, user_id, "SELECT user_id::text FROM app.user_profiles")
        assert (len(rows) == len(people)) if role == "ADMIN" else rows == [(user_id,)]


@pytest.mark.parametrize("sql", [
    "UPDATE app.user_profiles SET role = 'ADMIN'",
    "INSERT INTO app.approvals (approval_id, run_id, decision, comment, user_name, role, created_at) "
    "VALUES ('x', 'x', 'APPROVED', '', '', '', now())",
    "UPDATE core.purchase_orders SET quantity = 0", "DELETE FROM app.audit_log",
    "INSERT INTO app.audit_log (created_at, event_type, entity_id, user_name, role, payload, previous_hash, event_hash) "
    "VALUES ('', '', '', '', '', '{}', '', '')",
    "SELECT app.acting_user()"])
def test_user_tokens_cannot_write(url, people, sql):
    for user_id in people.values():
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_user(url, user_id, sql)


def test_storage_bucket_is_private_and_role_bound(url, db, people):
    assert db.execute("SELECT public, file_size_limit FROM storage.buckets WHERE id = 'ecn-documents'").fetchone() == (False, 10485760)
    db.execute("INSERT INTO storage.objects (bucket_id, name) VALUES ('ecn-documents', 'ECN-001/a.pdf')")
    for role, user_id in people.items():
        assert bool(as_user(url, user_id, "SELECT * FROM storage.objects")) == (role in READERS)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_user(url, user_id, "INSERT INTO storage.objects (bucket_id, name) VALUES ('ecn-documents', 'b')")
    assert as_user(url, None, "SELECT * FROM storage.objects", "anon") == []


def test_constraints_survive_the_conversion(db):
    for sql in ("UPDATE core.materials SET revision = 'B'", "UPDATE core.inventory SET reserved = on_hand + 1",
                "UPDATE core.suppliers SET supplier_status = 'OK'", "UPDATE core.purchase_orders SET quantity = -1",
                "INSERT INTO core.demand VALUES ('D-X', 'NOPE', 'MAT-101', 'P', 1, 1)",
                "UPDATE core.engineering_changes SET new_material_id = part_number"):
        with pytest.raises(psycopg.IntegrityError):
            db.execute(sql)


def test_migrations_apply_once_and_are_recorded():
    server = local_postgres.server_url()
    name = f"cw_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(server, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = conninfo.make_conninfo(server, dbname=name)
    with psycopg.connect(url) as conn:
        conn.execute((local_postgres.ROOT / "supabase" / "tests" / "local_stub.sql").read_text(encoding="utf-8"))
    assert len(apply_migrations.apply(url)) == 5
    assert apply_migrations.apply(url) == []
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY 1 LIMIT 1").fetchone()             == ("20261124000100", "core_schema")


def test_import_is_repeatable(url):
    content = source_rows("member1", common.SOURCES["member1"])
    assert sum(t["inserted"] for t in import_postgres.load(url, content)["tables"]) == 0


def test_import_refuses_bad_rows_and_rolls_back():
    url = local_postgres.create_database()
    content = source_rows("member1", common.SOURCES["member1"])
    content["member1"]["rows"]["inventory"][0]["reserved"] = 10 ** 6
    content["member1"]["rows"]["action_tracker"] = [{"tracker_id": 1}]
    report = import_postgres.load(url, content)
    assert report["rolled_back"] and [r["table"] for r in report["rejected"]] == ["member1.inventory", "member1.action_tracker"]
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT count(*) FROM core.materials").fetchone()[0] == 0


def test_application_records_migrate_with_chain_and_replay(url, tmp_path, monkeypatch):
    """A full SQLite workflow from the old application, moved to PostgreSQL."""
    from member3.application.access_control import User
    from member3.services import action_tracker_service, approval_service, ecn_service, planning_service, what_if_service
    monkeypatch.setenv("CHANGEWISE_DB", str(tmp_path / "app.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    user = User("Asha", "Planner")
    member1 = Member1Adapter("member3.integration.member1_module")
    member2 = Member2Adapter(member1.simulate)
    text = next(d["text"] for d in member1.sample_documents() if d["id"] == "ECN-001")
    review = ecn_service.create_review(text, "base", member1, user)
    ecn_service.confirm(review, member1, user)
    run_id = planning_service.run_planning(review, member1, member2, user)
    run = planning_service.get_run(run_id)
    what_if_service.submit_scenario_to_optimizer({"lead_time_delta": 1}, run, member2, user, "late")
    approval_service.decide(run_id, "APPROVED", user, member1, member2, "ok", run["result"]["recommended_plan_id"])
    action_tracker_service.advance(action_tracker_service.list_items()[0]["action_id"], user)

    content = {**source_rows("member1", common.SOURCES["member1"]), **source_rows("member3", tmp_path / "app.db")}
    content["member1"]["rows"]["audit_log"] = [{
        "event_id": 7, "event_time": "2026-11-20T09:00:00", "actor": "m1", "event_type": "OLD", "entity_type": "ECN",
        "entity_id": "ECN-001", "payload_json": "{}", "previous_hash": None, "event_hash": "h"}]
    assert not import_postgres.load(url, content)["rejected"]
    results, foreign_keys, unprotected, _ = verify_migration.compare(url, content)
    assert [r for r in results if r["missing"] or r["different"]] == [] and not unprotected and not foreign_keys["bad"]
    assert {r["target"]: r["source_rows"] for r in results}["app.audit_log"] >= 7
    database.open_pool(url)
    try:
        assert audit_service.verify_chain() is None
        stored = planning_service.get_run(run_id)
        assert stored["result"] == run["result"] and member2.same_result(stored["result"], stored["dataset"], stored["config"])
        # new events continue the migrated chain
        assert audit_service.replay(run_id, member2, user)["matches"]
        assert audit_service.verify_chain() is None
        with database.read() as conn:
            rows = conn.execute("SELECT source, source_event_id FROM audit_events WHERE event_type = 'OLD'").fetchall()
        assert rows == [{"source": "member1", "source_event_id": 7}]
    finally:
        database.close_pool()


def test_numerical_parity_with_the_frozen_baseline(pool):
    report = capture_baseline.check(member1_postgres.__name__)
    assert set(report) == {"base", "rev_c_supplier_delay", "excess_rev_b_orders", "blocked_supplier", "date_conflict",
                           "missing_records"}
    assert all(found == [] for found in report.values()), report


@pytest.mark.parametrize("scenario", ["base", "rev_c_supplier_delay", "excess_rev_b_orders", "blocked_supplier", "missing_records"])
def test_api_results_equal_the_frozen_baseline(planned, planner, scenario):
    """The whole way round: PostgreSQL, engines, JSON storage, HTTP."""
    frozen = json.loads((capture_baseline.OUT / f"{scenario}.json").read_text(encoding="utf-8"))
    expected = frozen["optimization"]
    run = planned(scenario)
    for key in ("decision", "recommended_plan_id", "counts", "input_hash", "config_hash", "engine_version", "near_ties",
                "escalations", "effective_week_comparison"):
        assert run[key] == expected[key], key
    assert [{k: r[k] for k in ("plan_id", "rank", "actions", "shortage_units", "excess_value", "action_cost", "secondary_cost")}
            for r in run["recommendations"]] == \
        [{k: r[k] for k in ("plan_id", "rank", "actions", "shortage_units", "excess_value", "action_cost", "secondary_cost")}
         for r in expected["recommendations"]]
    assert [r["robustness"]["scenarios"] for r in run["recommendations"]] == \
        [r["robustness"]["scenarios"] for r in expected["recommendations"]]
    rejected = planner.call("GET", f"/planning/runs/{run['run_id']}/rejected-plans")["items"]
    assert [(p["plan_id"], p["rejection_reasons"]) for p in rejected] == \
        [(p["plan_id"], p["rejection_reasons"]) for p in expected["rejected_plans"]]
    ranked, offset = [], 0
    while True:
        page = planner.call("GET", f"/planning/runs/{run['run_id']}/plans?limit=100&offset={offset}")
        ranked += page["items"]
        offset += 100
        if offset >= page["total"]:
            break
    assert [(p["plan_id"], p["rank"], p["secondary_cost"]) for p in ranked] == \
        [(p["plan_id"], p["rank"], p["secondary_cost"]) for p in expected["ranked_plans"]]
    inventory = planner.call("GET", f"/changes/ECN-001/inventory?scenario={scenario}")
    assert inventory["simulation_id"] == frozen["simulation"]["simulation_id"]
    assert inventory["excess_value"] == frozen["simulation"]["excess_value"]
    for row, frozen_row in zip(inventory["weeks"], frozen["simulation"]["weeks"], strict=True):
        assert {k: frozen_row[k] for k in row if k in frozen_row} == row


def test_a_date_conflict_stops_before_planning(users):
    """The ECN says use-up W5, the changed record says W3: the review cannot be confirmed, so nothing is planned."""
    api = users["ENGINEERING"]
    doc = api.call("POST", "/ecn/samples", {"change_id": "ECN-001", "scenario": "date_conflict", "sample_id": "ECN-001"})
    review = api.call("POST", f"/ecn/{doc['document_id']}/extract")
    assert review["validation"]["validation_status"] == "INVALID"
    assert api.error("POST", f"/ecn/{review['review_id']}/confirm") == (409, "NOT_READY")


def test_a_second_change_has_its_own_dataset(pool, db):
    db.execute("INSERT INTO core.engineering_changes SELECT 'ECN-900', part_number, new_material_id, old_revision, new_revision, "
               "7, 6, interchangeability, reason, approver, approval_status, approval_week, created_at FROM core.engineering_changes")
    assert member1_postgres.list_scenarios()[-1] == "base@ECN-900"
    assert member1_postgres.load_dataset("base@ECN-900")["engineering_change"]["effective_week"] == 7
    assert member1_postgres.load_dataset("base")["engineering_change"]["change_id"] == "ECN-001"
