"""Authentication, roles, request limits, and what never reaches the browser."""
import re
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.routing import APIRoute

from backend.app.core import database
from backend.app.main import create_app

from .conftest import KEY, add_user, token

PUBLIC = {"/health", "/ready"}


def routes(app):
    found = []
    for path, operations in app.openapi()["paths"].items():
        found += [(method.upper(), path) for method in operations if path not in PUBLIC]
    return found


def test_health_and_readiness(client):
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/ready")
    assert ready.status_code == 200 and ready.json()["database"] and ready.json()["ai"] == "fallback"


def test_not_ready_without_database(env, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("DATABASE_URL", "")
    from backend.app.core import config
    config.get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        assert test_client.get("/ready").status_code == 503
        assert test_client.get("/health").status_code == 200


def test_every_route_needs_a_token(client):
    app = client.app
    listed = routes(app)
    assert len(listed) > 45
    for method, path in listed:
        response = client.request(method, re.sub(r"\{\w+\}", "1", path))
        assert response.status_code == 401, (method, path, response.status_code)
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
        assert response.headers["x-request-id"] == response.json()["error"]["request_id"]


@pytest.mark.parametrize("make", [
    lambda u: "garbage",
    lambda u: token(u, key="shared-secret-shared-secret-shared-1234", algorithm="HS256"),
    lambda u: jwt.encode({"sub": u, "aud": "authenticated"}, None, algorithm="none"),
    lambda u: token(u, exp=int(time.time()) - 60),
    lambda u: token(u, iss="https://evil.example/auth/v1"),
    lambda u: token(u, aud="anon"),
    lambda u: token(u, key=ec.generate_private_key(ec.SECP256R1())),
], ids=["garbage", "hs256", "none", "expired", "issuer", "audience", "other-key"])
def test_bad_tokens_are_refused(client, db, make):
    user_id = add_user(db, "ADMIN", "Admin")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {make(user_id)}"})
    assert response.status_code == 401, response.text


def test_unknown_and_inactive_accounts_have_no_access(client, db):
    for user_id in ("00000000-0000-0000-0000-000000000001", add_user(db, "ADMIN", "Gone", active=False)):
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token(user_id)}"})
        assert (response.status_code, response.json()["error"]["code"]) == (403, "NO_ACCESS")


def test_a_guest_is_only_ever_a_viewer(client, db, users):
    guest = str(db.execute("INSERT INTO auth.users (email) VALUES (NULL) RETURNING id").fetchone()[0])
    headers = {"Authorization": f"Bearer {token(guest, is_anonymous=True)}"}
    db.execute("UPDATE app.user_profiles SET role = 'ADMIN' WHERE user_id = %s", [guest])
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert (me["name"], me["role"], me["permissions"]) == ("Guest", "VIEWER", ["VIEW"])
    assert client.get("/api/v1/changes", headers=headers).status_code == 200
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    assert client.post("/api/v1/planning/optimize", headers=headers, json={"review_id": "x"}).status_code == 403
    admin = users["ADMIN"]
    assert guest not in str(admin.call("GET", "/admin/users"))
    assert admin.error("PATCH", f"/admin/users/{guest}", {"role": "ADMIN"}) == (404, "NOT_FOUND")


def test_role_comes_from_the_database_not_the_token(client, db):
    user_id = add_user(db, "VIEWER", "Viewer")
    forged = token(user_id, role="ADMIN", user_role="ADMIN", app_metadata={"role": "ADMIN"}, user_metadata={"role": "ADMIN"})
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}).json()
    assert me["role"] == "VIEWER" and "MANAGE_USERS" not in me["permissions"]


def test_signup_metadata_cannot_set_the_role(db):
    db.execute("INSERT INTO auth.users (email, raw_user_meta_data) VALUES ('x@example.test', "
               "'{\"role\": \"ADMIN\", \"full_name\": \"X\"}')")
    assert db.execute("SELECT role FROM app.user_profiles WHERE email = 'x@example.test'").fetchone()[0] == "VIEWER"


