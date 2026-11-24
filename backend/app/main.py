"""ChangeWise AI API: uvicorn backend.app.main:app"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import audit, auth, changes, ecn, health, planning, workflow
from .core import database, errors, logging
from .core.config import get_settings
from .core.middleware import RequestMiddleware
from .schemas.api import ErrorResponse


@asynccontextmanager
async def lifespan(app):
    database.open_pool()
    yield
    database.close_pool()


def create_app():
    settings = get_settings()
    logging.configure(settings.log_level)
    app = FastAPI(title="ChangeWise AI API", version="1.0.0", lifespan=lifespan,
                  docs_url=None if settings.production else "/docs", redoc_url=None,
                  openapi_url=None if settings.production else "/openapi.json")
    errors.install(app)
    app.include_router(health.router)
    problems = {code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 503)}
    for module in (auth, changes, ecn, planning, workflow, audit):
        app.include_router(module.router, prefix="/api/v1", responses=problems)
    app.add_middleware(RequestMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.frontend_origins), allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH"], max_age=600,
                       allow_headers=["Authorization", "Content-Type", "X-Request-ID"], expose_headers=["X-Request-ID"])
    return app


app = create_app()
