"""PostgreSQL access. Member 3's repositories run on it unchanged.

`transaction()` stands in for member3.database.connection.transaction: same `?` placeholders, rows as
mappings, JSON as text (Member 3 decodes it) and sqlite3.IntegrityError for broken constraints.
"""
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar

import psycopg
from psycopg.adapt import Loader
from psycopg.rows import dict_row
from psycopg.types.numeric import FloatLoader
from psycopg.types.string import TextLoader
from psycopg_pool import ConnectionPool

from member3.database import connection as member3_connection

from .config import get_settings

_LOCK_KEY = 4207001  # any constant: one advisory lock serialises Member 3's write transactions
_acting_user = ContextVar("acting_user", default="")
_pool = None


class _TimestampLoader(Loader):
    """ISO 8601, the form Member 3 writes: 2026-11-24T12:00:00+00:00 (no offset for TIMESTAMP)."""

    def load(self, data):
        text = bytes(data).decode().replace(" ", "T")
        return text + ":00" if text[-3:] in ("+00", "-00") else text


def _configure(conn):
    for name, loader in (("json", TextLoader), ("jsonb", TextLoader), ("uuid", TextLoader), ("date", TextLoader),
                         ("timestamp", _TimestampLoader), ("timestamptz", _TimestampLoader),
                         ("numeric", FloatLoader)):  # the engines calculate in floats, as they do from SQLite
        conn.adapters.register_loader(name, loader)


def open_pool(url=None):
    global _pool
    url = url or get_settings().database_url
    if _pool or not url:
        return
    _pool = ConnectionPool(
        url, min_size=1, max_size=get_settings().pool_size, timeout=8, max_idle=300, max_lifetime=1800,
        configure=_configure, check=ConnectionPool.check_connection, open=False,
        # prepare_threshold=None keeps the pool usable behind Supabase's transaction pooler as well
        kwargs={"row_factory": dict_row, "connect_timeout": 8, "prepare_threshold": None})
    _pool.open(wait=False)
    member3_connection.use(transaction)


def close_pool():
    global _pool
    if _pool:
        _pool.close()
    _pool = None
    member3_connection.use(None)


class _Database:
    """The part of sqlite3.Connection that Member 3's repositories use."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        return self._conn.execute(sql.replace("?", "%s"), list(params))

    def executemany(self, sql, rows):
        with self._conn.cursor() as cursor:
            cursor.executemany(sql.replace("?", "%s"), rows)


@contextmanager
def acting(user_id):
    """Everything written inside carries this user id (column defaults read it)."""
    token = _acting_user.set(str(user_id))
    try:
        yield
    finally:
        _acting_user.reset(token)


@contextmanager
def _session(lock):
    if _pool is None:
        raise psycopg.OperationalError("DATABASE_URL is not configured")
    with _pool.connection() as conn:
        # One round trip, and transaction-local, so it is correct behind any connection pooler.
        conn.execute("SELECT set_config('search_path', 'app, core, public', true), "
                     "set_config('timezone', 'UTC', true), set_config('app.user_id', %s, true), "
                     "set_config('statement_timeout', '20000', true)", [_acting_user.get()])
        if lock:
            # shortcut: one writer at a time, as SQLite's BEGIN IMMEDIATE does; use a lock per change
            # when many planners write at once
            conn.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK_KEY])
        try:
            yield _Database(conn)
        except psycopg.IntegrityError as error:
            raise sqlite3.IntegrityError(str(error.diag.message_primary)) from error


def transaction():
    return _session(lock=True)


def read():
    """For the backend's own queries, which never write."""
    return _session(lock=False)


def ping():
    with _pool.connection(timeout=3) as conn:
        conn.execute("SELECT 1")
