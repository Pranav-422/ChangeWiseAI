"""Real PostgreSQL with the real migrations and Member 1's real records. Only Supabase's HTTP services are faked."""
import sqlite3
import time
import uuid
from types import SimpleNamespace

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from psycopg import conninfo

from backend.app.core import config, database
from backend.app.integrations import storage
from backend.app.main import create_app
from backend.app.security import auth
from backend.app.services import planning
from scripts.dev import local_postgres
from scripts.migration import common, import_postgres

ISSUER_BASE = "http://supabase.test"
KEY = ec.generate_private_key(ec.SECP256R1())
ROLES = ("ADMIN", "ENGINEERING", "PURCHASING", "PRODUCTION_PLANNER", "QUALITY", "VIEWER")


def source_rows(name, path):
    db = common.connect(path)
    try:
        return {name: {"rows": {t: [dict(r) for r in db.execute(
            f"SELECT * FROM {t}" if name == "member1" else f"SELECT rowid, * FROM {t} ORDER BY rowid")]
            for t in common.tables(db)}}}
    finally:
        db.close()


@pytest.fixture(scope="session")
def template():
    """One migrated database with Member 1's data; each test works on a copy."""
    url = local_postgres.create_database()
    report = import_postgres.load(url, source_rows("member1", common.SOURCES["member1"]))
    assert not report["rejected"]
    return url


@pytest.fixture
def url(template):
    name = f"cw_{uuid.uuid4().hex[:10]}"
    server = local_postgres.server_url()
    with psycopg.connect(server, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}" TEMPLATE "{conninfo.conninfo_to_dict(template)["dbname"]}"')
    yield conninfo.make_conninfo(server, dbname=name)
    with psycopg.connect(server, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def stored(monkeypatch):
    """The private bucket, as a dictionary."""
    objects = {}
    monkeypatch.setattr(storage, "put", lambda path, content, mime: objects.__setitem__(path, content))
    monkeypatch.setattr(storage, "get", lambda path: objects[path])
    monkeypatch.setattr(storage, "signed_url", lambda path: f"https://signed.test/{path}")
    return objects


@pytest.fixture
def env(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SUPABASE_URL", ISSUER_BASE)
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://app.test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(auth, "_jwks", lambda _: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=KEY.public_key())))
    config.get_settings.cache_clear()
    planning._load.cache_clear()
    yield
    config.get_settings.cache_clear()


def token(user_id, key=KEY, algorithm="ES256", **claims):
    now = int(time.time())
    return jwt.encode({"sub": user_id, "aud": "authenticated", "iss": f"{ISSUER_BASE}/auth/v1", "iat": now,
                       "exp": now + 600, **claims}, key, algorithm=algorithm)


class Api:
    """Calls as one user. `call` returns the body of a success and fails the test on anything else."""

    def __init__(self, client, user_id):
        self.client, self.user_id, self.headers = client, user_id, {"Authorization": f"Bearer {token(user_id)}"}

    def raw(self, method, path, **kwargs):
        return self.client.request(method, f"/api/v1{path}", headers=self.headers, **kwargs)

    def call(self, method, path, body=None, **kwargs):
        response = self.raw(method, path, **({"json": body} if body is not None else {}), **kwargs)
        assert response.status_code < 300, (response.status_code, response.text)
        return response.json() if response.content else None

    def error(self, method, path, body=None, **kwargs):
        response = self.raw(method, path, **({"json": body} if body is not None else {}), **kwargs)
        assert response.status_code >= 400, response.text
        return response.status_code, response.json()["error"]["code"]


def add_user(conn, role, name, active=True):
    user_id = str(uuid.uuid4())
    conn.execute("INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES (%s, %s, jsonb_build_object('full_name', %s::text))",
                 [user_id, f"{role.lower()}-{user_id[:6]}@example.test", name])
    conn.execute("UPDATE app.user_profiles SET role = %s, is_active = %s WHERE user_id = %s", [role, active, user_id])
    return user_id


@pytest.fixture
def client(env, stored):
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db(url):
    with psycopg.connect(url, autocommit=True) as conn:
        yield conn


@pytest.fixture
def users(client, db):
    return {role: Api(client, add_user(db, role, f"{role.title()} Person")) for role in ROLES}


@pytest.fixture
def planner(users):
    return users["PRODUCTION_PLANNER"]


@pytest.fixture
def confirmed(users):
    """confirmed(scenario) -> review ID of a confirmed ECN, through the API with a real sample PDF."""
    def make(scenario="base", api=None, sample="ECN-001"):
        api = api or users["ENGINEERING"]
        doc = api.call("POST", "/ecn/samples", {"change_id": "ECN-001", "scenario": scenario, "sample_id": sample})
        review = api.call("POST", f"/ecn/{doc['document_id']}/extract")
        api.call("POST", f"/ecn/{review['review_id']}/confirm")
        return review["review_id"]
    return make


@pytest.fixture
def planned(confirmed, planner):
    def make(scenario="base"):
        return planner.call("POST", "/planning/optimize", {"review_id": confirmed(scenario)})
    return make


@pytest.fixture
def pool(env, url):
    """The backend's connections without HTTP."""
    database.open_pool(url)
    yield
    database.close_pool()


sqlite3.register_adapter(bool, int)