WRITES = [  # (method, path, body, roles that may)
    ("POST", "/changes/ECN-001/simulate", None, {"PRODUCTION_PLANNER", "ENGINEERING"}),
    ("POST", "/ecn/samples", {"change_id": "ECN-001", "sample_id": "ECN-001"}, {"PRODUCTION_PLANNER", "ENGINEERING"}),
    ("POST", "/ecn/manual", {"change_id": "ECN-001"}, {"PRODUCTION_PLANNER", "ENGINEERING"}),
    ("POST", "/planning/optimize", {"review_id": "x"}, {"PRODUCTION_PLANNER"}),
    ("POST", "/planning/what-if/parse", {"run_id": "x", "question": "y"}, {"PRODUCTION_PLANNER", "ENGINEERING", "PURCHASING"}),
    ("POST", "/approvals/x/decision", {"decision": "REJECTED", "comment": "no"}, {"PRODUCTION_PLANNER"}),
    ("POST", "/approvals/x/modification", {"actions": []}, {"PRODUCTION_PLANNER"}),
    ("POST", "/approvals/x/close", None, {"PRODUCTION_PLANNER"}),
    ("PATCH", "/actions/x", {"status": "DONE"}, {"PRODUCTION_PLANNER", "ENGINEERING", "PURCHASING", "QUALITY"}),
    ("POST", "/audit/replay", {"run_id": "x"}, {"ADMIN", "PRODUCTION_PLANNER"}),
    ("POST", "/explanations/generate", {"run_id": "x"}, {"PRODUCTION_PLANNER"}),
    ("GET", "/audit", None, {"ADMIN", "PRODUCTION_PLANNER", "ENGINEERING", "QUALITY"}),
    ("GET", "/ecn", None, {"ADMIN", "PRODUCTION_PLANNER", "ENGINEERING", "QUALITY"}),
    ("GET", "/admin/users", None, {"ADMIN"}),
    ("PATCH", "/admin/users/x", {"role": "ADMIN"}, {"ADMIN"}),
]


@pytest.mark.parametrize("method,path,body,roles", WRITES, ids=[f"{m} {p}" for m, p, _, _ in WRITES])
def test_roles(users, method, path, body, roles):
    for role, api in users.items():
        response = api.raw(method, path, **({"json": body} if body else {}))
        assert (response.status_code == 403) == (role not in roles), (role, response.status_code, response.text)


def test_a_client_cannot_send_identity_or_results(planner, planned):
    run = planned()
    for extra in ({"role": "ADMIN"}, {"user_id": "x"}, {"user_name": "Someone"}, {"result": {}}):
        status, code = planner.error("POST", f"/approvals/{run['run_id']}/decision",
                                     {"decision": "REJECTED", "comment": "no", **extra})
        assert (status, code) == (422, "VALIDATION_ERROR")


def test_role_administration(users, db):
    admin, viewer = users["ADMIN"], users["VIEWER"]
    assert viewer.error("POST", "/planning/optimize", {"review_id": "x"}) == (403, "FORBIDDEN")
    changed = admin.call("PATCH", f"/admin/users/{viewer.user_id}", {"role": "PRODUCTION_PLANNER"})
    assert changed["role"] == "PRODUCTION_PLANNER"
    assert viewer.error("POST", "/planning/optimize", {"review_id": "x"}) == (404, "NOT_FOUND")  # allowed now
    event = admin.call("GET", "/audit?event_type=ACCESS_CHANGED")["items"][0]
    assert event["payload"]["from"]["role"] == "VIEWER" and event["entity_id"] == viewer.user_id
    assert admin.error("PATCH", f"/admin/users/{admin.user_id}", {"role": "VIEWER"}) == (409, "LAST_ADMIN")
    admin.call("PATCH", f"/admin/users/{viewer.user_id}", {"is_active": False})
    assert viewer.error("GET", "/auth/me") == (403, "NO_ACCESS")


