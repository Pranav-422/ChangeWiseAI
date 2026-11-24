"""What moves where. One mapping, used by export, import and verification."""
import hashlib
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "member1": ROOT / "member1" / "database" / "changewise.db",
    "member3": Path(os.environ.get("CHANGEWISE_DB") or ROOT / "member3" / "data" / "app.db"),
}
BACKUPS = ROOT / "backups"

# (source database, source table) -> (target table, primary key), in foreign-key-safe order.
MAPPING = [
    ("member1", "materials", "core.materials", ["material_id"]),
    ("member1", "suppliers", "core.suppliers", ["supplier_id"]),
    ("member1", "engineering_changes", "core.engineering_changes", ["change_id"]),
    ("member1", "planning_groups", "core.planning_groups", ["group_id", "material_id", "supplier_id"]),
    ("member1", "bom", "core.bom", ["bom_id"]),
    ("member1", "inventory", "core.inventory", ["inventory_id"]),
    ("member1", "demand", "core.demand", ["demand_id"]),
    ("member1", "purchase_orders", "core.purchase_orders", ["po_id"]),
    ("member1", "simulation_runs", "core.simulation_runs", ["simulation_id"]),
    ("member1", "exceptions", "core.exceptions", ["simulation_id", "exception_id"]),
    ("member3", "ecn_reviews", "app.ecn_reviews", ["review_id"]),
    ("member3", "planning_runs", "app.planning_runs", ["run_id"]),
    ("member3", "what_if_requests", "app.what_if_requests", ["request_id"]),
    ("member3", "approvals", "app.approvals", ["approval_id"]),
    ("member3", "action_items", "app.action_items", ["action_id"]),
    ("member3", "audit_log", "app.audit_log", ["seq"]),
    ("member1", "candidate_plans", "core.candidate_plans", ["optimization_run_id", "plan_id"]),
    ("member1", "plan_actions", "core.plan_actions", ["action_id"]),
    ("member1", "audit_log", "app.legacy_audit_events", ["source_database", "source_event_id"]),
]
# Member 1 proposed this table for Member 3, who built app.action_items instead. Rows are reported, not loaded.
SUPERSEDED = [("member1", "action_tracker", "app.action_items is the execution tracker")]

BOOLEANS = {("engineering_changes", "interchangeability"), ("suppliers", "expedite_available"),
            ("purchase_orders", "expedited"), ("approvals", "modified")}


def connect(path):
    """Read-only: the sources are never changed."""
    connection = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def tables(connection):
    return [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target_row(source, table, row):
    """A source row as the target table stores it. Keys and values keep their meaning; only types change."""
    row = {k: bool(v) if (table, k) in BOOLEANS and v is not None else v for k, v in row.items()}
    if source == "member1" and table == "audit_log":
        row["source_event_id"] = row.pop("event_id")
        row["source_database"] = "member1"
    if source == "member1" or table == "audit_log":
        row.pop("rowid", None)  # audit_log keeps its own seq
    return row
