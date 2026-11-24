"""Append-only, hash-chained audit log and plan replay."""
import hashlib
import json

from ..database.connection import transaction
from ..database.repositories import records

GENESIS = "0" * 64


def _hash(previous, row):
    content = json.dumps([previous, row["created_at"], row["event_type"], row["entity_id"], row["user_name"],
                          row["role"], row["payload"]], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def append(db, event_type, entity_id, user, payload=None):
    """Write one event inside the caller's transaction."""
    last = db.execute("SELECT event_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    previous = last["event_hash"] if last else GENESIS
    row = {"created_at": records.now(), "event_type": event_type, "entity_id": entity_id,
           "user_name": user.name, "role": user.role, "payload": payload or {}}
    records.insert(db, "audit_log", **row, previous_hash=previous, event_hash=_hash(previous, row))


def history(**where):
    with transaction() as db:
        return records.select(db, "audit_log", order="seq DESC", **where)


def verify_chain():
    """First broken sequence number, or None when every event is intact."""
    previous = GENESIS
    with transaction() as db:
        for row in records.select(db, "audit_log", order="seq"):
            if row["previous_hash"] != previous or row["event_hash"] != _hash(previous, row):
                return row["seq"]
            previous = row["event_hash"]
    return None


def replay(run_id, member2, user):
    """Rerun a stored planning run from its own snapshot and record whether it matches."""
    with transaction() as db:
        run = records.get(db, "planning_runs", run_id=run_id)
    intact = member2.hash(run["dataset"]) == run["input_hash"]
    matches = intact and member2.same_result(run["result"], run["dataset"], run["config"])
    with transaction() as db:
        append(db, "RUN_REPLAYED", run_id, user, {"matches": matches, "snapshot_intact": intact})
    return {"run_id": run_id, "matches": matches, "snapshot_intact": intact}
