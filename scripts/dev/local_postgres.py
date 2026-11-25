"""A disposable PostgreSQL with the stub and every migration applied, for tests and local development.

Uses TEST_DATABASE_URL (an empty database, for example a CI service) or pixeltable-pgserver's embedded server.
"""
import os
import tempfile
import uuid
from pathlib import Path

import psycopg
from psycopg import conninfo

ROOT = Path(__file__).resolve().parents[2]
_server = None


def server_url():
    """URL of a server this process may create databases on."""
    global _server
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    import pixeltable_pgserver
    _server = _server or pixeltable_pgserver.get_server(
        os.environ.get("LOCAL_PGDATA") or tempfile.mkdtemp(prefix="changewise-pg-"))
    return _server.get_uri()


def apply_migrations(url, stub=True):
    files = sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
    with psycopg.connect(url) as conn:
        for path in ([ROOT / "supabase" / "tests" / "local_stub.sql"] if stub else []) + files:
            conn.execute(path.read_text(encoding="utf-8"))


def create_database(name=None):
    """A new migrated database. Returns its URL."""
    server = server_url()
    name = name or f"cw_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(server, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = conninfo.make_conninfo(server, dbname=name)
    apply_migrations(url)
    return url
