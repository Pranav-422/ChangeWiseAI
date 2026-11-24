"""Apply supabase/migrations to DATABASE_URL and record them as the Supabase CLI does.

    python -m scripts.migration.apply_migrations

For computers where the CLI cannot run. Each file is one transaction; applied ones are skipped, so it can be repeated,
and `supabase db push` later sees the same history.
"""
import os

import psycopg

from .common import ROOT


def apply(url):
    done = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS supabase_migrations")
        conn.execute("CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations "
                     "(version TEXT PRIMARY KEY, statements TEXT[], name TEXT)")
        applied = {r[0] for r in conn.execute("SELECT version FROM supabase_migrations.schema_migrations")}
        for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql")):
            version, _, name = path.stem.partition("_")
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            with conn.transaction():
                conn.execute(sql)
                conn.execute("INSERT INTO supabase_migrations.schema_migrations (version, statements, name) VALUES (%s, %s, %s)",
                             [version, [sql], name])
            done.append(path.name)
    return done


if __name__ == "__main__":
    for file in apply(os.environ["DATABASE_URL"]) or ["nothing to apply"]:
        print(file)
