from urllib.parse import unquote, urlsplit

import psycopg
import pytest

from scripts.deploy import setup_cloud


def test_any_password_survives_the_connection_string():
    password = "p@s:s/w#o?r%d[] "
    parts = urlsplit(setup_cloud.database_url(password))
    assert unquote(parts.password) == password
    assert parts.username == f"postgres.{setup_cloud.PROJECT_REF}"
    assert (parts.hostname, parts.port) == ("aws-0-ap-south-1.pooler.supabase.com", 6543)


@pytest.mark.parametrize("password,secret,text", [
    ("", "sb_secret_x", "Enter"), ("pw", "sb_publishable_x", "sb_secret_")])
def test_missing_answers_are_refused(password, secret, text):
    assert text in setup_cloud.problem(password, secret)


@pytest.mark.parametrize("raised,text", [("password authentication failed", "wrong"), ("timeout", "reached")])
def test_a_failed_connection_is_reported(monkeypatch, raised, text):
    def refuse(*_args, **_kwargs):
        raise psycopg.OperationalError(raised)
    monkeypatch.setattr(setup_cloud.psycopg, "connect", refuse)
    assert text in setup_cloud.problem("pw", "sb_secret_x")
