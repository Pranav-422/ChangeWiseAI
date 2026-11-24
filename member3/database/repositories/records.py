"""Row access. Table and column names come from code only; values are always bound parameters."""
import json
import uuid
from datetime import datetime, timezone

JSON_COLUMNS = {"extraction", "fields", "validation", "dataset", "config", "result", "context", "explanation",
                "parameters", "plan", "action", "payload"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def _encode(column, value):
    return json.dumps(value, ensure_ascii=False) if column in JSON_COLUMNS and value is not None else value


def _decode(row):
    return {k: json.loads(row[k]) if k in JSON_COLUMNS and row[k] is not None else row[k] for k in row.keys()}


def insert(db, table, **values):
    db.execute(f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
               [_encode(k, v) for k, v in values.items()])


def update(db, table, key, key_value, **values):
    changed = db.execute(f"UPDATE {table} SET {', '.join(f'{k} = ?' for k in values)} WHERE {key} = ?",
                         [*(_encode(k, v) for k, v in values.items()), key_value]).rowcount
    if changed != 1:
        raise LookupError(f"{table} has no {key_value}")


def select(db, table, columns="*", order="rowid", **where):
    clause = " WHERE " + " AND ".join(f"{k} = ?" for k in where) if where else ""
    return [_decode(r) for r in db.execute(
        f"SELECT {columns} FROM {table}{clause} ORDER BY {order}", list(where.values()))]


def get(db, table, **where):
    rows = select(db, table, **where)
    if not rows:
        raise LookupError(f"{table} has no {', '.join(map(str, where.values()))}")
    return rows[-1]


def find(db, table, **where):
    """Newest matching row, or None."""
    rows = select(db, table, **where)
    return rows[-1] if rows else None
