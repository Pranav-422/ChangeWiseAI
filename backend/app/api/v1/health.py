"""Liveness and readiness. Gemini is optional: without it the deterministic fallback answers."""
import logging

from fastapi import APIRouter, Response

from ...core import database
from ...core.config import get_settings
from ...schemas import api
from ...services.engines import get_provider

router = APIRouter(tags=["health"])
log = logging.getLogger("changewise")


@router.get("/health", response_model=api.Health)
def health():
    return {"status": "ok"}


@router.get("/ready", response_model=api.Ready, responses={503: {"model": api.Ready}})
def ready(response: Response):
    settings, reachable = get_settings(), True
    try:
        database.ping()
    except Exception as error:  # any failure to reach the database means not ready
        log.warning("not_ready", extra={"fields": {"error": type(error).__name__}})
        reachable = False
    provider = get_provider()
    auth = bool(settings.supabase_url)
    if not (reachable and auth):
        response.status_code = 503
    return {"status": "ready" if reachable and auth else "not_ready", "database": reachable,
            "ai": provider.name if provider else "fallback", "storage": bool(settings.supabase_secret_key), "auth": auth}
