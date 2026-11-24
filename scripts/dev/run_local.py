"""The whole backend on this computer, without cloud accounts: python -m scripts.dev.run_local

Starts PostgreSQL (embedded), applies the migrations, loads Member 1's data, starts the Supabase stand-in on 54321
and the API on 8000. Creates one test user per role. Data lives in .dev/ and survives restarts (documents do not).
"""
import json
import os
import sys
import threading

ROOT_BIN = None
try:
    from importlib.util import find_spec
    from pathlib import Path
    ROOT_BIN = Path(find_spec("pixeltable_pgserver").origin).parent / "pginstall" / "bin"
    os.environ["PATH"] = f"{ROOT_BIN}{os.pathsep}{os.environ['PATH']}"  # psycopg finds libpq here
except AttributeError:
    sys.exit("pip install -r backend/requirements-dev.txt")

import psycopg  # noqa: E402
import uvicorn  # noqa: E402
from psycopg import conninfo  # noqa: E402

from . import local_postgres  # noqa: E402

PASSWORD = "local-test-password"  # test accounts of this local database only
USERS = {"ADMIN": "admin", "ENGINEERING": "engineering", "PURCHASING": "purchasing", "PRODUCTION_PLANNER": "planner",
         "QUALITY": "quality", "VIEWER": "viewer"}


def prepare(name="changewise_dev"):
    data = local_postgres.ROOT / ".dev" / "pgdata"
    data.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("LOCAL_PGDATA", str(data))
    server = local_postgres.server_url()
    if "--reset" in sys.argv:
        with psycopg.connect(server, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    with psycopg.connect(server, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name]).fetchone()
    if exists:
        return conninfo.make_conninfo(server, dbname=name)
    url = local_postgres.create_database(name)
    from scripts.migration import export_sqlite, import_postgres
    from scripts.migration.backup_sources import backup
    import_postgres.load(url, json.loads(export_sqlite.export(backup()).read_text(encoding="utf-8")))
    return url


def add_users(url):
    from .supabase_stub import hashlib
    with psycopg.connect(url, autocommit=True) as conn:
        for role, name in USERS.items():
            conn.execute("INSERT INTO auth.users (email, encrypted_password, raw_user_meta_data) VALUES (%s, %s, "
                         "jsonb_build_object('full_name', %s::text)) ON CONFLICT DO NOTHING",
                         [f"{name}@changewise.test", hashlib.sha256(PASSWORD.encode()).hexdigest(), f"{name.title()} (test)"])
            conn.execute("UPDATE app.user_profiles SET role = %s WHERE email = %s", [role, f"{name}@changewise.test"])


def main():
    url = prepare()
    add_users(url)
    supabase = "http://localhost:54321"
    from .supabase_stub import create
    threading.Thread(target=uvicorn.Server(uvicorn.Config(
        create(supabase, url), host="localhost", port=54321, log_level="warning")).run, daemon=True).start()
    os.environ.update(DATABASE_URL=url, SUPABASE_URL=supabase, SUPABASE_SECRET_KEY="local",
                      FRONTEND_ORIGIN=os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000"))
    print(f"Test accounts: {', '.join(n + '@changewise.test' for n in USERS.values())} (password in scripts/dev/run_local.py)")
    uvicorn.run("backend.app.main:app", host="localhost", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
