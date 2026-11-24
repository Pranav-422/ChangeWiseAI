import sqlite3

import pytest

from database.connection import get_connection
from database.initialize_db import initialize_database
from engine.data_loader import load_csv_data, load_data_from_db, load_data_to_db, save_simulation_run
from engine.inventory import simulate_from_data


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    counts = initialize_database(path)
    conn = get_connection(path)
    yield conn, counts
    conn.close()


def test_fourteen_tables_and_row_counts(db):
    conn, counts = db
    assert len(counts) == 14
    for name, df in load_csv_data().items():
        assert counts[name] == len(df)


def test_initialization_is_repeatable(tmp_path):
    path = tmp_path / "r.db"
    assert initialize_database(path) == initialize_database(path)


def test_foreign_keys_enforced(db):
    conn, _ = db
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO bom VALUES ('BOM-X','PUMP-001','NOPE',1,1,NULL)")


@pytest.mark.parametrize("sql", [
    "INSERT INTO inventory VALUES ('INV-X','MAT-101','P',-1,0,0,'2026-01-01')",
    "INSERT INTO inventory VALUES ('INV-X','MAT-101','P',10,20,0,'2026-01-01')",
    "INSERT INTO suppliers VALUES ('S9','X','Maybe',1,0,NULL,0,NULL)",
    "INSERT INTO materials VALUES ('MAT-101','dup','d','Rev B','COMPONENT','Active',1,'EA')",
])
def test_check_and_unique_constraints(db, sql):
    conn, _ = db
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)


def test_loading_is_atomic(db):
    conn, counts = db
    bad = load_csv_data()
    bad["purchase_orders"].loc[0, "supplier_id"] = "NOPE"           # FK violation in the last table
    with pytest.raises(sqlite3.IntegrityError):
        load_data_to_db(conn, bad)
    assert conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == counts["materials"]   # rolled back


def test_audit_log_is_append_only(db):
    conn, _ = db
    conn.execute("INSERT INTO audit_log (event_time, actor, event_type, entity_type, entity_id, payload_json, event_hash)"
                 " VALUES ('t','planner','APPROVE','plan','P1','{}','h')")
    for sql in ("UPDATE audit_log SET actor='x'", "DELETE FROM audit_log"):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(sql)


def test_simulation_run_saved_once_and_replays_to_same_id(db):
    conn, _ = db
    sim = simulate_from_data(load_data_from_db(conn))
    save_simulation_run(conn, sim)
    save_simulation_run(conn, simulate_from_data(load_data_from_db(conn)))   # replay
    assert conn.execute("SELECT COUNT(*) FROM simulation_runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM exceptions").fetchone()[0] == len(sim["exceptions"])


def test_db_and_csv_give_same_simulation(db):
    conn, _ = db
    assert simulate_from_data(load_data_from_db(conn))["simulation_id"] == simulate_from_data(load_csv_data())["simulation_id"]


def test_saving_run_for_unknown_change_gives_clear_error(db):
    conn, _ = db
    sim = simulate_from_data(load_data_from_db(conn))
    with pytest.raises(ValueError, match="not in the database"):
        save_simulation_run(conn, {**sim, "change_id": "ECN-404"})
