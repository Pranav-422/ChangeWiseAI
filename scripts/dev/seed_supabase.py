"""Test users and Member 1's data in a local Supabase stack (CI): python -m scripts.dev.seed_supabase

Needs DATABASE_URL, SUPABASE_URL and SUPABASE_SECRET_KEY of a disposable project. Refuses any other host.
"""
import json
import os
from urllib.parse import urlparse

import httpx
import psycopg

from scripts.migration import export_sqlite, import_postgres
from scripts.migration.backup_sources import backup

from .accounts import PASSWORD, USERS


def main():
    url, base, key = (os.environ[k] for k in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SECRET_KEY"))
    if urlparse(base).hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit("This script creates accounts with a known password; it only runs against a local stack.")
    headers = {"apikey": key, **({"Authorization": f"Bearer {key}"} if key.startswith("eyJ") else {})}
    for name in USERS.values():
        response = httpx.post(f"{base}/auth/v1/admin/users", headers=headers, timeout=20, json={
            "email": f"{name}@changewise.test", "password": PASSWORD, "email_confirm": True,
            "user_metadata": {"full_name": f"{name.title()} (test)"}})
        if response.status_code not in (200, 201, 422):  # 422: exists already
            raise SystemExit(f"{name}: {response.status_code} {response.text}")
    with psycopg.connect(url, autocommit=True) as conn:
        for role, name in USERS.items():
            changed = conn.execute("UPDATE app.user_profiles SET role = %s WHERE email = %s", [role, f"{name}@changewise.test"])
            if changed.rowcount != 1:
                raise SystemExit(f"No profile for {name}: the sign-up trigger did not run.")
    report = import_postgres.load(url, json.loads(export_sqlite.export(backup()).read_text(encoding="utf-8")))
    print(sum(t["inserted"] for t in report["tables"]), "rows loaded,", len(report["rejected"]), "rejected")


if __name__ == "__main__":
    main()
