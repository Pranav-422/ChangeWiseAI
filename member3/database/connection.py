"""One transaction per `with transaction()` block: state change and audit event commit together."""
import sqlite3
from contextlib import contextmanager

from ..settings import database_path
from .initialize_db import initialize

_ready = set()
_replacement = None


def use(factory):
    """Send every `transaction()` to another store (the cloud backend's PostgreSQL). None restores SQLite."""
    global _replacement
    _replacement = factory


def transaction(path=None):
    return _replacement() if _replacement and path is None else _sqlite(path)


@contextmanager
def _sqlite(path):
    path = path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        if path not in _ready or not path.stat().st_size:
            initialize(connection)
            _ready.add(path)
        connection.execute("BEGIN IMMEDIATE")  # serialises writers, so the audit chain cannot fork
        yield connection
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
