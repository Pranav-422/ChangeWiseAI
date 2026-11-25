"""RLS, roles and storage on a real Supabase stack (not the stand-in): python -m scripts.dev.check_supabase

Run after the end-to-end tests, so there are reviews, runs, audit events and stored documents to protect.
"""
import json
import os

import httpx
import psycopg

READERS = {"ADMIN", "ENGINEERING", "PRODUCTION_PLANNER", "QUALITY"}


def as_role(url, role, user_id, sql):
    with psycopg.connect(url) as conn:
        conn.execute("SELECT set_config('request.jwt.claims', %s, true)", [json.dumps({"sub": user_id, "role": role})])
        conn.execute(f"SET LOCAL ROLE {role}")
        try:
            return len(conn.execute(sql).fetchall()) if sql.startswith("SELECT") else conn.execute(sql).rowcount
        except psycopg.errors.InsufficientPrivilege:
            return "denied"


def main():
    url, base = os.environ["DATABASE_URL"], os.environ["SUPABASE_URL"]
    failed = []

    def check(name, ok):
        print("ok  " if ok else "FAIL", name)
        if not ok:
            failed.append(name)
    with psycopg.connect(url) as conn:
        users = dict(conn.execute("SELECT role, user_id::text FROM app.user_profiles WHERE email LIKE '%@changewise.test' "
                                  "AND email NOT LIKE '%-%' AND is_active").fetchall())
        open_tables = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname IN ('core', 'app') AND NOT rowsecurity").fetchone()[0]
        bucket = conn.execute("SELECT public FROM storage.buckets WHERE id = 'ecn-documents'").fetchone()
        path = conn.execute("SELECT name FROM storage.objects WHERE bucket_id = 'ecn-documents' LIMIT 1").fetchone()
    check("every table has RLS", open_tables == 0)
    check("the bucket is private", bucket == (False,))
    check("six roles are present", set(users) >= {*READERS, "PURCHASING", "VIEWER"})
    for role, user_id in users.items():
        check(f"{role} reads planning data", as_role(url, "authenticated", user_id, "SELECT 1 FROM core.materials") == 9)
        for table in ("app.ecn_reviews", "app.audit_log", "app.document_metadata"):
            seen = as_role(url, "authenticated", user_id, f"SELECT 1 FROM {table}")
            check(f"{role} on {table}", (seen != 0) == (role in READERS))
        seen = as_role(url, "authenticated", user_id, "SELECT 1 FROM storage.objects WHERE bucket_id = 'ecn-documents'")
        check(f"{role} on stored documents", (seen != 0) == (role in READERS))
        for sql in ("UPDATE app.user_profiles SET role = 'ADMIN'", "DELETE FROM app.audit_log",
                    "UPDATE core.demand SET required_quantity = 0"):
            check(f"{role} cannot {sql[:28]}", as_role(url, "authenticated", user_id, sql) == "denied")
        upload = as_role(url, "authenticated", user_id,
                         "INSERT INTO storage.objects (bucket_id, name) VALUES ('ecn-documents', 'x')")
        check(f"{role} cannot write documents", upload == "denied")
    check("anonymous reads no planning data", as_role(url, "anon", None, "SELECT 1 FROM core.materials") == "denied")
    for kind in ("public", "authenticated"):
        response = httpx.get(f"{base}/storage/v1/object/{kind}/ecn-documents/{path[0] if path else 'x'}")
        check(f"no {kind} download without a token", response.status_code in (400, 401, 403, 404))
    for schema in ("core", "app"):
        response = httpx.get(f"{base}/rest/v1/materials", headers={
            "apikey": os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""), "Accept-Profile": schema})
        check(f"schema {schema} is not in the REST API", response.status_code in (401, 403, 406))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
