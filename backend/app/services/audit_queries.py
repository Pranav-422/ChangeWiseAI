"""Audit history and replay. Events are written by audit_service.append inside each state change."""
import json

from member3.database.repositories import records
from member3.services import audit_service

from ..core.database import acting, read, transaction
from ..core.errors import not_found
from ..security.permissions import require
from . import planning
from .engines import engines

_COLUMNS = "seq, created_at, event_type, entity_id, user_name, role, payload, previous_hash, event_hash, source"


def page(limit, offset, event_type=None, entity_id=None, search=None):
    where, values = [], []
    if event_type:
        where.append("event_type = ?")
        values.append(event_type)
    if entity_id:
        where.append("(entity_id = ? OR payload::text LIKE ?)")
        values += [entity_id, f'%"{_like(entity_id)}"%']
    if search:
        where.append("(event_type ILIKE ? OR entity_id ILIKE ? OR user_name ILIKE ? OR payload::text ILIKE ?)")
        values += [f"%{_like(search)}%"] * 4
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    with read() as db:
        rows = db.execute(f"SELECT {_COLUMNS} FROM audit_log{clause} ORDER BY seq DESC LIMIT ? OFFSET ?",
                          [*values, limit, offset]).fetchall()
        total = db.execute(f"SELECT count(*) AS n FROM audit_log{clause}", values).fetchone()["n"]
        types = [r["event_type"] for r in db.execute("SELECT DISTINCT event_type FROM audit_log ORDER BY 1")]
    return {"items": [records._decode(r) for r in rows], "total": total, "event_types": types}


def _like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get(seq):
    with read() as db:
        row = db.execute(f"SELECT {_COLUMNS} FROM audit_log WHERE seq = ?", [seq]).fetchone()
    if row is None:
        raise not_found(f"Audit event {seq}")
    return records._decode(row)


def chain():
    broken = audit_service.verify_chain()
    with read() as db:
        row = db.execute("SELECT count(*) AS n, max(event_hash) FILTER (WHERE seq = (SELECT max(seq) FROM audit_log)) AS head "
                         "FROM audit_log").fetchone()
    return {"intact": broken is None, "broken_at": broken, "events": row["n"], "head_hash": row["head"]}


_SUMMARY = ("decision", "recommended_plan_id", "input_hash", "config_hash", "engine_version", "simulator", "counts")


def _summary(result):
    return {k: result[k] for k in _SUMMARY}


def _differences(stored, again):
    return [{"field": k, "original": str(stored.get(k))[:300], "reproduced": str(again.get(k))[:300]}
            for k in sorted(set(stored) | set(again)) if k != "computation_seconds" and stored.get(k) != again.get(k)]


def replay(run_id, user):
    """Member 3 reruns the stored snapshot and records the verdict; this adds the evidence beside it."""
    require(user, "REPLAY_RUN")
    run, (_, member2) = planning.get(run_id), engines()
    with acting(user.user_id):
        outcome = audit_service.replay(run_id, member2, user)
        again = run["result"] if outcome["matches"] else \
            member2.optimize(run["dataset"], run["config"]) if outcome["snapshot_intact"] else None
        status = "MATCHED" if outcome["matches"] else "DIFFERENT" if outcome["snapshot_intact"] else "SNAPSHOT_ALTERED"
        replay_id = records.new_id("RPL")
        with transaction() as db:
            db.execute("INSERT INTO replay_records (replay_id, run_id, status, snapshot_intact, original, reproduced, "
                       "differences, created_by) VALUES (?,?,?,?,?,?,?,?)",
                       [replay_id, run_id, status, outcome["snapshot_intact"], json.dumps(_summary(run["result"])),
                        json.dumps(_summary(again)) if again else None,
                        json.dumps(_differences(run["result"], again) if again else []), user.name])
    return get_replay(replay_id)


def _replay_view(row):
    return {**row, **{k: json.loads(row[k]) if row[k] else None for k in ("original", "reproduced", "differences")}}


def get_replay(replay_id):
    with read() as db:
        row = db.execute("SELECT * FROM replay_records WHERE replay_id = ?", [replay_id]).fetchone()
    if row is None:
        raise not_found(f"Replay {replay_id}")
    return _replay_view(row)


def replays(limit=20):
    with read() as db:
        rows = db.execute("SELECT * FROM replay_records ORDER BY created_at DESC LIMIT ?", [limit]).fetchall()
    return [_replay_view(r) for r in rows]
