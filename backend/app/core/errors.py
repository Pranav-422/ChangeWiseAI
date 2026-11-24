"""One error shape for every failure: {"error": {code, message, details, request_id}}. No traceback leaves the API."""
import logging
import sqlite3

import psycopg
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from member3.ai.ecn_extractor import ExtractionFailure
from member3.application.access_control import NotAllowed
from member3.services.action_tracker_service import InvalidTransition
from member3.services.approval_service import DecisionRefused
from member3.services.ecn_service import NotReady

log = logging.getLogger("changewise")


class ApiError(Exception):
    def __init__(self, status, code, message, details=()):
        super().__init__(message)
        self.status, self.code, self.details = status, code, list(details)


def not_found(what):
    return ApiError(404, "NOT_FOUND", f"{what} does not exist.")


# First match wins, so subclasses come before ValueError.
_KNOWN = (
    (NotAllowed, 403, "FORBIDDEN"),
    (ExtractionFailure, 422, "UNREADABLE_DOCUMENT"),
    (DecisionRefused, 409, "DECISION_REFUSED"),
    (NotReady, 409, "NOT_READY"),
    (InvalidTransition, 409, "INVALID_TRANSITION"),
)
_HTTP_CODES = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED",
               413: "TOO_LARGE", 429: "RATE_LIMITED"}


def _response(request, status, code, message, details=(), headers=None):
    return JSONResponse({"error": {"code": code, "message": message, "details": list(details),
                                   "request_id": getattr(request.state, "request_id", None)}}, status, headers)


def install(app):
    @app.exception_handler(ApiError)
    def api_error(request: Request, error: ApiError):
        return _response(request, error.status, error.code, str(error), error.details)

    @app.exception_handler(StarletteHTTPException)
    def http_error(request: Request, error: HTTPException):
        return _response(request, error.status_code, _HTTP_CODES.get(error.status_code, "HTTP_ERROR"),
                         str(error.detail), headers=getattr(error, "headers", None))

    @app.exception_handler(RequestValidationError)
    def invalid_request(request: Request, error: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in error.errors()]
        return _response(request, 422, "VALIDATION_ERROR", "The request is not valid.", details)

    for kind, status, code in _KNOWN:
        def known(request: Request, error: Exception, status=status, code=code):
            return _response(request, status, code, str(error))
        app.add_exception_handler(kind, known)

    @app.exception_handler(sqlite3.IntegrityError)
    def conflict(request: Request, error: Exception):
        log.warning("integrity_error", extra={"fields": {"error": str(error)}})
        return _response(request, 409, "CONFLICT", "The change conflicts with a record that already exists.")

    def unavailable(request: Request, error: Exception):
        log.error("database_unavailable", extra={"fields": {"error": type(error).__name__}})
        return _response(request, 503, "DATABASE_UNAVAILABLE", "The database cannot be reached. Try again shortly.",
                         headers={"Retry-After": "5"})
    app.add_exception_handler(psycopg.OperationalError, unavailable)
    app.add_exception_handler(PoolTimeout, unavailable)
