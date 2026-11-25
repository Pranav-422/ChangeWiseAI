"""Supabase Storage, private bucket. Only the backend holds the key that reads and writes it."""
from urllib.parse import quote

import httpx

from ..core.config import get_settings
from ..core.errors import ApiError

SIGNED_URL_SECONDS = 60


def _call(method, path, **kwargs):
    settings = get_settings()
    key = settings.supabase_secret_key
    if not settings.supabase_url or not key:
        raise ApiError(503, "STORAGE_UNAVAILABLE", "Document storage is not configured.")
    headers = {"apikey": key, **kwargs.pop("headers", {})}
    if key.startswith("eyJ"):  # the legacy service_role key is a JWT and also goes in Authorization
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = httpx.request(method, f"{settings.supabase_url}/storage/v1/{path}", headers=headers, timeout=20, **kwargs)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code in (400, 404) and method == "GET":
            raise ApiError(404, "NOT_FOUND", "The stored document does not exist.") from error
        raise ApiError(502, "STORAGE_ERROR", "Document storage refused the request.") from error
    except httpx.HTTPError as error:
        raise ApiError(503, "STORAGE_UNAVAILABLE", "Document storage cannot be reached.") from error
    return response


def _object(path):
    return f"{get_settings().storage_bucket}/{quote(path)}"


def put(path, content, mime_type):
    _call("POST", f"object/{_object(path)}", content=content,
          headers={"Content-Type": mime_type, "x-upsert": "false"})


def get(path):
    return _call("GET", f"object/authenticated/{_object(path)}").content


def signed_url(path):
    signed = _call("POST", f"object/sign/{_object(path)}", json={"expiresIn": SIGNED_URL_SECONDS}).json()["signedURL"]
    return f"{get_settings().supabase_url}/storage/v1{signed}"