def test_cors_allows_only_the_configured_origin(client):
    ok = client.options("/api/v1/changes", headers={"Origin": "http://app.test", "Access-Control-Request-Method": "GET"})
    assert ok.headers["access-control-allow-origin"] == "http://app.test"
    bad = client.options("/api/v1/changes", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_wildcard_origin_is_refused(monkeypatch):
    from backend.app.core import config
    monkeypatch.setenv("FRONTEND_ORIGIN", "*")
    config.get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        config.get_settings()
    config.get_settings.cache_clear()


def test_errors_do_not_leak_internals(client, users, monkeypatch):
    from backend.app.api.v1 import changes

    def explode(*_):
        raise RuntimeError("postgresql://user:password@host/secret")
    monkeypatch.setattr(changes.service, "list_changes", explode)
    response = users["VIEWER"].raw("GET", "/changes")
    assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "password" not in response.text and "Traceback" not in response.text


def test_database_failure_is_503(client, users, db):
    api = users["VIEWER"]
    database.close_pool()
    assert api.error("GET", "/changes") == (503, "DATABASE_UNAVAILABLE")


@pytest.mark.parametrize("text", ["' OR 1=1 --", "'; DROP TABLE app.audit_log; --", "%", "_", "\\"])
def test_search_is_not_an_injection_point(users, text):
    page = users["ADMIN"].call("GET", "/audit", params={"search": text})
    assert page["total"] == 0
    assert users["ADMIN"].error("GET", "/changes/x' OR '1'='1/inventory") == (404, "NOT_FOUND")
    users["ADMIN"].call("GET", "/audit")  # the table is still there


def test_invalid_requests(planner):
    assert planner.error("POST", "/planning/optimize", {}) == (422, "VALIDATION_ERROR")
    assert planner.error("POST", "/planning/optimize", {"review_id": 5}) == (422, "VALIDATION_ERROR")
    assert planner.error("GET", "/audit?limit=100000") == (422, "VALIDATION_ERROR")
    assert planner.error("GET", "/audit/not-a-number") == (422, "VALIDATION_ERROR")
    assert planner.error("GET", "/changes/ECN-999/overview")[0] == 404
    assert planner.error("GET", "/changes/ECN-001/overview?scenario=unknown") == (404, "NOT_FOUND")
    for path in ("/planning/runs/x", "/planning/what-if/x", "/explanations/x", "/approvals/x", "/actions/x", "/audit/999",
                 "/audit/replay/x", "/ecn/x", "/ecn/documents/x/url"):
        assert planner.error("GET", path) == (404, "NOT_FOUND"), path


def test_upload_limits(users, stored):
    api = users["ENGINEERING"]

    def send(name, content, mime="application/pdf"):
        return api.error("POST", "/ecn/upload", data={"change_id": "ECN-001"}, files={"file": (name, content, mime)})
    assert send("a.pdf", b"not a pdf at all") == (415, "UNSUPPORTED_TYPE")
    assert send("a.exe", b"MZ") == (415, "UNSUPPORTED_TYPE")
    assert send("a.txt", b"abc\x00def", "text/plain") == (415, "UNSUPPORTED_TYPE")
    assert send("a.pdf", b"") == (422, "EMPTY_DOCUMENT")
    assert send("a.pdf", b"%PDF-" + b"0" * (4 * 1024 * 1024 + 1))[0] == 413
    assert send("a.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024)) == (413, "TOO_LARGE")
    assert api.error("POST", "/ecn/upload", data={"change_id": "ECN-001"}) == (422, "EMPTY_DOCUMENT")
    assert not stored
    doc = api.call("POST", "/ecn/upload", data={"change_id": "ECN-001"},
                   files={"file": ("../../etc/pass wd<script>.txt", b"Engineering Change Notice ECN-001 for the bracket", "text/html")})
    assert doc["original_filename"] == "pass wd_script_.txt" and doc["mime_type"] == "text/plain"
    assert list(stored) == [f"ECN-001/{doc['document_id']}.txt"]


def test_documents_are_reachable_only_by_engineering_roles(users, planned):
    planned()
    doc = users["ENGINEERING"].call("GET", "/ecn")["items"][0]["document_id"]
    assert users["QUALITY"].call("GET", f"/ecn/documents/{doc}/url")["expires_in"] <= 60
    for role in ("VIEWER", "PURCHASING"):
        assert users[role].error("GET", f"/ecn/documents/{doc}/url") == (403, "FORBIDDEN")


def test_responses_are_not_cached_and_carry_safe_headers(client):
    response = client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert response.headers["cache-control"] == "no-store" and response.headers["x-content-type-options"] == "nosniff"
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_production_hides_the_schema(env, monkeypatch):
    from backend.app.core import config
    monkeypatch.setenv("ENVIRONMENT", "production")
    config.get_settings.cache_clear()
    app = create_app()
    assert not any(isinstance(r, APIRoute) and r.path == "/openapi.json" for r in app.routes)
    assert app.openapi_url is None and KEY
